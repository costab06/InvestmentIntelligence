"""BEA industry observations: never automatically treated as corroboration."""
from __future__ import annotations
from datetime import date
from decimal import Decimal, InvalidOperation
import hashlib
import json
from urllib.parse import urlencode
from urllib.request import Request, urlopen

API = 'https://apps.bea.gov/api/data'
REQUIRED = {'table_id', 'industry_code', 'measure', 'unit', 'geography', 'rationale'}

def validate_mapping(mapping):
    if not isinstance(mapping, dict) or not isinstance(mapping.get('industries'), list) or not mapping['industries']:
        raise ValueError('Mapping requires nonempty industries list')
    for entry in mapping['industries']:
        if REQUIRED - set(entry):
            raise ValueError(f'Missing mapping fields: {sorted(REQUIRED - set(entry))}')
        if not str(entry['industry_code']).strip() or not str(entry['rationale']).strip():
            raise ValueError('Explicit industry code and rationale required')
    return mapping

def fetch_bea(entry, api_key, fetcher=None):
    if not api_key:
        raise ValueError('BEA_API_KEY required')
    params = {'UserID': api_key, 'method': 'GetData', 'datasetname': 'GDPbyIndustry',
              'TableID': str(entry['table_id']), 'Industry': str(entry['industry_code']),
              'Frequency': 'A', 'Year': 'ALL', 'ResultFormat': 'JSON'}
    if fetcher is None:
        def fetcher(url):
            with urlopen(Request(url, headers={'User-Agent': 'InvestmentIntelligence/0.9'}), timeout=35) as r:
                return r.read()
    raw = fetcher(API + '?' + urlencode(params))
    if isinstance(raw, str): raw = raw.encode()
    payload = json.loads(raw)
    bea = payload.get('BEAAPI', {})
    result = bea.get('Results', {})
    if isinstance(result, list):
        if len(result) != 1 or not isinstance(result[0], dict):
            raise ValueError(f'Unexpected BEA Results list with {len(result)} entries')
        result = result[0]
    if not isinstance(result, dict):
        raise ValueError(f'Unexpected BEA Results type: {type(result).__name__}')
    error = bea.get('Error') or result.get('Error')
    if error:
        raise ValueError(f'BEA API error: {str(error)[:400]}')
    rows = result.get('Data')
    if not isinstance(rows, list):
        raise ValueError(f'BEA response missing Data list; result keys: {sorted(result)}')
    return rows, hashlib.sha256(raw).hexdigest()

def normalize_rows(rows, entry, as_of):
    cutoff = int(as_of[:4]); out = []
    for row in rows:
        if str(row.get('Industry', '')).strip() != str(entry['industry_code']).strip(): continue
        year = str(row.get('Year', ''))
        if not (len(year) == 4 and year.isdigit()) or int(year) > cutoff: continue
        try:
            value = Decimal(str(row.get('DataValue', '')).replace(',', '').strip())
            if not value.is_finite(): continue
        except InvalidOperation: continue
        out.append({'year': int(year), 'value': str(value), 'raw_value': row.get('DataValue'),
                    'description': row.get('IndustryDescription') or row.get('IndustrYDescription')})
    out.sort(key=lambda x: x['year'])
    if len({r['year'] for r in out}) != len(out):
        raise ValueError('Ambiguous BEA series: duplicate annual observations')
    return out

def build_industry_context(mapping, *, ticker, as_of, api_key=None, fetcher=None):
    validate_mapping(mapping)
    if mapping.get('ticker', '').upper() != ticker.upper():
        raise ValueError('Industry mapping ticker mismatch')
    series = []
    for entry in mapping['industries']:
        record = {'source': 'BEA GDPbyIndustry', 'source_url': API, 'table_id': str(entry['table_id']),
                  'industry_code': str(entry['industry_code']), 'measure': entry['measure'],
                  'unit': entry['unit'], 'geography': entry['geography'], 'rationale': entry['rationale'],
                  'comparability_status': 'not_established', 'corroboration_status': 'not_assessed'}
        if not api_key:
            record.update(status='not_retrieved', reason='BEA_API_KEY not provided')
        else:
            try:
                rows, digest = fetch_bea(entry, api_key, fetcher)
                values = normalize_rows(rows, entry, as_of)
                record.update(status='retrieved' if values else 'no_usable_rows',
                              response_sha256=digest, observations=values)
            except Exception as exc:
                record.update(status='retrieval_failed', error=f'{type(exc).__name__}: {exc}')
        series.append(record)
    return {'schema_version': '0.9.0-industry', 'ticker': ticker, 'as_of': as_of,
            'status': 'observations_only_no_claim_corroboration', 'series': series,
            'limitations': ['BEA industry data is not automatically comparable to company revenue.',
                            'US industry observations do not measure global company operations.',
                            'No market-share, causal, or forward-looking inference is established.',
                            'Industry mapping requires review, especially for diversified companies.']}

def attach_industry_context(analysis, context):
    result = dict(analysis)
    result['industry_context'] = context
    return result
