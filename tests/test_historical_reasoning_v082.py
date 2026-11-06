import asyncio
import pytest
from investment_intelligence.historical_reasoning import prepare_investigations, validate_response, investigate_history

ANALYSIS = {'historical_dimension_signals': {'signals': [{'code': 'capex_outpaces_ocf', 'observation': 'Capital expenditures outpace operating cash flow', 'dimensions': ['risk','financial'], 'evidence': [{'metric': 'capital_expenditures'}]}]}, 'report_markdown': '# Report'}
DOCS = [{'id':'D0001', 'text':'Capital expenditures support datacenter investment and infrastructure expansion.', 'published_at':'2026-07-29'}]

def test_retrieval_uses_supplied_ids():
    rows = prepare_investigations(ANALYSIS, DOCS)
    assert rows[0]['documents'][0]['id'] == 'D0001'

def test_unknown_reference_rejected():
    with pytest.raises(ValueError):
        validate_response({'assessment':'context_found','management_explanation':'Claim','investment_implication':None,'uncertainties':[],'evidence_ids':['D9999']}, {'D0001'})

def test_no_evidence_cannot_claim_explanation():
    with pytest.raises(ValueError):
        validate_response({'assessment':'no_explanatory_evidence','management_explanation':'Cause','investment_implication':None,'uncertainties':[],'evidence_ids':[]}, {'D0001'})

def test_offline_preserves_original():
    out = asyncio.run(investigate_history(ANALYSIS, DOCS, None))
    assert out['historical_investigations']['records'][0]['status'] == 'not_evaluated'
    assert 'historical_investigations' not in ANALYSIS
    assert out['historical_dimension_signals'] == ANALYSIS['historical_dimension_signals']


def test_valid_context_response():
    r = validate_response({'assessment':'context_found','management_explanation':'Management describes investment.','investment_implication':None,'uncertainties':['Return unknown'],'evidence_ids':['D0001']}, {'D0001'})
    assert r['evidence_ids'] == ['D0001']
