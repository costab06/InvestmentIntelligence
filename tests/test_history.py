from investment_intelligence.report import build_report, markdown


def fixture():
    tags = {'Revenues': [], 'OperatingIncomeLoss': [], 'NetIncomeLoss': [],
            'NetCashProvidedByUsedInOperatingActivities': [],
            'PaymentsToAcquirePropertyPlantAndEquipment': []}
    for year in range(2022, 2027):
        start, end = f'{year-1}-07-01', f'{year}-06-30'
        for tag, val in [('Revenues', year * 10), ('OperatingIncomeLoss', year * 3),
                         ('NetIncomeLoss', year * 2),
                         ('NetCashProvidedByUsedInOperatingActivities', year * 4),
                         ('PaymentsToAcquirePropertyPlantAndEquipment', year)]:
            tags[tag].append(dict(form='10-K', fp='FY', fy=year, start=start, end=end,
                                  filed=f'{year}-08-01', accn=f'{year}-original', val=val))
    return {'entityName': 'Example', 'facts': {'us-gaap': {
        tag: {'units': {'USD': entries}} for tag, entries in tags.items()}}}


def test_five_years_growth_fcf_and_markdown():
    report = build_report(fixture(), 123, '2026-10-22')
    history = report['financial_history']
    assert len(history) == 5
    assert [x['period_end'] for x in history] == [f'{y}-06-30' for y in range(2022, 2027)]
    assert history[0]['growth_percent'] == {}
    assert history[-1]['growth_percent']['revenue'] == '0.05'
    assert history[-1]['free_cash_flow']['value'] == str(2026 * 3)
    assert history[-1]['free_cash_flow']['inputs']['capital_expenditures']['accession'] == '2026-original'
    assert 'Five-year financial history' in markdown(report)


def test_restated_year_and_cutoff():
    facts = fixture()
    rows = facts['facts']['us-gaap']['Revenues']['units']['USD']
    rows.append({**rows[2], 'filed': '2026-09-01', 'accn': 'restated', 'val': 9999})
    current = build_report(facts, 123, '2026-10-22')['financial_history'][2]['financials']['revenue']
    earlier = build_report(facts, 123, '2026-08-01')['financial_history'][2]['financials']['revenue']
    assert current['accession'] == 'restated'
    assert earlier['accession'] == '2024-original'


def test_missing_capex_does_not_invent_fcf():
    facts = fixture()
    del facts['facts']['us-gaap']['PaymentsToAcquirePropertyPlantAndEquipment']
    report = build_report(facts, 123, '2026-10-22')
    assert report['free_cash_flow']['status'] == 'unavailable'
    assert report['free_cash_flow']['value'] is None
