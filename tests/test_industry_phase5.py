from investment_intelligence.industry_corroboration import assess_claim
from investment_intelligence.industry_hypothesis import evaluate_hypothesis

def test_bea_only_direction_no_manual_approval():
    context={'as_of':'2026-10-30','series':[{'industry_code':'511','status':'retrieved','measure':'index','unit':'index','geography':'US','response_sha256':'abc','source':'BEA','table_id':'16','observations':[{'year':2021,'value':'100'},{'year':2022,'value':'105'},{'year':2023,'value':'110'},{'year':2024,'value':'125'}]}]}
    claim={'id':'I001','industry_code':'511','relation':'industry_increased','start_year':2021,'end_year':2024,'measure':'index','unit':'index','geography':'US'}
    result=assess_claim(claim,context)
    assert result['status']=='supported'
    assert result['publication_eligible'] is False

def test_hypothesis_direction_no_fake_review():
    analysis={'findings':[{'id':'F002','metric':'revenue','kind':'growth','value':'17.7','source_paths':['/revenue']}], 'industry_corroboration':{'records':[{'claim_id':'I001','status':'supported','observed_relation':'industry_increased','source_evidence':[{'source':'BEA'}]}]}}
    result=evaluate_hypothesis({'id':'H001','relation':'company_and_industry_same_direction','company_finding_id':'F002','industry_claim_id':'I001'},analysis)
    assert result['status']=='directional_agreement_only'
    assert result['publication_eligible'] is False
    assert any(x['type']=='period' for x in result['challenges'])
