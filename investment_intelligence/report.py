"""Auditable annual financial report from SEC Company Facts."""
from __future__ import annotations
import argparse
import asyncio
import json
from datetime import date
from decimal import Decimal
from pathlib import Path

from secagent.clients.edgar import EdgarClient

CONCEPTS = {
    'revenue': ('RevenueFromContractWithCustomerExcludingAssessedTax', 'Revenues', 'SalesRevenueNet'),
    'net_income': ('NetIncomeLoss',),
    'operating_income': ('OperatingIncomeLoss',),
    'operating_cash_flow': ('NetCashProvidedByUsedInOperatingActivities',),
    'assets': ('Assets',),
    'cash': ('CashAndCashEquivalentsAtCarryingValue',),
    'capital_expenditures': ('PaymentsToAcquirePropertyPlantAndEquipment', 'PaymentsToAcquireProductiveAssets'),
}
INSTANT = {'assets', 'cash'}


def _candidates(companyfacts: dict, metric: str, cutoff: date) -> list[tuple[str, dict]]:
    """Only full-year 10-K facts filed by cutoff; preserve all candidate provenance."""
    facts = companyfacts.get('facts', {}).get('us-gaap', {})
    selected = []
    for tag in CONCEPTS[metric]:
        for entry in facts.get(tag, {}).get('units', {}).get('USD', []):
            if entry.get('form') != '10-K' or entry.get('fp') != 'FY':
                continue
            if not entry.get('filed') or entry['filed'] > cutoff.isoformat():
                continue
            if not entry.get('end') or not entry.get('accn') or entry.get('val') is None:
                continue
            if metric not in INSTANT:
                if not entry.get('start'):
                    continue
                duration = (date.fromisoformat(entry['end']) - date.fromisoformat(entry['start'])).days
                if not 330 <= duration <= 380:
                    continue
            selected.append((tag, entry))
    return selected


def _select_for_period(candidates: list[tuple[str, dict]], metric: str, end: str) -> dict:
    matches = [(tag, e) for tag, e in candidates if e['end'] == end]
    if not matches:
        return {'status': 'missing', 'value': None, 'period_end': end}
    # The most recent filing wins, including restatements, but conflicting facts
    # from that filing must not be silently resolved.
    filed = max(e['filed'] for _, e in matches)
    matches = [(tag, e) for tag, e in matches if e['filed'] == filed]
    values = {Decimal(str(e['val'])) for _, e in matches}
    if metric == 'capital_expenditures' and len({tag for tag, _ in matches}) > 1:
        return {'status':'ambiguous', 'value':None, 'period_end':end, 'reason':'multiple_capex_definitions_in_same_filing', 'filing_date':filed}
    if len(values) != 1:
        return {'status': 'ambiguous', 'value': None, 'period_end': end,
                'filing_date': filed, 'candidate_count': len(matches)}
    tag, entry = sorted(matches, key=lambda x: CONCEPTS[metric].index(x[0]))[0]
    return {
        'status': 'selected', 'value': str(next(iter(values))), 'unit': 'USD',
        'concept': f'us-gaap:{tag}', 'period_start': entry.get('start'),
        'period_end': entry['end'], 'filing_date': entry['filed'],
        'accession': entry['accn'], 'form': entry['form'],
        'measure_definition': ('productive_assets_including_intangibles' if metric == 'capital_expenditures' and tag == 'PaymentsToAcquireProductiveAssets' else 'property_plant_equipment_only' if metric == 'capital_expenditures' else None),
    }


def financial_history(companyfacts: dict, as_of: str | None = None, years: int = 5) -> list[dict]:
    """Latest fiscal years anchored on annual revenue; ascending chronological order."""
    cutoff = date.fromisoformat(as_of) if as_of else date.today()
    cache = {metric: _candidates(companyfacts, metric, cutoff) for metric in CONCEPTS}
    periods = sorted({e['end'] for _, e in cache['revenue']}, reverse=True)[:years]
    history = []
    for end in reversed(periods):
        financials = {metric: _select_for_period(cache[metric], metric, end)
                      for metric in CONCEPTS}
        margins = {
            'operating_margin': ratio(financials['operating_income'], financials['revenue']),
            'net_margin': ratio(financials['net_income'], financials['revenue']),
        }
        fcf = difference(financials['operating_cash_flow'], financials['capital_expenditures'])
        history.append({'period_end': end, 'financials': financials,
                        'ratios_percent': margins, 'free_cash_flow': fcf,
                        'growth_percent': {}})
    for previous, current in zip(history, history[1:]):
        for metric in ('revenue', 'net_income', 'operating_income', 'operating_cash_flow'):
            old = previous['financials'][metric]
            new = current['financials'][metric]
            # Require comparable, adjacent fiscal years, not an arbitrary gap.
            adjacent = 330 <= (date.fromisoformat(current['period_end']) -
                                date.fromisoformat(previous['period_end'])).days <= 380
            current['growth_percent'][metric] = growth(new, old) if adjacent else None
    return history


def annual_facts(companyfacts: dict, as_of: str | None = None) -> dict:
    history = financial_history(companyfacts, as_of, years=1)
    return history[-1]['financials'] if history else {
        metric: {'status': 'missing', 'value': None} for metric in CONCEPTS
    }


def difference(a: dict, b: dict) -> dict:
    if a['status'] != 'selected' or b['status'] != 'selected':
        return {'status': 'unavailable', 'value': None}
    if a.get('period_start') != b.get('period_start') or a['period_end'] != b['period_end']:
        return {'status': 'period_mismatch', 'value': None}
    return {'status': 'calculated', 'value': str(Decimal(a['value']) - Decimal(b['value'])),
            'period_start': a['period_start'], 'period_end': a['period_end'],
            'inputs': {'operating_cash_flow': a, 'capital_expenditures': b}}


def growth(new: dict, old: dict) -> str | None:
    if new['status'] != 'selected' or old['status'] != 'selected':
        return None
    base = Decimal(old['value'])
    if base <= 0:
        return None  # Percentage growth is not meaningful with zero/negative base.
    return str(((Decimal(new['value']) / base - 1) * 100).quantize(Decimal('0.01')))


def ratio(a: dict, b: dict) -> str | None:
    if a['status'] != 'selected' or b['status'] != 'selected':
        return None
    # Ratios require the same period, not just independently latest metrics.
    if a.get('period_start') != b.get('period_start') or a['period_end'] != b['period_end']:
        return None
    denom = Decimal(b['value'])
    return str((Decimal(a['value']) / denom * 100).quantize(Decimal('0.01'))) if denom else None


def build_report(companyfacts: dict, cik: int, as_of: str | None = None) -> dict:
    history = financial_history(companyfacts, as_of)
    metrics = history[-1]['financials'] if history else annual_facts(companyfacts, as_of)
    return {
        'schema_version': '0.2', 'report_type': 'Investment Intelligence Report',
        'entity': {'name': companyfacts.get('entityName'), 'cik': f'{cik:010d}'},
        'as_of': as_of or date.today().isoformat(),
        'source': f'https://data.sec.gov/api/xbrl/companyfacts/CIK{cik:010d}.json',
        'financials': metrics,
        'financial_history': history,
        'free_cash_flow': history[-1]['free_cash_flow'] if history else {'status': 'unavailable', 'value': None},
        'ratios_percent': {
            'operating_margin': ratio(metrics['operating_income'], metrics['revenue']),
            'net_margin': ratio(metrics['net_income'], metrics['revenue']),
        },
        'modules': {'factor_analysis': 'not_available', 'debt_analysis': 'not_available',
                    'macro_analysis': 'not_available'},
        'limitations': ['Annual 10-K facts only; no security valuation or investment recommendation.',
                        'Historical facts may reflect subsequent restatements; each observation records its supplying filing.',
                        'Year-over-year growth requires adjacent fiscal years and a positive prior-year value.',
                        'Fiscal periods and amendments are not assumed interchangeable.',
                        'Ratios omitted when numerator and denominator periods differ.'],
    }


def markdown(report: dict) -> str:
    entity = report['entity']
    lines = [f"# {report['report_type']}", '', f"**Company:** {entity['name'] or 'Unknown'}",
             f"**CIK:** {entity['cik']}", f"**As of:** {report['as_of']}", '',
             '## Annual reported financials', '', '| Metric | USD | Period end | Filing | Status |',
             '|---|---:|---|---|---|']
    for name, item in report['financials'].items():
        value = f"{int(Decimal(item['value'])):,}" if item.get('value') is not None else '—'
        accession = item.get('accession', '—')
        lines.append(f"| {name.replace('_', ' ').title()} | {value} | {item.get('period_end', '—')} | {accession} | {item['status']} |")
    lines += ['', '## Five-year financial history', '',
              '| Fiscal year end | Revenue (USD B) | Revenue YoY | Operating margin | Net margin | Operating cash flow (USD B) | Capex (USD B) | Free cash flow (USD B) |',
              '|---|---:|---:|---:|---:|---:|---:|---:|']
    def billions(item):
        if not item or item.get('value') is None:
            return '—'
        return f"{Decimal(item['value']) / Decimal(1000000000):,.2f}"
    def pct(value):
        return f"{value}%" if value is not None else '—'
    for year in report.get('financial_history', []):
        f = year['financials']
        r = year['ratios_percent']
        lines.append(
            f"| {year['period_end']} | {billions(f['revenue'])} | "
            f"{pct(year['growth_percent'].get('revenue'))} | "
            f"{pct(r['operating_margin'])} | {pct(r['net_margin'])} | "
            f"{billions(f['operating_cash_flow'])} | {billions(f['capital_expenditures'])} | "
            f"{billions(year['free_cash_flow'])} |"
        )
    lines += ['', 'Growth and cash-flow calculations are omitted when required facts are missing or periods differ.', '']
    lines += ['', '## Margins', '']
    for name, value in report['ratios_percent'].items():
        lines.append(f"- {name.replace('_', ' ').title()}: {value + '%' if value is not None else 'unavailable'}")
    lines += ['', '## Additional analysis', '', 'Factor, debt, and macroeconomic analysis: not yet available.',
              '', '## Source and limitations', '', f"SEC Company Facts: {report['source']}"]
    lines.extend(f'- {item}' for item in report['limitations'])
    return '\n'.join(lines) + '\n'


async def fetch(cik: int, user_agent: str) -> dict:
    async with EdgarClient(user_agent=user_agent) as client:
        response = await client._get(f'https://data.sec.gov/api/xbrl/companyfacts/CIK{cik:010d}.json')
        return response.json()


async def main_async(args):
    facts = json.loads(Path(args.companyfacts).read_text()) if args.companyfacts else await fetch(args.cik, args.user_agent)
    report = build_report(facts, args.cik, args.as_of)
    if args.market_data:
        from .market import attach_market
        market = json.loads(Path(args.market_data).read_text())
        attach_market(report, market, facts, args.symbol)
    dest = Path(args.output)
    dest.mkdir(parents=True, exist_ok=True)
    (dest / 'report.json').write_text(json.dumps(report, indent=2) + '\n')
    rendered = markdown(report)
    if args.market_data:
        from .market import markdown_market
        rendered = rendered.replace('## Source and limitations', markdown_market(report) + '## Source and limitations')
    (dest / 'report.md').write_text(rendered)
    print(dest / 'report.md')


def main():
    parser = argparse.ArgumentParser(description='Generate an SEC-based Investment Intelligence Report')
    parser.add_argument('--cik', type=int, required=True)
    parser.add_argument('--user-agent', help='Identifying SEC User-Agent, required for live fetch')
    parser.add_argument('--companyfacts', help='Offline SEC Company Facts JSON fixture')
    parser.add_argument('--as-of', help='Filing cutoff date YYYY-MM-DD')
    parser.add_argument('--output', default='reports/company')
    parser.add_argument('--market-data', help='MarketDataAgents market_data.json output')
    parser.add_argument('--symbol', help='Expected security ticker; required with --market-data')
    args = parser.parse_args()
    if args.market_data and not args.symbol:
        parser.error('--symbol is required with --market-data')
    if args.cik <= 0:
        parser.error('--cik must be positive')
    if not args.companyfacts and not args.user_agent:
        parser.error('--user-agent is required for live SEC fetch')
    asyncio.run(main_async(args))


if __name__ == '__main__':
    main()
