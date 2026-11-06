"""Bounded retry for numeric text in model-generated qualitative statements."""
from __future__ import annotations

from .analyst_v043 import _complete, _structural_gate

NUMERIC_REJECTION = 'Numerical text must be rendered from Python findings'
REWRITE_SYSTEM = '''Return JSON only: {"text":"..."}.
Rewrite the supplied investment statement to remove ALL numbers, percentages,
currency amounts, numeric dates, and valuation multiples. Preserve the qualitative
claim, uncertainty, category, and cited findings. Do not invent new claims or facts.
Do not include digits anywhere in the text. The deterministic Python report will
render financial figures separately.'''


async def retry_numeric_statement(client, statement, lookup, *, max_retries=2):
    """Return (candidate, audit). Never bypass structural validation.

    Only a numeric-text violation is repairable. Invalid IDs or categories fail
    closed. An unsuccessful retry returns the original, still-invalid statement.
    """
    audit = {'attempted': False, 'outcome': 'not_needed', 'attempts': []}
    reason = _structural_gate(statement, lookup)
    if reason != NUMERIC_REJECTION:
        return statement, audit
    audit['attempted'] = True
    audit['original_statement'] = statement.copy()
    for number in range(1, max_retries + 1):
        try:
            response = await _complete(client, REWRITE_SYSTEM, {
                'original_statement': statement,
                'cited_findings': [lookup[i] for i in statement.get('finding_ids', []) if i in lookup],
                'instruction': 'Return only the replacement text; preserve cited finding IDs.',
            })
            candidate = dict(statement)
            candidate['text'] = response.get('text')
            outcome = _structural_gate(candidate, lookup)
            audit['attempts'].append({'attempt': number, 'text': candidate['text'], 'rejection_reason': outcome})
            if outcome is None:
                audit['outcome'] = 'recovered'
                return candidate, audit
            if outcome != NUMERIC_REJECTION:
                audit['outcome'] = 'invalid_rewrite'
                return statement, audit
        except (ValueError, KeyError, TypeError) as exc:
            audit['attempts'].append({'attempt': number, 'error': f'{type(exc).__name__}: {exc}'})
    audit['outcome'] = 'exhausted'
    return statement, audit
