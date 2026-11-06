"""Company-neutral signal registry. Deterministic triggers, no causal verdicts."""
from decimal import Decimal, InvalidOperation

REGISTRY = (
    {'id':'capital_investment_economics','metrics':('operating_cash_flow','capital_expenditures','revenue'),
     'trigger':'capex_growth_exceeds_ocf_growth', 'investigator':'capital_investigation',
     'evidence_needs':('capital spending composition','incremental return on capital','utilization and monetization')},
    {'id':'earnings_quality','metrics':('net_income','operating_cash_flow'),
     'trigger':'earnings_growth_exceeds_ocf_growth','investigator':None,
     'evidence_needs':('working capital changes','accruals','cash conversion')},
    {'id':'revenue_margin_divergence','metrics':('revenue','operating_income'),
     'trigger':'revenue_growth_and_operating_income_decline','investigator':None,
     'evidence_needs':('segment margins','pricing','cost structure')},
)

def _observations(analysis, metric):
    rows = ((analysis.get('historical_intelligence') or {}).get('metrics') or {}).get(metric, {}).get('observations', [])
    result = {}
    for row in rows:
        try:
            n = Decimal(str(row['value']))
            if n.is_finite() and row['period_end'] not in result:
                result[row['period_end']] = n
        except (KeyError, TypeError, InvalidOperation):
            pass
    return result

def select_investigations(analysis):
    selected = []
    for spec in REGISTRY:
        series = {m: _observations(analysis,m) for m in spec['metrics']}
        periods = sorted(set.intersection(*(set(x) for x in series.values())))
        entry = {'id':spec['id'],'status':'insufficient_data','trigger':spec['trigger'],
                 'required_metrics':list(spec['metrics']),'evidence_needs':list(spec['evidence_needs']),
                 'investigator':spec['investigator'],'periods_evaluated':periods[-2:]}
        if len(periods) >= 2:
            old,new = periods[-2:]
            if spec['id'] == 'capital_investment_economics':
                rows = (((analysis.get('historical_intelligence') or {}).get('metrics') or {}).get('capital_expenditures') or {}).get('observations', [])
                by_end = {r.get('period_end'): (r.get('provenance') or {}).get('concept') for r in rows}
                if by_end.get(old) and by_end.get(new) and by_end[old] != by_end[new]:
                    entry['status'] = 'noncomparable_capex_definitions'
                    entry['limitations'] = ['CapEx XBRL concepts differ across comparison years; do not compare growth without definition review.']
                    selected.append(entry)
                    continue
                if by_end.get(old) and by_end.get(new):
                    entry['capex_definition_check'] = {'status':'same_xbrl_concept',
                        'concept':by_end[old], 'economic_comparability':'not_independently_verified'}
            def growth(m):
                a,b=series[m][old],series[m][new]
                return (b-a)/abs(a) if a != 0 else None
            g={m:growth(m) for m in spec['metrics']}
            if all(v is not None for v in g.values()):
                t=spec['trigger']
                matched=(g['capital_expenditures']>g['operating_cash_flow'] if t=='capex_growth_exceeds_ocf_growth'
                         else g['net_income']>g['operating_cash_flow'] if t=='earnings_growth_exceeds_ocf_growth'
                         else g['revenue']>0 and g['operating_income']<0)
                entry['status']='triggered' if matched else 'not_triggered'
                entry['observed_growth_percent']={k:str(v*100) for k,v in g.items()}
        selected.append(entry)
    return {'schema_version':'1.0.0','investigations':selected,
            'limitations':['Signals identify investigation priorities; they do not establish causality.',
                           'Applicability to financial institutions and nonstandard cash-flow reporting requires further rules.']}
