from investment_intelligence.market import attach_market


def facts(shares=100, end='2026-09-15', filed='2026-09-20'):
    return {'facts': {'dei': {'EntityCommonStockSharesOutstanding': {'units': {'shares': [
        {'val': shares, 'end': end, 'filed': filed, 'accn': 'x'}]}}}}}


def report():
    return {'as_of': '2026-10-01', 'financials': {'net_income': {'status': 'selected', 'value': '500'}},
            'free_cash_flow': {'status': 'calculated', 'value': '250'},
            'limitations': ['Annual 10-K facts only; no security valuation or investment recommendation.']}


def market(symbol='MSFT', date='2026-09-30', close='10'):
    return {'symbol': symbol, 'currency': 'USD', 'observations': [{'date': date, 'close': close}]}


def test_valuation():
    r = attach_market(report(), market(), facts(), 'MSFT')
    assert r['valuation']['market_cap_usd'] == '1000'
    assert r['valuation']['pe_ratio'] == '2'
    assert r['valuation']['fcf_yield_percent'] == '25.00'
    assert r['schema_version'] == '0.3'


def test_stale_share_count():
    r = attach_market(report(), market(), facts(end='2026-01-01'), 'MSFT')
    assert r['valuation']['status'] == 'unavailable'


def test_stale_price():
    r = attach_market(report(), market(date='2026-09-01'), facts(), 'MSFT')
    assert r['valuation']['status'] == 'unavailable'


def test_future_price_excluded():
    r = attach_market(report(), market(date='2026-10-02'), facts(), 'MSFT')
    assert r['valuation']['status'] == 'unavailable'


def test_symbol_mismatch():
    import pytest
    with pytest.raises(ValueError, match='symbol'):
        attach_market(report(), market(), facts(), 'AAPL')


def test_future_filing_excluded():
    r = attach_market(report(), market(), facts(filed='2026-10-10'), 'MSFT')
    assert r['valuation']['status'] == 'unavailable'
