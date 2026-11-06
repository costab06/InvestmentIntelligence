"""Company-neutral, deterministic earnings/cash-conversion investigation."""
from decimal import Decimal, InvalidOperation

METRICS = ('net_income', 'operating_cash_flow', 'revenue')


def _series(analysis, name):
    rows = (((analysis.get('historical_intelligence') or {}).get('metrics') or {}).get(name) or {}).get('observations', [])
    result = {}
    for row in rows:
        try:
            value = Decimal(str(row['value']))
            period = str(row['period_end'])
            if value.is_finite() and period not in result:
                result[period] = {'value': value, 'provenance': row.get('provenance')}
        except (KeyError, TypeError, InvalidOperation):
            continue
    return result


def investigate_earnings_quality(analysis, cash_flow_evidence=None):
    data = {name: _series(analysis, name) for name in METRICS}
    periods = sorted(set(data['net_income']) & set(data['operating_cash_flow']))
    result = {'schema_version':'1.0.0', 'topic':'earnings_quality', 'status':'insufficient_evidence',
              'periods':[], 'observations':[], 'hypotheses':[], 'next_evidence':[],
              'publication_eligible':False,
              'limitations':['Operating cash flow minus net income is not a direct measure of accrual manipulation.',
                             'Cash conversion may vary with working capital, deferred revenue, taxes and noncash expenses.']}
    for p in periods:
        ni = data['net_income'][p]['value']; ocf = data['operating_cash_flow'][p]['value']
        rev = data['revenue'].get(p, {}).get('value')
        result['periods'].append({'period_end':p,'net_income_usd':str(ni),'operating_cash_flow_usd':str(ocf),
            'cash_earnings_gap_usd':str(ocf-ni),
            'ocf_to_net_income':str(ocf/ni) if ni > 0 else None,
            'ocf_margin_percent':str(100*ocf/rev) if rev and rev>0 else None,
            'source_provenance':{m:data[m].get(p,{}).get('provenance') for m in METRICS}})
    if len(periods) < 2:
        result['limitations'].append('Two matched periods of net income and operating cash flow are required.')
        return result
    old,new=periods[-2:]
    ni0=data['net_income'][old]['value']; ni1=data['net_income'][new]['value']
    cf0=data['operating_cash_flow'][old]['value']; cf1=data['operating_cash_flow'][new]['value']
    if ni0 <= 0 or cf0 <= 0:
        result['limitations'].append('Positive prior-period net income and cash flow required for growth comparison.')
        return result
    ni_growth=(ni1/ni0-1)*100; cf_growth=(cf1/cf0-1)*100
    result['observations']=[{'id':'EQ-O1','status':'calculated','from':old,'to':new,
         'net_income_growth_percent':str(ni_growth),'operating_cash_flow_growth_percent':str(cf_growth),
         'growth_spread_percentage_points':str(ni_growth-cf_growth)},
        {'id':'EQ-O2','status':'calculated','from':old,'to':new,
         'cash_earnings_gap_change_usd':str((cf1-ni1)-(cf0-ni0)),
         'ocf_to_net_income_previous':str(cf0/ni0),'ocf_to_net_income_current':str(cf1/ni1) if ni1>0 else None}]
    result['hypotheses']=[
      {'id':'EQ-H1','proposition':'Earnings growth outpaced operating cash flow growth in the observed interval',
       'status':'supported_for_observed_interval' if ni_growth>cf_growth else 'not_supported_for_observed_interval',
       'evidence':['EQ-O1'],'causal_assessment':'not_established'},
      {'id':'EQ-H2','proposition':'Working-capital movements explain the growth difference',
       'status':'unresolved','evidence':['EQ-O1','EQ-O2'],'causal_assessment':'not_established'},
      {'id':'EQ-H3','proposition':'The difference indicates deteriorating earnings quality',
       'status':'not_established','evidence':['EQ-O1','EQ-O2'],'causal_assessment':'not_established'}]
    result['next_evidence']=[
      {'question':'Which working-capital accounts explain cash conversion?','needed':'Receivables, inventories, payables, deferred revenue and other operating assets/liabilities from cash-flow statement','status':'not_verified'},
      {'question':'How much of the difference is noncash accounting?','needed':'Stock-based compensation, depreciation, deferred taxes and other reconciliation line items','status':'not_verified'},
      {'question':'Is the gap temporary or persistent?','needed':'Several comparable annual periods and quarterly seasonality','status':'not_verified'}]
    if cash_flow_evidence is not None:
        _resolve_cash_flow_hypotheses(result, cash_flow_evidence, old, new)
    result['status']='observations_verified_hypotheses_open'
    return result


def attach_earnings_quality(analysis, cash_flow_evidence=None):
    enriched=dict(analysis)
    enriched['earnings_quality_investigation']=investigate_earnings_quality(analysis, cash_flow_evidence)
    return enriched

def _resolve_cash_flow_hypotheses(result, evidence, old, new):
    """Match annual evidence to analysis, preserving unresolved items."""
    by_end = {p.get('period_end'): p for p in evidence.get('periods', [])}
    a, b = by_end.get(old), by_end.get(new)
    if not a or not b or any(p.get('status') != 'partial_reconciliation' for p in (a, b)):
        return
    expected = {p['period_end']: p for p in result['periods']}
    for p in (a, b):
        ep = expected.get(p['period_end'], {})
        if Decimal(str(p['net_income_usd'])) != Decimal(str(ep.get('net_income_usd'))) or Decimal(str(p['operating_cash_flow_usd'])) != Decimal(str(ep.get('operating_cash_flow_usd'))):
            result['limitations'].append('Cash-flow bridge disagrees with earnings analysis; evidence not promoted.')
            return
    components = []
    for name in sorted(set(a.get('components', {})) | set(b.get('components', {}))):
        before, after = a.get('components', {}).get(name, {}), b.get('components', {}).get(name, {})
        if before.get('status') != 'selected' or after.get('status') != 'selected': continue
        bp, ap = before.get('provenance') or {}, after.get('provenance') or {}
        if bp.get('concept') != ap.get('concept') or bp.get('unit') != 'USD' or ap.get('unit') != 'USD': continue
        if bp.get('period_end') != old or ap.get('period_end') != new: continue
        try:
            delta = Decimal(after['cash_flow_contribution_usd']) - Decimal(before['cash_flow_contribution_usd'])
        except (InvalidOperation, KeyError, TypeError): continue
        components.append({'component': name, 'category': after.get('category'),
                           'prior_contribution_usd': before['cash_flow_contribution_usd'],
                           'current_contribution_usd': after['cash_flow_contribution_usd'],
                           'change_usd': str(delta), 'concept': ap['concept'],
                           'prior_accession': bp.get('accession'), 'current_accession': ap.get('accession')})
    if not components: return
    components.sort(key=lambda c: abs(Decimal(c['change_usd'])), reverse=True)
    delta_gap = Decimal(b['observed_ocf_less_ni_usd']) - Decimal(a['observed_ocf_less_ni_usd'])
    selected_delta = sum((Decimal(c['change_usd']) for c in components), Decimal(0))
    residual_delta = delta_gap - selected_delta
    wc = sum((Decimal(c['change_usd']) for c in components if c['category'] == 'working_capital'), Decimal(0))
    noncash = sum((Decimal(c['change_usd']) for c in components if c['category'] == 'noncash'), Decimal(0))
    result['observations'].append({'id': 'EQ-O3', 'status': 'calculated_from_filed_components',
        'from': old, 'to': new, 'component_changes': components,
        'working_capital_change_usd': str(wc), 'noncash_change_usd': str(noncash),
        'matched_component_change_usd': str(selected_delta),
        'observed_cash_earnings_gap_change_usd': str(delta_gap),
        'unexplained_change_usd': str(residual_delta),
        'identity': 'observed_cash_earnings_gap_change = matched_component_change + unexplained_change',
        'complete_reconciliation': False, 'evidence_source': 'cash-flow-evidence.json'})
    h2 = next(h for h in result['hypotheses'] if h['id'] == 'EQ-H2')
    h2['status'] = ('supported_as_partial_contributor' if wc < 0 and delta_gap < 0
                    else 'not_supported_as_deterioration_driver' if wc >= 0 and delta_gap < 0
                    else 'mixed_or_inconclusive')
    h2['evidence'].append('EQ-O3')
    h2['working_capital_change_usd'] = str(wc)
    h2['causal_assessment'] = 'accounting_bridge_only'
    h2['qualification'] = 'Accounting contribution does not establish why balances changed or whether the change is adverse.'
    for item in result['next_evidence']:
        if item['question'].startswith('Which working-capital') or item['question'].startswith('How much of the difference'):
            item['status'] = 'partially_verified'
    result['limitations'].append('Only identically tagged components in both fiscal years enter the year-over-year bridge; missing and company-specific components remain unresolved.')
