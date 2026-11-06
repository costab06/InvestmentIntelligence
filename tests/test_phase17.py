import json
from investment_intelligence.phase17_validation import audit_local_raw_html, build_cash_flow_reconciliation


def test_reconciliation_signed_and_provenance():
    data = {'periods':[{'period_end':'2026-01-25','net_income_usd':'100','operating_cash_flow_usd':'80',
             'components':{'receivables_change':{'status':'selected','category':'working_capital',
             'cash_flow_contribution_usd':'-30','provenance':{'concept':'test:AR'}},
             'depreciation_amortization':{'status':'missing_or_unmatched'}},
             'unexplained_residual_usd':'10'}]}
    p = build_cash_flow_reconciliation(data)['periods'][0]
    assert p['observed_gap_usd']=='-20'
    assert p['unexplained_residual_usd']=='10'
    assert p['source_residual_agrees'] is True
    assert p['selected_components'][0]['provenance']['concept']=='test:AR'
    assert p['complete_reconciliation'] is False


def test_no_periods_abstains():
    result = build_cash_flow_reconciliation({})
    assert result['status']=='no_periods'
    assert result['publication_eligible'] is False


def test_raw_audit_flags_table_only(tmp_path):
    raw = tmp_path/'filing.html'
    raw.write_text('<html><body><p>Material customer supply constraints and manufacturing strategy.</p></body></html>')
    parsed = tmp_path/'parsed.json'
    parsed.write_text(json.dumps({'document':{'blocks':[{'type':'table','text':'Net income 100'}]}}))
    audit = audit_local_raw_html(raw, parsed)
    assert audit['narrative_missing_suspected']
    assert audit['raw_token_recall']=='0'
    assert len(audit['raw_sha256'])==64


def test_raw_audit_does_not_overstate_complete(tmp_path):
    raw = tmp_path/'filing.html'
    raw.write_text('<p>Customer supply constraints</p>')
    parsed = tmp_path/'parsed.json'
    parsed.write_text(json.dumps({'document':{'blocks':[{'type':'paragraph','text':'Customer supply constraints'}]}}))
    audit = audit_local_raw_html(raw, parsed)
    assert audit['raw_token_recall']=='1'
    assert not audit['narrative_missing_suspected']
    assert any('not semantic' in x for x in audit['limitations'])
