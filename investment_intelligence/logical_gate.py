"""Conservative, deterministic guardrails for dimension-level LLM proposals.

This is not an entailment verifier. It rejects narrow, mechanically identifiable
errors; all other proposals still require human or independent review.
"""
from __future__ import annotations
import re

HISTORICAL_METRICS = {'revenue', 'net_income', 'operating_income', 'operating_cash_flow',
                      'capital_expenditures', 'free_cash_flow', 'assets', 'cash'}
FUTURE_PATTERN = re.compile(r'\b(?:could|may|might|will|would|expect|anticipat\w*|forecast\w*|project\w*|future|potential|risk of|uncertain\w*)\b', re.I)


def check_proposal(statement, dimension, proposal, findings, documents):
    """Return (accepted, reason). Fails closed on malformed proposal references."""
    assessment = proposal.get('assessment')
    ids = proposal.get('evidence_ids', [])
    if not isinstance(ids, list):
        return False, 'invalid_evidence_ids'
    f_by_id = {f['id']: f for f in findings}
    d_by_id = {d['id']: d for d in documents}
    cited_f = [f_by_id[i] for i in ids if i in f_by_id]
    cited_d = [d_by_id[i] for i in ids if i in d_by_id]
    if assessment == 'insufficient_evidence':
        return True, 'insufficient_evidence'
    if not ids:
        return False, 'no_cited_evidence'
    if assessment == 'contradicts':
        # A possible future adverse event does not disprove an observed historical metric.
        linked = {f['id'] for f in findings if f['id'] in statement['statement'].get('finding_ids', [])}
        historical = any(f['id'] in linked and f.get('kind') in {'growth', 'level'}
                         and f.get('metric') in HISTORICAL_METRICS for f in findings)
        if historical and cited_d and all(FUTURE_PATTERN.search(d.get('text', '')) for d in cited_d):
            # Narrow guard: only when cited numerical facts do not themselves refute the claim.
            if not any(f['id'] not in linked for f in cited_f):
                return False, 'future_risk_does_not_contradict_historical_fact'
    return True, 'passed_structural_gate'
