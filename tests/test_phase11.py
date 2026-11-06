from decimal import Decimal
from investment_intelligence.capital_investigation import investigate_capital
from investment_intelligence.business_model import capital_evidence_plan


def sample(sic=None, capex=(3236,6042), ocf=(64089,102718)):
    dates=('2025-01-26','2026-01-25')
    values={'capital_expenditures':capex,'operating_cash_flow':ocf,'revenue':(130497,215938)}
    return {'industry_resolution':{'sic':sic} if sic else {}, 'historical_intelligence':{'metrics':{
        metric:{'observations':[{'period_end':date,'value':str(value),
            'provenance':{'concept':'us-gaap:PaymentsToAcquireProductiveAssets'} if metric=='capital_expenditures' else {}}
            for date,value in zip(dates, series)]} for metric,series in values.items()}}}


def test_nvda_growth_rate_predicate_and_generic_semiconductor_plan():
    r=investigate_capital(sample('3674'))
    h=next(x for x in r['hypotheses'] if x['id']=='CAP-H1')
    assert h['status']=='supported_for_observed_interval'
    assert Decimal(h['predicate_inputs']['capex_growth_percent']) > Decimal(h['predicate_inputs']['ocf_growth_percent'])
    assert r['business_model_evidence_plan']['business_model']=='semiconductor_or_electronics'
    assert 'Azure' not in str(r)
    assert not r['publication_eligible']


def test_microsoft_software_plan_without_hardcoded_issuer():
    r=investigate_capital(sample('7372'))
    assert r['business_model_evidence_plan']['business_model']=='software_or_services'
    assert any('infrastructure utilization' in x['question'] for x in r['next_evidence'])
    assert 'Azure' not in str(r)


def test_unknown_company_gets_neutral_plan():
    r=investigate_capital(sample())
    assert r['business_model_evidence_plan']['business_model']=='unclassified'
    assert all('Azure' not in x['needed'] for x in r['next_evidence'])


def test_growth_rate_not_absolute_delta():
    r=investigate_capital(sample('3674', capex=(10,30), ocf=(1000,1200)))
    assert next(x for x in r['hypotheses'] if x['id']=='CAP-H1')['status']=='supported_for_observed_interval'


def test_capex_not_faster():
    r=investigate_capital(sample('3674', capex=(100,105), ocf=(1000,1200)))
    assert next(x for x in r['hypotheses'] if x['id']=='CAP-H1')['status']=='not_supported_for_observed_interval'


def test_zero_prior_capex_withheld():
    r=investigate_capital(sample('3674', capex=(0,105), ocf=(1000,1200)))
    assert next(x for x in r['hypotheses'] if x['id']=='CAP-H1')['status']=='insufficient_data'
