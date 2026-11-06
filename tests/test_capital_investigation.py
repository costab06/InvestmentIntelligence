from investment_intelligence.capital_investigation import investigate_capital, attach_capital_investigation

def make_analysis():
    vals = {'revenue':[100,120], 'operating_cash_flow':[30,40], 'capital_expenditures':[10,25]}
    return {'historical_intelligence': {'metrics': {k: {'observations': [
      {'period_end':f'{year}-06-30', 'value':str(v), 'provenance':{'form':'10-K'}}
      for year,v in zip([2025,2026],values)]} for k,values in vals.items()}}, 'report_markdown':'Prior report\n'}

def test_bridge_and_no_causality():
    x=investigate_capital(make_analysis())
    assert x['status']=='observations_verified_hypotheses_open'
    bridge=x['observations'][0]
    assert (bridge['delta_ocf_usd'],bridge['delta_capex_usd'],bridge['delta_fcf_usd'])==('10','15','-5')
    assert x['hypotheses'][0]['status']=='supported_for_observed_interval'
    assert all(h['causal_assessment']=='not_established' for h in x['hypotheses'])
    assert not x['publication_eligible']

def test_missing_history():
    assert investigate_capital({})['status']=='insufficient_evidence'

def test_output_is_additive():
    x=attach_capital_investigation(make_analysis())
    assert 'Prior report' in x['report_markdown']
    assert 'Capital Investment Economics' in x['report_markdown']
