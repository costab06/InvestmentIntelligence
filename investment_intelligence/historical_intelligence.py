"""v0.8.0: deterministic, provenance-preserving multi-year financial intelligence.

Consumes report['financial_history'] from the existing SEC report pipeline.
No LLM calls, network access, or modification of v0.7.3 assessments.
"""
from __future__ import annotations
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any

METRICS = ('revenue', 'net_income', 'operating_income', 'operating_cash_flow',
           'capital_expenditures', 'cash', 'assets', 'free_cash_flow')

def _number(item: Any) -> Decimal | None:
    if not isinstance(item, dict) or item.get('status') not in ('selected', 'calculated'):
        return None
    try:
        n = Decimal(str(item['value']))
        return n if n.is_finite() else None
    except (KeyError, InvalidOperation, TypeError, ValueError):
        return None

def _observation(row: dict, metric: str) -> dict | None:
    if metric == 'free_cash_flow':
        item = row.get('free_cash_flow')
        if item is None:
            fin = row.get('financials', {})
            a, b = _number(fin.get('operating_cash_flow')), _number(fin.get('capital_expenditures'))
            x, y = fin.get('operating_cash_flow', {}), fin.get('capital_expenditures', {})
            if a is not None and b is not None and x.get('period_end') == y.get('period_end') and x.get('period_start') == y.get('period_start'):
                item = {'status': 'calculated', 'value': str(a-b), 'inputs': {'operating_cash_flow': x, 'capital_expenditures': y}}
    else:
        item = row.get('financials', {}).get(metric)
    value = _number(item)
    if value is None:
        return None
    return {'period_end': row['period_end'], 'value': str(value),
            'provenance': item}

def _adjacent(a: str, b: str) -> bool:
    try:
        days = (date.fromisoformat(b) - date.fromisoformat(a)).days
        return 330 <= days <= 380
    except ValueError:
        return False

def _pct(new: Decimal, old: Decimal) -> str | None:
    return str((new-old)/abs(old)*100) if old != 0 else None

def _series(history: list[dict], metric: str) -> dict:
    observations = [o for row in history if (o := _observation(row, metric)) is not None]
    changes = []
    for left, right in zip(observations, observations[1:]):
        if not _adjacent(left['period_end'], right['period_end']):
            changes.append({'from': left['period_end'], 'to': right['period_end'], 'status': 'non_adjacent', 'percent': None})
            continue
        percent = _pct(Decimal(right['value']), Decimal(left['value']))
        changes.append({'from': left['period_end'], 'to': right['period_end'],
                        'status': 'calculated' if percent is not None else 'zero_baseline', 'percent': percent})
    cagr = None
    if len(observations) >= 3 and len(observations) == len(history) and len(changes) == len(history)-1 and all(x['status']=='calculated' for x in changes):
        first, last = Decimal(observations[0]['value']), Decimal(observations[-1]['value'])
        if first > 0 and last > 0:
            # Decimal power avoids floating-point conversion of financial inputs.
            cagr = str((((last / first) ** (Decimal(1) / Decimal(len(changes))) - 1) * 100).normalize())
    return {'observations': observations, 'year_over_year': changes,
            'cagr_percent': cagr, 'complete_years': len(observations),
            'trend_status': 'multi_year' if cagr is not None else 'insufficient_comparable_history'}

def analyze_history(report: dict, *, years: int = 5) -> dict:
    """Create an auditable history supplement. Missing values never become zero."""
    if not 2 <= years <= 20:
        raise ValueError('years must be between 2 and 20')
    history = report.get('financial_history', [])
    if not isinstance(history, list):
        raise TypeError('financial_history must be a list')
    history = sorted(history, key=lambda x: x['period_end'])[-years:]
    if len({r['period_end'] for r in history}) != len(history):
        raise ValueError('duplicate fiscal period_end')
    series = {metric: _series(history, metric) for metric in METRICS}
    return {'schema_version': '0.8.0', 'source': 'report.financial_history',
            'periods': [r['period_end'] for r in history], 'metrics': series,
            'limitations': ['CAGR requires at least three complete adjacent fiscal years and positive endpoints.',
                            'Nonadjacent fiscal years are never treated as consecutive.',
                            'SEC filing provenance and restatements are inherited from the supplied report.',
                            'Trends describe historical observations, not forecasts or investment recommendations.']}

def attach_history(analysis: dict, report: dict, *, years: int = 5) -> dict:
    """Non-mutating adapter; preserves all v0.7.3 keys and evaluations."""
    result = dict(analysis)
    result['historical_intelligence'] = analyze_history(report, years=years)
    return result
