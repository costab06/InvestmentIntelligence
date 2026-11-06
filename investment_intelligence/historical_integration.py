"""v0.8.1: audited historical signals for the existing 12-dimension report.

These are deterministic observations, NOT LLM assessments of investment merit.
No v0.7.3 validation, statement evaluations, or evidence IDs are modified.
"""
from __future__ import annotations
from decimal import Decimal
from .historical_intelligence import analyze_history

DIMENSIONS = ('historical','industry','competitive','financial','valuation',
              'macroeconomic','management_strategy','operational','risk',
              'temporal','forward_looking','evidence_quality')

def _values(history, metric):
    series = history['metrics'][metric]
    return [Decimal(o['value']) for o in series['observations']]

def _ref(history, metric):
    return {'source': 'historical_intelligence', 'metric': metric,
            'periods': [o['period_end'] for o in history['metrics'][metric]['observations']]}

def derive_signals(history):
    """Signals describe arithmetic relationships only, with direct metric references."""
    signals = []
    metrics = history['metrics']
    def add(dimensions, code, description, *names):
        signals.append({'code': code, 'dimensions': list(dimensions), 'observation': description,
                        'evidence': [_ref(history, n) for n in names],
                        'status': 'deterministic_observation',
                        'investment_assessment': 'not_assessed'})

    revenue = metrics['revenue']
    if revenue['cagr_percent'] is not None:
        add(('historical','financial','temporal'), 'revenue_cagr',
            f"Revenue CAGR over {revenue['complete_years']-1} annual intervals: {Decimal(revenue['cagr_percent']):.2f}%.", 'revenue')
    ocf = metrics['operating_cash_flow']
    capex = metrics['capital_expenditures']
    if ocf['cagr_percent'] is not None and capex['cagr_percent'] is not None:
        delta = Decimal(capex['cagr_percent']) - Decimal(ocf['cagr_percent'])
        if delta > 0:
            add(('historical','financial','risk','operational'), 'capex_outpaces_ocf',
                f'Capital expenditures CAGR exceeds operating cash flow CAGR by {delta:.2f} percentage points; business significance requires further evidence.',
                'capital_expenditures','operating_cash_flow')
    fcf = metrics['free_cash_flow']
    changes = fcf['year_over_year']
    if len(changes) >= 2 and all(c['status']=='calculated' and Decimal(c['percent']) < 0 for c in changes[-2:]):
        add(('historical','financial','risk','temporal'), 'fcf_two_year_decline',
            'Free cash flow declined in each of the two most recent adjacent fiscal-year comparisons; this is not by itself a distress finding.',
            'free_cash_flow')
    return signals

def integrate_history(analysis, report, *, years=5):
    """Non-mutating merge preserving v0.7.3 evaluations and existing report text."""
    history = analyze_history(report, years=years)
    signals = derive_signals(history)
    coverage = {d: [s['code'] for s in signals if d in s['dimensions']] for d in DIMENSIONS}
    result = dict(analysis)
    result['historical_intelligence'] = history
    result['historical_dimension_signals'] = {
        'schema_version': '0.8.1', 'signals': signals, 'dimension_coverage': coverage,
        'note': 'Signals are historical facts for subsequent dimension evaluation, not validated LLM investment assessments.'}
    if isinstance(result.get('report_markdown'), str):
        lines = ['','## Historical Financial Intelligence (v0.8.1)','',
                 'Deterministic observations; investment implications remain unassessed.','']
        for signal in signals:
            lines.append(f"- **{signal['code']}** ({', '.join(signal['dimensions'])}): {signal['observation']}")
        if not signals:
            lines.append('Insufficient comparable history for predefined signals.')
        result['report_markdown'] = result['report_markdown'].rstrip() + '\n' + '\n'.join(lines) + '\n'
    return result
