import asyncio
from investment_intelligence.evidence_integrity import enforce_evidence_integrity

def test_formula_component_not_falsely_rejected():
    a={'findings':[{'id':'F017','metric':'operating_cash_flow','kind':'margin'}], 'qualitative_audit':[{'id':'S003','status':'warning','statement':{'text':'Operating cash flow margin indicates cash generation relative to revenue','finding_ids':['F017']}}], 'published_statements':[{'id':'S003','status':'warning','statement':{'text':'Operating cash flow margin indicates cash generation relative to revenue','finding_ids':['F017']}}]}
    b=enforce_evidence_integrity(a)
    assert b['evidence_integrity']['invalid_statement_ids']==[]
    assert 'S003' in b['report_markdown']

def test_wrong_metric_still_rejected():
    a={'findings':[{'id':'F016','metric':'operating_income','kind':'margin'}], 'qualitative_audit':[{'id':'S1','status':'warning','statement':{'text':'Operating cash flow margin is high','finding_ids':['F016']}}], 'published_statements':[{'id':'S1'}]}
    b=enforce_evidence_integrity(a)
    assert b['published_statements']==[]
    assert 'S1' not in b['report_markdown'].split('## Final Qualitative Publication (v0.8.5)')[1].split('## Rejected Statements')[0]

def test_render_no_stale_publications():
    a={'findings':[], 'qualitative_audit':[{'id':'S1','status':'rejected','statement':{'text':'Bad claim','finding_ids':[]}}], 'published_statements':[], 'report_markdown':'# Report\n\n## Qualitative Interpretations (Validated)\n\n- **WARNING** Bad claim\n\n## Coverage and Limitations\n\nSome limits.\n\n## Twelve-Dimension Statement Evaluations\n\nStale table\n\n## Framework Provenance\n\nProvenance.'}
    b=enforce_evidence_integrity(a)
    assert 'Stale table' not in b['report_markdown']
    assert '**WARNING** Bad claim' not in b['report_markdown']
    assert 'Some limits.' in b['report_markdown']
    assert 'Provenance.' in b['report_markdown']

def test_semantic_retry():
    import sys, types
    if "investment_intelligence.evidence_retrieval" not in sys.modules:
        mod=types.ModuleType("investment_intelligence.evidence_retrieval");mod.retrieve=lambda *a,**k: []
        sys.modules["investment_intelligence.evidence_retrieval"]=mod
    from investment_intelligence import historical_reasoning as h
    class Client: pass
    calls=[]
    async def mock_complete(client,prompt,payload):
        calls.append(payload)
        return {'assessment':'context_found','management_explanation':'issuer disclosed investment', 'investment_implication':None,'uncertainties':[], 'evidence_ids':['D9999'] if len(calls)==1 else ['D0001']}
    import sys, types
    old=sys.modules.get('investment_intelligence.json_recovery')
    module=types.ModuleType('investment_intelligence.json_recovery');module.complete_json=mock_complete
    sys.modules['investment_intelligence.json_recovery']=module
    try:
        data={'historical_dimension_signals':{'signals':[{'code':'revenue_cagr','observation':'Revenue grew','dimensions':['historical'],'evidence':[]}]}}
        original=h.prepare_investigations
        h.prepare_investigations=lambda a,d:[{'signal_code':'revenue_cagr','dimensions':['historical'],'observation':'Revenue grew','financial_evidence':[],'documents':[{'id':'D0001','text':'Growth from services'}]}]
        try: result=asyncio.run(h.investigate_history(data,[],Client()))
        finally:h.prepare_investigations=original
        assert result['historical_investigations']['records'][0]['semantic_recovery']=='retry_succeeded'
        assert len(calls)==2
    finally:
        if old is None:del sys.modules['investment_intelligence.json_recovery']
        else:sys.modules['investment_intelligence.json_recovery']=old
