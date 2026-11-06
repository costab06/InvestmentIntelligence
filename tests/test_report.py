from investment_intelligence.report import build_report, markdown


def test_missing_facts_explicit():
    result = build_report({'entityName': 'Test', 'facts': {}}, 123, '2026-10-22')
    assert result['financials']['revenue']['status'] == 'missing'
    assert result['ratios_percent']['operating_margin'] is None
    assert 'not_available' == result['modules']['factor_analysis']
    assert '# Investment Intelligence Report' in markdown(result)


def test_no_mismatched_period_margin():
    def entry(tag, start, end, value):
        return {tag: {'units': {'USD': [{'form': '10-K', 'fp': 'FY', 'fy': 2025,
                  'start': start, 'end': end, 'filed': '2025-08-01',
                  'accn': '0000000000-25-000001', 'val': value}]}}}
    facts = {'facts': {'us-gaap': {
        **entry('Revenues', '2024-07-01', '2025-06-30', 100),
        **entry('OperatingIncomeLoss', '2024-01-01', '2024-12-31', 30),
    }}}
    assert build_report(facts, 123, '2026-10-22')['ratios_percent']['operating_margin'] is None


def test_as_of_excludes_future_filing():
    facts = {'facts': {'us-gaap': {'Revenues': {'units': {'USD': [
        {'form': '10-K', 'fp': 'FY', 'fy': 2025, 'start': '2024-01-01',
         'end': '2024-12-31', 'filed': '2026-12-01',
         'accn': '0000000000-26-000001', 'val': 100}]}}}}}
    assert build_report(facts, 123, '2026-10-22')['financials']['revenue']['status'] == 'missing'
