from investment_intelligence.dimension_routing import route_claim, build_investigation_plan

def test_growth_selects_industry_without_twelve_mandatory_reviews():
    result = route_claim('Revenue CAGR was 13% over four periods')
    assert result['selected_dimensions'] == ['historical', 'financial', 'industry']
    assert result['independent_industry_evidence'] == 'required_not_retrieved'
    assert result['assessment'] == 'investigation_plan_only'

def test_valuation_does_not_claim_independent_support():
    result = route_claim('P/E valuation compared with earnings yield')
    assert 'valuation' in result['selected_dimensions']
    assert result['assessment'] != 'verified'
    assert 'inverse financial ratios' in ' '.join(result['evidence_requirements'])

def test_audit_is_preserved_and_no_data_is_fabricated():
    original = {'qualitative_audit': [{'id':'S1','statement':{'text':'Revenue growth is strong'},'status':'warning'}],
                'statement_evaluations': {'keep':'untouched'}}
    from investment_intelligence.dimension_routing import attach_investigation_plan
    updated = attach_investigation_plan(original)
    assert updated['statement_evaluations'] == original['statement_evaluations']
    assert updated['dimension_investigation_plan']['records'][0]['publication_status'] == 'warning'
    assert 'planning_only' in updated['dimension_investigation_plan']['status']
