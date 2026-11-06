"""v0.8.2: evidence-grounded investigations of deterministic historical signals.

A parallel assessment track: does not modify or bypass the frozen v0.7.3 gates.
"""
from __future__ import annotations
import json
from .evidence_retrieval import retrieve

PROMPT = '''Investigate a deterministic financial observation using only the supplied SEC issuer disclosures.
Return a JSON object with exactly these keys:
{"assessment":"context_found|no_explanatory_evidence|conflicting_disclosures",
 "management_explanation":"... or null", "investment_implication":"... or null",
 "uncertainties":["..."], "evidence_ids":["D0001"]}.
The deterministic observation is established by the financial calculations, not by issuer narrative.
Treat issuer statements as MANAGEMENT CLAIMS, never independent verification.
Do not assert causal relationships, expected returns, capital efficiency or forecasts as facts.
If the documents do not explicitly explain the observation, use no_explanatory_evidence,
null explanation and implication, and empty evidence_ids. Do not invent evidence IDs.
Only cite supplied document IDs. A document merely mentioning investment or cash flow
is not necessarily an explanation of the observed divergence.
Distinguish what is observed, what management claims, and what remains unknown.'''

SIGNAL_QUERIES = {
 'revenue_cagr': ('revenue growth annual recurring cloud demand fiscal year', 'historical'),
 'capex_outpaces_ocf': ('capital expenditures investment datacenter infrastructure AI capacity cash flow returns', 'management_strategy'),
 'fcf_two_year_decline': ('free cash flow capital expenditures cash generation investment liquidity', 'financial'),
}


def prepare_investigations(analysis, docs, limit=6):
    """Use the full imported evidence set; preserve existing D IDs and original analysis."""
    rows = []
    ids = set()
    for signal in analysis.get('historical_dimension_signals', {}).get('signals', []):
        code = signal['code']
        query, dimension = SIGNAL_QUERIES.get(code, (signal['observation'], 'historical'))
        selected = retrieve(query + ' ' + signal['observation'], dimension, docs, limit=limit)
        selected = [d for d in selected if d.get('id') and d.get('text')]
        ids.update(d['id'] for d in selected)
        rows.append({'signal_code': code, 'dimensions': signal['dimensions'],
                     'observation': signal['observation'], 'financial_evidence': signal['evidence'],
                     'documents': selected})
    return rows


def validate_response(candidate, allowed):
    if not isinstance(candidate, dict):
        raise ValueError('response must be object')
    status = candidate.get('assessment')
    if status not in ('context_found', 'no_explanatory_evidence', 'conflicting_disclosures'):
        raise ValueError('invalid assessment')
    ids = candidate.get('evidence_ids')
    if not isinstance(ids, list) or len(ids) != len(set(ids)) or any(not isinstance(x, str) or x not in allowed for x in ids):
        raise ValueError('unknown or duplicate evidence ID')
    uncertainties = candidate.get('uncertainties')
    if not isinstance(uncertainties, list) or any(not isinstance(x, str) for x in uncertainties):
        raise ValueError('invalid uncertainties')
    explanation = candidate.get('management_explanation')
    implication = candidate.get('investment_implication')
    if explanation is not None and (not isinstance(explanation, str) or not explanation.strip()):
        raise ValueError('invalid explanation')
    if implication is not None and (not isinstance(implication, str) or not implication.strip()):
        raise ValueError('invalid implication')
    if status == 'no_explanatory_evidence' and (ids or explanation is not None or implication is not None):
        raise ValueError('no-evidence response contains unsupported claims')
    if status != 'no_explanatory_evidence' and (not ids or not explanation):
        raise ValueError('explanation requires cited documents')
    return {k: candidate[k] for k in ('assessment','management_explanation','investment_implication','uncertainties','evidence_ids')}


async def investigate_history(analysis, docs, client=None):
    """Attach separately audited investigations; never rewrite v0.7.3 evaluations."""
    output = dict(analysis)
    records = []
    for row in prepare_investigations(analysis, docs):
        allowed = {d['id'] for d in row['documents']}
        base = {'signal_code': row['signal_code'], 'dimensions': row['dimensions'],
                'observation': row['observation'], 'financial_evidence': row['financial_evidence'],
                'retrieved_document_ids': sorted(allowed)}
        if client is None:
            base.update(status='not_evaluated', reason='LLM disabled')
        elif not allowed:
            base.update(status='insufficient_evidence', reason='No matching SEC passages')
        else:
            payload = {'observation': row['observation'], 'financial_evidence': row['financial_evidence'],
                       'dimensions': row['dimensions'], 'documents': row['documents']}
            from .json_recovery import complete_json
            last_error = None
            for attempt in range(2):
                try:
                    if attempt:
                        retry_payload = dict(payload)
                        retry_payload['validation_feedback'] = str(last_error)
                        retry_payload['permitted_evidence_ids'] = sorted(allowed)
                        retry_prompt = PROMPT + ("\nYour previous response failed semantic validation: "
                            + str(last_error) + ". Correct the JSON using ONLY the permitted evidence IDs. "
                            "Do not invent or repeat IDs. If no evidence directly explains the observation, "
                            "return no_explanatory_evidence with null explanations and empty evidence_ids.")
                        proposal = await complete_json(client, retry_prompt, retry_payload)
                    else:
                        proposal = await complete_json(client, PROMPT, payload)
                    checked = validate_response(proposal, allowed)
                    base.update(status='model_proposed_unverified', **checked)
                    if attempt:
                        base['semantic_recovery'] = 'retry_succeeded'
                    break
                except (ValueError, TypeError, KeyError, json.JSONDecodeError) as exc:
                    last_error = exc
            else:
                base.update(status='rejected', reason=f'{type(last_error).__name__}: {last_error}',
                            semantic_recovery='retry_failed')
        records.append(base)
    output['historical_investigations'] = {
        'schema_version': '0.8.2', 'status': 'model_proposals_not_independently_validated',
        'records': records,
        'note': 'Independent historical narrative investigations. v0.7.3 statement evaluation and validation gates are unchanged.'}
    if isinstance(output.get('report_markdown'), str):
        lines = ['', '## Historical Evidence Investigations (v0.8.2)', '',
                 'Model interpretations are unverified proposals, not validated investment conclusions.', '']
        for rec in records:
            lines.append(f"### {rec['signal_code']} — {rec['status']}")
            if rec.get('management_explanation'):
                lines.append('Management explanation (model interpretation): ' + rec['management_explanation'])
            if rec.get('investment_implication'):
                lines.append('Potential implication (unverified): ' + rec['investment_implication'])
            if rec.get('evidence_ids'):
                lines.append('SEC passages: ' + ', '.join(rec['evidence_ids']))
            if rec.get('reason'):
                lines.append('Reason: ' + rec['reason'])
            lines.append('')
        output['report_markdown'] = output['report_markdown'].rstrip() + '\n' + '\n'.join(lines) + '\n'
    return output
