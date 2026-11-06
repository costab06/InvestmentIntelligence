from investment_intelligence.industry_hypothesis import attach_hypotheses, evaluate_hypothesis

BASE = {'findings': [{'id': 'F001', 'metric': 'revenue', 'kind': 'growth', 'value': '12', 'source_paths': ['/revenue']}],
        'published_statements': [{'id': 'S001'}],
        'industry_corroboration': {'records': [{'claim_id': 'I001', 'status': 'supported',
             'observed_relation': 'industry_increased', 'source_evidence': [{'source': 'BEA', 'response_sha256': 'abc'}]}]}}
H = {'id': 'H001', 'proposition': 'Company and industry both grew',
     'relation': 'company_and_industry_same_direction', 'company_finding_id': 'F001',
     'company_direction': 'increased', 'industry_claim_id': 'I001',
     'company_direction_review': {'approved': True, 'reviewed_by': 'analyst', 'finding_id': 'F001', 'direction': 'increased'},
     'reasoning_review': {'approved': True, 'reviewed_by': 'analyst',
         'alternative_explanations': 'Company-specific factors', 'scope_limitations': 'Different measures'}}

def test_consistent_never_publishes():
    result = attach_hypotheses(BASE, [H])
    assert result['industry_hypotheses']['records'][0]['status'] == 'directional_agreement_only'
    assert result['published_statements'] == BASE['published_statements']
    assert result['industry_hypotheses']['records'][0]['publication_eligible'] is False

def test_conflicting_industry():
    import copy
    a = copy.deepcopy(BASE)
    a['industry_corroboration']['records'][0]['observed_relation'] = 'industry_decreased'
    assert evaluate_hypothesis(H, a)['status'] == 'directional_disagreement_only'

def test_missing_company_provenance():
    import copy
    a = copy.deepcopy(BASE)
    a['findings'][0]['source_paths'] = []
    assert evaluate_hypothesis(H, a)['status'] == 'insufficient_evidence'

def test_missing_reasoning_review():
    assert evaluate_hypothesis({**H, 'reasoning_review': {}}, BASE)['status'] == 'directional_agreement_only'

def test_unsupported_claim():
    import copy
    a = copy.deepcopy(BASE)
    a['industry_corroboration']['records'][0]['status'] = 'contradicted'
    assert evaluate_hypothesis(H, a)['status'] == 'insufficient_evidence'
