"""Single-command investment analysis orchestrator using installed sibling packages.

Requires OpenAgentFabric, SECAgents, MarketDataAgents and InvestmentIntelligence
installed in the same environment; Redis and Ollama running. No manual mappings.
"""
from __future__ import annotations

import argparse
import asyncio
from datetime import date, timedelta
import json
import os
from pathlib import Path
import re
from urllib.parse import unquote, urlsplit


def resolve_ticker(records, ticker):
    """Resolve symbol from SEC's official company ticker listing; reject ambiguity."""
    matches = [r for r in records.values() if str(r.get('ticker', '')).upper() == ticker.upper()]
    if len(matches) != 1:
        raise ValueError(f'SEC ticker resolution ambiguous or missing for {ticker}: {len(matches)} matches')
    return int(matches[0]['cik_str'])


def local_artifact_path(ref):
    """Resolve a local artifact reference returned by SECAgents."""
    parsed = urlsplit(ref['uri'])
    if parsed.scheme != 'file' or parsed.netloc or parsed.query or parsed.fragment:
        raise ValueError(f"Expected local file artifact: {ref['uri']}")
    path = Path(unquote(parsed.path)).resolve()
    if not path.is_file():
        raise FileNotFoundError(path)
    return path


async def run(ticker, output, user_agent, model='qwen3:8b', base_url='http://localhost:11434/v1',
              as_of=None, redis_url=None, skip_llm=False, sec_stream='investment.sec.events', industry_mapping=None, industry_claims=None, industry_hypotheses=None, auto_industry=True):
    from secagent.clients.edgar import EdgarClient
    from secagent.runtime import run_sec_cycle
    from marketdataagents.agents.runtime import run_cycle
    from investment_intelligence.report import build_report, markdown
    from investment_intelligence.market import attach_market, markdown_market
    from investment_intelligence.analyst_v060 import analyze_v060
    from investment_intelligence.sec_narrative import import_sec_parsed, enrich_analysis
    from investment_intelligence.historical_integration import integrate_history
    from investment_intelligence.historical_reasoning import investigate_history
    from investment_intelligence.evidence_reconciliation import reconcile_history

    ticker = ticker.upper().strip()
    if not re.fullmatch(r'[A-Z][A-Z0-9.-]{0,12}', ticker):
        raise ValueError('Invalid ticker')
    if not user_agent:
        raise ValueError('SEC_USER_AGENT is required with a real contact email')
    today = date.today()
    cutoff = date.fromisoformat(as_of) if as_of else today
    if cutoff > today:
        raise ValueError('Future as-of dates are not supported')
    root = Path(output).expanduser().resolve() / ticker / cutoff.isoformat()
    root.mkdir(parents=True, exist_ok=True)
    runlog = {'ticker': ticker, 'as_of': cutoff.isoformat(), 'stages': {}, 'status': 'running'}
    logpath = root / 'run-manifest.json'

    def checkpoint(stage, value):
        runlog['stages'][stage] = value
        logpath.write_text(json.dumps(runlog, indent=2, default=str) + '\n')

    checkpoint('initialization', {'framework': '1.0', 'model': model})
    try:
        async with EdgarClient(user_agent=user_agent) as client:
            listing = (await client._get('https://www.sec.gov/files/company_tickers.json')).json()
            cik = resolve_ticker(listing, ticker)
            checkpoint('ticker_resolution', {'cik': cik})
            from investment_intelligence.industry_resolver import resolve_industry
            try:
                submissions = (await client._get(f'https://data.sec.gov/submissions/CIK{cik:010d}.json')).json()
            except Exception as exc:
                submissions = {}
                checkpoint('industry_classification_warning', {'reason': type(exc).__name__})
            industry_resolution = resolve_industry(ticker, cik, submissions,
                mapping_dir=Path(__file__).resolve().parent.parent / 'config',
                explicit_mapping=industry_mapping)
            (root / 'industry-resolution.json').write_text(json.dumps(industry_resolution, indent=2) + '\n')
            checkpoint('industry_resolution', {'sic': industry_resolution['sic'],
                'mapping_status': industry_resolution['mapping_status']})
            from investment_intelligence.industry_sources import discover_industry_sources
            industry_sources = discover_industry_sources(industry_resolution)
            (root / 'industry-source-candidates.json').write_text(json.dumps(industry_sources, indent=2) + '\n')
            checkpoint('industry_source_discovery', {'status':industry_sources['status'], 'candidates':len(industry_sources['candidates'])})
            if auto_industry and not industry_mapping and industry_resolution['mapping']:
                industry_mapping = str(Path(__file__).resolve().parent.parent / 'config' / 'msft-industry-mapping.json')
            facts = (await client._get(f'https://data.sec.gov/api/xbrl/companyfacts/CIK{cik:010d}.json')).json()
            filings = await client.get_recent_filings(cik, forms={'10-K', '10-Q'}, limit=None)
            filings = [f for f in filings if f.filing_date <= cutoff]
            if not filings:
                raise ValueError('No eligible 10-K or 10-Q in SEC recent submissions')
            selected = []
            for form in ('10-K', '10-Q'):
                match = next((f for f in filings if f.form == form), None)
                if match:
                    selected.append(match)

            parsed = []
            for filing in selected:
                target = root / 'sec_filings' / str(cik) / filing.accession_number / 'parsed.json'
                if target.exists():
                    obj = json.loads(target.read_text(encoding='utf-8'))
                    if obj.get('source', {}).get('filing_date') == filing.filing_date.isoformat() and \
                       str(obj.get('source', {}).get('accession_number')) == filing.accession_number:
                        parsed.append(target)
                        continue

                # Each form is requested separately so the public SEC workflow selects
                # the same most-recent eligible filing as this orchestrator.
                cycle = await run_sec_cycle(
                    cik=cik,
                    forms={filing.form},
                    as_of=cutoff,
                    limit=1,
                    output=root / 'sec_filings',
                    redis_url=redis_url,
                    user_agent=user_agent,
                    stream=sec_stream,
                )
                matches = [entry for entry in cycle['filings']
                           if entry['accession_number'] == filing.accession_number]
                if len(matches) != 1:
                    raise RuntimeError(
                        f'SEC workflow did not return expected {filing.form} '
                        f'filing {filing.accession_number}'
                    )
                path = local_artifact_path(matches[0]['parsed_artifact'])
                document = json.loads(path.read_text(encoding='utf-8'))
                source = document.get('source', {})
                if str(source.get('cik')) != str(cik) or \
                   source.get('accession_number') != filing.accession_number or \
                   source.get('filing_date') != filing.filing_date.isoformat():
                    raise ValueError(f'SEC parsed artifact metadata mismatch: {path}')
                parsed.append(path)

            checkpoint('sec', {
                'cik': cik,
                'filings': [{'accession': f.accession_number, 'form': f.form,
                             'filing_date': f.filing_date.isoformat()} for f in selected],
                'parsed_files': [str(p) for p in parsed],
            })

        start = (cutoff - timedelta(days=40)).isoformat()
        end = (cutoff + timedelta(days=1)).isoformat()
        if cutoff == today:
            end = today.isoformat()  # market provider uses exclusive end
        market = await run_cycle(ticker, start, end, output=root / 'market', redis_url=redis_url)
        marketfile = Path(market['file'])
        checkpoint('market', {'file': str(marketfile), 'sha256': market['sha256']})
        report = build_report(facts, cik, cutoff.isoformat())
        attach_market(report, json.loads(marketfile.read_text()), facts, ticker)
        from investment_intelligence.cash_flow_evidence import build_cash_flow_evidence
        cash_flow_evidence = build_cash_flow_evidence(facts, report, cutoff.isoformat())
        (root / 'cash-flow-evidence.json').write_text(json.dumps(cash_flow_evidence, indent=2) + '\n')
        checkpoint('cash_flow_evidence', {'status':cash_flow_evidence['status']})
        reportfile = root / 'report.json'
        reportfile.write_text(json.dumps(report, indent=2) + '\n')
        rendered = markdown(report).replace('## Source and limitations',
                                            markdown_market(report) + '## Source and limitations')
        (root / 'report.md').write_text(rendered)
        checkpoint('financial_report', {'file': str(reportfile)})
        client_llm = None
        if not skip_llm:
            from shared.llm import LLMClient, LLMConfig
            client_llm = LLMClient(LLMConfig(provider='openai_compatible', model=model,
                                             base_url=base_url, timeout_seconds=600))
        analysis = await analyze_v060(report, client_llm)
        analysisfile = root / 'analysis-v060.json'
        analysisfile.write_text(json.dumps(analysis, indent=2) + '\n')
        checkpoint('financial_analysis', {'file': str(analysisfile), 'status': analysis.get('status')})
        docs = import_sec_parsed(parsed)
        if client_llm is not None:
            enriched = await enrich_analysis(analysis, docs, client_llm)
        else:
            enriched = dict(analysis)
            enriched['document_evidence'] = docs
            enriched['narrative_integration'] = {'status': 'skipped', 'reason': 'LLM disabled'}
        enriched = integrate_history(enriched, report)
        enriched = await investigate_history(enriched, docs, client_llm)
        enriched = reconcile_history(enriched)
        from investment_intelligence.evidence_integrity import enforce_evidence_integrity
        enriched = enforce_evidence_integrity(enriched)
        checkpoint('evidence_integrity', {'invalid_statements': enriched['evidence_integrity']['invalid_statement_ids']})
        checkpoint('historical_reconciliation', {'records': len(enriched['historical_reconciliation']['records'])})
        checkpoint('historical_investigations', {'records': len(enriched['historical_investigations']['records'])})
        checkpoint('historical_intelligence', {'periods': len(enriched['historical_intelligence']['periods']),
            'signals': len(enriched['historical_dimension_signals']['signals'])})
        from investment_intelligence.dimension_routing import attach_investigation_plan
        enriched = attach_investigation_plan(enriched)
        checkpoint('dimension_investigation_plan', {'records': len(enriched['dimension_investigation_plan']['records'])})
        if industry_mapping:
            from investment_intelligence.industry_context import build_industry_context, attach_industry_context
            mapping = json.loads(Path(industry_mapping).read_text(encoding='utf-8'))
            context = build_industry_context(mapping, ticker=ticker, as_of=cutoff.isoformat(),
                                             api_key=os.environ.get('BEA_API_KEY'))
            enriched = attach_industry_context(enriched, context)
            (root / 'industry-context.json').write_text(json.dumps(context, indent=2) + '\n')
            checkpoint('industry_context', {'status': context['status'],
                      'retrieved_series': sum(x['status'] == 'retrieved' for x in context['series'])})
        if industry_claims:
            from investment_intelligence.industry_corroboration import attach_corroboration
            claims = json.loads(Path(industry_claims).read_text(encoding='utf-8'))
            if not isinstance(claims, list):
                raise ValueError('Industry claims file must be a JSON list')
            enriched = attach_corroboration(enriched, claims)
            (root / 'industry-corroboration.json').write_text(json.dumps(enriched['industry_corroboration'], indent=2) + '\n')
            checkpoint('industry_corroboration', {'records': len(enriched['industry_corroboration']['records']),
                       'publication_decisions_changed': False})
        if industry_hypotheses:
            from investment_intelligence.industry_hypothesis import attach_hypotheses
            hypotheses = json.loads(Path(industry_hypotheses).read_text(encoding='utf-8'))
            enriched = attach_hypotheses(enriched, hypotheses)
            (root / 'industry-hypotheses.json').write_text(json.dumps(enriched['industry_hypotheses'], indent=2) + '\n')
            checkpoint('industry_hypotheses', {'records': len(enriched['industry_hypotheses']['records']),
                       'publication_decisions_changed': False})
        enriched['cash_flow_evidence'] = cash_flow_evidence
        from investment_intelligence.investigation_registry import select_investigations
        enriched['investigation_registry'] = select_investigations(enriched)
        (root / 'investigation-registry.json').write_text(json.dumps(enriched['investigation_registry'], indent=2) + '\n')
        checkpoint('investigation_registry', {'triggered': [x['id'] for x in enriched['investigation_registry']['investigations'] if x['status'] == 'triggered']})
        from investment_intelligence.financial_diagnostics import diagnose_financial_coverage
        coverage = diagnose_financial_coverage(enriched, enriched['investigation_registry'])
        enriched['financial_coverage_diagnostics'] = coverage
        (root / 'financial-coverage-diagnostics.json').write_text(json.dumps(coverage, indent=2) + '\n')
        checkpoint('financial_coverage_diagnostics', {'status':coverage['status'], 'records':len(coverage['records'])})
        from investment_intelligence.earnings_quality import attach_earnings_quality
        if any(x['id'] == 'earnings_quality' and x['status'] == 'triggered' for x in enriched['investigation_registry']['investigations']):
            enriched = attach_earnings_quality(enriched, cash_flow_evidence)
            enriched['earnings_quality_investigation']['cash_flow_evidence_status'] = cash_flow_evidence['status']
            enriched['earnings_quality_investigation']['cash_flow_evidence_file'] = 'cash-flow-evidence.json'
        else:
            enriched['earnings_quality_investigation'] = {'status':'not_triggered','hypotheses':[], 'observations':[]}
        (root / 'earnings-quality-investigation.json').write_text(json.dumps(enriched['earnings_quality_investigation'], indent=2) + '\n')
        checkpoint('earnings_quality_investigation', {'status':enriched['earnings_quality_investigation']['status']})
        enriched['industry_resolution'] = {k:v for k,v in industry_resolution.items() if k != 'mapping'}
        from investment_intelligence.capital_investigation import attach_capital_investigation
        if any(x['id'] == 'capital_investment_economics' and x['status'] == 'triggered' for x in enriched['investigation_registry']['investigations']):
            enriched = attach_capital_investigation(enriched)
        else:
            enriched['capital_investigation'] = {'status':'not_triggered','hypotheses':[], 'observations':[]}
        (root / 'capital-investigation.json').write_text(json.dumps(enriched['capital_investigation'], indent=2) + '\n')
        checkpoint('capital_investigation', {'status': enriched['capital_investigation']['status']})
        from investment_intelligence.evidence_orchestration import orchestrate_evidence
        enriched['evidence_orchestration'] = orchestrate_evidence(enriched)
        from investment_intelligence.sec_disclosure_retrieval import retrieve_disclosures, attach_disclosure_results
        disclosure_evidence = retrieve_disclosures(enriched['evidence_orchestration']['tasks'], parsed,
                                                    cik=cik, as_of=cutoff.isoformat())
        enriched['sec_disclosure_evidence'] = disclosure_evidence
        (root / 'sec-disclosure-evidence.json').write_text(json.dumps(disclosure_evidence, indent=2) + '\n')
        enriched['evidence_orchestration'] = attach_disclosure_results(enriched['evidence_orchestration'], disclosure_evidence)
        checkpoint('sec_disclosure_retrieval', {'filings':len(disclosure_evidence['filings_searched']),
                   'candidate_tasks':sum(v['status']=='candidate_passages_retrieved' for v in disclosure_evidence['tasks'].values())})
        (root / 'evidence-orchestration.json').write_text(json.dumps(enriched['evidence_orchestration'], indent=2) + '\n')
        from investment_intelligence.evidence_quality import build_evidence_quality
        enriched['evidence_quality'] = build_evidence_quality(disclosure_evidence, enriched['evidence_orchestration'], enriched.get('cash_flow_evidence'))
        (root / 'evidence-quality.json').write_text(json.dumps(enriched['evidence_quality'], indent=2) + '\n')
        from investment_intelligence.phase17_validation import build_cash_flow_reconciliation
        enriched['cash_flow_reconciliation'] = build_cash_flow_reconciliation(cash_flow_evidence)
        (root / 'cash-flow-reconciliation.json').write_text(json.dumps(enriched['cash_flow_reconciliation'], indent=2) + '\n')
        checkpoint('evidence_quality', {'table_only_filings':sum(x['table_only'] for x in enriched['evidence_quality']['coverage']), 'temporal_routes':len(enriched['evidence_quality']['temporal_task_routes'])})
        (root / 'investigation-registry.json').write_text(json.dumps(enriched['investigation_registry'], indent=2) + '\n')
        checkpoint('evidence_orchestration', enriched['evidence_orchestration']['summary'])
        enriched['industry_source_candidates'] = industry_sources
        enriched['industry_resolution'] = {k:v for k,v in industry_resolution.items() if k != 'mapping'}
        (root / 'analysis.json').write_text(json.dumps(enriched, indent=2) + '\n')
        (root / 'analysis.md').write_text(enriched['report_markdown'] + '\n')
        runlog['status'] = 'completed'
        checkpoint('narrative', {'passages': len(docs), 'file': str(root / 'analysis.json'),
                                 'markdown': str(root / 'analysis.md')})
        return root
    except Exception as exc:
        runlog['status'] = 'failed'
        checkpoint('error', {'type': type(exc).__name__, 'message': str(exc)})
        raise


def main():
    p = argparse.ArgumentParser(description='One-command investment intelligence pipeline')
    p.add_argument('--ticker', required=True)
    p.add_argument('--output', default='reports')
    p.add_argument('--as-of', help='YYYY-MM-DD; defaults to today')
    p.add_argument('--model', default='qwen3:8b')
    p.add_argument('--base-url', default='http://localhost:11434/v1')
    p.add_argument('--redis-url', default=None)
    p.add_argument('--sec-stream', default='investment.sec.events')
    p.add_argument('--financials-only', action='store_true')
    p.add_argument('--no-auto-industry', action='store_true', help='Disable automatic reviewed industry mapping')
    p.add_argument('--industry-mapping', help='Reviewed JSON mapping of ticker to BEA industry series')
    p.add_argument('--industry-claims', help='Reviewed structured industry-premise claims JSON')
    p.add_argument('--industry-hypotheses', help='Reviewed company/industry hypothesis list JSON')
    args = p.parse_args()
    dest = asyncio.run(run(args.ticker, args.output, os.environ.get('SEC_USER_AGENT'),
                           args.model, args.base_url, args.as_of, args.redis_url,
                           args.financials_only, args.sec_stream, args.industry_mapping, args.industry_claims, args.industry_hypotheses, not args.no_auto_industry))
    print(f'Investment report: {dest / "analysis.md"}')


if __name__ == '__main__':
    main()
