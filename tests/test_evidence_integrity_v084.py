from investment_intelligence.evidence_integrity import enforce_evidence_integrity

def test_wrong_metric_is_rejected():
    a={'findings':[{'id':'F016','metric':'operating_income','kind':'margin'},{'id':'F015','metric':'net_income','kind':'margin'}],
       'qualitative_audit':[{'id':'S002','status':'warning','statement':{'text':'Operating cash flow margin exceeds net income margin','finding_ids':['F016','F015']}}],
       'published_statements':[{'id':'S002'}], 'statement_evaluations':[]}
    b=enforce_evidence_integrity(a)
    assert b['published_statements']==[]
    assert 'uncited_metric:operating_cash_flow' in b['evidence_integrity']['statements'][0]['issues']
    assert a['published_statements']

def test_sustained_requires_history():
    a={'findings':[{'id':'F002','metric':'revenue','kind':'growth'}], 'qualitative_audit':[{'id':'S001','status':'warning','statement':{'text':'Sustained revenue growth','finding_ids':['F002']}}], 'published_statements':[{'id':'S001'}]}
    b=enforce_evidence_integrity(a)
    assert 'S001' in b['evidence_integrity']['invalid_statement_ids']

def test_dimension_support_downgraded_pending_entailment():
    a={'findings':[], 'qualitative_audit':[], 'statement_evaluations':[{'statement_id':'S3','dimensions':{'competitive':{'assessment':'supports','confidence':'high','evidence_ids':['D0051']}}}]}
    b=enforce_evidence_integrity(a)
    v=b['statement_evaluations'][0]['dimensions']['competitive']
    assert v['assessment']=='insufficient_evidence' and v['original_assessment']=='supports'
    assert a['statement_evaluations'][0]['dimensions']['competitive']['assessment']=='supports'

def test_reconciled_evidence_stays_distinct():
    a={'findings':[], 'qualitative_audit':[], 'historical_reconciliation':{'records':[{'signal_code':'capex_outpaces_ocf','financial_evidence':['H1'],'direct_topic_passage_ids':['D0051'],'context_passage_ids':['D0079']}]}}
    b=enforce_evidence_integrity(a)
    assert b['historical_statement_evidence']['links'][0]['direct_topic_passage_ids']==['D0051']
    assert b['historical_statement_evidence']['links'][0]['status']=='context_only_not_claim_verified'
