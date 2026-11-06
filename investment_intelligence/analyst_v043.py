"""v0.4.3: deterministic financial findings, evidence-gated qualitative statements.

Semantic entailment remains an LLM assessment, not a formal proof. Fail closed on
missing/invalid evidence, and record every judgment and challenge.
"""
from __future__ import annotations
import asyncio
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
import hashlib
import json
import re
from .analyst import build_catalog

METRICS = ('revenue','net_income','operating_income','operating_cash_flow','capital_expenditures','assets','cash')

def _dec(value):
    try: return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError): return None

def _leaf(section, key):
    obj=section.get('financials',{}).get(key) if key in METRICS else section.get(key)
    if isinstance(obj,dict): obj=obj.get('value')
    return _dec(obj)

def deterministic_findings(report):
    """Calculate comparisons in Python; retain exact source pointers and formulas."""
    findings=[]
    def add(metric, kind, value, refs, formula, detail=None):
        findings.append({'id':f'F{len(findings)+1:03d}','metric':metric,'kind':kind,
                         'value':str(value),'unit':'percent' if kind in ('margin','growth','intensity') else 'USD',
                         'formula':formula,'source_paths':refs,'detail':detail or {}})
    history=report.get('financial_history',[])
    if not isinstance(history,list): history=[]
    for metric in METRICS:
        current=_leaf(report,metric)
        if current is None: continue
        path=f'/financials/{metric}/value'
        add(metric,'level',current,[path],'source value')
        if len(history)>=2:
            previous=_leaf(history[-2],metric)
            if previous is not None and previous!=0:
                delta=(current-previous)/abs(previous)*100
                add(metric,'growth',delta,[f'/financial_history/{len(history)-2}/financials/{metric}/value',path],
                    '(current - prior) / abs(prior) * 100',{'current':str(current),'prior':str(previous),
                    'direction':'increase' if delta>0 else 'decrease' if delta<0 else 'unchanged'})
    revenue=_leaf(report,'revenue')
    if revenue is not None and revenue>0:
        for metric in ('net_income','operating_income','operating_cash_flow','capital_expenditures'):
            amount=_leaf(report,metric)
            if amount is not None:
                add(metric,'intensity' if metric=='capital_expenditures' else 'margin',amount/revenue*100,
                    [f'/financials/{metric}/value','/financials/revenue/value'],'numerator / revenue * 100')
    cash=_leaf(report,'operating_cash_flow');capex=_leaf(report,'capital_expenditures')
    if cash is not None and capex is not None:
        fcf=cash-capex
        add('free_cash_flow','level',fcf,['/financials/operating_cash_flow/value','/financials/capital_expenditures/value'],
            'operating_cash_flow - capital_expenditures')
        if revenue is not None and revenue>0:
            add('free_cash_flow','margin',fcf/revenue*100,
                ['/financials/operating_cash_flow/value','/financials/capital_expenditures/value','/financials/revenue/value'],
                '(operating_cash_flow - capital_expenditures) / revenue * 100')
        if len(history)>=2:
            prior_cash=_leaf(history[-2],'operating_cash_flow');prior_capex=_leaf(history[-2],'capital_expenditures')
            if prior_cash is not None and prior_capex is not None and prior_cash!=prior_capex:
                prior=prior_cash-prior_capex
                change=(fcf-prior)/abs(prior)*100
                add('free_cash_flow','growth',change,
                    [f'/financial_history/{len(history)-2}/financials/operating_cash_flow/value',
                     f'/financial_history/{len(history)-2}/financials/capital_expenditures/value',
                     '/financials/operating_cash_flow/value','/financials/capital_expenditures/value'],
                    '(current_fcf - prior_fcf) / abs(prior_fcf) * 100',
                    {'current':str(fcf),'prior':str(prior),'direction':'increase' if change>0 else 'decrease' if change<0 else 'unchanged'})
    for name,path in [('pe_ratio','/valuation/pe_ratio'),('earnings_yield_percent','/valuation/earnings_yield_percent'),
                      ('fcf_yield_percent','/valuation/fcf_yield_percent'),('market_cap_usd','/valuation/market_cap_usd')]:
        obj=report.get('valuation',{}).get(name)
        val=_dec(obj)
        if val is not None:
            add(name,'level',val,[path],'source value')
    return findings

SYSTEM='''You are a cautious qualitative financial analyst. All arithmetic has already been done in Python.
Return JSON only: {"statements":[{"text":"qualitative assertion with no numbers", "finding_ids":["F001"],"category":"strength|risk|valuation|thesis"}],"limitations":["..."]}.
Every statement must be directly supported by cited findings. Do not calculate, compare values, assert unsupported causes, mention peers, debt, benchmarks or historical valuations unless provided. No numeric literals in text; financial figures will be rendered separately. Prefer specific explanations of the significance of supplied findings. Statements are independently reviewed and may be rejected.'''
JUDGE='''You are an evidence reviewer. Evaluate only the supplied statement and Python findings. Return JSON only with {"supported":boolean,"uncertain":boolean,"reason":string}. "supported" means every factual assertion is directly supported by the findings, not merely compatible with them. If the statement invents external facts, peer comparisons, debt, causal claims or benchmarks, supported=false. "uncertain" means an otherwise supported statement may overstate implications. Never perform arithmetic.'''
CHALLENGE='''You are testing a proposition against supplied evidence. Return JSON only with {"original": "true|false|unknown", "equivalent":"true|false|unknown", "negation":"true|false|unknown", "counterexample_possible":boolean,"reason":string}. Judge original and equivalent as the same proposition and negation as its logical opposite. Do not assume the proposition is true. 'unknown' is appropriate for subjective inferences. A possible counterexample indicates caution, not a factual contradiction.'''

def _json(raw):
    data=json.loads(raw)
    if not isinstance(data,dict): raise ValueError('Expected JSON object')
    return data

async def _complete(client,system,payload):
    return _json(await client.complete([{'role':'system','content':system},
                                        {'role':'user','content':json.dumps(payload,default=str)}]))

def _structural_gate(statement, lookup):
    if not isinstance(statement,dict): return 'Statement is not an object'
    ids=statement.get('finding_ids')
    if not isinstance(ids,list) or not ids or not all(isinstance(i,str) and i in lookup for i in ids):
        return 'Missing or unknown finding IDs'
    content=statement.get('text')
    if not isinstance(content,str) or not content.strip(): return 'Empty statement'
    if re.search(r'(?<![A-Za-z])\d+(?:\.\d+)?',content): return 'Numerical text must be rendered from Python findings'
    if statement.get('category') not in ('strength','risk','valuation','thesis'): return 'Invalid category'
    return None

async def analyze_v043(report,client):
    canonical=json.dumps(report,sort_keys=True,separators=(',',':'))
    findings=deterministic_findings(report)
    if not findings: raise ValueError('No deterministic financial findings available')
    lookup={f['id']:f for f in findings}
    proposal=await _complete(client,SYSTEM,{'findings':findings,'limitations':report.get('limitations',[])})
    statements=proposal.get('statements',[])
    if not isinstance(statements,list): raise ValueError('Invalid statements array')
    results=[]
    for idx,s in enumerate(statements):
        item={'id':f'S{idx+1:03d}','statement':s,'status':'rejected','warnings':[],'audit':{}}
        reason=_structural_gate(s,lookup)
        if reason:
            item['reason']=reason;results.append(item);continue
        cited=[lookup[i] for i in s['finding_ids']]
        try:
            judgment=await _complete(client,JUDGE,{'statement':s['text'],'findings':cited})
            item['audit']['evidence_judgment']=judgment
            if judgment.get('supported') is not True:
                item['reason']='Semantic evidence review did not establish direct support';results.append(item);continue
            # Explicit negation is generated deterministically. Equivalent surface phrasing
            # is proposed by the model, but equivalence is not formally guaranteed.
            challenge=await _complete(client,CHALLENGE,{
                'original':s['text'],
                'equivalent':f'It is the case that: {s["text"]}',
                'negation':f'It is not the case that: {s["text"]}',
                'findings':cited})
            item['audit']['logical_challenge']=challenge
            item['status']='accepted'
            if judgment.get('uncertain') is True:
                item['warnings'].append('Evidence-supported interpretation has uncertain implications')
            a,b,c=(challenge.get(k) for k in ('original','equivalent','negation'))
            if a not in ('true','false','unknown') or b not in ('true','false','unknown') or c not in ('true','false','unknown'):
                item['warnings'].append('Logical test returned invalid judgment')
            else:
                if a!=b: item['warnings'].append('Equivalent formulations received inconsistent judgments')
                if (a=='true' and c=='true') or (a=='false' and c=='false'):
                    item['warnings'].append('Proposition and negation received inconsistent judgments')
                if a=='unknown' or c=='unknown': item['warnings'].append('Logical judgment is indeterminate')
            if challenge.get('counterexample_possible') is True:
                item['warnings'].append('Plausible counterexample identified')
            if item['warnings']: item['status']='warning'
        except (ValueError,KeyError,TypeError) as exc:
            item['reason']=f'Validation failed closed: {exc}'
        results.append(item)
    published=[r for r in results if r['status']!='rejected']
    return {'schema_version':'0.4.3','status':'review_required' if any(r['status']!='accepted' for r in results) else 'verified',
            'findings':findings,'evidence_catalog':build_catalog(report),
            'statements':results,'published_statements':published,
            'limitations':proposal.get('limitations',[]),
            'provenance':{'provider':client.config.provider,'model':client.config.model,
                          'generated_at':datetime.now(timezone.utc).isoformat(),
                          'input_sha256':hashlib.sha256(canonical.encode()).hexdigest()},
            'validation_note':'Semantic support and logical consistency are LLM assessments, not formal proofs.'}
