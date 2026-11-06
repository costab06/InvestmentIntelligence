import json
from investment_intelligence.sec_disclosure_retrieval import retrieve_disclosures, normalize_block


def filing(tmp_path, suffix, blocks):
    path = tmp_path / f'{suffix}.json'
    path.write_text(json.dumps({'source': {'cik': 1045810, 'filing_type': '10-K',
        'filing_date': '2026-02-25', 'accession_number': f'0001045810-26-{suffix:06d}'},
        'document': {'blocks': blocks}}))
    return path


def task():
    return {'id': 'supplier', 'source': 'sec_filing_disclosures',
            'question': 'What are supplier manufacturing commitments?',
            'needed': 'Purchase obligations and supplier manufacturing agreements'}


def test_nonstandard_content_block(tmp_path):
    blocks = [{'type': 'section', 'content': 'Our supplier manufacturing commitments include significant purchase obligations for capacity and advanced packaging.'}]
    result = retrieve_disclosures([task()], [filing(tmp_path, 1, blocks)], cik=1045810, as_of='2026-11-03')
    assert result['tasks']['supplier']['hits']
    assert result['filing_diagnostics'][0]['block_type_counts'] == {'section': 1}
    assert result['tasks']['supplier']['hits'][0]['block_index'] == 0


def test_nested_structures(tmp_path):
    blocks = [{'type': 'table', 'rows': [{'cells': [{'text': 'Purchase obligations for suppliers and manufacturing commitments'}, {'value': '$5 billion over three years'}]}]}]
    result = retrieve_disclosures([task()], [filing(tmp_path, 2, blocks)], cik=1045810, as_of='2026-11-03')
    assert result['tasks']['supplier']['hits']
    assert '$5 billion' in result['tasks']['supplier']['hits'][0]['passage']


def test_metadata_does_not_become_narrative(tmp_path):
    blocks = [{'type': 'section', 'metadata': {'text': 'supplier manufacturing commitments purchase obligations'}, 'url': 'https://example.com'}]
    result = retrieve_disclosures([task()], [filing(tmp_path, 3, blocks)], cik=1045810, as_of='2026-11-03')
    assert result['tasks']['supplier']['status'] == 'no_lexical_match'
    assert result['filing_diagnostics'][0]['eligible_text_characters'] == 0


def test_does_not_claim_verified_entailment(tmp_path):
    blocks = [{'type': 'paragraph', 'text': 'Supplier manufacturing commitments and purchase obligations are discussed here but no amounts are provided.'}]
    result = retrieve_disclosures([task()], [filing(tmp_path, 4, blocks)], cik=1045810, as_of='2026-11-03')
    assert result['tasks']['supplier']['hits'][0]['entailment'] == 'not_evaluated'
    assert result['hypothesis_status_changed'] is False
