"""Filed annual cash-flow reconciliation evidence, with no estimated or inferred facts."""
from __future__ import annotations
from decimal import Decimal

# Signed direction is how each tagged concept contributes to OCF - net income.
# Sign is applied to the positive-valued SEC fact, not to its display in a filing.
COMPONENTS = {
    'share_based_compensation': ('ShareBasedCompensation', 1, 'noncash'),
    'depreciation_amortization': ('DepreciationDepletionAndAmortization', 1, 'noncash'),
    'deferred_income_tax': ('DeferredIncomeTaxExpenseBenefit', 1, 'noncash'),
    'receivables_change': ('IncreaseDecreaseInAccountsReceivable', -1, 'working_capital'),
    'inventory_change': ('IncreaseDecreaseInInventories', -1, 'working_capital'),
    'payables_change': ('IncreaseDecreaseInAccountsPayable', 1, 'working_capital'),
}


def _select_component(facts, concept, period, cutoff):
    from datetime import date
    entries = facts.get('facts', {}).get('us-gaap', {}).get(concept, {}).get('units', {}).get('USD', [])
    matches = []
    for e in entries:
        if e.get('form') != '10-K' or e.get('fp') != 'FY' or not e.get('start'):
            continue
        if e.get('end') != period or not e.get('filed') or e['filed'] > cutoff or e.get('val') is None or not e.get('accn'):
            continue
        try:
            days = (date.fromisoformat(e['end']) - date.fromisoformat(e['start'])).days
        except ValueError:
            continue
        if 330 <= days <= 380:
            matches.append(e)
    if not matches:
        return {'status':'missing', 'period_end':period}
    filed = max(e['filed'] for e in matches)
    latest = [e for e in matches if e['filed'] == filed]
    if len({(str(e['val']), e['start']) for e in latest}) != 1:
        return {'status':'ambiguous', 'period_end':period, 'filing_date':filed}
    e = latest[0]
    return {'status':'selected', 'value':str(e['val']), 'unit':'USD', 'concept':'us-gaap:'+concept,
            'period_start':e['start'], 'period_end':e['end'], 'filing_date':e['filed'],
            'accession':e['accn'], 'form':e['form']}


def build_cash_flow_evidence(facts, report, as_of):
    output = {'schema_version':'1.0.0', 'status':'insufficient_data', 'periods':[],
              'interpretation':'Cash-flow component signs follow XBRL concept definitions; selected components are not a complete reconciliation.',
              'limitations':['Company-specific extensions and untagged cash-flow lines are not inferred.',
                             'A residual does not establish misstatement or poor earnings quality.',
                             'Selected components may not exhaust the filed reconciliation.']}
    for year in report.get('financial_history', []):
        end = year['period_end']
        financials = year['financials']
        ni = financials.get('net_income', {})
        ocf = financials.get('operating_cash_flow', {})
        row = {'period_end':end, 'components':{}, 'status':'insufficient_data'}
        if ni.get('status') != 'selected' or ocf.get('status') != 'selected' or ni.get('period_start') != ocf.get('period_start'):
            output['periods'].append(row)
            continue
        target = Decimal(ocf['value']) - Decimal(ni['value'])
        total = Decimal(0)
        for label,(concept,sign,category) in COMPONENTS.items():
            selected = _select_component(facts, concept, end, as_of)
            if selected['status'] == 'selected' and selected.get('period_start') == ni.get('period_start'):
                contribution = Decimal(selected['value']) * sign
                total += contribution
                row['components'][label] = {'status':'selected','category':category,
                     'cash_flow_contribution_usd':str(contribution), 'provenance':selected}
            else:
                row['components'][label] = {'status': 'missing_or_unmatched', 'provenance': selected}
        residual = target - total
        row.update({'status':'partial_reconciliation', 'net_income_usd':ni['value'],
                    'operating_cash_flow_usd':ocf['value'], 'observed_ocf_less_ni_usd':str(target),
                    'selected_component_total_usd':str(total), 'unexplained_residual_usd':str(residual),
                    'complete_reconciliation':False,
                    'residual_is_unexplained_not_error':True})
        output['periods'].append(row)
    if any(p['status']=='partial_reconciliation' for p in output['periods']):
        output['status'] = 'partial_evidence_retrieved'
    return output
