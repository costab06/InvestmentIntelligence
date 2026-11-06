"""Evidence-needs routing, not twelve automatic evidence verdicts.

This module does not claim to corroborate anything. It produces a deterministic,
inspectable plan for independent evidence collection and claim verification.
"""
from __future__ import annotations

from typing import Any

DIMENSIONS = ('historical','industry','competitive','financial','valuation',
              'macroeconomic','management_strategy','operational','risk',
              'temporal','forward_looking','evidence_quality')

# Curated routing rules: transparent and deliberately conservative.
ROUTES = (
    (('revenue', 'growth', 'cagr'), ('historical', 'financial', 'industry'),
     'Compare company growth to a genuinely comparable industry series, with period/geography alignment.'),
    (('market share', 'competitor', 'competitive'), ('industry', 'competitive'),
     'Seek independent market share or competitor evidence.'),
    (('capital expenditure', 'capital spending', 'capex', 'free cash flow', 'cash flow'),
     ('financial', 'operational', 'risk'),
     'Check company cash-flow figures and independent sector investment conditions.'),
    (('valuation', 'overvalu', 'undervalu', 'p/e', 'earnings yield', 'multiple'),
     ('valuation', 'financial'),
     'Obtain independent peer benchmarks; inverse financial ratios are not independent corroboration.'),
    (('management', 'strategy', 'pricing'), ('management_strategy', 'competitive'),
     'Identify specific claims and seek independent corroboration rather than treating management assertions as proof.'),
    (('forecast', 'future', 'expected', 'will ', 'outlook'), ('forward_looking', 'risk'),
     'Require explicit forecast assumptions and independent evidence before projecting outcomes.'),
)

def route_claim(text: str, *, signal_id: str | None = None) -> dict[str, Any]:
    lower = text.lower()
    dimensions = []
    needs = []
    for terms, dims, need in ROUTES:
        if any(term in lower for term in terms):
            for dim in dims:
                if dim not in dimensions:
                    dimensions.append(dim)
            needs.append(need)
    if not dimensions:
        dimensions = ['financial']
        needs = ['Specify the investment proposition and its required external corroboration before evaluating.']
    # Quality is an always-on verification gate, not a request for another LLM verdict.
    return {
        'signal_id': signal_id,
        'selected_dimensions': dimensions,
        'verification_gate': 'evidence_quality',
        'evidence_requirements': needs,
        'independent_industry_evidence': 'required_not_retrieved' if 'industry' in dimensions else 'not_requested',
        'assessment': 'investigation_plan_only',
    }

def build_investigation_plan(analysis: dict[str, Any]) -> dict[str, Any]:
    records = []
    for item in analysis.get('qualitative_audit', []):
        statement = item.get('statement') or {}
        claim = statement.get('text', '')
        if claim:
            route = route_claim(claim, signal_id=item.get('id'))
            route.update({'source': 'qualitative_statement', 'claim': claim,
                          'publication_status': item.get('status', 'unknown')})
            records.append(route)
    signals = (analysis.get('historical_dimension_signals') or {}).get('signals', [])
    for item in signals:
        claim = item.get('observation') or item.get('description') or item.get('text') or ''
        if not claim:
            continue
        route = route_claim(str(claim), signal_id=item.get('id'))
        route.update({'source': 'historical_signal', 'claim': str(claim)})
        records.append(route)
    return {
        'schema_version': '0.9.0-plan',
        'status': 'planning_only_no_external_data_retrieved',
        'purpose': 'Select relevant investigative dimensions; never imply corroboration from topical relevance.',
        'records': records,
        'limitations': [
            'Routing uses keyword heuristics and requires review for ambiguous or diversified issuers.',
            'Industry classification, BEA retrieval, peer matching and independent corroboration are not implemented here.',
            'Legacy twelve-dimensional evaluations are preserved for audit, not treated as verification.'
        ],
    }

def attach_investigation_plan(analysis: dict[str, Any]) -> dict[str, Any]:
    result = dict(analysis)
    result['dimension_investigation_plan'] = build_investigation_plan(result)
    return result
