from investment_intelligence.sufficiency_gate import check_sufficiency, normalize_insufficient

F=[{'id':'F002','metric':'revenue','kind':'growth'}, {'id':'F014','metric':'cash','kind':'growth'}, {'id':'F021','metric':'free_cash_flow','kind':'growth'}, {'id':'F022','metric':'pe_ratio','kind':'level'}]
D=[{'id':'D0001','text':'Management described investments in datacenters.'}]
def proposal(ids, roles=None):
    return {'assessment':'supports','evidence_ids':ids,'evidence_roles':roles or {i:'establishes_fact' for i in ids}}
def stmt(text): return {'statement':{'text':text}}
def test_management_revenue_rejected():
    ok,why=check_sufficiency(stmt('Revenue increased'),'management_strategy',proposal(['F002']),F,D)
    assert not ok and 'document' in why
def test_cash_risk_rejected():
    ok,why=check_sufficiency(stmt('Cash decline may signal liquidity pressure'),'risk',proposal(['F014']),F,D)
    assert not ok and 'independent' in why
def test_fcf_sustainability_rejected():
    assert not check_sufficiency(stmt('FCF decline raises concerns about sustainability'),'risk',proposal(['F021']),F,D)[0]
def test_sustained_one_year_rejected():
    assert not check_sufficiency(stmt('Sustained net income growth'),'historical',proposal(['F002']),F,D)[0]
def test_ordinary_historical_fact_allowed():
    assert check_sufficiency(stmt('Recent revenue increased'),'historical',proposal(['F002']),F,D)[0]
def test_valuation_operating_metric_rejected():
    assert not check_sufficiency(stmt('Valuation looks attractive'),'valuation',proposal(['F002']),F,D)[0]
def test_valuation_metric_allowed():
    assert check_sufficiency(stmt('P/E ratio is reported'),'valuation',proposal(['F022']),F,D)[0]
def test_normalize_insufficient():
    p={'assessment':'insufficient_evidence','confidence':'high','evidence_ids':['F002'],'evidence_roles':{'F002':'establishes_fact'},'rationale':'Missing context'}
    n,changed=normalize_insufficient(p)
    assert changed and n['confidence'] is None and n['evidence_ids']==[] and n['evidence_roles']=={} and p['confidence']=='high'
def test_context_only_document_not_enough():
    assert not check_sufficiency(stmt('Management strategy'),'management_strategy',proposal(['D0001'],{'D0001':'context_only'}),F,D)[0]
