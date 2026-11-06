"""Authoritative report renderer for the post-integrity publication state."""
from __future__ import annotations
import re


def render_final_report(analysis):
    original = analysis.get('report_markdown', '')
    # Drop the old LLM-authored publication list and pre-integrity dimensional tables.
    original = re.sub(r'\n## Qualitative Interpretations \(Validated\).*?(?=\n## Coverage and Limitations|\Z)',
                      '', original, flags=re.S)
    original = re.sub(r'\n## Twelve-Dimension Statement Evaluations.*?(?=\n## Framework Provenance|\Z)',
                      '', original, flags=re.S)
    original = re.sub(r'\n## Evidence Integrity — Authoritative Publication Status.*?(?=\n## |\Z)',
                      '', original, flags=re.S)
    audits = {x.get('id'): x for x in analysis.get('qualitative_audit', [])}
    published = analysis.get('published_statements', [])
    lines = ['## Final Qualitative Publication (v0.8.5)', '',
             'Only statements surviving all integrity checks appear here. Warnings are not approvals of investment implications.', '']
    if not published:
        lines.append('No qualitative statements met the publication criteria.')
    for item in published:
        sid = item.get('id', '')
        statement = item.get('statement') or audits.get(sid, {}).get('statement') or {}
        lines.append(f"- **{sid} / {item.get('status', 'review')}**: {statement.get('text', '')} "
                     f"(Findings: {', '.join(statement.get('finding_ids') or [])})")
        for warning in item.get('warnings', []):
            lines.append('  - Warning: ' + str(warning))
    lines += ['', '## Rejected Statements', '']
    rejected = [x for x in analysis.get('qualitative_audit', []) if x.get('status') == 'rejected']
    if not rejected:
        lines.append('None.')
    for item in rejected:
        lines.append(f"- **{item.get('id')}**: {(item.get('statement') or {}).get('text', '')} — "
                     f"{item.get('reason', 'failed qualitative validation')}")
    lines += ['', '## Twelve-Dimension Evidence Review (Final)', '',
              'A passage relevant to a topic does not by itself verify a claim. '
              'Original assessments are retained in JSON; unverified support is downgraded.', '']
    for evaluation in analysis.get('statement_evaluations', []):
        sid = evaluation.get('statement_id', evaluation.get('id', ''))
        lines += [f'### {sid}', '', '| Dimension | Final assessment | Original | Evidence |',
                  '|---|---|---|---|']
        dims = evaluation.get('dimensions', evaluation.get('dimension_assessments', {}))
        if isinstance(dims, dict):
            rows = dims.items()
        else:
            rows = [(v.get('dimension', ''), v) for v in dims if isinstance(v, dict)]
        for name, v in rows:
            if not isinstance(v, dict):
                continue
            lines.append('| ' + ' | '.join((str(name), str(v.get('assessment', '—')),
                str(v.get('original_assessment', '—')), ', '.join(v.get('evidence_ids') or []) or '—')) + ' |')
        if evaluation.get('integrity_override'):
            lines.append('\n**Integrity override:** ' + str(evaluation['integrity_override']))
        lines.append('')
    lines += ['## Evidence Integrity Summary', '',
              'Invalid statement IDs: ' + (', '.join(analysis.get('evidence_integrity', {}).get('invalid_statement_ids', [])) or 'none'),
              'Published: ' + str(len(published)) + '; rejected: ' + str(len(rejected)) + '.',
              'A clean citation check does not establish semantic entailment.', '']
    # Keep all prior financial, historical, and source sections, but replace outdated publication displays.
    return original.rstrip() + '\n\n' + '\n'.join(lines) + '\n'
