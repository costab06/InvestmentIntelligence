from investment_intelligence.claim_validation import check_evidence_roles, validate_decomposition

F = [{'id':'F017','metric':'operating_cash_flow'}, {'id':'F022','metric':'pe_ratio'}]

def test_operating_cash_flow_not_valuation():
    p={'assessment':'supports','evidence_ids':['F017'],'evidence_roles':{'F017':'establishes_fact'}}
    assert check_evidence_roles('valuation',p,F,[])[0] is False

def test_valuation_metric_allowed():
    p={'assessment':'supports','evidence_ids':['F022'],'evidence_roles':{'F022':'establishes_fact'}}
    assert check_evidence_roles('valuation',p,F,[])[0] is True

def test_context_is_not_support():
    p={'assessment':'supports','evidence_ids':['F017'],'evidence_roles':{'F017':'context_only'}}
    assert check_evidence_roles('financial',p,F,[])[0] is False

def test_claim_types():
    data={'claims':[{'text':'Cash declined','type':'observed_fact','evidence_ids':['F014']},
                    {'text':'Liquidity may weaken','type':'interpretation','evidence_ids':[]}]}
    assert len(validate_decomposition(data,{}, {'F014'})) == 2

def test_fact_requires_evidence():
    try:
        validate_decomposition({'claims':[{'text':'Cash declined','type':'observed_fact','evidence_ids':[]}]},{},set())
    except ValueError:
        return
    assert False
