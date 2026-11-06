import hashlib
import json
from investment_intelligence.industry_context import fetch_bea, normalize_rows

ENTRY = {'table_id': '16', 'industry_code': '511'}
ROWS = [{'Industry': '511', 'Year': '2024', 'DataValue': '124.5', 'IndustrYDescription': 'Software'}]

def test_actual_bea_list_response():
    raw = json.dumps({'BEAAPI': {'Results': [{'Statistic': 'GDP by Industry Table', 'Data': ROWS}]}}).encode()
    rows, digest = fetch_bea(ENTRY, 'fake', lambda url: raw)
    assert rows == ROWS
    assert digest == hashlib.sha256(raw).hexdigest()
    assert normalize_rows(rows, ENTRY, '2026-10-30')[0]['description'] == 'Software'

def test_legacy_dict_response():
    raw = json.dumps({'BEAAPI': {'Results': {'Data': ROWS}}}).encode()
    assert fetch_bea(ENTRY, 'fake', lambda url: raw)[0] == ROWS

def test_api_error_is_explained():
    raw = json.dumps({'BEAAPI': {'Results': [{'Error': {'APIErrorDescription': 'Invalid table'}}]}}).encode()
    try:
        fetch_bea(ENTRY, 'fake', lambda url: raw)
    except ValueError as exc:
        assert 'Invalid table' in str(exc)
    else:
        assert False, 'Expected API error'
