import asyncio
import json
from types import SimpleNamespace
import sys,types
if 'shared.llm' not in sys.modules:
    shared=types.ModuleType('shared');llm=types.ModuleType('shared.llm')
    llm.LLMClient=object;llm.LLMConfig=object
    sys.modules.setdefault('shared',shared);sys.modules.setdefault('shared.llm',llm)
from investment_intelligence.analyst_v044 import analyze_v044

REPORT={'financials':{'revenue':{'value':'200'},'cash':{'value':'70'}},
        'financial_history':[{'financials':{'revenue':{'value':'100'},'cash':{'value':'90'}}},
                             {'financials':{'revenue':{'value':'200'},'cash':{'value':'70'}}}],
        'valuation':{'pe_ratio':'20','earnings_yield_percent':'5','fcf_yield_percent':'2'}}
class Fake:
    config=SimpleNamespace(provider='test',model='fake')
    def __init__(self,mode='normal'):
        self.mode=mode;self.calls=[]
    async def complete(self,messages):
        sysmsg=messages[0]['content'];self.calls.append(sysmsg)
        if 'cautious qualitative financial analyst' in sysmsg:
            return json.dumps({'statements':[
                {'text':'Declining cash may indicate liquidity pressure','finding_ids':['F004'],'category':'risk'},
                {'text':'Valuation matches historical benchmarks','finding_ids':['F007'],'category':'valuation'},
                {'text':'Revenue increased','finding_ids':['F002'],'category':'strength'}]})
        if 'Review the statement' in sysmsg:
            stmt=json.loads(messages[1]['content'])['statement']
            return json.dumps({'premise_supported':True,'unsupported_factual_claim':'historical' in stmt,
                               'interpretation_uncertain':'may' in stmt,'reason':'test'})
        if 'Rewrite the supplied assertion' in sysmsg:
            return json.dumps({'paraphrase':'Cash decline might signal liquidity pressure'})
        if 'Assess ONLY' in sysmsg:
            prop=json.loads(messages[1]['content'])['proposition']
            if self.mode=='inconsistent' and 'not the case' in prop:return json.dumps({'judgment':'true'})
            if self.mode=='inconsistent':return json.dumps({'judgment':'true'})
            return json.dumps({'judgment':'unknown'})
        if 'Given a qualitative assertion' in sysmsg:
            return json.dumps({'possible':False,'reason':'none'})
        raise AssertionError(sysmsg)

def test_warn_not_reject_for_tentative_inference():
    result=asyncio.run(analyze_v044(REPORT,Fake()))
    assert [s['status'] for s in result['statements']]==['warning','rejected','accepted'] or [s['status'] for s in result['statements']]==['warning','rejected','warning']
    assert 'Logical judgment is indeterminate' not in result['statements'][0]['warnings']
    assert len(result['published_statements'])==2

def test_detects_true_and_negation_both_true():
    result=asyncio.run(analyze_v044(REPORT,Fake('inconsistent')))
    assert any('contradictory' in w for w in result['statements'][0]['warnings'])

def test_valuation_units():
    result=asyncio.run(analyze_v044(REPORT,Fake()))
    units={f['metric']:f['unit'] for f in result['findings']}
    assert units['pe_ratio']=='ratio'
    assert units['earnings_yield_percent']=='percent'
    assert units['fcf_yield_percent']=='percent'
