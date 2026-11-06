from copy import deepcopy
from investment_intelligence.historical_integration import integrate_history

def fixture():
    years = ['2022-06-30','2023-06-30','2024-06-30','2025-06-30','2026-06-30']
    rev = [100,110,125,140,160]
    ocf = [60,65,75,90,100]
    capex = [10,20,35,60,80]
    history=[]
    for i, period in enumerate(years):
        history.append({'period_end':period,'financials': {
            k:{'status':'selected','value':str(v),'period_end':period,'period_start':f'{2021+i}-07-01'}
            for k,v in [('revenue',rev[i]),('operating_cash_flow',ocf[i]),('capital_expenditures',capex[i])]}})
    return {'financial_history':history}

def test_integrates_without_mutating_or_overwriting_assessments():
    original={'schema_version':'0.6.0','statement_evaluations':[{'a':1}], 'report_markdown':'Existing report'}
    before=deepcopy(original)
    out=integrate_history(original,fixture())
    assert original==before
    assert out['statement_evaluations']==before['statement_evaluations']
    assert 'Existing report' in out['report_markdown']
    assert out['historical_intelligence']['periods'][-1]=='2026-06-30'
    assert out['historical_dimension_signals']['dimension_coverage']['risk']
    assert out['historical_dimension_signals']['dimension_coverage']['competitive']==[]
    assert all(s['investment_assessment']=='not_assessed' for s in out['historical_dimension_signals']['signals'])

def test_no_history_no_fabricated_signals():
    out=integrate_history({}, {'financial_history':[]})
    assert out['historical_dimension_signals']['signals']==[]
    assert len(out['historical_dimension_signals']['dimension_coverage'])==12

def test_fcf_decline_requires_two_adjacent_years():
    report=fixture()
    out=integrate_history({},report)
    codes={s['code'] for s in out['historical_dimension_signals']['signals']}
    assert 'fcf_two_year_decline' in codes
    report['financial_history'][3]['period_end']='2024-12-31'
    out=integrate_history({},report)
    codes={s['code'] for s in out['historical_dimension_signals']['signals']}
    assert 'fcf_two_year_decline' not in codes
