import asyncio
import json
import pytest
from investment_intelligence.sec_narrative import import_sec_parsed, enrich_analysis

def test_import_requires_date(tmp_path):
    p=tmp_path/'parsed.json'
    p.write_text(json.dumps({'source':{'cik':'1','accession_number':'123','filing_type':'10-K'},
      'document':{'blocks':[{'type':'paragraph','text':'Capital expenditures and cash flow '+ 'investment '*12}]}}))
    with pytest.raises(ValueError,match='filing date'):import_sec_parsed([p],{})
    docs=import_sec_parsed([p],{'123':'2026-07-30'})
    assert docs[0]['source_location']=='block:0'
    assert docs[0]['published_at']=='2026-07-30'
    assert docs[0]['source_document']=='1:123'

def test_empty_evidence():
    assert import_sec_parsed([], {})==[]

def test_rejected_statements_not_reassessed():
    class Client:
        async def complete(self,*a):raise AssertionError('should not call LLM')
    obj={'schema_version':'0.6.0','status':'review_required','findings':[], 'qualitative_audit':[{'id':'S001','status':'rejected',
      'statement':{'text':'Unsupported','finding_ids':[]}}], 'coverage':{k:[] for k in ('growth','profitability','cash_generation','balance_sheet','valuation')},'published_statements':[],
      'limitations':[],'framework':{'id':'investment_statement_evaluation','version':'1.0','sha256':'x'}}
    result=asyncio.run(enrich_analysis(obj,[],Client()))
    assert all(v['assessment']=='insufficient_evidence' for v in result['statement_evaluations'][0]['dimensions'].values())
