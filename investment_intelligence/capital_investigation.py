"""Evidence-first capital-investment investigation; no unsupported causal verdicts."""
from decimal import Decimal, InvalidOperation
from investment_intelligence.business_model import capital_evidence_plan

METRICS = ('revenue', 'operating_cash_flow', 'capital_expenditures')

def _history(analysis, metric):
    series = (analysis.get('historical_intelligence') or {}).get('metrics', {}).get(metric, {})
    out = {}
    for row in series.get('observations', []):
        try:
            val = Decimal(str(row['value']))
            if not val.is_finite() or (metric == 'revenue' and val <= 0):
                continue
            if row['period_end'] in out:
                raise ValueError('Duplicate fiscal period: ' + row['period_end'])
            out[row['period_end']] = {'value': val, 'provenance': row.get('provenance')}
        except (InvalidOperation, TypeError, KeyError):
            continue
    return out

def _pct(now, before):
    return str((now / abs(before) - 1) * 100) if before > 0 else None

def investigate_capital(analysis):
    """Calculate matched-period cash investment and test alternative explanations.

    Deliberately does not infer returns on invested capital or AI ROI from spending.
    """
    data = {m: _history(analysis, m) for m in METRICS}
    periods = sorted(set.intersection(*(set(v) for v in data.values())))
    result = {'schema_version': '1.0.0', 'status': 'insufficient_evidence',
              'topic': 'capital_investment_economics', 'periods': [], 'observations': [],
              'hypotheses': [], 'next_evidence': [], 'limitations': [],
              'publication_eligible': False}
    for p in periods:
        rev = data['revenue'][p]['value']; ocf = data['operating_cash_flow'][p]['value']; capex = data['capital_expenditures'][p]['value']
        if rev <= 0: continue
        result['periods'].append({'period_end': p, 'revenue_usd': str(rev),
             'operating_cash_flow_usd': str(ocf), 'capital_expenditures_usd': str(capex),
             'free_cash_flow_usd': str(ocf-capex),
             'capex_to_revenue_percent': str(capex/rev*100),
             'capex_to_ocf_percent': str(capex/ocf*100) if ocf > 0 else None,
             'source_provenance': {m: data[m][p]['provenance'] for m in METRICS}})
    rows = result['periods']
    if len(rows) < 2:
        result['limitations'].append('At least two matched annual periods required')
        return result
    a,b = rows[-2:]
    cap0 = (data['capital_expenditures'][a['period_end']].get('provenance') or {}).get('concept')
    cap1 = (data['capital_expenditures'][b['period_end']].get('provenance') or {}).get('concept')
    if cap0 and cap1 and cap0 != cap1:
        result['status'] = 'noncomparable_capex_definitions'
        result['limitations'].append('CapEx reporting concepts differ between compared years; growth comparison withheld.')
        return result
    result['capex_definition_check'] = {'status': 'same_xbrl_concept' if cap0 and cap1 else 'provenance_incomplete',
        'concept': cap0 if cap0 == cap1 else None,
        'economic_comparability': 'not_independently_verified'}
    result['limitations'].append('Matching XBRL concepts do not independently verify economic comparability or the split between physical and intangible investment.')
    current, previous = {}, {}
    for m in METRICS:
        current[m] = data[m][b['period_end']]['value']
        previous[m] = data[m][a['period_end']]['value']
    fcf_now = current['operating_cash_flow']-current['capital_expenditures']
    fcf_prev = previous['operating_cash_flow']-previous['capital_expenditures']
    delta_ocf = current['operating_cash_flow']-previous['operating_cash_flow']
    delta_capex = current['capital_expenditures']-previous['capital_expenditures']
    delta_fcf = fcf_now-fcf_prev
    assert delta_fcf == delta_ocf-delta_capex
    result['observations'] = [
      {'code': 'cash_flow_bridge', 'status': 'verified', 'from': a['period_end'], 'to': b['period_end'],
       'delta_ocf_usd': str(delta_ocf), 'delta_capex_usd': str(delta_capex),
       'delta_fcf_usd': str(delta_fcf), 'identity': 'delta_fcf = delta_ocf - delta_capex',
       'fcf_growth_percent': _pct(fcf_now, fcf_prev),
       'ocf_growth_percent': _pct(current['operating_cash_flow'], previous['operating_cash_flow']),
       'capex_growth_percent': _pct(current['capital_expenditures'], previous['capital_expenditures'])},
      {'code': 'capital_intensity', 'status': 'verified', 'from': a['period_end'], 'to': b['period_end'],
       'capex_to_revenue_pp_change': str(Decimal(b['capex_to_revenue_percent'])-Decimal(a['capex_to_revenue_percent']))}
    ]
    ocf_growth = _pct(current['operating_cash_flow'], previous['operating_cash_flow'])
    capex_growth = _pct(current['capital_expenditures'], previous['capital_expenditures'])
    growth_supported = (capex_growth is not None and ocf_growth is not None)
    result['hypotheses'] = [
      {'id':'CAP-H1', 'proposition':'Capital investment is growing faster than operating cash generation',
       'status': ('supported_for_observed_interval' if Decimal(capex_growth) > Decimal(ocf_growth) else 'not_supported_for_observed_interval') if growth_supported else 'insufficient_data',
       'predicate': 'capex_growth_percent > ocf_growth_percent',
       'predicate_inputs': {'capex_growth_percent': capex_growth, 'ocf_growth_percent': ocf_growth},
       'evidence':['cash_flow_bridge'], 'challenge':'An annual cash-flow bridge cannot establish long-term investment returns.',
       'causal_assessment':'not_established'},
      {'id':'CAP-H2', 'proposition':'Higher infrastructure spending is productive growth investment',
       'status':'unresolved', 'evidence':['cash_flow_bridge','capital_intensity'],
       'challenge':'Spending may reflect replacement, capacity prebuild, price inflation or project delays; attributable future cash returns are not measured.',
       'causal_assessment':'not_established'},
      {'id':'CAP-H3', 'proposition':'Lower free cash flow implies operating deterioration',
       'status':'not_established', 'evidence':['cash_flow_bridge'],
       'challenge':'Higher operating cash flow can coexist with lower free cash flow when capex rises faster.',
       'causal_assessment':'not_established'},
      {'id':'CAP-H4', 'proposition':'Industry output expansion explains issuer revenue growth',
       'status':'unresolved', 'evidence':['industry_corroboration'],
       'challenge':'BEA real US gross output and worldwide nominal issuer revenue are not like-for-like; market share cannot be inferred.',
       'causal_assessment':'not_established'}
    ]
    plan = capital_evidence_plan(analysis)
    result['business_model_evidence_plan'] = {k:v for k,v in plan.items() if k != 'questions'}
    result['next_evidence'] = plan['questions']
    result['limitations'] = ['Financial figures are annual issuer observations, not causal attribution.',
      'Free cash flow is defined as operating cash flow minus capital expenditures; financing leases may need separate analysis.',
      'Industry growth is contextual and does not validate issuer ROI.',
      'No investment recommendation or forecast is established.']
    result['status'] = 'observations_verified_hypotheses_open'
    return result

def attach_capital_investigation(analysis):
    result = dict(analysis)
    investigation = investigate_capital(analysis)
    result['capital_investigation'] = investigation
    lines = ['\n## Capital Investment Economics — Evidence Investigation (Phase 6)',
             '', 'Cash-flow decomposition is deterministic. Explanations remain hypotheses, not verified investment conclusions.', '']
    for obs in investigation['observations']:
        if obs['code'] == 'cash_flow_bridge':
            lines.append(f"- {obs['from']} to {obs['to']}: ΔOCF ${Decimal(obs['delta_ocf_usd'])/Decimal(10**9):,.2f}B; ΔCapEx ${Decimal(obs['delta_capex_usd'])/Decimal(10**9):,.2f}B; ΔFCF ${Decimal(obs['delta_fcf_usd'])/Decimal(10**9):,.2f}B (verified accounting bridge).")
    for h in investigation['hypotheses']:
        lines.append(f"- **{h['id']} / {h['status']}**: {h['proposition']}. Challenge: {h['challenge']}")
    lines.extend(['', '### Evidence needed before causal conclusions'])
    lines.extend('- '+q['question'] for q in investigation['next_evidence'])
    result['report_markdown'] = result.get('report_markdown', '') + '\n'.join(lines) + '\n'
    return result
