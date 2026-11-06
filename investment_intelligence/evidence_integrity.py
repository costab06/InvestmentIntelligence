"""Conservative post-evaluation integrity guard; never upgrades LLM conclusions."""
from __future__ import annotations
import copy
import re

METRIC_TERMS = {
    'operating_cash_flow': (r'operating cash flow', r'cash flow from operations'),
    'operating_income': (r'operating income', r'operating profit'),
    'net_income': (r'net income', r'net profit'),
    'free_cash_flow': (r'free cash flow',),
    'capital_expenditures': (r'capital expenditures', r'capital spending', r'capex'),
    'revenue': (r'revenue', r'top.line'),
}


def _metric_mentions(text):
    # longest/specific phrases first; avoid 'operating income' conflation with OCF
    return {metric for metric, patterns in METRIC_TERMS.items()
            if any(re.search(r'\b'+p+r'\b', text, re.I) for p in patterns)}


def _check_statement(statement, findings):
    text = statement.get('text', '')
    ids = statement.get('finding_ids') or []
    referenced = [findings[i] for i in ids if i in findings]
    reasons = []
    if len(referenced) != len(ids) or not ids:
        reasons.append('missing_or_unknown_financial_finding')
    cited_metrics = {f.get('metric') for f in referenced}
    # Derived findings establish their formula components as well as their named metric.
    # This does not permit an unrelated metric: e.g. operating_income != operating_cash_flow.
    FORMULA_COMPONENTS = {
        ('operating_cash_flow', 'margin'): {'revenue'},
        ('operating_income', 'margin'): {'revenue'},
        ('net_income', 'margin'): {'revenue'},
        ('free_cash_flow', 'margin'): {'revenue', 'operating_cash_flow', 'capital_expenditures'},
        ('capital_expenditures', 'intensity'): {'revenue'},
        ('free_cash_flow', 'level'): {'operating_cash_flow', 'capital_expenditures'},
        ('free_cash_flow', 'growth'): {'operating_cash_flow', 'capital_expenditures'},
    }
    for f in referenced:
        cited_metrics.update(FORMULA_COMPONENTS.get((f.get('metric'), f.get('kind')), set()))
    mentioned = _metric_mentions(text)
    for metric in sorted(mentioned - cited_metrics):
        reasons.append('uncited_metric:' + metric)
    if re.search(r'\b(sustained|consecutive|multi.year|over (?:several|multiple) years)\b', text, re.I):
        # One year-over-year growth datum cannot establish a sustained trend.
        if not any(f.get('kind') in ('multi_year_growth', 'cagr', 'trend') for f in referenced):
            reasons.append('longitudinal_claim_without_longitudinal_finding')
    return reasons


def enforce_evidence_integrity(analysis):
    """Fail closed on identifiable citation mismatches; do not rewrite source audits."""
    out = copy.deepcopy(analysis)
    findings = {f['id']: f for f in out.get('findings', []) if f.get('id')}
    audits = []
    invalid = set()
    for item in out.get('qualitative_audit', []):
        sid = item.get('id')
        reasons = _check_statement(item.get('statement') or {}, findings)
        audits.append({'statement_id': sid, 'issues': reasons, 'integrity': 'failed' if reasons else 'not_disproven'})
        if reasons:
            invalid.add(sid)
            if item.get('status') != 'rejected':
                item['status'] = 'rejected'
                item['reason'] = 'Evidence integrity: ' + ', '.join(reasons)
    published = []
    for item in out.get('published_statements', []):
        if item.get('id') not in invalid:
            published.append(item)
    out['published_statements'] = published
    for item in out.get('statement_evaluations', []):
        if item.get('statement_id', item.get('id')) in invalid:
            item['integrity_override'] = 'rejected_invalid_financial_citation'
        # Dimensional relevance alone cannot justify an unqualified positive assessment.
        # Preserve source output for auditing; attach an explicit usability restriction.
        assessments = item.get('dimensions', item.get('dimension_assessments'))
        if isinstance(assessments, dict):
            for val in assessments.values():
                if isinstance(val, dict) and val.get('assessment') == 'supports':
                    val['integrity_review'] = 'requires_claim_level_entailment; relevance_not_support'
                    val['original_assessment'] = val['assessment']
                    val['assessment'] = 'insufficient_evidence'
                    val['confidence'] = None
        elif isinstance(assessments, list):
            for val in assessments:
                if isinstance(val, dict) and val.get('assessment') == 'supports':
                    val['integrity_review'] = 'requires_claim_level_entailment; relevance_not_support'
                    val['original_assessment'] = val['assessment']
                    val['assessment'] = 'insufficient_evidence'
                    val['confidence'] = None
    out['historical_statement_evidence'] = {'schema_version': '0.8.4', 'links': [
        {'signal_code': row.get('signal_code'), 'financial_evidence': row.get('financial_evidence', []),
         'direct_topic_passage_ids': row.get('direct_topic_passage_ids', []),
         'context_passage_ids': row.get('context_passage_ids', []),
         'status': 'context_only_not_claim_verified'}
        for row in out.get('historical_reconciliation', {}).get('records', [])]}
    out['evidence_integrity'] = {'schema_version': '0.8.4', 'status': 'conservative_post_evaluation_audit',
        'statements': audits, 'invalid_statement_ids': sorted(invalid),
        'note': 'A clean result does not verify semantic entailment. Original source audits remain available.'}
    from .final_report import render_final_report
    out['report_markdown'] = render_final_report(out)
    return out
