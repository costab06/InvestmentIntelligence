from investment_intelligence.industry_corroboration import assess_claim, attach_corroboration

CONTEXT = {'as_of':'2026-10-30','series':[{'status':'retrieved','industry_code':'51',
 'measure':'value_added','unit':'millions_usd','geography':'US',
 'source':'BEA GDPbyIndustry','source_url':'https://apps.bea.gov/api/data',
 'table_id':'1','response_sha256':'abcdef',
 'observations':[{'year':2022,'value':'100'},{'year':2023,'value':'110'},
                 {'year':2024,'value':'120'}]}]}
CLAIM = {'id':'I001','proposition':'US industry value added increased from 2022 to 2024',
 'industry_code':'51','measure':'value_added','unit':'millions_usd','geography':'US',
 'relation':'industry_increased','start_year':2022,'end_year':2024,
 'comparison_review':{'approved':True,'reviewed_by':'analyst',
   'industry_relevance':'Information sector context only',
   'geographic_scope':'US only', 'metric_scope':'Value added, not company revenue'}}

def test_supported_narrow_direction():
    r=assess_claim(CLAIM, CONTEXT)
    assert r['status']=='supported' and not r['publication_eligible']
    assert r['source_evidence'][0]['response_sha256']=='abcdef'

def test_contradiction():
    c=dict(CLAIM, relation='industry_decreased')
    assert assess_claim(c, CONTEXT)['status']=='contradicted'

def test_missing_review_blocks():
    c=dict(CLAIM, comparison_review={})
    assert assess_claim(c, CONTEXT)['status']=='supported'

def test_incomplete_period_blocks():
    context=dict(CONTEXT, series=[dict(CONTEXT['series'][0], observations=[{'year':2022,'value':'100'},{'year':2024,'value':'120'}])])
    assert assess_claim(CLAIM, context)['status']=='insufficient_evidence'

def test_mismatched_scope_blocks():
    assert assess_claim(dict(CLAIM, geography='Global'), CONTEXT)['status']=='insufficient_evidence'

def test_no_publication_change():
    a={'industry_context':CONTEXT,'published_statements':[{'id':'S1'}], 'status':'review_required'}
    b=attach_corroboration(a,[CLAIM])
    assert b['published_statements']==a['published_statements']
    assert b['status']=='review_required'
    assert b['industry_corroboration']['publication_decisions_changed'] is False

def test_relative_growth_not_claimed():
    c=dict(CLAIM, relation='company_outperformed_industry')
    assert assess_claim(c, CONTEXT)['status']=='insufficient_evidence'
