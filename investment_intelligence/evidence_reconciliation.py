"""v0.8.3: conservative, reproducible reconciliation of historical LLM proposals.

This is *not* semantic entailment or independent verification of issuer claims.
Classification is a documented, rule-based evidence triage. Original proposals remain intact.
"""
from __future__ import annotations
import re

# Signal-specific, issuer-language indicators. Context is never promoted to proof of causality.
RULES = {
 'revenue_cagr': {
   'direct': (('revenue', 'growth'), ('revenue', 'increased'), ('revenue', 'driven')),
   'context': (('customer', 'demand'), ('subscription',), ('cloud', 'growth'))},
 'capex_outpaces_ocf': {
   'direct': (('capital expenditures', 'datacenter'), ('capital expenditures', 'ai'),
              ('capital', 'investment', 'infrastructure')),
   'context': (('infrastructure', 'capacity'), ('datacenter', 'energy'), ('cloud', 'strategy'))},
 'fcf_two_year_decline': {
   'direct': (('free cash flow', 'capital expenditures'), ('free cash flow', 'declined'),
              ('cash flow', 'capital expenditures')),
   'context': (('capital expenditures', 'datacenter'), ('capital expenditures', 'ai'),
               ('infrastructure', 'capacity'), ('datacenter', 'power'))},
}

def _normalize(text):
    return re.sub(r'\s+', ' ', str(text or '').lower())

def classify_passage(signal, doc):
    """Classify topical relevance; 'direct' does not mean verified causal explanation."""
    text = _normalize(doc.get('text'))
    rules = RULES.get(signal, {'direct': (), 'context': ()})
    for level in ('direct', 'context'):
        if any(all(term in text for term in group) for group in rules[level]):
            return level
    return 'not_relevant'

def reconcile_history(analysis):
    """Append reconciliation without changing any v0.7.3 gate or v0.8.2 proposal."""
    result = dict(analysis)
    investigations = analysis.get('historical_investigations', {}).get('records', [])
    docs = {d['id']: d for d in analysis.get('document_evidence', []) if isinstance(d, dict) and d.get('id')}
    records = []
    for proposal in investigations:
        code = proposal.get('signal_code', '')
        cited = set(proposal.get('evidence_ids') or [])
        retrieved = set(proposal.get('retrieved_document_ids') or [])
        entries = []
        for did in sorted(cited | retrieved):
            doc = docs.get(did)
            if not doc:
                entries.append({'id': did, 'role': 'unavailable', 'cited_by_model': did in cited})
                continue
            entries.append({'id': did, 'role': classify_passage(code, doc),
                            'cited_by_model': did in cited,
                            'source_document': doc.get('source_document'),
                            'source_location': doc.get('source_location')})
        cited_not_relevant = [e['id'] for e in entries if e['cited_by_model'] and e['role'] in ('not_relevant', 'unavailable')]
        direct = [e['id'] for e in entries if e['role'] == 'direct']
        context = [e['id'] for e in entries if e['role'] == 'context']
        if direct:
            status = 'issuer_disclosure_relevant'
        elif context:
            status = 'context_only'
        else:
            status = 'no_relevant_disclosure_identified'
        records.append({
            'signal_code': code, 'observation': proposal.get('observation'),
            'dimensions': proposal.get('dimensions', []),
            'financial_evidence': proposal.get('financial_evidence', []),
            'evidence_status': status, 'passages': entries,
            'direct_topic_passage_ids': direct, 'context_passage_ids': context,
            'unsupported_model_citation_ids': cited_not_relevant,
            'model_assessment': proposal.get('assessment'),
            'model_explanation': proposal.get('management_explanation'),
            'model_implication': proposal.get('investment_implication'),
            'reconciliation_note': (
                'Issuer passages are topically classified by deterministic rules; '
                'no causal attribution, financial return, or investment implication is verified. '
                'A cited passage is not automatically evidence for every claim in the model explanation.'),
            'unresolved': [
                'Whether identified investments caused the measured financial relationship',
                'Whether future returns will justify investment costs',
            ] if code in ('capex_outpaces_ocf', 'fcf_two_year_decline') else [
                'Which factors quantitatively account for the observed historical growth'],
        })
    result['historical_reconciliation'] = {
        'schema_version': '0.8.3', 'method': 'deterministic_issuer_passage_triage',
        'status': 'context_reconciled_not_independently_verified', 'records': records,
        'note': 'Does not modify v0.7.3 statement validation or v0.8.2 model proposals.'}
    if isinstance(result.get('report_markdown'), str):
        lines = ['', '## Historical Evidence Reconciliation (v0.8.3)', '',
                 'Issuer disclosures are management claims. Passage relevance is not proof of causation.', '']
        for row in records:
            lines += [f"### {row['signal_code']} — {row['evidence_status']}", '',
                      'Established financial observation: ' + str(row['observation']),
                      'Direct-topic passages: ' + (', '.join(row['direct_topic_passage_ids']) or 'none'),
                      'Contextual passages: ' + (', '.join(row['context_passage_ids']) or 'none'),
                      'Model citations lacking signal-specific topical support: ' +
                      (', '.join(row['unsupported_model_citation_ids']) or 'none'),
                      'Not established: ' + '; '.join(row['unresolved']), '']
        result['report_markdown'] = result['report_markdown'].rstrip() + '\n' + '\n'.join(lines) + '\n'
    return result
