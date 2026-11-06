import json
from investment_intelligence.evidence_reconciliation import classify_passage, reconcile_history

def test_infrastructure_disclosure_is_relevant_not_causal_proof():
    d={'text':'We made significant capital expenditures expanding AI datacenters.'}
    assert classify_passage('capex_outpaces_ocf', d)=='direct'
    assert classify_passage('fcf_two_year_decline', d)=='context'

def test_acquisition_risk_is_not_fcf_explanation():
    assert classify_passage('fcf_two_year_decline', {'text':'Acquisitions and joint ventures involve risks.'})=='not_relevant'

def test_reconciliation_preserves_proposals_and_gates():
    analysis={'published_statements':[{'id':'S1'}], 'statement_evaluations':{'S1':{'status':'warning'}},
      'report_markdown':'# Report', 'document_evidence':[
      {'id':'D0051','text':'We made significant capital expenditures expanding AI datacenters.'},
      {'id':'D0059','text':'Acquisitions and joint ventures involve risks.'}],
      'historical_investigations':{'records':[{'signal_code':'fcf_two_year_decline','observation':'FCF declined',
      'retrieved_document_ids':['D0051','D0059'],'evidence_ids':['D0051','D0059'],
      'assessment':'context_found','management_explanation':'Acquisitions caused decline'}]}}
    before=json.dumps(analysis,sort_keys=True)
    result=reconcile_history(analysis)
    row=result['historical_reconciliation']['records'][0]
    assert row['evidence_status']=='context_only'
    assert row['unsupported_model_citation_ids']==['D0059']
    assert result['statement_evaluations']==analysis['statement_evaluations']
    assert result['historical_investigations']==analysis['historical_investigations']
    assert json.dumps(analysis,sort_keys=True)==before
    assert 'Not established' in result['report_markdown']

def test_missing_document_is_not_validated():
    a={'historical_investigations':{'records':[{'signal_code':'revenue_cagr','evidence_ids':['D999'], 'retrieved_document_ids':['D999']}]}}
    assert reconcile_history(a)['historical_reconciliation']['records'][0]['unsupported_model_citation_ids']==['D999']
