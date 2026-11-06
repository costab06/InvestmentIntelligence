"""Deterministic integration of MarketDataAgents output and SEC share-count facts."""
from datetime import date
from decimal import Decimal, InvalidOperation


def _positive(value):
    try:
        n = Decimal(str(value))
        return n if n.is_finite() and n > 0 else None
    except (InvalidOperation, TypeError, ValueError):
        return None


def select_share_count(facts, price_date, cutoff, max_age_days=120):
    """Use SEC DEI actual common shares outstanding; never EPS weighted-average shares."""
    units = (facts.get('facts', {}).get('dei', {})
             .get('EntityCommonStockSharesOutstanding', {}).get('units', {}).get('shares', []))
    candidates = []
    for e in units:
        try:
            end = date.fromisoformat(e['end'])
            filed = date.fromisoformat(e['filed'])
            age = (price_date - end).days
            count = _positive(e.get('val'))
            if count is not None and 0 <= age <= max_age_days and filed <= cutoff and end <= cutoff:
                candidates.append((end, filed, e.get('accn', ''), count, e))
        except (KeyError, ValueError, TypeError):
            continue
    if not candidates:
        return {'status': 'unavailable', 'reason': 'No SEC DEI common-share count within 120 days of the price date, filed by the report cutoff'}
    end, filed, accession, count, entry = max(candidates, key=lambda x: (x[0], x[1], x[2]))
    # Avoid silently resolving conflicting share classes or records at the same reporting date.
    peers = [x for x in candidates if x[0] == end and x[1] == filed]
    if len({x[3] for x in peers}) > 1:
        return {'status': 'unavailable', 'reason': 'Conflicting SEC common-share counts for selected reporting date'}
    return {'status': 'selected', 'value': str(count), 'date': end.isoformat(),
            'filed': filed.isoformat(), 'accession': accession,
            'concept': 'dei:EntityCommonStockSharesOutstanding', 'age_days': (price_date-end).days}


def attach_market(report, market, facts, symbol, max_price_age_days=7):
    """Enrich report in place; refuse symbol mismatches, stale prices and future observations."""
    if not symbol or market.get('symbol', '').upper() != symbol.upper():
        raise ValueError('MarketDataAgents symbol does not match --symbol')
    cutoff = date.fromisoformat(report['as_of'])
    rows = []
    for item in market.get('observations', []):
        try:
            day = date.fromisoformat(item['date'])
            price = _positive(item['close'])
            if day <= cutoff and price is not None:
                rows.append((day, price, item))
        except (KeyError, TypeError, ValueError):
            continue
    market_info = {'status': 'unavailable', 'symbol': symbol.upper(),
                   'source': market.get('source'), 'retrieved_at': market.get('retrieved_at'),
                   'price_basis': 'unadjusted close', 'requested_start': market.get('requested_start'),
                   'requested_end_exclusive': market.get('requested_end_exclusive')}
    valuation = {'status': 'unavailable', 'reason': 'No eligible price observation'}
    if rows:
        day, price, _ = max(rows, key=lambda x: x[0])
        age = (cutoff - day).days
        market_info.update({'price_date': day.isoformat(), 'close': str(price),
                            'currency': market.get('currency'), 'price_age_days': age})
        if age > max_price_age_days:
            valuation['reason'] = f'Latest market price is {age} days before report as-of date (maximum {max_price_age_days})'
        elif market.get('currency') != 'USD':
            valuation['reason'] = 'Only USD prices are supported for USD SEC fundamentals'
        else:
            market_info['status'] = 'selected'
            shares = select_share_count(facts, day, cutoff)
            market_info['shares_outstanding'] = shares
            if shares['status'] != 'selected':
                valuation['reason'] = shares['reason']
            else:
                cap = price * Decimal(shares['value'])
                valuation = {'status': 'calculated', 'market_cap_usd': str(cap),
                             'price_date': day.isoformat(), 'share_count_date': shares['date'],
                             'share_count_age_days': shares['age_days'],
                             'earnings_yield_percent': None, 'pe_ratio': None,
                             'fcf_yield_percent': None}
                income = report['financials'].get('net_income', {})
                if income.get('status') == 'selected':
                    ni = Decimal(income['value'])
                    valuation['earnings_yield_percent'] = str(ni / cap * 100)
                    if ni > 0:
                        valuation['pe_ratio'] = str(cap / ni)
                fcf = report.get('free_cash_flow', {})
                if fcf.get('status') == 'calculated':
                    valuation['fcf_yield_percent'] = str(Decimal(fcf['value']) / cap * 100)
    report['market_data'] = market_info
    report['valuation'] = valuation
    report['schema_version'] = '0.3'
    report['limitations'] = [x for x in report['limitations'] if 'no security valuation' not in x.lower()]
    report['limitations'].extend([
        'Market valuation uses unadjusted closing price and SEC DEI common shares outstanding; their observation dates may differ.',
        'Valuation multiples use latest available annual SEC earnings and cash flow, not trailing-twelve-month results.',
        'SEC share counts may be class-specific; multi-class issuers require further reconciliation.',
        'Yahoo Finance data is prototype-grade and has not been independently verified against a licensed provider.',
    ])
    return report


def markdown_market(report):
    if 'market_data' not in report:
        return ''
    m = report['market_data']
    v = report['valuation']
    def fmt_num(n, digits=2):
        return f'{Decimal(n):,.{digits}f}' if n is not None else 'unavailable'
    lines = ['## Market data and valuation', '',
             f"- Security: {m['symbol']}", f"- Provider: {m.get('source') or 'unknown'}",
             f"- Retrieved at: {m.get('retrieved_at') or 'unknown'}",
             f"- Closing price (unadjusted): {fmt_num(m.get('close'))} {m.get('currency') or ''} on {m.get('price_date', 'unavailable')}",
             f"- Price age at report date: {m.get('price_age_days', 'unavailable')} days"]
    shares = m.get('shares_outstanding', {})
    if shares.get('status') == 'selected':
        lines.append(f"- SEC shares outstanding: {fmt_num(shares['value'], 0)} as of {shares['date']} (filed {shares['filed']}; accession {shares['accession']})")
    if v['status'] == 'calculated':
        lines += [f"- Market capitalization: USD {fmt_num(v['market_cap_usd'], 0)}",
                  f"- P/E (latest fiscal-year earnings): {fmt_num(v['pe_ratio'])}",
                  f"- Earnings yield: {fmt_num(v['earnings_yield_percent'])}%",
                  f"- Free-cash-flow yield: {fmt_num(v['fcf_yield_percent'])}%"]
    else:
        lines.append(f"- Valuation unavailable: {v['reason']}")
    return '\n'.join(lines) + '\n\n'
