from investment_intelligence.evidence_quality import build_evidence_quality, analyze_cash_conversion_periods


def test_table_only_warning_does_not_claim_raw_comparison():
    d = {'filing_diagnostics': [{'accession':'x','total_blocks':64,'block_type_counts':{'table':64}}], 'tasks':{}}
    out = build_evidence_quality(d, {'tasks':[]}, {})
    assert out['coverage'][0]['structural_status'] == 'table_only_suspicious'
    assert out['coverage'][0]['raw_vs_parsed_coverage'] is None
    assert out['publication_eligible'] is False


def test_mixed_blocks_no_structural_warning():
    d = {'filing_diagnostics': [{'accession':'x','total_blocks':4,'block_type_counts':{'table':1,'paragraph':3}}], 'tasks':{}}
    assert build_evidence_quality(d, {'tasks':[]}, {})['coverage'][0]['table_only'] is False


def test_generic_balance_sheet_not_promoted():
    d = {'tasks':{'q':{'status':'candidate_passages_retrieved','hits':[{'passage':'Inventory and cash. Total assets. Current liabilities.', 'passage_truncated':False}]}}}
    o = {'tasks':[{'id':'q','question':'Does inventory affect cash conversion?','needed':'Inventory balances and cash flows'}]}
    out = build_evidence_quality(d,o,{})
    assert out['candidate_triage']['q']['candidates'][0]['grade']=='context_only'
    assert out['candidate_triage']['q']['question_answered']=='not_evaluated'


def test_specific_candidate_remains_unverified():
    d = {'tasks':{'q':{'status':'candidate_passages_retrieved','hits':[{'passage':'Finance lease cash paid for operating leases was reported.', 'passage_truncated':False}]}}}
    o = {'tasks':[{'id':'q','question':'How do finance leases affect cash flow?','needed':'Lease cash payments'}]}
    c = build_evidence_quality(d,o,{})['candidate_triage']['q']['candidates'][0]
    assert c['grade']=='specific_candidate_unverified'


def test_historical_route_is_not_causal_claim():
    cf = {'periods':[{'period_end':str(2020+i)+'-12-31','net_income_usd':'100','operating_cash_flow_usd':str(100+i*10)} for i in range(3)]}
    o = {'tasks':[{'id':'eq','question':'Is the gap temporary or persistent?'}]}
    out = build_evidence_quality({'tasks':{}},o,cf)
    assert out['temporal_task_routes'][0]['route']=='structured_cash_flow_history'
    assert out['cash_conversion_history']['period_count']==3
    assert out['cash_conversion_history']['persistence_conclusion']=='not_established'


def test_missing_periods_abstain():
    assert analyze_cash_conversion_periods({'periods':[]})['status']=='insufficient_periods'
