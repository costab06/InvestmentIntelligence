"""v0.5: deterministic investment coverage and human-readable reporting.

Qualitative commentary is optional and always remains subject to the v0.4.4 gate.
Verified financial observations never disappear when commentary is rejected.
"""
from __future__ import annotations
import hashlib
import json
from datetime import datetime, timezone
from decimal import Decimal
from .analyst_v043 import deterministic_findings
from .analyst_v044 import analyze_v044

SECTIONS = ('growth', 'profitability', 'cash_generation', 'balance_sheet', 'valuation')

def _find(findings, metric, kind):
    return next((f for f in findings if f['metric'] == metric and f['kind'] == kind), None)

def _observation(section, label, *findings):
    fs = [f for f in findings if f is not None]
    return {'section':section, 'label':label, 'finding_ids':[f['id'] for f in fs],
            'values':[{'finding_id':f['id'],'metric':f['metric'],'kind':f['kind'],
                       'value':f['value'],'unit':f['unit']} for f in fs]}

def coverage(findings):
    """Choose and relate facts, without model-written arithmetic or explanations."""
    f=lambda metric,kind: _find(findings,metric,kind)
    result={s:[] for s in SECTIONS}
    def add(section,label,*fs):
        if all(x is not None for x in fs): result[section].append(_observation(section,label,*fs))
    add('growth','Revenue and net-income growth',f('revenue','growth'),f('net_income','growth'))
    add('growth','Revenue and operating-income growth',f('revenue','growth'),f('operating_income','growth'))
    add('profitability','Operating and net margins',f('operating_income','margin'),f('net_income','margin'))
    add('cash_generation','Operating cash flow and capital expenditure growth',f('operating_cash_flow','growth'),f('capital_expenditures','growth'))
    add('cash_generation','Operating cash flow, capital expenditures and free cash flow',f('operating_cash_flow','level'),f('capital_expenditures','level'),f('free_cash_flow','level'))
    add('cash_generation','Free cash flow growth and margin',f('free_cash_flow','growth'),f('free_cash_flow','margin'))
    add('balance_sheet','Cash balance and year-over-year change',f('cash','level'),f('cash','growth'))
    add('balance_sheet','Total assets and year-over-year change',f('assets','level'),f('assets','growth'))
    add('valuation','P/E ratio and earnings yield',f('pe_ratio','level'),f('earnings_yield_percent','level'))
    add('valuation','Free cash flow yield and market capitalization',f('fcf_yield_percent','level'),f('market_cap_usd','level'))
    return result

def _fmt(v):
    n=Decimal(v['value']);unit=v['unit']
    if unit=='USD':
        for scale,suffix in ((Decimal('1e12'),'T'),(Decimal('1e9'),'B'),(Decimal('1e6'),'M')):
            if abs(n)>=scale: return f'${n/scale:,.2f}{suffix}'
        return f'${n:,.2f}'
    if unit=='percent': return f'{n:,.2f}%'
    if unit=='ratio': return f'{n:,.2f}x'
    return f'{n:,.2f}'

def render_markdown(result):
    lines=['# Investment Intelligence — Financial Assessment','',
           f'**Validation status:** {result["status"]}  ',
           '**Financial observations:** deterministic Python calculations.  ',
           '**Qualitative statements:** model-generated and separately validated.','']
    headings={'growth':'Growth','profitability':'Profitability','cash_generation':'Cash Generation',
              'balance_sheet':'Balance Sheet','valuation':'Valuation'}
    for section in SECTIONS:
        lines.extend([f'## {headings[section]}',''])
        entries=result['coverage'][section]
        if not entries: lines.extend(['No supported observations available.','']);continue
        for item in entries:
            values='; '.join(f'{v["metric"].replace("_"," ")} ({v["kind"]}): {_fmt(v)} [{v["finding_id"]}]' for v in item['values'])
            lines.append(f'- **{item["label"]}:** {values}')
        lines.append('')
        # Preserve statement categories without pretending a statement belongs to an exact section.
        # Commentary is presented separately below instead.
    lines.extend(['## Qualitative Interpretations (Validated)',''])
    published=result.get('published_statements',[])
    if not published: lines.append('No model interpretations passed validation. The financial observations above remain available.')
    for item in published:
        s=item['statement'];lines.append(f'- **{item["status"].upper()} / {s["category"]}:** {s["text"]} (Findings: {", ".join(s["finding_ids"])})')
        for warning in item.get('warnings',[]):lines.append(f'  - Warning: {warning}')
    lines.extend(['','## Coverage and Limitations',''])
    for section in SECTIONS:
        if not result['coverage'][section]:lines.append(f'- Missing deterministic coverage: {headings[section]}')
    for limitation in result.get('limitations',[]):lines.append(f'- {limitation}')
    lines.extend(['','Rejected qualitative statements are retained in JSON audit, not published here.',''])
    return '\n'.join(lines)

async def analyze_v050(report, client=None):
    findings=deterministic_findings(report)
    if not findings:raise ValueError('No deterministic financial findings available')
    for f in findings:
        if f['metric']=='pe_ratio':f['unit']='ratio'
        elif f['metric'] in ('earnings_yield_percent','fcf_yield_percent'):f['unit']='percent'
    sections=coverage(findings)
    qualitative=None
    if client is not None:qualitative=await analyze_v044(report,client)
    published=qualitative['published_statements'] if qualitative else []
    result={'schema_version':'0.5.0','status': 'review_required' if qualitative and qualitative['status']=='review_required' else 'verified_financials',
            'findings':findings,'coverage':sections,'published_statements':published,
            'qualitative_audit':qualitative['statements'] if qualitative else [],
            'limitations':report.get('limitations',[]),
            'provenance':{'generated_at':datetime.now(timezone.utc).isoformat(),
                          'input_sha256':hashlib.sha256(json.dumps(report,sort_keys=True,separators=(',',':')).encode()).hexdigest(),
                          'qualitative_model':client.config.model if client else None}}
    result['report_markdown']=render_markdown(result)
    return result
