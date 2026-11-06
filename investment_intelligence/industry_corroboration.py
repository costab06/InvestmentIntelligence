"""Phase 3: claim-specific, conservative, inspectable industry corroboration.

No LLM assertions, no automatic publication upgrades. Comparability must be
explicitly attested, and only narrow directional claims are eligible.
"""
from __future__ import annotations
from decimal import Decimal, InvalidOperation

ELIGIBLE_RELATIONS = {'industry_increased', 'industry_decreased', 'industry_flat'}

def _direction(a, b):
    a, b = Decimal(str(a)), Decimal(str(b))
    if a <= 0 or b <= 0:
        return None
    change = (b-a)/a
    if change > Decimal('0.01'):
        return 'industry_increased'
    if change < Decimal('-0.01'):
        return 'industry_decreased'
    return 'industry_flat'

def assess_claim(claim, context):
    """Assess a structured claim; never interpret arbitrary prose as proven.

    Required claim keys: id, proposition, industry_code, relation, start_year,
    end_year, comparison_review. `comparison_review` must explicitly document
    relevance, geographic/metric scope, and reviewed_by. This attestation is
    a gate, not evidence of the investment thesis itself.
    """
    result = {'claim_id': claim.get('id'), 'proposition': claim.get('proposition'),
              'status': 'insufficient_evidence', 'publication_eligible': False,
              'source_evidence': [], 'reason': None,
              'remaining_uncertainties': ['Industry direction does not establish company causation, market share, or future returns.']}
    relation = claim.get('relation')
    if relation not in ELIGIBLE_RELATIONS:
        result['reason'] = 'Unsupported relation; only independently observed industry direction is evaluated'
        return result
    # A BEA-only directional assertion requires no company comparability approval.
    # It makes no company-vs-industry comparison and does not certify relevance.
    review = claim.get('comparison_review') or {}
    if claim.get('requires_company_comparison', False):
        if not all(review.get(k) for k in ('reviewed_by', 'industry_relevance', 'geographic_scope', 'metric_scope')) or review.get('approved') is not True:
            result['reason'] = 'Comparability review missing or not approved'
            return result
    if review.get('company_metric_directly_comparable') is True:
        # Even when attested, this engine only supports direction, not relative outperformance.
        result['reason'] = 'Direct company-versus-industry metric comparisons not implemented'
        return result
    try:
        start, end = int(claim['start_year']), int(claim['end_year'])
    except (ValueError, TypeError, KeyError):
        result['reason'] = 'Valid start_year and end_year required'
        return result
    if start >= end or end > int(context.get('as_of', '0000')[:4]):
        result['reason'] = 'Invalid or future observation period'
        return result
    series = [s for s in context.get('series', []) if str(s.get('industry_code')) == str(claim.get('industry_code'))]
    if len(series) != 1 or series[0].get('status') != 'retrieved':
        result['reason'] = 'Exactly one successfully retrieved industry series is required'
        return result
    s = series[0]
    # Require an exact scope match. Prevent comparisons with different data types.
    for key in ('measure', 'unit', 'geography'):
        if claim.get(key) != s.get(key):
            result['reason'] = f'Series {key} does not match claim scope'
            return result
    if not s.get('response_sha256'):
        result['reason'] = 'Source response fingerprint missing'
        return result
    obs = s.get('observations', [])
    years = [x.get('year') for x in obs]
    if len(years) != len(set(years)):
        result['reason'] = 'Duplicate annual observations'
        return result
    by_year = {x['year']: x for x in obs}
    if any(y not in by_year for y in range(start, end+1)):
        result['reason'] = 'Incomplete annual series for the requested interval'
        return result
    try:
        observed = _direction(by_year[start]['value'], by_year[end]['value'])
    except (InvalidOperation, ValueError, TypeError):
        observed = None
    if observed is None:
        result['reason'] = 'Nonpositive or invalid values cannot establish direction'
        return result
    result['comparability_status'] = 'not_established'
    result['observed_relation'] = observed
    result['source_evidence'] = [{'source': s.get('source'), 'source_url': s.get('source_url'),
        'response_sha256': s['response_sha256'], 'table_id': s.get('table_id'),
        'industry_code': s['industry_code'], 'measure': s['measure'], 'unit': s['unit'],
        'geography': s['geography'], 'start_year': start, 'end_year': end,
        'start_value': by_year[start]['value'], 'end_value': by_year[end]['value']}]
    result['status'] = 'supported' if observed == relation else 'contradicted'
    result['reason'] = ('BEA observations support the narrowly stated industry direction' if observed == relation
                        else 'BEA observations contradict the stated industry direction')
    # The directional industry premise may be supported, but a composite investment
    # judgment requires additional company and reasoning verification.
    return result

def build_corroboration(analysis, claims):
    context = analysis.get('industry_context') or {}
    records = [assess_claim(c, context) for c in claims]
    return {'schema_version': '0.9.0-corroboration', 'status': 'premise_checks_only',
            'records': records, 'publication_decisions_changed': False,
            'limitations': ['Structured claims require reviewed mappings and exact scope.',
                            'Only direction of industry change is assessed; no industry/company growth-rate comparison.',
                            'No qualitative statement is automatically published, upgraded, or declared verified.',
                            'Industry evidence must be combined with verified company evidence and adversarial reasoning.']}

def attach_corroboration(analysis, claims):
    updated = dict(analysis)
    updated['industry_corroboration'] = build_corroboration(updated, claims)
    return updated
