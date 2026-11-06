import asyncio
import sys, types
if "shared.llm" not in sys.modules:
    shared=types.ModuleType("shared"); llm=types.ModuleType("shared.llm")
    llm.LLMClient=object;llm.LLMConfig=object
    sys.modules.setdefault("shared",shared);sys.modules.setdefault("shared.llm",llm)
from investment_intelligence.analyst_v050 import analyze_v050,coverage,render_markdown

def sample():
    def metric(x):return {'value':str(x)}
    def period(rev,ni,oi,ocf,capex,cash,assets):
        return {'financials':dict(zip(('revenue','net_income','operating_income','operating_cash_flow','capital_expenditures','cash','assets'),map(metric,(rev,ni,oi,ocf,capex,cash,assets))))}
    prior=period(100,20,30,40,10,50,200)
    current=period(120,30,40,50,20,45,230)
    return {**current,'financial_history':[prior,current], 'valuation':{'pe_ratio':20,'earnings_yield_percent':5,'fcf_yield_percent':2},'limitations':['Prototype data']}

def test_all_sections_and_units():
    result=asyncio.run(analyze_v050(sample()))
    assert all(result['coverage'][s] for s in ('growth','profitability','cash_generation','balance_sheet','valuation'))
    assert next(f for f in result['findings'] if f['metric']=='pe_ratio')['unit']=='ratio'
    assert '20.00x' in result['report_markdown']
    assert 'Prototype data' in result['report_markdown']
    assert result['status']=='verified_financials'

def test_missing_valuation_not_fabricated():
    data=sample();del data['valuation']
    result=asyncio.run(analyze_v050(data))
    assert not result['coverage']['valuation']
    assert 'Missing deterministic coverage: Valuation' in result['report_markdown']

def test_verified_facts_survive_rejected_commentary():
    data=sample()
    class Client:
        config=type('Config',(),{'provider':'test','model':'fake'})()
        async def complete(self,messages):
            return '{"statements":[{"text":"Unsupported claim","finding_ids":["F001"],"category":"thesis"}],"limitations":[]}' if 'cautious qualitative financial analyst' in messages[0]['content'] else '{"premise_supported":false,"unsupported_factual_claim":true,"interpretation_uncertain":false,"reason":"unsupported"}'
    result=asyncio.run(analyze_v050(data,Client()))
    assert result['status']=='review_required'
    assert not result['published_statements']
    assert result['qualitative_audit'][0]['status']=='rejected'
    assert 'Revenue and net-income growth' in result['report_markdown']
