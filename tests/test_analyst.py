import asyncio
import json
from investment_intelligence.analyst import analyze, build_catalog, verify_claims
from shared.llm import LLMConfig

REPORT={'entity':{'name':'Example'},'financials':{'revenue':{'value':'100000000000'}},'ratios_percent':{'net_margin':'40.31'},'valuation':{'pe_ratio':'28.48'}}

def claim(e):
    return {
        'metric': e['metric'],
        'value': e['value'],
        'evidence_id': e['id']
    }

def response(e, prose=None):
    return {'thesis':prose or 'Revenue is strong.', 'strengths':[], 'risks':[], 'valuation':'Valuation requires context.', 'claims':[claim(e)],'limitations':[]}

class FakeClient:
    config=LLMConfig(model='test')
    def __init__(self, outputs): self.outputs=iter(outputs);self.calls=0
    async def complete(self,messages): self.calls+=1;return json.dumps(next(self.outputs))

def test_catalog_points_to_real_values():
    from investment_intelligence.analyst import resolve_pointer
    for e in build_catalog(REPORT): assert str(resolve_pointer(REPORT,e['path']))==e['value']

def test_valid_claim():
    e=build_catalog(REPORT)[0];c=FakeClient([response(e)])
    out=asyncio.run(analyze(REPORT,c))
    assert out['status']=='verified' and c.calls==1

def test_reject_wrong_number():
    e=build_catalog(REPORT)[0];a=response(e);a['claims'][0]['value']='999'
    assert not verify_claims(a,REPORT)['all_verified']

def test_reject_missing_id():
    e=build_catalog(REPORT)[0];a=response(e);a['claims'][0]['evidence_id']='E999'
    assert not verify_claims(a,REPORT)['all_verified']

def test_reject_uncited_narrative():
    e=build_catalog(REPORT)[0];a=response(e,'Revenue grew 12.5% last year.')
    assert verify_claims(a,REPORT)['narrative_issues']

def test_reject_mismatched_narrative_citation():
    e=build_catalog(REPORT)[0];a=response(e,f'Revenue grew 12.5% [{e["id"]}].')
    assert verify_claims(a,REPORT)['narrative_issues']

def test_valid_cited_narrative():
    e=build_catalog(REPORT)[0];a=response(e,f'Revenue is {e["value"]} [{e["id"]}].')
    assert verify_claims(a,REPORT)['all_verified']

def test_corrective_retry():
    e=build_catalog(REPORT)[0];c=FakeClient([response(e,'Revenue grew 12.5%.'),response(e)])
    out=asyncio.run(analyze(REPORT,c))
    assert out['status']=='verified' and len(out['attempts'])==2 and c.calls==2

def test_fail_closed_after_retry():
    e=build_catalog(REPORT)[0];bad=response(e,'Revenue grew 12.5%.');c=FakeClient([bad,bad])
    assert asyncio.run(analyze(REPORT,c))['status']=='review_required'
