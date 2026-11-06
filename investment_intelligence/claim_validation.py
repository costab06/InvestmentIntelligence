"""v0.7.2 conservative evidence-role and claim-scope validation.

Heuristics reject recognizable unsupported inferences; they do not prove entailment.
"""
from __future__ import annotations

VALID_ROLES = {'establishes_fact', 'supports_inference', 'context_only'}
VALUATION_METRICS = {'pe_ratio', 'earnings_yield_percent', 'fcf_yield_percent', 'market_cap_usd'}


def check_evidence_roles(dimension, proposal, findings, documents):
    """Validate explicit evidence roles and prevent contextual evidence becoming proof."""
    if proposal.get('assessment') == 'insufficient_evidence':
        return True, 'insufficient_evidence'
    ids = proposal.get('evidence_ids', [])
    roles = proposal.get('evidence_roles')
    if not isinstance(roles, dict) or set(roles) != set(ids):
        return False, 'missing_or_mismatched_evidence_roles'
    if any(role not in VALID_ROLES for role in roles.values()):
        return False, 'invalid_evidence_role'
    if proposal.get('assessment') in ('supports', 'contradicts', 'mixed') and not any(
        roles[i] != 'context_only' for i in ids
    ):
        return False, 'context_only_cannot_establish_assessment'
    facts = {f['id']: f for f in findings}
    if dimension == 'valuation' and proposal.get('assessment') in ('supports', 'contradicts', 'mixed'):
        if not any(facts[i].get('metric') in VALUATION_METRICS for i in ids if i in facts):
            # SEC disclosure may discuss valuation; require explicit valuation evidence
            # rather than treating profitability or spending as a valuation judgment.
            return False, 'valuation_requires_valuation_metric'
    if dimension == 'evidence_quality' and proposal.get('assessment') in ('supports', 'contradicts', 'mixed'):
        # A finding's value alone does not establish quality of its source.
        if not any(i.startswith('D') for i in ids):
            return False, 'evidence_quality_requires_source_evidence'
    return True, 'evidence_roles_accepted'


def validate_decomposition(data, statement, valid_ids):
    """Accept a structured model decomposition, without treating it as proof."""
    if not isinstance(data, dict) or not isinstance(data.get('claims'), list):
        raise ValueError('Invalid claim decomposition')
    claims = data['claims']
    if not claims or len(claims) > 12:
        raise ValueError('Claim decomposition must contain 1-12 claims')
    for claim in claims:
        if not isinstance(claim, dict) or claim.get('type') not in ('observed_fact', 'interpretation', 'prediction'):
            raise ValueError('Invalid claim type')
        if not isinstance(claim.get('text'), str) or not claim['text'].strip():
            raise ValueError('Invalid claim text')
        ids = claim.get('evidence_ids')
        if not isinstance(ids, list) or any(not isinstance(i, str) or i not in valid_ids for i in ids):
            raise ValueError('Invalid claim evidence IDs')
        if claim['type'] == 'observed_fact' and not ids:
            raise ValueError('Observed fact requires cited evidence')
    return claims
