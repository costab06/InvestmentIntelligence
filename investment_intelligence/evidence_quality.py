"""Phase 16: auditable coverage warnings, question-specific triage, and temporal routing.

No SEC HTTP requests, no claims of entailment, and no publication promotion.
"""
from __future__ import annotations
import re
from decimal import Decimal, InvalidOperation


def _words(s):
    return set(re.findall(r'[a-z]+', str(s).lower()))


def assess_coverage(disclosure):
    reports = []
    for d in disclosure.get('filing_diagnostics', []):
        types = d.get('block_type_counts') or {}
        count = d.get('total_blocks', 0)
        table_only = count > 0 and types.get('table', 0) == count
        reports.append({
            'accession': d.get('accession'),
            'structural_status': 'table_only_suspicious' if table_only else 'no_structural_warning',
            'table_only': table_only,
            'raw_filing_comparison': 'not_performed',
            'raw_vs_parsed_coverage': None,
            'reason': ('Every parsed block is a table; narrative sections may be missing.' if table_only
                       else 'No table-only warning; completeness remains unverified.'),
        })
    return reports


# These are diagnostic topic-specific anchors, not proof that a question is answered.
ANCHORS = {
    'lease': ({'lease', 'leases'}, {'cash', 'paid', 'finance', 'operating', 'depreciation'}),
    'supplier': ({'supplier', 'suppliers', 'purchase', 'manufacturing'}, {'obligations', 'commitments', 'capacity', 'agreement'}),
    'inventory': ({'inventory', 'inventories'}, {'purchase', 'obligations', 'receivables', 'cash', 'channel'}),
    'utilization': ({'utilization', 'capacity'}, {'utilization', 'revenue', 'margin', 'demand'}),
    'returns': ({'returns', 'return', 'invested'}, {'capital', 'profit', 'cash', 'segment'}),
}


def _topic(task):
    q = _words(task.get('question', '') + ' ' + task.get('needed', ''))
    if 'leases' in q or 'lease' in q: return 'lease'
    if 'supplier' in q or 'manufacturing' in q: return 'supplier'
    if 'inventory' in q or 'inventories' in q: return 'inventory'
    if 'utilization' in q: return 'utilization'
    if 'returns' in q or 'return' in q: return 'returns'
    return None


def assess_candidates(disclosure, orchestration):
    tasks = {t['id']: t for t in orchestration.get('tasks', [])}
    out = {}
    for task_id, result in disclosure.get('tasks', {}).items():
        task = tasks.get(task_id, {})
        topic = _topic(task)
        primary, secondary = ANCHORS.get(topic, (set(), set()))
        candidates = []
        for index, hit in enumerate(result.get('hits', [])):
            passage = hit.get('passage', '')
            w = _words(passage)
            p = len(primary & w)
            s = len(secondary & w)
            # Reject broad balance sheets as answers to causal or longitudinal questions.
            is_balance_sheet = ('total assets' in passage.lower() and 'current liabilities' in passage.lower())
            is_liquidity = ('fixed-income securities' in passage.lower() and 'short-term investments' in passage.lower())
            truncated = bool(hit.get('passage_truncated'))
            if is_balance_sheet or is_liquidity:
                grade = 'context_only'
            elif p and s:
                grade = 'specific_candidate_unverified'
            else:
                grade = 'context_only'
            candidates.append({'hit_index': index, 'grade': grade,
                               'topic': topic, 'anchor_primary_matches': p,
                               'anchor_secondary_matches': s,
                               'passage_truncated': truncated,
                               'limitation': 'Candidate relevance only; does not establish entailment or causality.'})
        out[task_id] = {'status': result.get('status'), 'candidates': candidates,
                        'question_answered': 'not_evaluated'}
    return out


def analyze_cash_conversion_periods(cash_flow):
    periods = []
    for p in (cash_flow or {}).get('periods', []):
        try:
            ni = Decimal(str(p['net_income_usd']))
            ocf = Decimal(str(p['operating_cash_flow_usd']))
            if ni == 0:
                raise InvalidOperation
            periods.append({'period_end': p['period_end'],
                            'ocf_to_net_income': str(ocf / ni),
                            'ocf_less_net_income_usd': str(ocf - ni),
                            'complete_reconciliation': bool(p.get('complete_reconciliation', False))})
        except (KeyError, TypeError, ValueError, InvalidOperation, ArithmeticError):
            continue
    periods.sort(key=lambda p: p['period_end'])
    return {'status': 'descriptive_history_available' if len(periods) >= 3 else 'insufficient_periods',
            'periods': periods, 'period_count': len(periods),
            'persistence_conclusion': 'not_established',
            'limitations': ['Historical ratios do not establish whether a gap is temporary or persistent.',
                            'Cash-flow reconciliations may be incomplete.',
                            'Quarterly seasonality is not assessed.']}


def build_evidence_quality(disclosure, orchestration, cash_flow):
    temporal = analyze_cash_conversion_periods(cash_flow)
    routed = []
    for t in orchestration.get('tasks', []):
        q = (t.get('question') or '').lower()
        if ('temporary' in q or 'persistent' in q) and ('gap' in q or 'cash' in q):
            routed.append({'task_id': t['id'], 'route': 'structured_cash_flow_history',
                           'status': temporal['status'], 'narrative_search_result_retained': True})
    return {'schema_version': '1.0.0', 'coverage': assess_coverage(disclosure),
            'candidate_triage': assess_candidates(disclosure, orchestration),
            'cash_conversion_history': temporal, 'temporal_task_routes': routed,
            'hypothesis_status_changed': False, 'publication_eligible': False,
            'limitations': ['Raw SEC filing bytes are not available to this layer; raw-versus-parsed coverage cannot be measured.',
                            'Table-only parsing is flagged, not automatically repaired.',
                            'Candidate relevance is heuristic; entailment has not been evaluated.']}
