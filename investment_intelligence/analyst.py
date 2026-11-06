"""Evidence-grounded financial interpretation; fail closed on unsupported claims."""
from __future__ import annotations
import argparse
import asyncio
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
import hashlib
import json
import re
from pathlib import Path
from shared.llm import LLMClient, LLMConfig

FIELDS = ('thesis', 'strengths', 'risks', 'valuation', 'claims', 'limitations')
NUM = re.compile(r'(?<![A-Za-z0-9_])(?:\$\s*)?-?\d[\d,]*(?:\.\d+)?(?:\s*(?:trillion|billion|million|thousand|basis points|bps|%|[BbMmTt](?![A-Za-z])))?', re.I)
SYSTEM = """You are an evidence-bound financial analyst. Use only the supplied curated facts. Return JSON with thesis (string), strengths (string array), risks (string array), valuation (string), claims (array of {metric,value,evidence_id}), limitations (string array). Use the exact catalog value string in each claim and its matching evidence ID. In narrative, cite each number directly as [EID] and use its correct unit (e.g. $331.839 billion [E001], 17.79% [E070]). Do not assert peer comparisons, causes, forecasts, or liquidity/solvency conclusions unsupported by evidence. Do not describe cash flow or assets as risks without an explained relationship. Prefer current-period trends and the distinction between profitability and cash generation. Do not invent facts."""

# These are deliberately descriptive rather than model-generated labels.
METRIC_NAMES = {
 'revenue':'Revenue', 'net_income':'Net income', 'operating_income':'Operating income',
 'operating_cash_flow':'Operating cash flow', 'assets':'Total assets', 'cash':'Cash and equivalents',
 'capital_expenditures':'Capital expenditures', 'free_cash_flow':'Free cash flow',
 'operating_margin':'Operating margin', 'net_margin':'Net margin',
 'market_cap_usd':'Market capitalization', 'pe_ratio':'P/E ratio',
 'fcf_yield_percent':'Free cash flow yield', 'earnings_yield_percent':'Earnings yield',
 'close':'Share price', 'shares_outstanding':'Shares outstanding',
}

def metric_name(path):
    tokens = path.strip('/').split('/')
    if 'growth_percent' in tokens:
        return METRIC_NAMES.get(tokens[-1], tokens[-1].replace('_',' ').title()) + ' growth'
    for token in reversed(tokens):
        if token in METRIC_NAMES: return METRIC_NAMES[token]
    return tokens[-1].replace('_',' ').title()

def _unit_number(text):
    s = str(text).strip().lower().replace(',', '').replace('$', '')
    match = re.fullmatch(r'(-?\d+(?:\.\d+)?)\s*(trillion|billion|million|thousand|basis points|bps|%|[bmt])?', s)
    if not match: raise ValueError('Invalid number')
    factor = {'trillion':10**12,'t':10**12,'billion':10**9,'b':10**9,
              'million':10**6,'m':10**6,'thousand':10**3,
              'basis points':Decimal('.01'),'bps':Decimal('.01'),'%':1,None:1}
    return Decimal(match.group(1))*Decimal(factor[match.group(2)]),match.group(2)

def _metric_compatible(label, path):
    if not isinstance(label,str) or not label.strip(): return False
    norm=lambda t: re.sub(r'[^a-z0-9]+',' ',t.lower()).strip()
    actual=norm(metric_name(path)); claimed=norm(label)
    aliases={'pe ratio':{'pe ratio','price earnings ratio'},'cash and equivalents':{'cash reserves','cash','cash and equivalents'},
             'total assets':{'total assets','assets'},'market capitalization':{'market cap','market capitalization'},
             'free cash flow yield':{'fcf yield','free cash flow yield'},
             'free cash flow':{'fcf','free cash flow'}}
    return claimed==actual or claimed in aliases.get(actual,set())


def resolve_pointer(document, pointer):
    if not isinstance(pointer, str) or not pointer.startswith('/'):
        raise ValueError('Invalid evidence pointer')
    cur = document
    for token in pointer[1:].split('/'):
        token = token.replace('~1', '/').replace('~0', '~')
        if isinstance(cur, dict): cur = cur[token]
        elif isinstance(cur, list): cur = cur[int(token)]
        else: raise ValueError('Pointer traverses scalar')
    return cur

def _pointer(tokens):
    return '/' + '/'.join(str(t).replace('~','~0').replace('/','~1') for t in tokens)

def build_catalog(report):
    """Only numeric leaf values in recognized financial sections; no untrusted arbitrary text."""
    entries = []
    roots = ('financials','financial_history','ratios_percent','free_cash_flow','market_data','valuation')
    def walk(value, path):
        if isinstance(value, dict):
            for k, v in value.items():
                if k in ('inputs',): continue  # duplicate facts
                walk(v, path+[k])
        elif isinstance(value, list):
            for i, v in enumerate(value): walk(v, path+[i])
        elif isinstance(value, (str, int, float)) and not isinstance(value, bool):
            try: Decimal(str(value))
            except (InvalidOperation, ValueError): return
            key = str(path[-1])
            if key in ('age_days', 'price_age_days', 'share_count_age_days'): return
            unit = ('%' if ('percent' in path or key.endswith('_percent')) else
                    'USD' if key in ('value','market_cap_usd','close') and ('financials' in path or 'free_cash_flow' in path or 'market_cap_usd' in path or key=='close') else
                    'ratio' if key=='pe_ratio' else 'number')
            entries.append({'id':f'E{len(entries)+1:03d}', 'path':_pointer(path), 'metric':metric_name(_pointer(path)), 'value':str(value), 'unit':unit})
    for root in roots:
        if root in report: walk(report[root], [root])
    return entries

def _same_value(actual, asserted, unit):
    try:
        a, _ = _unit_number(actual)
        b, suffix = _unit_number(asserted)
        if suffix=='%' and unit!='%': return False
        if suffix in ('bps','basis points') and unit!='%': return False
        if suffix in ('b','m','t','billion','million','trillion','thousand') and unit!='USD': return False
        return abs(a-b) <= max(Decimal('0.005'),abs(a)*Decimal('0.00005'))
    except (InvalidOperation,ValueError,TypeError): return False

def _prose(analysis):
    yield analysis.get('thesis','')
    yield analysis.get('valuation','')
    for field in ('strengths','risks','limitations'):
        for s in analysis.get(field,[]): yield s

def verify_claims(analysis, report, catalog=None):
    catalog = catalog if catalog is not None else build_catalog(report)
    lookup={e['id']:e for e in catalog}
    checks=[]
    for claim in analysis.get('claims',[]):
        eid=claim.get('evidence_id') if isinstance(claim,dict) else None
        entry=lookup.get(eid)
        ok=bool(entry and _same_value(entry['value'],claim.get('value'),entry['unit']) and _metric_compatible(claim.get('metric'),entry['path']))
        checks.append({'claim':claim,'verified':ok,'reason':None if ok else 'Missing evidence ID, numeric mismatch, or metric mismatch'})
    narrative=[]
    for s in _prose(analysis):
        if not isinstance(s,str):
            narrative.append({'text':str(s),'verified':False,'reason':'Non-string narrative'});continue
        citations=re.findall(r'\[(E\d+)\]',s)
        unknown=[c for c in citations if c not in lookup]
        # Each number in narrative must be directly followed by a valid citation for the same value.
        for match in NUM.finditer(s):
            following=s[match.end():]
            cited=re.match(r'\s*\[(E\d+)\]',following)
            eid=cited.group(1) if cited else None
            entry=lookup.get(eid)
            if not entry or not _same_value(entry['value'],match.group(),entry['unit']):
                narrative.append({'text':match.group().strip(),'verified':False,'reason':'Uncited or mismatched narrative number'})
        for c in unknown: narrative.append({'text':c,'verified':False,'reason':'Unknown narrative evidence ID'})
    valid=bool(checks) and all(c['verified'] for c in checks) and not narrative
    return {'claims':checks,'narrative_issues':narrative,'all_verified':valid}

def _validate_shape(a):
    if not isinstance(a,dict) or any(k not in a for k in FIELDS): raise ValueError('Model response missing required fields')
    if not isinstance(a['claims'],list) or not a['claims']: raise ValueError('Model response missing claims')
    if not all(isinstance(a[k],list) for k in ('strengths','risks','limitations')): raise ValueError('Invalid array field')
    if not all(isinstance(a[k],str) for k in ('thesis','valuation')): raise ValueError('Invalid text field')

async def analyze(report, client):
    canonical=json.dumps(report,sort_keys=True,separators=(',',':'))
    catalog=build_catalog(report)
    if not catalog: raise ValueError('No eligible financial evidence in report')
    curated = [e for e in catalog if not e['path'].startswith('/financial_history/') or '/financial_history/4/' in e['path']]
    payload=json.dumps({'entity':report.get('entity'), 'as_of':report.get('as_of'), 'catalog':curated,
                        'limitations':report.get('limitations',[])},separators=(',',':'))
    messages=[{'role':'system','content':SYSTEM},{'role':'user','content':payload}]
    attempts=[]
    for attempt in range(2):
        raw=await client.complete(messages)
        try:
            a=json.loads(raw);_validate_shape(a)
            check=verify_claims(a,report,catalog)
            error=None
        except (ValueError,TypeError) as exc:
            a=None;check={'claims':[],'narrative_issues':[],'all_verified':False};error=str(exc)
        attempts.append({'attempt':attempt+1,'raw_response':raw,'analysis':a,'verification':check,'error':error})
        if check['all_verified']: break
        if attempt==0:
            messages += [{'role':'assistant','content':raw}, {'role':'user','content':json.dumps({
                'instruction':'Correct the entire response using only catalog entries. Every numerical assertion in prose must have a matching [EID] citation. Remove unsupported comparisons. Return JSON only.',
                'verification':check,'error':error})}]
    last=attempts[-1]
    return {'schema_version':'0.4.2','status':'verified' if last['verification']['all_verified'] else 'review_required',
            'analysis':last['analysis'],'verification':last['verification'],
            'evidence_catalog':catalog,'prompt_evidence_ids':[e['id'] for e in curated],'attempts':attempts,
            'provenance':{'provider':client.config.provider,'model':client.config.model,
                          'generated_at':datetime.now(timezone.utc).isoformat(),
                          'input_sha256':hashlib.sha256(canonical.encode()).hexdigest()}}

def main():
    p=argparse.ArgumentParser(description='Evidence-grounded InvestmentIntelligence analysis')
    p.add_argument('--report',required=True);p.add_argument('--output',required=True)
    p.add_argument('--provider',choices=['openai','openai_compatible'],default='openai_compatible')
    p.add_argument('--model',required=True);p.add_argument('--base-url',default='http://localhost:11434/v1')
    p.add_argument('--financials-only',action='store_true',help='Skip LLM and publish deterministic coverage only');p.add_argument('--markdown-output',help='Write readable Markdown report (v0.5)');p.add_argument('--api-key-env');p.add_argument('--schema-version',choices=['0.4.2','0.4.3','0.4.4','0.5.0','0.6.0'],default='0.5.0')
    p.add_argument('--document-evidence',help='JSON array of attributable documentary evidence')
    p.add_argument('--dimension-assessments',help='JSON mapping statement IDs to 12-dimension assessments')
    args=p.parse_args()
    report=json.loads(Path(args.report).read_text())
    client=LLMClient(LLMConfig(provider=args.provider,model=args.model,base_url=args.base_url,api_key_env=args.api_key_env))

    if args.schema_version=='0.6.0':
        from .analyst_v060 import analyze_v060
        docs=json.loads(Path(args.document_evidence).read_text()) if args.document_evidence else None
        assessments=json.loads(Path(args.dimension_assessments).read_text()) if args.dimension_assessments else None
        result=asyncio.run(analyze_v060(report,None if args.financials_only else client,docs,assessments))
    elif args.schema_version=='0.5.0':
        from .analyst_v050 import analyze_v050
        result=asyncio.run(analyze_v050(report,None if args.financials_only else client))
    elif args.schema_version=='0.4.4':
        from .analyst_v044 import analyze_v044
        result=asyncio.run(analyze_v044(report,client))
    elif args.schema_version=='0.4.3':
        from .analyst_v043 import analyze_v043
        result=asyncio.run(analyze_v043(report,client))
    else:
        result=asyncio.run(analyze(report,client))
    output=Path(args.output);output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(json.dumps(result,indent=2)+'\n')
    if args.schema_version in ('0.5.0','0.6.0'):
        md=Path(args.markdown_output) if args.markdown_output else output.with_suffix('.md')
        md.parent.mkdir(parents=True,exist_ok=True)
        md.write_text(result['report_markdown']+'\n')
        print(f'Markdown: {md}')
    print(f'{result["status"]}: {output}')

if __name__=='__main__': main()
