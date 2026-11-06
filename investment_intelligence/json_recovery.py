"""Bounded malformed-JSON recovery for local model responses."""
from __future__ import annotations
import json

async def complete_json(client, system, payload, *, attempts=2, diagnostics=None):
    if attempts < 1 or attempts > 3:
        raise ValueError('attempts must be between 1 and 3')
    errors = []
    for attempt in range(1, attempts + 1):
        messages = [{'role': 'system', 'content': system},
                    {'role': 'user', 'content': json.dumps(payload, default=str)}]
        if attempt > 1:
            messages.append({'role': 'user', 'content':
                'Your previous response was not a valid JSON object. Return ONLY a complete JSON object, no markdown or explanation.'})
        raw = await client.complete(messages)
        try:
            obj = json.loads(raw)
            if not isinstance(obj, dict):
                raise ValueError('Expected JSON object')
            if diagnostics is not None:
                diagnostics.update({'attempts': attempt, 'errors': errors, 'recovered': attempt > 1})
            return obj
        except (json.JSONDecodeError, ValueError) as exc:
            errors.append({'attempt': attempt, 'error': str(exc), 'raw_excerpt': str(raw)[:500]})
    if diagnostics is not None:
        diagnostics.update({'attempts': attempts, 'errors': errors, 'recovered': False})
    raise ValueError(f'Model did not produce valid JSON after {attempts} attempts: {errors[-1]["error"]}')
