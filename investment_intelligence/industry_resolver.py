"""Resolve SEC issuer SIC and safely plan industry evidence without guessing mappings."""
from pathlib import Path
import json

# Reviewed proxy mappings only. These do not establish company/industry comparability.
REVIEWED_SIC = {
    '7372': {'label':'Prepackaged Software', 'mapping':'msft-industry-mapping.json',
             'scope':'US software and information services proxy; not global company revenue'},
}

def resolve_industry(ticker, cik, submissions, mapping_dir=None, explicit_mapping=None):
    """Never infer a BEA series from an unreviewed SIC code."""
    sic = str(submissions.get('sic') or '').strip()
    name = submissions.get('sicDescription')
    info = REVIEWED_SIC.get(sic)
    result = {'schema_version':'1.0.0','ticker':ticker,'cik':cik,'sic':sic or None,
              'sic_description':name,'classification_source':'SEC submissions',
              'classification_confidence':'issuer_classification' if sic else 'unavailable',
              'mapping_status':'unmapped','mapping':None,'mapping_source':None,
              'limitations':['SEC SIC identifies issuer primary classification, not all revenue segments.',
                             'BEA US real output indices are not directly comparable to global nominal issuer sales.']}
    if explicit_mapping:
        path=Path(explicit_mapping)
        result['mapping_source']='user_supplied'
    elif info and mapping_dir:
        path=Path(mapping_dir)/info['mapping']
        result['mapping_source']='reviewed_registry'
    else:
        return result
    if not path.is_file():
        result['mapping_status']='mapping_file_missing'
        return result
    mapping=json.loads(path.read_text(encoding='utf-8'))
    # An MSFT-reviewed proxy cannot silently become a validated mapping for other issuers.
    if str(mapping.get('ticker','')).upper()!=ticker.upper():
        result['mapping_status']='requires_company_review'
        return result
    result['mapping_status']='mapped_proxy_not_comparable'
    result['mapping']=mapping
    return result
