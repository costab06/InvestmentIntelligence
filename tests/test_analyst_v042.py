import asyncio
import json
from investment_intelligence.analyst import build_catalog, verify_claims, analyze

REPORT={'financials':{'revenue':{'value':'331839000000'},'cash':{'value':'20935000000'},'capital_expenditures':{'value':'115948000000'}},'valuation':{'market_cap_usd':'3808562463621.6317','pe_ratio':'28.4754462734'}}
CAT=build_catalog(REPORT)
def eid(metric): return next(e['id'] for e in CAT if e['metric']==metric)
def base():
    return {'thesis':'Strong revenue','strengths':[f'Revenue of $331.839 billion [{eid("Revenue")}]'], 'risks':[], 'valuation':f'P/E ratio of 28.48 [{eid("P/E ratio")}]', 'claims':[{'metric':'Revenue','value':'331839000000','evidence_id':eid('Revenue')}], 'limitations':[]}

def test_scaled_narrative():
    assert verify_claims(base(),REPORT,CAT)['all_verified']

def test_wrong_metric_rejected():
    a=base(); a['claims']=[{'metric':'Cash reserves','value':'115948000000','evidence_id':eid('Capital expenditures')}]
    assert not verify_claims(a,REPORT,CAT)['all_verified']

def test_wrong_scale_rejected():
    a=base(); a['strengths']=[f'Revenue of $331.839 million [{eid("Revenue")}]']
    assert not verify_claims(a,REPORT,CAT)['all_verified']

def test_wrong_market_cap_rejected():
    a=base(); a['claims']=[{'metric':'Market cap','value':'38085600000000','evidence_id':eid('Market capitalization')}]
    assert not verify_claims(a,REPORT,CAT)['all_verified']

def test_curated_prompt_and_retry():
    class Config: provider='openai_compatible';model='fake'
    class Client:
        config=Config()
        def __init__(self):self.messages=[]
        async def complete(self,messages):
            self.messages.append(messages)
            if len(self.messages)==1:
                a=base();a['claims'][0]['value']='1';return json.dumps(a)
            return json.dumps(base())
    c=Client();result=asyncio.run(analyze(REPORT,c))
    assert result['schema_version']=='0.4.2' and result['status']=='verified'
    assert len(result['attempts'])==2
