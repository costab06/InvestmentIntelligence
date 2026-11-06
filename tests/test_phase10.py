from decimal import Decimal
from investment_intelligence.earnings_quality import investigate_earnings_quality
from investment_intelligence.investigation_registry import select_investigations

def analysis():
    metrics={}
    for k, vals in {'net_income':[72880,120067], 'operating_cash_flow':[64089,102718], 'capital_expenditures':[3236,6042], 'revenue':[130497,215938]}.items():
        metrics[k]={'observations':[{'period_end':d,'value':str(v),'provenance':{'concept':'us-gaap:PaymentsToAcquireProductiveAssets','measure_definition':'productive_assets_including_intangibles'} if k=='capital_expenditures' else {}} for d,v in zip(['2025-01-26','2026-01-25'], vals)]}
    return {'historical_intelligence':{'metrics':metrics}}

def evidence():
    periods=[]
    for date,ni,cf,rc,inv,sc in [('2025-01-26',72880,64089,-13063,-4781,4737),('2026-01-25',120067,102718,-15399,-11324,6386)]:
        components={}
        for name,cat,v in [('receivables_change','working_capital',rc),('inventory_change','working_capital',inv),('share_based_compensation','noncash',sc)]:
            components[name]={'status':'selected','category':cat,'cash_flow_contribution_usd':str(v),'provenance':{'concept':'us-gaap:'+name,'unit':'USD','period_end':date,'accession':'abc'}}
        periods.append({'period_end':date,'status':'partial_reconciliation','net_income_usd':str(ni),'operating_cash_flow_usd':str(cf),'observed_ocf_less_ni_usd':str(cf-ni),'components':components})
    return {'periods':periods}

def test_evidence_promotes_partial_working_capital_hypothesis():
    r=investigate_earnings_quality(analysis(),evidence())
    o=next(x for x in r['observations'] if x['id']=='EQ-O3')
    assert Decimal(o['working_capital_change_usd']) == -8879
    assert Decimal(o['observed_cash_earnings_gap_change_usd']) == -8558
    assert Decimal(o['matched_component_change_usd']) + Decimal(o['unexplained_change_usd']) == -8558
    assert next(h for h in r['hypotheses'] if h['id']=='EQ-H2')['status']=='supported_as_partial_contributor'
    assert all(x['status']=='partially_verified' for x in r['next_evidence'][:2])
    assert not r['publication_eligible']

def test_mismatched_bridge_not_promoted():
    e=evidence();e['periods'][1]['net_income_usd']='999'
    r=investigate_earnings_quality(analysis(),e)
    assert not any(x['id']=='EQ-O3' for x in r['observations'])
    assert next(h for h in r['hypotheses'] if h['id']=='EQ-H2')['status']=='unresolved'

def test_missing_component_excluded():
    e=evidence();e['periods'][0]['components']['inventory_change']['status']='missing_or_unmatched'
    r=investigate_earnings_quality(analysis(),e)
    o=next(x for x in r['observations'] if x['id']=='EQ-O3')
    assert Decimal(o['working_capital_change_usd']) == -2336
    assert len(o['component_changes']) == 2

def test_capex_mismatched_concept_withheld():
    a=analysis();a['historical_intelligence']['metrics']['capital_expenditures']['observations'][0]['provenance']['concept']='us-gaap:PaymentsToAcquirePropertyPlantAndEquipment'
    assert select_investigations(a)['investigations'][0]['status']=='noncomparable_capex_definitions'
