from investment_intelligence.historical_intelligence import analyze_history, attach_history
import pytest

def row(year, revenue=None, cash=None):
    def obs(v):
        return {'status': 'selected', 'value': str(v), 'period_end': f'{year}-06-30', 'period_start': f'{year-1}-07-01', 'accession': f'a{year}'} if v is not None else {'status': 'missing', 'value': None}
    return {'period_end': f'{year}-06-30', 'financials': {'revenue': obs(revenue), 'cash': obs(cash)}}

def test_three_year_cagr_and_provenance():
    out = analyze_history({'financial_history': [row(2022, 100), row(2023, 110), row(2024, 121)]})
    assert float(out['metrics']['revenue']['cagr_percent']) == 10.0
    assert out['metrics']['revenue']['observations'][0]['provenance']['accession'] == 'a2022'

def test_missing_year_does_not_invent_growth():
    out = analyze_history({'financial_history': [row(2022, 100), row(2023), row(2024, 120)]})
    s = out['metrics']['revenue']
    assert s['cagr_percent'] is None
    assert s['year_over_year'][0]['status'] == 'non_adjacent'

def test_zero_baseline():
    out = analyze_history({'financial_history': [row(2022, 0), row(2023, 100)]})
    assert out['metrics']['revenue']['year_over_year'][0]['status'] == 'zero_baseline'

def test_missing_not_zero():
    out = analyze_history({'financial_history': [row(2022), row(2023)]})
    assert out['metrics']['revenue']['observations'] == []

def test_duplicate_period_rejected():
    with pytest.raises(ValueError, match='duplicate'):
        analyze_history({'financial_history': [row(2022), row(2022)]})

def test_nonmutating_adapter():
    analysis = {'status': 'review_required', 'evaluations': [1]}
    new = attach_history(analysis, {'financial_history': [row(2022), row(2023)]})
    assert 'historical_intelligence' not in analysis
    assert new['evaluations'] == [1]

def test_negative_endpoint_disables_cagr():
    out = analyze_history({'financial_history': [row(2022, 100), row(2023, 10), row(2024, -10)]})
    assert out['metrics']['revenue']['cagr_percent'] is None

def test_years_bounds():
    with pytest.raises(ValueError):
        analyze_history({}, years=1)
