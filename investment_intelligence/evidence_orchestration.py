"""Phase 12: bounded, auditable orchestration of existing evidence.

No network calls: SEC CompanyFacts has already been retrieved by the run pipeline.
Unanswered narrative questions are explicitly marked as not attempted rather than resolved.
"""
from __future__ import annotations
from decimal import Decimal, InvalidOperation

ROUTES = {
    'earnings_quality': ('sec_companyfacts_cash_flow', 'sec_filing_disclosures'),
    'capital_investment_economics': ('sec_companyfacts_capex', 'sec_filing_disclosures'),
    'revenue_margin_divergence': ('sec_companyfacts_financials', 'sec_filing_disclosures'),
}


def _number(value):
    try:
        n = Decimal(str(value))
        return n if n.is_finite() else None
    except (InvalidOperation, ValueError, TypeError):
        return None


def _cash_flow_observations(analysis):
    investigation = analysis.get('earnings_quality_investigation') or {}
    return [o for o in investigation.get('observations', []) if o.get('id') == 'EQ-O3' and o.get('status') == 'calculated_from_filed_components']


def _capital_observations(analysis):
    investigation = analysis.get('capital_investigation') or {}
    return [o for o in investigation.get('observations', []) if o.get('code') == 'cash_flow_bridge' and o.get('status') == 'verified']


def orchestrate_evidence(analysis):
    """Build tasks for triggered investigations and resolve only bounded structured evidence.

    Source status is not a claim that the underlying economic hypothesis is proven.
    Each question remains open unless an explicit matching structured observation exists.
    """
    tasks = []
    investigations = (analysis.get('investigation_registry') or {}).get('investigations', [])
    for item in investigations:
        if item.get('status') != 'triggered':
            continue
        topic = item['id']
        routes = ROUTES.get(topic, ('sec_filing_disclosures',))
        inv = (analysis.get('earnings_quality_investigation') if topic == 'earnings_quality'
               else analysis.get('capital_investigation') if topic == 'capital_investment_economics'
               else {}) or {}
        # First task: independently trace the available numerical evidence to its source artifact.
        observations = _cash_flow_observations(analysis) if topic == 'earnings_quality' else _capital_observations(analysis) if topic == 'capital_investment_economics' else []
        verified = bool(observations)
        tasks.append({
            'id': f'{topic}:structured', 'investigation': topic,
            'question': 'Which filed numerical observations support the trigger?',
            'source': routes[0], 'status': 'retrieved' if verified else 'insufficient_evidence',
            'attempted': True,
            'evidence_refs': (['earnings-quality-investigation.json#EQ-O3', 'cash-flow-evidence.json'] if verified and topic == 'earnings_quality'
                              else ['capital-investigation.json#cash_flow_bridge'] if verified else []),
            'limitations': ['Numerical reconciliation does not establish a causal explanation.'],
        })
        for i, need in enumerate(inv.get('next_evidence', []), 1):
            question = need.get('question')
            if not question:
                continue
            # Existing Phase 10 bridge partially addresses cash conversion, but does not
            # answer inventory quality, business causes, investment returns, or utilization.
            partially = (topic == 'earnings_quality' and verified and
                         (question.startswith('Which working-capital') or question.startswith('How much of the difference')))
            tasks.append({
                'id': f'{topic}:question:{i}', 'investigation': topic,
                'question': question, 'needed': need.get('needed'),
                'source': 'sec_companyfacts_cash_flow' if partially else 'sec_filing_disclosures',
                'status': 'partial_evidence_retrieved' if partially else 'not_attempted',
                'attempted': partially,
                'evidence_refs': ['earnings-quality-investigation.json#EQ-O3'] if partially else [],
                'reason': ('Partial cash-flow components are available; untagged and issuer-specific components remain.' if partially
                           else 'Requires a separately implemented, passage-level SEC disclosure retrieval and verification adapter.'),
            })
    for entry in investigations:
        if entry.get('id') == 'earnings_quality' and entry.get('status') == 'triggered':
            entry['investigator'] = 'earnings_quality'
    counts = {s: sum(t['status'] == s for t in tasks) for s in ('retrieved', 'partial_evidence_retrieved', 'insufficient_evidence', 'not_attempted')}
    return {'schema_version': '1.0.0', 'status': 'bounded_orchestration_completed',
            'tasks': tasks, 'summary': counts,
            'limitations': ['No new external retrieval is performed in this phase; SEC CompanyFacts observations are reused from the run.',
                            'Disclosure retrieval is not implemented: not_attempted must not be presented as searched or unavailable.',
                            'Evidence availability is distinct from hypothesis verification or publication eligibility.']}
