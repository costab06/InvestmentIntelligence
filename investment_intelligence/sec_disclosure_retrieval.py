"""Passage-level retrieval over SECAgents' already-fetched, verified parsed filings.

Retrieval is lexical candidate discovery, NOT entailment or independent verification.
"""
from __future__ import annotations
import hashlib
import json
import re

# Conservative heuristics: diagnostics and passage triage, not causal inference.
DIRECT_TERMS = {'lease': {'lease','leases','leasing'}, 'inventory': {'inventory','inventories'}, 'supplier': {'supplier','suppliers','purchase','manufacturing'}, 'capacity': {'capacity','utilization','datacenter','datacenters'}, 'capital': {'capital','capex','expenditures','equipment'}}
from pathlib import Path

STOP = set('which what how does do is are can could versus versus over from with without into about their there these those where much more most than that this and the for its issuer reported available measurable future support supports affect between versus'.split())
SYNONYMS = {
    'capex': {'capital', 'expenditures', 'property', 'equipment', 'investments'},
    'manufacturing': {'manufacturing', 'foundry', 'fabrication', 'suppliers'},
    'supplier': {'supplier', 'suppliers', 'purchase', 'commitments', 'obligations'},
    'inventory': {'inventory', 'inventories', 'channel', 'stock'},
    'receivables': {'receivables', 'customers', 'accounts'},
    'leases': {'lease', 'leases', 'leasing', 'right-of-use'},
    'utilization': {'utilization', 'capacity', 'datacenter', 'data', 'centers'},
    'cash': {'cash', 'operating', 'flows'},
    'returns': {'returns', 'profit', 'margins', 'capital'},
}

def terms(s):
    words = set(re.findall(r'[a-z][a-z-]{3,}', str(s).lower())) - STOP
    expanded = set(words)
    for w in words:
        if w in SYNONYMS:
            expanded.update(SYNONYMS[w])
    return expanded

# Parser-compatibility layer. Keep original block indices for provenance.
TEXT_KEYS = ('text', 'content', 'paragraph', 'body', 'value', 'plain_text', 'raw_text')
CONTAINER_KEYS = ('paragraphs', 'children', 'items', 'lines', 'spans', 'runs', 'cells', 'rows')
SKIP_KEYS = {'html', 'raw_html', 'metadata', 'attributes', 'style', 'source', 'url', 'href'}


def _text_parts(node, depth=0):
    if depth > 8:
        return []
    if isinstance(node, str):
        return [node]
    if isinstance(node, list):
        return [piece for item in node[:5000] for piece in _text_parts(item, depth + 1)]
    if not isinstance(node, dict):
        return []
    out = []
    for key in TEXT_KEYS:
        if key in node:
            out.extend(_text_parts(node[key], depth + 1))
    for key in CONTAINER_KEYS:
        if key in node:
            out.extend(_text_parts(node[key], depth + 1))
    # Avoid scraping metadata or arbitrary JSON keys as filing narrative.
    return out


def normalize_block(block):
    if not isinstance(block, dict):
        return ''
    return ' '.join(' '.join(_text_parts(block)).split())


def block_diagnostics(blocks):
    from collections import Counter
    types = Counter(str(b.get('type', '<missing>')) for b in blocks if isinstance(b, dict))
    fields = Counter(k for b in blocks if isinstance(b, dict) for k in b.keys())
    normalized = [normalize_block(b) for b in blocks]
    return normalized, dict(types.most_common(20)), dict(fields.most_common(20))

def retrieve_disclosures(tasks, parsed_paths, *, cik, as_of, max_hits=3, min_score=2):
    """Search existing parsed 10-K/10-Q blocks, retaining auditable filing provenance.

    A missing artifact is not a negative search. Only fully parsed and validated
    documents count as searched; no online requests are made here.
    """
    corpus = []
    sources = []
    errors = []
    diagnostics = []
    for path in parsed_paths:
        try:
            raw = Path(path).read_bytes()
            obj = json.loads(raw)
            source = obj['source']
            if int(source['cik']) != int(cik):
                raise ValueError('CIK mismatch')
            accession = source['accession_number']
            form = source['filing_type']
            date = source['filing_date']
            if form not in ('10-K', '10-Q') or not re.fullmatch(r'\d{4}-\d{2}-\d{2}', date) or date > as_of:
                raise ValueError('ineligible filing')
            if not re.fullmatch(r'\d{10}-\d{2}-\d{6}', accession):
                raise ValueError('invalid accession')
            blocks = obj['document']['blocks']
            if not isinstance(blocks, list):
                raise ValueError('blocks not a list')
            digest = hashlib.sha256(raw).hexdigest()
            normalized, type_histogram, field_histogram = block_diagnostics(blocks)
            eligible_count = sum(bool(t) for t in normalized)
            characters = sum(map(len, normalized))
            # These are heuristic flags, not raw-filing completeness proofs.
            suspect = eligible_count == 0 or characters < 30000
            diagnostics.append({'accession': accession, 'total_blocks': len(blocks),
                                'text_bearing_blocks': eligible_count,
                                'eligible_text_blocks': eligible_count,
                                'eligible_text_characters': characters,
                                'block_type_counts': type_histogram,
                                'block_field_counts': field_histogram,
                                'parsed_artifact_bytes': len(raw),
                                'coverage_status': 'suspect_incomplete' if suspect else 'not_flagged',
                                'coverage_basis': 'normalized_text_heuristic_no_raw_filing_comparison'})
            sources.append({'accession': accession, 'form': form, 'filing_date': date, 'source_sha256': digest, 'blocks': len(blocks)})
            for idx, txt in enumerate(normalized):
                if len(txt) < 65:
                    continue
                corpus.append({'text': txt, 'block_index': idx, 'accession': accession, 'form': form,
                               'filing_date': date, 'source_sha256': digest,
                               'source_document': f'{cik}:{accession}'})
        except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
            errors.append({'path': str(path), 'error': str(exc)})
    results = {}
    for task in tasks:
        if task.get('source') != 'sec_filing_disclosures':
            continue
        query = terms((task.get('question') or '') + ' ' + (task.get('needed') or ''))
        ranked = []
        direct = set()
        for key, vocab in DIRECT_TERMS.items():
            if key in query or (query & vocab):
                direct |= vocab
        for p in corpus:
            found = query & terms(p['text'])
            score = len(found)
            if score >= min_score:
                ranked.append((score, p))
        ranked.sort(key=lambda x: (-x[0], -len(x[1]['text']), x[1]['accession'], x[1]['block_index']))
        hits = []
        for score, p in ranked[:max_hits]:
            passage_terms = terms(p['text'])
            # Context-only passages are retained for audit but not claimed to answer.
            is_heading = p['text'].lower().rstrip().endswith(('as follows:', 'below:', 'following:'))
            direct_match = bool(direct & passage_terms)
            relevance = ('incomplete_table_reference' if is_heading else
                         'topic_relevant_unverified' if direct_match else 'contextual_or_irrelevant')
            hits.append({**{k:v for k,v in p.items() if k != 'text'},
                         'source_location': f"block:{p['block_index']}",
                         'passage': p['text'][:1200], 'passage_truncated': len(p['text']) > 1200,
                         'lexical_score': score, 'relevance': relevance,
                         'entailment': 'not_evaluated'})
        suspect_all = len(diagnostics) >= 2 and all(d['coverage_status'] == 'suspect_incomplete' for d in diagnostics)
        results[task['id']] = {'status': ('candidate_passages_retrieved' if hits else
                                         'retrieval_incomplete' if suspect_all or errors else
                                         'no_lexical_match' if sources else 'retrieval_incomplete'),
                               'attempted': bool(sources), 'hits': hits,
                               'searched_filing_count': len(sources),
                               'limitations': ['Lexical relevance is not evidence of hypothesis support.',
                                               'Issuer disclosure is not independent corroboration.']}
    return {'schema_version':'1.0.0', 'source':'existing_secagents_parsed_filings',
            'filings_searched': sources, 'filing_diagnostics': diagnostics, 'filing_errors': errors,
            'tasks': results, 'hypothesis_status_changed': False,
            'publication_eligible': False}


def attach_disclosure_results(orchestration, retrieval):
    for task in orchestration.get('tasks', []):
        result = retrieval.get('tasks', {}).get(task['id'])
        if not result:
            continue
        task['status'] = result['status']
        task['attempted'] = result['attempted']
        task['evidence_refs'] = [f"sec-disclosure-evidence.json#tasks/{task['id']}/hits/{i}"
                                 for i in range(len(result['hits']))]
        task['retrieval_status'] = result['status']
        task['reason'] = ('Candidate passages require separate relevance and entailment verification.'
                          if result['hits'] else 'Parsing coverage is suspect or filing processing failed; absence of a match is inconclusive.'
                          if result['status'] == 'retrieval_incomplete' else
                          'No matching passages in searched filings; this is not proof of absence.'
                          if result['attempted'] else 'No eligible parsed filings available to search.')
    states = ('retrieved','partial_evidence_retrieved','insufficient_evidence','not_attempted',
              'candidate_passages_retrieved','no_lexical_match','retrieval_incomplete')
    orchestration['summary'] = {s:sum(t['status']==s for t in orchestration['tasks']) for s in states}
    orchestration['status'] = 'passage_retrieval_completed'
    orchestration['limitations'] = ['Existing parsed SEC filings searched locally; no additional SEC HTTP request.',
                                    'Candidate passages do not verify hypotheses or publication eligibility.',
                                    'Only the filings already selected by the run were searched.']
    return orchestration
