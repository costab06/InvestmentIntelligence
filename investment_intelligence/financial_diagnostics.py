"""Explain missing financial signal inputs without filling them with guesses."""
from investment_intelligence.investigation_registry import REGISTRY, _observations

def diagnose_financial_coverage(analysis, registry):
    records=[]
    for entry in registry['investigations']:
        if entry['status'] != 'insufficient_data':
            continue
        metrics={}
        for name in entry['required_metrics']:
            rows=_observations(analysis,name)
            metrics[name]={'periods':sorted(rows),'observation_count':len(rows)}
        common=set.intersection(*(set(v['periods']) for v in metrics.values())) if metrics else set()
        records.append({'investigation':entry['id'],'reason':'fewer_than_two_matched_periods',
            'metrics':metrics,'matched_periods':sorted(common),
            'next_action':'Inspect SEC XBRL tag normalization, fiscal-period alignment, and source filing coverage; do not substitute estimated values.'})
    return {'schema_version':'1.0.0','status':'gaps_detected' if records else 'no_signal_input_gaps', 'records':records}
