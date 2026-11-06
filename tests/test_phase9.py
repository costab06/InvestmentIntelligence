import sys, types
if "secagent.clients.edgar" not in sys.modules:
    sys.modules.setdefault("secagent", types.ModuleType("secagent"))
    sys.modules.setdefault("secagent.clients", types.ModuleType("secagent.clients"))
    stub = types.ModuleType("secagent.clients.edgar")
    stub.EdgarClient = object
    sys.modules["secagent.clients.edgar"] = stub
from investment_intelligence.report import financial_history
from investment_intelligence.cash_flow_evidence import build_cash_flow_evidence

def fact(value, tag, start='2025-01-27', end='2026-01-25'):
    return {'val':value,'start':start,'end':end,'filed':'2026-02-25','accn':'test-accession','form':'10-K','fp':'FY'}

def facts():
    values={'Revenues':215938000000,'NetIncomeLoss':120067000000,
            'NetCashProvidedByUsedInOperatingActivities':102718000000,
            'PaymentsToAcquireProductiveAssets':6042000000,
            'ShareBasedCompensation':6386000000,
            'IncreaseDecreaseInAccountsReceivable':15399000000}
    return {'facts':{'us-gaap':{k:{'units':{'USD':[fact(v,k)]}} for k,v in values.items()}}}

def test_nvda_productive_asset_tag_selected_with_definition():
    h=financial_history(facts(), '2026-10-31')
    cap=h[-1]['financials']['capital_expenditures']
    assert cap['value']=='6042000000'
    assert cap['concept']=='us-gaap:PaymentsToAcquireProductiveAssets'
    assert cap['measure_definition']=='productive_assets_including_intangibles'
    assert h[-1]['free_cash_flow']['value']=='96676000000'

def test_cash_bridge_is_partial_and_provenanced():
    f=facts(); h=financial_history(f,'2026-10-31')
    r=build_cash_flow_evidence(f,{'financial_history':h},'2026-10-31')
    row=r['periods'][0]
    assert row['status']=='partial_reconciliation'
    assert row['components']['share_based_compensation']['cash_flow_contribution_usd']=='6386000000'
    assert row['components']['receivables_change']['cash_flow_contribution_usd']=='-15399000000'
    assert row['complete_reconciliation'] is False

def test_conflicting_capex_definitions_not_silently_merged():
    f=facts()
    f['facts']['us-gaap']['PaymentsToAcquirePropertyPlantAndEquipment']={'units':{'USD':[fact(1000000000,'PaymentsToAcquirePropertyPlantAndEquipment')]}}
    assert financial_history(f,'2026-10-31')[-1]['financials']['capital_expenditures']['status']=='ambiguous'
