import json
from investment_intelligence.sec_disclosure_retrieval import retrieve_disclosures


def filing(tmp_path, suffix, blocks):
    path = tmp_path / f'{suffix}.json'
    path.write_text(json.dumps({'source': {'cik': 1045810, 'filing_type': '10-K',
        'filing_date': '2026-02-25', 'accession_number': f'0001045810-26-{suffix:06d}'},
        'document': {'blocks': blocks}}))
    return path


def test_two_thin_filings_cannot_support_negative_search(tmp_path):
    b = [{'type': 'paragraph', 'text': 'Unrelated governance statement describing administrative procedures and corporate office locations.'}]
    paths = [filing(tmp_path, n, b) for n in (1, 2)]
    t = {'id':'x','source':'sec_filing_disclosures','question':'supplier commitments manufacturing inventory'}
    result = retrieve_disclosures([t], paths, cik=1045810, as_of='2026-11-02')
    assert result['tasks']['x']['status'] == 'retrieval_incomplete'
    assert len(result['filing_diagnostics']) == 2
    assert all(d['coverage_status'] == 'suspect_incomplete' for d in result['filing_diagnostics'])


def test_heading_not_answer(tmp_path):
    b = [{'type':'paragraph', 'text':'Supplemental cash flow information related to leases was as follows:'}]
    t = {'id':'x','source':'sec_filing_disclosures','question':'How do lease cash flows affect free cash flow?', 'needed':'Lease cash flow disclosures'}
    result = retrieve_disclosures([t], [filing(tmp_path, 1, b)], cik=1045810, as_of='2026-11-02', min_score=1)
    assert result['tasks']['x']['hits'][0]['relevance'] == 'incomplete_table_reference'
    assert result['tasks']['x']['hits'][0]['entailment'] == 'not_evaluated'
