"""v0.6: frozen 12-dimension evidence matrix; no fabricated dimension assessments.

Assessment records are explicitly supplied by an evaluator or left insufficient.
A deterministic gate checks vocabulary, evidence references, and evidence quality.
"""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
from .analyst_v050 import analyze_v050, render_markdown

DIMENSIONS = (
    'historical','industry','competitive','financial','valuation','macroeconomic',
    'management_strategy','operational','risk','temporal','forward_looking','evidence_quality'
)
ASSESSMENTS = {'supports','contradicts','mixed','neutral','insufficient_evidence'}
LEVELS = {'high','medium','low'}
FRAMEWORK_FILE = Path(__file__).with_name('evaluation_framework_v1.yaml')
FRAMEWORK_SHA256 = hashlib.sha256(FRAMEWORK_FILE.read_bytes()).hexdigest()


def normalize_evidence(evidence):
    """Documentary evidence must be attributable; source text is never promoted to fact."""
    if not isinstance(evidence,list):raise ValueError('evidence must be an array')
    out=[];seen=set()
    for item in evidence:
        if not isinstance(item,dict):raise ValueError('evidence entry must be an object')
        for key in ('id','source_type','source_document','source_location','published_at','text'):
            if not isinstance(item.get(key),str) or not item[key].strip():
                raise ValueError(f'evidence requires {key}')
        if item['id'] in seen or not item['id'].startswith('D'):
            raise ValueError('duplicate or invalid documentary evidence id')
        seen.add(item['id']);out.append(dict(item))
    return out


def _empty_dimension():
    return {'assessment':'insufficient_evidence','materiality':None,'confidence':None,
            'evidence_ids':[],'rationale':'No dimension-specific assessment established.'}


def evaluate_statement(statement, available_ids, supplied=None):
    supplied=supplied or {}
    if not isinstance(supplied,dict) or set(supplied)-set(DIMENSIONS):
        raise ValueError('unknown dimension in supplied evaluation')
    dimensions={}
    for dimension in DIMENSIONS:
        data={**_empty_dimension(),**supplied.get(dimension,{})}
        if data['assessment'] not in ASSESSMENTS:raise ValueError('invalid assessment')
        ids=data['evidence_ids']
        if not isinstance(ids,list) or len(set(ids))!=len(ids) or not set(ids)<=available_ids:
            raise ValueError('unknown or duplicate evidence references')
        if data['assessment']=='insufficient_evidence':
            if ids or data['confidence'] is not None:raise ValueError('insufficient evidence cannot claim support or confidence')
        else:
            if not ids:raise ValueError('assessed dimension must cite evidence')
            if data['confidence'] not in LEVELS:raise ValueError('confidence required')
        if data['materiality'] is not None and data['materiality'] not in LEVELS:
            raise ValueError('invalid materiality')
        if not isinstance(data['rationale'],str) or not data['rationale'].strip():
            raise ValueError('rationale required')
        dimensions[dimension]=data
    counts={status:sum(d['assessment']==status for d in dimensions.values()) for status in sorted(ASSESSMENTS)}
    return {'statement_id':statement['id'],'statement':statement['statement']['text'],
            'factual_validation':statement['status'], 'dimensions':dimensions,
            'summary':{'counts':counts,
                'high_materiality_contradictions':[k for k,v in dimensions.items() if v['assessment']=='contradicts' and v['materiality']=='high'],
                'high_materiality_gaps':[k for k,v in dimensions.items() if v['assessment']=='insufficient_evidence' and v['materiality']=='high']}}


def render_v060(result):
    lines=[render_markdown(result).rstrip(),'','## Twelve-Dimension Statement Evaluations','',
           'All dimensions are reported. Missing evidence is explicitly identified, not treated as neutral.','']
    for row in result['statement_evaluations']:
        lines.extend([f'### {row["statement_id"]}: {row["statement"]}','',
                      f'Factual validation: **{row["factual_validation"]}**','',
                      '| Dimension | Assessment | Materiality | Confidence | Evidence |','|---|---|---|---|---|'])
        for name,d in row['dimensions'].items():
            lines.append(f'| {name.replace("_"," ").title()} | {d["assessment"]} | {d["materiality"] or "—"} | {d["confidence"] or "—"} | {", ".join(d["evidence_ids"]) or "—"} |')
        lines.extend(['',f'**Coverage:** {row["summary"]["counts"]}',''])
    lines.extend(['## Framework Provenance','',
                  f'- Framework: {result["framework"]["id"]} v{result["framework"]["version"]}',
                  f'- SHA-256: `{result["framework"]["sha256"]}`',
                  '- Evaluations not provided by a qualified evaluator remain `insufficient_evidence`.',''])
    return '\n'.join(lines)


async def analyze_v060(report,client=None,document_evidence=None,dimension_assessments=None):
    base=await analyze_v050(report,client)
    docs=normalize_evidence(document_evidence or [])
    audit=base['qualitative_audit']
    available={f['id'] for f in base['findings']}|{d['id'] for d in docs}
    dimension_assessments=dimension_assessments or {}
    if not isinstance(dimension_assessments,dict) or set(dimension_assessments)-{s['id'] for s in audit}:
        raise ValueError('evaluations reference unknown statement')
    base['schema_version']='0.6.0'
    base['framework']={'id':'investment_statement_evaluation','version':'1.0','sha256':FRAMEWORK_SHA256,
                       'dimensions':list(DIMENSIONS)}
    base['document_evidence']=docs
    base['statement_evaluations']=[evaluate_statement(s,available,dimension_assessments.get(s['id'])) for s in audit]
    base['evidence_gaps']={name:sum(row['dimensions'][name]['assessment']=='insufficient_evidence'
                                    for row in base['statement_evaluations']) for name in DIMENSIONS}
    base['report_markdown']=render_v060(base)
    return base
