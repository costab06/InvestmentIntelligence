import asyncio
from types import SimpleNamespace
from unittest.mock import patch

from investment_intelligence.statement_retry import retry_numeric_statement

LOOKUP = {'F002': {'id': 'F002', 'value': '17.78', 'unit': 'percent'}}
BAD = {'text': 'Revenue rose 17.78%, suggesting expansion.', 'finding_ids': ['F002'], 'category': 'strength'}


def test_numeric_retry_recovers_without_changing_citations():
    async def complete(client, system, payload):
        return {'text': 'Revenue growth suggests expanding top-line performance.'}
    with patch('investment_intelligence.statement_retry._complete', complete):
        result, audit = asyncio.run(retry_numeric_statement(object(), BAD, LOOKUP))
    assert result['finding_ids'] == BAD['finding_ids']
    assert result['text'] != BAD['text']
    assert audit['outcome'] == 'recovered'
    assert audit['original_statement'] == BAD


def test_numeric_retry_exhausts_and_fails_closed():
    async def complete(client, system, payload):
        return {'text': 'Revenue rose 17.78%.'}
    with patch('investment_intelligence.statement_retry._complete', complete):
        result, audit = asyncio.run(retry_numeric_statement(object(), BAD, LOOKUP))
    assert result == BAD
    assert audit['outcome'] == 'exhausted'
    assert len(audit['attempts']) == 2


def test_invalid_ids_do_not_trigger_repair():
    bad = dict(BAD, finding_ids=['F999'])
    result, audit = asyncio.run(retry_numeric_statement(object(), bad, LOOKUP))
    assert result == bad
    assert audit['attempted'] is False


def test_non_numeric_statement_not_rewritten():
    good = dict(BAD, text='Revenue growth suggests expansion.')
    result, audit = asyncio.run(retry_numeric_statement(object(), good, LOOKUP))
    assert result == good
    assert audit['outcome'] == 'not_needed'
