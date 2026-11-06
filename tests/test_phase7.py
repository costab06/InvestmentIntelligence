from investment_intelligence.investigation_registry import select_investigations
from investment_intelligence.industry_resolver import resolve_industry

def _analysis(capex=(10,30),ocf=(50,60),revenue=(100,130),net=(20,25),operating=(30,32)):
    d={'capital_expenditures':capex,'operating_cash_flow':ocf,'revenue':revenue,'net_income':net,'operating_income':operating}
    return {'historical_intelligence':{'metrics':{k:{'observations':[{'period_end':str(2024+i),'value':v[i]} for i in range(2)]} for k,v in d.items()}}}

def test_capital_trigger():
    r=select_investigations(_analysis())['investigations']
    assert r[0]['status']=='triggered'

def test_capital_not_triggered():
    r=select_investigations(_analysis(capex=(10,11),ocf=(50,80)))['investigations']
    assert r[0]['status']=='not_triggered'

def test_missing_metrics():
    assert select_investigations({})['investigations'][0]['status']=='insufficient_data'

def test_unmapped_company_does_not_inherit_msft(tmp_path):
    x=resolve_industry('NVDA',1045810,{'sic':'3674','sicDescription':'Semiconductors'},tmp_path)
    assert x['mapping_status']=='unmapped' and x['mapping'] is None

def test_reviewed_msft_mapping(tmp_path):
    (tmp_path/'msft-industry-mapping.json').write_text('{"ticker":"MSFT","industries":[]}')
    x=resolve_industry('MSFT',789019,{'sic':'7372'},tmp_path)
    assert x['mapping_status']=='mapped_proxy_not_comparable'
    y=resolve_industry('OTHER',123,{'sic':'7372'},tmp_path)
    assert y['mapping_status']=='requires_company_review'
