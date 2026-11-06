"""v0.7.3 conservative, deterministic sufficiency constraints.

These rules reject recognizable evidence/category mismatches, not prove entailment.
"""
from __future__ import annotations
import re

SUSTAINED = re.compile(r'\b(?:sustain(?:ed|able)?|consistent(?:ly)?|persistent(?:ly)?|repeated(?:ly)?|multi[- ]year|year after year|over several years)\b', re.I)
IMPLICATION = re.compile(r'\b(?:liquidity pressure|liquidity strain|sustainability|deteriorat\w*|future|forecast|will|may|might|could|risk of|concerns? about|pricing power|competitive advantage)\b', re.I)
VALUATION = {'pe_ratio', 'earnings_yield_percent', 'fcf_yield_percent', 'market_cap_usd'}
# Dimensions whose conclusions are not established by a company's numeric result alone.
DOCUMENT_CONTEXT_DIMENSIONS = {'industry', 'competitive', 'macroeconomic', 'management_strategy', 'forward_looking'}


def normalize_insufficient(proposal):
    """Canonicalize non-supporting responses before the schema validator.

    Preserve rationale, discard contradictory confidence, citations and role maps.
    """
    if not isinstance(proposal, dict) or proposal.get('assessment') != 'insufficient_evidence':
        return proposal, False
    out = dict(proposal)
    changed = bool(out.get('evidence_ids') or out.get('evidence_roles') or out.get('confidence'))
    out['evidence_ids'] = []
    out['evidence_roles'] = {}
    out['confidence'] = None
    if not isinstance(out.get('rationale'), str) or not out['rationale'].strip():
        out['rationale'] = 'Insufficient evidence for this dimension.'
        changed = True
    return out, changed


def check_sufficiency(statement, dimension, proposal, findings, documents):
    """Return (accepted, reason) for an already schema-validated proposal."""
    assessment = proposal.get('assessment')
    if assessment in ('insufficient_evidence', 'neutral'):
        return True, 'no_positive_support_claim'
    if assessment not in ('supports', 'contradicts', 'mixed'):
        return False, 'unknown_assessment'
    ids = proposal.get('evidence_ids', [])
    roles = proposal.get('evidence_roles', {})
    f = {x['id']: x for x in findings}
    d = {x['id']: x for x in documents}
    active = [i for i in ids if roles.get(i) in ('establishes_fact', 'supports_inference')]
    active_docs = [i for i in active if i in d]
    active_facts = [f[i] for i in active if i in f]
    text = statement.get('statement', {}).get('text', '')
    if dimension in DOCUMENT_CONTEXT_DIMENSIONS and not active_docs:
        return False, f'{dimension}_requires_dimension_specific_document_evidence'
    if dimension == 'valuation' and not any(x.get('metric') in VALUATION for x in active_facts):
        return False, 'valuation_requires_active_valuation_metric'
    # A year-over-year observation is only one interval; it cannot prove persistence.
    if SUSTAINED.search(text) and dimension in {'historical', 'financial', 'temporal'}:
        return False, 'sustained_trend_requires_multi_period_evidence'
    # A financial fact may establish the historical premise, but not an adverse outcome.
    if dimension in {'risk', 'forward_looking'} and IMPLICATION.search(text) and not active_docs:
        return False, 'risk_or_prediction_requires_independent_document_support'
    # Even a document may only discuss a risk as hypothetical; issuer warnings are not occurrence evidence.
    if dimension == 'risk' and assessment == 'supports' and active_docs:
        if all(re.search(r'\b(?:may|might|could|risk|potential|forward-looking)\b', d[i].get('text',''), re.I)
               for i in active_docs):
            return False, 'hypothetical_risk_not_evidence_of_realized_harm'
    return True, 'sufficiency_gate_accepted'
