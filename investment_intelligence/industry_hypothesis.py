"""Phase 4: evidence-gated company/industry hypothesis adjudication.

This module does NOT infer causality or upgrade publication status. Only explicit
company finding IDs and corroborated independent industry premises are eligible.
"""
from __future__ import annotations
from decimal import Decimal, InvalidOperation


def _result(h):
    return {'hypothesis_id': h.get('id'), 'proposition': h.get('proposition'),
            'status': 'insufficient_evidence', 'publication_eligible': False,
            'company_evidence': [], 'industry_evidence': [], 'challenges': [],
            'reason': None}


def _finding_map(analysis):
    findings = analysis.get('findings', [])
    return {f.get('id'): f for f in findings if isinstance(f, dict) and f.get('id')}


def evaluate_hypothesis(h, analysis):
    """Deterministically reconcile two directional facts, without inferring causation.

    A company growth finding is an annual change, whereas BEA claims may span
    several calendar years. Such observations cannot establish synchronized growth.
    """
    out = _result(h)
    if h.get('relation') != 'company_and_industry_same_direction':
        out['reason'] = 'Only joint directional consistency is implemented'
        return out
    finding_id = h.get('company_finding_id')
    finding = _finding_map(analysis).get(finding_id)
    if not finding:
        out['reason'] = 'Company finding ID does not exist'
        return out
    if finding.get('kind') != 'growth' or finding.get('metric') != 'revenue':
        out['reason'] = 'A deterministic company revenue growth finding is required'
        return out
    try:
        change = Decimal(str(finding['value']))
        if not change.is_finite():
            raise InvalidOperation()
    except (InvalidOperation, ValueError, TypeError, KeyError):
        out['reason'] = 'Company growth finding is invalid'
        return out
    direction = 'increased' if change > 0 else 'decreased' if change < 0 else 'flat'
    out['company_evidence'] = [{'finding_id': finding_id,
                                'source_paths': finding.get('source_paths', []),
                                'direction': direction, 'growth_percent': str(change),
                                'verification': 'deterministic_finding'}]
    if not finding.get('source_paths'):
        out['reason'] = 'Company finding lacks source paths'
        return out
    records = (analysis.get('industry_corroboration') or {}).get('records', [])
    matches = [r for r in records if r.get('claim_id') == h.get('industry_claim_id')]
    if len(matches) != 1:
        out['reason'] = 'Exactly one industry claim assessment required'
        return out
    record = matches[0]
    if record.get('status') != 'supported' or not record.get('source_evidence'):
        out['reason'] = 'Industry premise is not supported by independent evidence'
        return out
    out['industry_evidence'] = record['source_evidence']
    out['challenges'] = [
        {'type': 'scope', 'assessment': 'unresolved',
         'detail': 'Worldwide nominal issuer revenue differs from US real industry gross output.'},
        {'type': 'period', 'assessment': 'unresolved',
         'detail': 'Company annual growth interval is not verified to match the BEA calendar-year interval.'},
        {'type': 'alternatives', 'assessment': 'unresolved',
         'detail': 'Product mix, geography, pricing, acquisitions and company-specific execution could explain differences.'},
    ]
    observed = record.get('observed_relation')
    out['directional_agreement'] = observed == 'industry_' + direction
    out['status'] = 'directional_agreement_only' if out['directional_agreement'] else 'directional_disagreement_only'
    out['reason'] = 'Both directions independently established; time alignment, comparability, and causality remain unresolved'
    return out


def attach_hypotheses(analysis, hypotheses):
    if not isinstance(hypotheses, list):
        raise ValueError('Hypotheses must be a JSON list')
    result = dict(analysis)
    result['industry_hypotheses'] = {
        'schema_version': '0.9.0-hypotheses', 'status': 'nonpublishing_premise_reconciliation',
        'records': [evaluate_hypothesis(h, analysis) for h in hypotheses],
        'publication_decisions_changed': False,
        'limitations': ['Company growth direction is calculated from a deterministic financial finding.',
                        'Agreement between industry and company directions does not prove causality.',
                        'No automatic publication or qualitative status upgrade.',
                        'This stage does not compare growth rates or establish market-share gains.']}
    return result
