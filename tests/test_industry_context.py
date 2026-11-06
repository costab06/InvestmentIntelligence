import json
import pytest
from investment_intelligence.industry_context import build_industry_context, normalize_rows

MAPPING = {'ticker':'MSFT', 'industries':[{'table_id':'1','industry_code':'51','measure':'value_added',
    'unit':'millions_usd','geography':'US','rationale':'Illustrative industry context only; mapping unverified'}]}

def test_missing_key_is_not_corroboration():
    result = build_industry_context(MAPPING, ticker='MSFT', as_of='2026-10-30')
    assert result['series'][0]['status'] == 'not_retrieved'
    assert result['series'][0]['corroboration_status'] == 'not_assessed'

def test_response_parsing_and_provenance():
    raw = json.dumps({'BEAAPI':{'Results':{'Data':[
        {'Industry':'51','Year':'2024','DataValue':'1,200.4'},
        {'Industry':'51','Year':'2025','DataValue':'1,300.0'},
        {'Industry':'51','Year':'2027','DataValue':'1,500'},
        {'Industry':'52','Year':'2025','DataValue':'900'}]}}}).encode()
    result = build_industry_context(MAPPING, ticker='MSFT', as_of='2026-10-30',
                                    api_key='dummy', fetcher=lambda url:raw)
    s=result['series'][0]
    assert [x['year'] for x in s['observations']] == [2024,2025]
    assert s['observations'][0]['value'] == '1200.4'
    assert s['response_sha256']
    assert s['corroboration_status'] == 'not_assessed'

def test_mismatch_rejected():
    with pytest.raises(ValueError): build_industry_context(MAPPING, ticker='JNJ', as_of='2026-10-30')

def test_duplicate_rows_rejected():
    rows=[{'Industry':'51','Year':'2025','DataValue':'100'},
          {'Industry':'51','Year':'2025','DataValue':'101'}]
    with pytest.raises(ValueError): normalize_rows(rows, MAPPING['industries'][0], '2026-10-30')

def test_invalid_api_response_not_published():
    result=build_industry_context(MAPPING,ticker='MSFT',as_of='2026-10-30',api_key='dummy',
        fetcher=lambda url:json.dumps({'BEAAPI':{'Results':{'Error':'Bad query'}}}))
    assert result['series'][0]['status']=='retrieval_failed'
