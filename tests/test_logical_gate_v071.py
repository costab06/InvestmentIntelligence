from investment_intelligence.logical_gate import check_proposal

STMT={'id':'S001','statement':{'text':'Revenue increased','finding_ids':['F002']}}
FINDINGS=[{'id':'F002','metric':'revenue','kind':'growth','value':'17.8'}]
DOCS=[{'id':'D0056','text':'Future capacity constraints could adversely affect revenue.'},
      {'id':'D0100','text':'Revenue declined during the current reporting period.'}]

def test_future_risk_cannot_contradict_observed_growth():
    ok, reason=check_proposal(STMT,'operational',{'assessment':'contradicts','evidence_ids':['F002','D0056']},FINDINGS,DOCS)
    assert not ok and reason=='future_risk_does_not_contradict_historical_fact'

def test_future_risk_can_still_be_relevant_as_risk():
    ok,_=check_proposal(STMT,'risk',{'assessment':'mixed','evidence_ids':['F002','D0056']},FINDINGS,DOCS)
    assert ok

def test_insufficient_is_allowed():
    ok,_=check_proposal(STMT,'industry',{'assessment':'insufficient_evidence','evidence_ids':[]},FINDINGS,DOCS)
    assert ok

def test_no_citations_rejected():
    ok,reason=check_proposal(STMT,'valuation',{'assessment':'supports','evidence_ids':[]},FINDINGS,DOCS)
    assert not ok and reason=='no_cited_evidence'
