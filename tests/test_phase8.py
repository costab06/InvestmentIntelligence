from investment_intelligence.earnings_quality import investigate_earnings_quality
from investment_intelligence.financial_diagnostics import diagnose_financial_coverage
from investment_intelligence.industry_sources import discover_industry_sources
from investment_intelligence.investigation_registry import select_investigations

def sample(**series):
    return {'historical_intelligence':{'metrics':{k:{'observations':[{'period_end':str(2024+i),'value':v[i],'provenance':{'source':'fixture'}} for i in range(2)]} for k,v in series.items()}}}

def test_earnings_investigation_and_alternatives():
    a=sample(net_income=(100,165),operating_cash_flow=(200,320),revenue=(1000,1500))
    x=investigate_earnings_quality(a)
    assert x['status']=='observations_verified_hypotheses_open'
    assert x['hypotheses'][0]['status']=='supported_for_observed_interval'
    assert x['hypotheses'][2]['status']=='not_established'
    assert x['publication_eligible'] is False

def test_missing_earnings():
    assert investigate_earnings_quality(sample(net_income=(100,200)))['status']=='insufficient_evidence'

def test_capex_diagnostics_specific():
    a=sample(net_income=(100,165),operating_cash_flow=(200,320),revenue=(1000,1500),operating_income=(200,300))
    reg=select_investigations(a)
    x=diagnose_financial_coverage(a,reg)
    assert x['records'][0]['investigation']=='capital_investment_economics'
    assert x['records'][0]['metrics']['capital_expenditures']['observation_count']==0

def test_semiconductor_source_candidates_not_fabricated_retrieval():
    x=discover_industry_sources({'ticker':'NVDA','sic':'3674'})
    assert x['status']=='candidates_found_review_required'
    assert len(x['candidates'])==3
    assert x['retrieval_performed'] is False
    assert all(c['status']=='candidate_requires_series_review' for c in x['candidates'])

def test_unknown_industry():
    assert discover_industry_sources({'ticker':'X','sic':'0000'})['status']=='no_reviewed_candidates'
