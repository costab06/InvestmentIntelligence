import asyncio
import json
from types import SimpleNamespace
import sys, types
if 'shared.llm' not in sys.modules:
    shared=types.ModuleType('shared');llm=types.ModuleType('shared.llm')
    llm.LLMClient=object;llm.LLMConfig=object
    sys.modules.setdefault('shared',shared);sys.modules.setdefault('shared.llm',llm)
from investment_intelligence.analyst_v043 import deterministic_findings, analyze_v043

REPORT={'financials':{'revenue':{'value':'200'},'operating_cash_flow':{'value':'80'},'capital_expenditures':{'value':'30'}},
        'financial_history':[{'financials':{'revenue':{'value':'100'},'operating_cash_flow':{'value':'60'},'capital_expenditures':{'value':'20'}}},
                             {'financials':{'revenue':{'value':'200'},'operating_cash_flow':{'value':'80'},'capital_expenditures':{'value':'30'}}}]}
class Fake:
    config=SimpleNamespace(provider='test',model='fake')
    def __init__(self,mode='good'): self.mode=mode;self.calls=0
    async def complete(self,messages):
        self.calls+=1
        if self.calls==1:
            return json.dumps({'statements':[{'text':'Revenue growth is a strength','finding_ids':['F002'],'category':'strength'},
              {'text':'Debt is rising','finding_ids':['BAD'],'category':'risk'}]})
        if self.calls==2:
            return json.dumps({'supported':True,'uncertain':False,'reason':'supported'})
        return json.dumps({'original':'true','equivalent':'true','negation':'false',
                           'counterexample_possible':self.mode=='warning','reason':'test'})

def test_python_calculations():
    fs=deterministic_findings(REPORT)
    assert next(f for f in fs if f['metric']=='revenue' and f['kind']=='growth')['value']=='100'
    assert next(f for f in fs if f['metric']=='free_cash_flow' and f['kind']=='level')['value']=='50'
    assert next(f for f in fs if f['metric']=='free_cash_flow' and f['kind']=='growth')['value']=='25.00'

def test_reject_unsupported_ids():
    result=asyncio.run(analyze_v043(REPORT,Fake()))
    assert [s['status'] for s in result['statements']]==['accepted','rejected']
    assert len(result['published_statements'])==1

def test_warning_kept():
    result=asyncio.run(analyze_v043(REPORT,Fake('warning')))
    assert result['statements'][0]['status']=='warning'
    assert len(result['published_statements'])==1
