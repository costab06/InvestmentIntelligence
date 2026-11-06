from investment_intelligence.evidence_retrieval import retrieve


def test_relevant_passage_preferred():
    docs = [
        {'id': 'D0001', 'text': 'The company maintains several facilities and offices.'},
        {'id': 'D0002', 'text': 'Cash flow from operations increased while capital expenditures rose.'},
    ]
    result = retrieve('Operating cash flow increased', 'financial', docs)
    assert result[0]['id'] == 'D0002'


def test_empty_and_stable():
    docs = [{'id': 'D0001', 'text': 'revenue growth'}, {'id': 'D0002', 'text': 'revenue growth'}]
    assert [d['id'] for d in retrieve('revenue growth', 'financial', docs)] == ['D0001', 'D0002']
    assert retrieve('revenue', 'financial', []) == []


def test_no_unrelated_passage():
    assert retrieve('revenue', 'historical', [{'id': 'D1', 'text': 'zebras graze peacefully'}]) == []
