"""SEC narrative bridge for SECAgents parsed.json -> v0.6 evidence matrix.

Offline-by-default: reads locally produced SECAgents artifacts. No fabricated filing dates.
LLM outputs are candidates; Python checks source IDs and conservative assessment shape.
"""
from __future__ import annotations
import argparse
import asyncio
import hashlib
import json
import re
from pathlib import Path
from .analyst_v060 import DIMENSIONS, evaluate_statement, normalize_evidence, render_v060

KEYWORDS = {
 'historical': ('previous year','historical','year over year','prior year'),
 'industry': ('industry','sector','industry trend'),
 'competitive': ('competition','competitor','market share'),
 'financial': ('cash flow','revenue','profit','margin','capital expenditure','liquidity'),
 'valuation': ('valuation','share price','market value'),
 'macroeconomic': ('interest rate','inflation','foreign exchange','economic'),
 'management_strategy': ('strategy','management','investment','priorities','capital allocation'),
 'operational': ('capacity','infrastructure','utilization','operations','datacenter','data center'),
 'risk': ('risk','uncertainty','material adverse','could adversely'),
 'temporal': ('future periods','long term','short term','fiscal year'),
 'forward_looking': ('expect','forecast','outlook','guidance','anticipate'),
 'evidence_quality': (),
}

def import_sec_parsed(paths, filing_dates=None, max_passages=90, max_chars=850):
    """Import filing passages with filing date embedded by SECAgents.

    Optional mapping is retained only for legacy artifacts; no inferred dates.
    """
    docs=[]
    for path in paths:
        raw=Path(path).read_bytes(); obj=json.loads(raw)
        source=obj['source']; accession=source['accession_number']
        date=source.get("filing_date") or (filing_dates or {}).get(accession)
        if not isinstance(date,str) or not re.fullmatch(r'\d{4}-\d{2}-\d{2}',date):
            raise ValueError(f'EDGAR filing date required for accession {accession}')
        blocks=obj['document']['blocks']
        for idx,block in enumerate(blocks):
            if block.get('type') not in ('paragraph','list_item'):
                continue
            txt=' '.join(str(block.get('text','')).split())
            if len(txt)<70: continue
            if not any(term in txt.lower() for terms in KEYWORDS.values() for term in terms):
                continue
            if len(docs)>=max_passages:break
            docs.append({'id':f'D{len(docs)+1:04d}','source_type':f"sec_{source['filing_type'].lower().replace('-','')}",
                'source_document':f"{source['cik']}:{accession}",
                'source_location':f'block:{idx}', 'published_at':date,
                'text':txt[:max_chars], 'source_sha256':hashlib.sha256(raw).hexdigest(),
                'attribution':'issuer_disclosure'})
    return normalize_evidence(docs)

PROMPT='''Evaluate ONE investment statement against ONE predeclared dimension. Use only supplied evidence.
Return JSON object {"assessment":"supports|contradicts|mixed|neutral|insufficient_evidence",
"materiality":"high|medium|low", "confidence":"high|medium|low|null",
"evidence_ids":["F...","D..."], "evidence_roles":{"F001":"establishes_fact|supports_inference|context_only"}, "rationale":"..."}.
If evidence cannot establish a dimension-specific evaluation, return insufficient_evidence with [] and null confidence.
Never infer that an issuer assertion is independently true; say management claims if using issuer text.
Never invent a benchmark, cause, future outcome, or evidence ID. Financial figures are supplied, not calculated.
Cite at least one supplied evidence ID for non-insufficient assessments. For each cited ID provide exactly one evidence_roles entry. Only label establishes_fact if the source directly establishes the tested proposition; use context_only for merely relevant background. For insufficient_evidence return evidence_roles {}.
Treat evidence from an unrelated reporting period as insufficient for claims about the current period.
IMPORTANT: Relevance is not support. Future risks cannot contradict already observed historical results.
For every non-insufficient assessment, explain the precise dimension-specific proposition tested and how the cited evidence bears on it.
A risk disclosure is not evidence that the adverse event occurred. If only tangential evidence exists, choose insufficient_evidence.'''

async def assess_with_model(client, statement, dimension, evidence, findings, diagnostics=None):
    """Propose a dimension assessment and record why evidence was not accepted."""
    from .json_recovery import complete_json as _complete
    from .evidence_retrieval import retrieve
    selected = retrieve(statement['statement']['text'], dimension, evidence, limit=5)
    cited = set(statement['statement'].get('finding_ids', []))
    related = [f for f in findings if f['id'] in cited]
    if diagnostics is not None:
        diagnostics['retrieved_document_ids'] = [d['id'] for d in selected]
        diagnostics['related_finding_ids'] = [f['id'] for f in related]
    if not related and not selected:
        if diagnostics is not None: diagnostics['outcome'] = 'no_retrieved_evidence'
        return None
    payload = {'statement': statement['statement']['text'], 'dimension': dimension,
               'findings': related, 'documents': selected}
    try:
        result = await _complete(client, PROMPT, payload)
    except (ValueError, TypeError, json.JSONDecodeError) as exc:
        if diagnostics is not None:
            diagnostics['outcome'] = 'model_output_error'
            diagnostics['error_type'] = type(exc).__name__
            diagnostics['error_message'] = str(exc)
        return None
    if not isinstance(result, dict):
        if diagnostics is not None: diagnostics['outcome'] = 'invalid_response_type'
        return None
    allowed = cited | {d['id'] for d in selected}
    evidence_ids = result.get('evidence_ids', [])
    if not isinstance(evidence_ids, list) or any(not isinstance(x, str) for x in evidence_ids):
        if diagnostics is not None: diagnostics['outcome'] = 'invalid_evidence_ids'
        return None
    if set(evidence_ids) - allowed:
        if diagnostics is not None: diagnostics['outcome'] = 'unknown_evidence_reference'
        return None
    if result.get('assessment') not in ('supports', 'contradicts', 'mixed', 'neutral', 'insufficient_evidence'):
        if diagnostics is not None: diagnostics['outcome'] = 'invalid_assessment'
        return None
    if diagnostics is not None: diagnostics['outcome'] = 'candidate_returned'
    return result

async def enrich_analysis(analysis, docs, client):
    """Reevaluate published statements; retain validation and retrieval diagnostics."""
    from collections import Counter
    from .logical_gate import check_proposal
    from .claim_validation import check_evidence_roles, validate_decomposition
    from .sufficiency_gate import check_sufficiency, normalize_insufficient
    docs = normalize_evidence(docs)
    if analysis.get('schema_version') != '0.6.0':
        raise ValueError('v0.6.0 analysis required')
    ids = {f['id'] for f in analysis['findings']} | {d['id'] for d in docs}
    if len(ids) != len(analysis['findings']) + len(docs):
        raise ValueError('duplicate evidence ID')
    rows = []
    diagnostics = []
    decompositions = []
    from .json_recovery import complete_json as _complete
    decompose_prompt = ("Split this investment statement into atomic claims. Return JSON only: "
        "{\"claims\":[{\"text\":\"...\",\"type\":\"observed_fact|interpretation|prediction\","
        "\"evidence_ids\":[\"F001\"]}]}. Only use supplied finding IDs. "
        "Observed facts require direct support; do not reclassify an inference as a fact. "
        "An interpretation or prediction may have an empty evidence_ids list.")
    for stmt in analysis['qualitative_audit']:
        supplied = {}
        if stmt['status'] == 'rejected':
            diagnostics.append({'statement_id': stmt['id'], 'outcome': 'rejected_statement_skipped'})
        else:
            claim_record = {'statement_id': stmt['id'], 'status': 'unavailable', 'claims': []}
            try:
                valid_finding_ids = set(stmt['statement'].get('finding_ids', []))
                decomposed = await _complete(client, decompose_prompt, {
                    'statement': stmt['statement']['text'],
                    'findings': [f for f in analysis['findings'] if f['id'] in valid_finding_ids],
                })
                claim_record['claims'] = validate_decomposition(decomposed, stmt, valid_finding_ids)
                claim_record['status'] = 'model_proposed_unverified'
            except (ValueError, TypeError, KeyError) as exc:
                claim_record['error'] = f'{type(exc).__name__}: {exc}'
            decompositions.append(claim_record)
            for dim in DIMENSIONS:
                diag = {'statement_id': stmt['id'], 'dimension': dim}
                proposal = await assess_with_model(client, stmt, dim, docs, analysis['findings'], diag)
                if proposal is not None:
                    proposal, normalized = normalize_insufficient(proposal)
                    if normalized: diag['insufficient_evidence_normalized'] = True
                    try:
                        evaluate_statement(stmt, ids, {dim: proposal})
                    except (ValueError, TypeError, KeyError) as exc:
                        diag['outcome'] = 'validation_rejected'
                        diag['error_type'] = type(exc).__name__
                        diag['error_message'] = str(exc)
                    else:
                        accepted, reason = check_proposal(stmt, dim, proposal, analysis['findings'], docs)
                        if accepted:
                            accepted, reason = check_evidence_roles(dim, proposal, analysis['findings'], docs)
                        if accepted:
                            accepted, reason = check_sufficiency(stmt, dim, proposal, analysis['findings'], docs)
                        diag['logical_gate_reason'] = reason
                        if not accepted:
                            diag['outcome'] = 'logical_gate_rejected'
                            diagnostics.append(diag)
                            continue
                        supplied[dim] = proposal
                        diag['outcome'] = ('insufficient_evidence' if proposal['assessment'] == 'insufficient_evidence'
                                           else 'assessed')
                diagnostics.append(diag)
        rows.append(evaluate_statement(stmt, ids, supplied))
    analysis = dict(analysis)
    analysis['claim_decompositions'] = decompositions
    analysis['document_evidence'] = docs
    analysis['statement_evaluations'] = rows
    analysis['evidence_gaps'] = {
        d: sum(r['dimensions'][d]['assessment'] == 'insufficient_evidence' for r in rows)
        for d in DIMENSIONS
    }
    analysis['evaluation_diagnostics'] = {
        'retriever': 'deterministic_bm25_v1',
        'counts': dict(sorted(Counter(d['outcome'] for d in diagnostics).items())),
        'records': diagnostics,
    }
    analysis['narrative_integration'] = {
        'mode': 'SECAgents parsed.json; BM25 retrieval and dimension-specific LLM candidates',
        'source_passages': len(docs), 'rejected_statements_skipped': True,
    }
    analysis['report_markdown'] = render_v060(analysis)
    return analysis

def main():
    p=argparse.ArgumentParser(description='Enrich v0.6 report using SECAgents parsed.json artifacts')
    p.add_argument('--analysis',required=True);p.add_argument('--parsed',nargs='+',required=True)
    p.add_argument('--filing-dates',help='Optional legacy-only accession date mapping')
    p.add_argument('--output',required=True);p.add_argument('--markdown-output')
    p.add_argument('--model',default='qwen3:8b');p.add_argument('--base-url',default='http://localhost:11434/v1')
    args=p.parse_args()
    from shared.llm import LLMClient,LLMConfig
    client=LLMClient(LLMConfig(provider='openai_compatible',model=args.model,base_url=args.base_url))
    docs=import_sec_parsed(args.parsed,json.loads(Path(args.filing_dates).read_text()) if args.filing_dates else None)
    result=asyncio.run(enrich_analysis(json.loads(Path(args.analysis).read_text()),docs,client))
    target=Path(args.output);target.parent.mkdir(parents=True,exist_ok=True)
    target.write_text(json.dumps(result,indent=2)+'\n')
    md=Path(args.markdown_output) if args.markdown_output else target.with_suffix('.md')
    md.write_text(result['report_markdown']+'\n')
    print(f'Imported {len(docs)} SEC passages; wrote {target} and {md}')
if __name__=='__main__':main()
