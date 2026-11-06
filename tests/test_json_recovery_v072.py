import asyncio
from investment_intelligence.json_recovery import complete_json

class Client:
    def __init__(self, outputs): self.outputs=iter(outputs)
    async def complete(self, messages): return next(self.outputs)

def test_json_recovery():
    d={}
    result=asyncio.run(complete_json(Client(['bad JSON','{"ok":true}']),'prompt',{},diagnostics=d))
    assert result == {'ok': True} and d['recovered'] and d['attempts']==2

def test_json_fails_closed():
    try: asyncio.run(complete_json(Client(['bad','also bad']),'prompt',{}))
    except ValueError: return
    assert False
