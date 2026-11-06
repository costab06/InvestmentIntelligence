import json
from pathlib import Path
from investment_intelligence.sec_disclosure_retrieval import retrieve_disclosures, attach_disclosure_results


def make_filing(tmp_path, cik=1045810, date='2026-02-25'):
    p=tmp_path/'parsed.json'
    p.write_text(json.dumps({'source':{'cik':cik,'filing_type':'10-K','filing_date':date,
                        'accession_number':'0001045810-26-000021'},
            'document':{'blocks':[{'type':'paragraph','text':
              'We have significant purchase obligations and manufacturing agreements with suppliers. '
              'Our manufacturing capacity commitments may change with expected customer demand.'},
              {'type':'paragraph','text':'This is an unrelated paragraph describing the corporate office location and governance arrangements.'}]}}))
    return p


def task():
    return {'id':'cap:question:1','source':'sec_filing_disclosures',
            'question':'What supplier manufacturing commitments are disclosed?',
            'needed':'Purchase obligations and supplier agreements'}


def test_passage_provenance_and_unverified(tmp_path):
    p=make_filing(tmp_path)
    result=retrieve_disclosures([task()],[p],cik=1045810,as_of='2026-11-02')
    t=result['tasks'][task()['id']]
    assert t['status']=='candidate_passages_retrieved'
    assert t['hits'][0]['source_location']=='block:0'
    assert t['hits'][0]['entailment']=='not_evaluated'
    assert t['hits'][0]['source_sha256']==result['filings_searched'][0]['source_sha256']
    assert result['publication_eligible'] is False


def test_wrong_company_rejected(tmp_path):
    p=make_filing(tmp_path)
    result=retrieve_disclosures([task()],[p],cik=789019,as_of='2026-11-02')
    assert not result['filings_searched']
    assert result['filing_errors']
    assert result['tasks'][task()['id']]['status']=='retrieval_incomplete'


def test_future_filing_rejected(tmp_path):
    p=make_filing(tmp_path,date='2026-12-01')
    result=retrieve_disclosures([task()],[p],cik=1045810,as_of='2026-11-02')
    assert result['tasks'][task()['id']]['attempted'] is False


def test_no_match_not_supported(tmp_path):
    p=make_filing(tmp_path)
    t={'id':'x','source':'sec_filing_disclosures','question':'quantum tunneling lithium battery chemistry'}
    result=retrieve_disclosures([t],[p],cik=1045810,as_of='2026-11-02')
    assert result['tasks']['x']['status']=='no_lexical_match'


def test_attached_task_preserves_no_causal_promotion(tmp_path):
    p=make_filing(tmp_path)
    evidence=retrieve_disclosures([task()],[p],cik=1045810,as_of='2026-11-02')
    o={'tasks':[dict(task(),status='not_attempted',attempted=False,evidence_refs=[])], 'summary':{}}
    updated=attach_disclosure_results(o,evidence)
    assert updated['summary']['candidate_passages_retrieved']==1
    assert updated['tasks'][0]['attempted']
    assert 'candidate' in updated['tasks'][0]['status']
    assert evidence['hypothesis_status_changed'] is False
