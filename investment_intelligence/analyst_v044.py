"""v0.4.4 evidence and metamorphic-consistency validation.

The LLM assesses semantics; Python checks source references and consistency.
No semantic entailment or paraphrase equivalence is claimed as formal proof.
"""
from __future__ import annotations
import hashlib
import json
from datetime import datetime, timezone
from .analyst import build_catalog
from .analyst_v043 import SYSTEM, _complete, _structural_gate, deterministic_findings
from .statement_retry import retry_numeric_statement
from .json_recovery import complete_json as _complete

REVIEW = '''Review the statement against ONLY the supplied deterministic findings. Return JSON:
{"premise_supported":true|false,"unsupported_factual_claim":true|false,
"interpretation_uncertain":true|false,"reason":"..."}.
Separate an evidenced financial premise from a tentative interpretation. A cautious
"may/could/suggests" inference grounded in a supported premise is uncertain, not
an unsupported factual claim. Unsupported factual claims include historical/peer
benchmarks, asserted causes, external facts, or definitive conditions absent from
findings. Never calculate. If no relevant premise is evidenced, premise_supported=false.
Do not infer actual liquidity trouble from falling cash; a possibility is not a fact.'''
PARAPHRASE = '''Rewrite the supplied assertion in different natural language while
preserving its meaning, strength, modality (may/must), scope and negation. Do not add
or remove claims. Return JSON only: {"paraphrase":"..."}.'''
JUDGMENT = '''Assess ONLY the supplied proposition against supplied deterministic
findings. Return JSON only: {"judgment":"true|false|unknown","reason":"..."}.
True means established by the evidence, false means contradicted, unknown means
not decidable. A plausible but unproven interpretation is unknown. Do not compute
numbers, assume causal relationships, or use outside facts.'''
COUNTER = '''Given a qualitative assertion and deterministic findings, return JSON
{"possible":true|false,"reason":"..."}. Is there a specific plausible
alternative interpretation consistent with ALL findings that weakens the claim?
Do not invent actual events. Return false if no specific alternative is identified.'''
VALID = {'true', 'false', 'unknown'}

async def _judge(client, proposition, findings):
    data = await _complete(client, JUDGMENT, {'proposition':proposition,'findings':findings})
    value = data.get('judgment')
    if value not in VALID:
        raise ValueError('Invalid proposition judgment')
    return data

async def analyze_v044(report, client):
    canonical=json.dumps(report,sort_keys=True,separators=(',',':'))
    findings=deterministic_findings(report)
    if not findings: raise ValueError('No deterministic financial findings available')
    for f in findings:
        if f['metric']=='pe_ratio': f['unit']='ratio'
        elif f['metric'] in ('earnings_yield_percent','fcf_yield_percent'): f['unit']='percent'
    lookup={f['id']:f for f in findings}
    proposal=await _complete(client,SYSTEM,{'findings':findings,'limitations':report.get('limitations',[])})
    statements=proposal.get('statements')
    if not isinstance(statements,list): raise ValueError('Invalid statements array')
    results=[]
    for idx, statement in enumerate(statements):
        item={'id':f'S{idx+1:03d}','statement':statement,'status':'rejected','warnings':[],'audit':{}}
        statement, retry_audit = await retry_numeric_statement(client, statement, lookup)
        item['statement'] = statement
        if retry_audit['attempted']:
            item['audit']['numeric_retry'] = retry_audit
        reason=_structural_gate(statement,lookup)
        if reason:
            item['reason']=reason; results.append(item); continue
        cited=[lookup[i] for i in statement['finding_ids']]
        original=statement['text']
        try:
            review=await _complete(client,REVIEW,{'statement':original,'findings':cited})
            item['audit']['evidence_review']=review
            # Require explicit booleans; malformed/ambiguous reviews fail closed.
            if not all(type(review.get(k)) is bool for k in
                       ('premise_supported','unsupported_factual_claim','interpretation_uncertain')):
                item['reason']='Invalid evidence review';results.append(item);continue
            if not review['premise_supported'] or review['unsupported_factual_claim']:
                item['reason']='Missing premise support or unsupported factual claim'
                results.append(item);continue
            item['status']='accepted'
            if review['interpretation_uncertain']:
                item['warnings'].append('Evidence-supported inference is uncertain')
            # Independent calls reduce answer-contamination. Negation is created by
            # Python; paraphrase is LLM-generated and is not formally guaranteed.
            rewrite=await _complete(client,PARAPHRASE,{'statement':original})
            equivalent=rewrite.get('paraphrase')
            if not isinstance(equivalent,str) or not equivalent.strip():
                raise ValueError('Invalid paraphrase')
            negated=f'It is not the case that: ({original})'
            judgments={}
            for key,proposition in [('original',original),('paraphrase',equivalent),('negation',negated)]:
                judgments[key]=await _judge(client,proposition,cited)
            item['audit']['logical_challenge']={
                'propositions':{'original':original,'paraphrase':equivalent,'negation':negated},
                'judgments':judgments,
                'equivalence_is_formally_verified':False}
            a=judgments['original']['judgment'];b=judgments['paraphrase']['judgment'];c=judgments['negation']['judgment']
            # Unknown vs known is a robustness discrepancy, not a formal contradiction.
            if a!=b:
                item['warnings'].append('Paraphrase judgments differ (possible wording sensitivity)')
            if (a=='true' and c=='true') or (a=='false' and c=='false'):
                item['warnings'].append('Assertion and negation have contradictory judgments')
            if (a=='unknown') != (c=='unknown'):
                item['warnings'].append('Negation judgments have inconsistent certainty')
            # Consistent unknown is not a logical error and does not create a warning.
            counter=await _complete(client,COUNTER,{'statement':original,'findings':cited})
            item['audit']['counterexample_assessment']=counter
            if type(counter.get('possible')) is not bool:
                item['warnings'].append('Counterexample assessment was inconclusive')
            elif counter['possible']:
                item['warnings'].append('Plausible alternative interpretation identified')
            if item['warnings']: item['status']='warning'
        except (ValueError,KeyError,TypeError,json.JSONDecodeError) as exc:
            item['status']='rejected'
            item['reason']=f'Validation failed closed: {exc}'
        results.append(item)
    published=[s for s in results if s['status']!='rejected']
    return {'schema_version':'0.4.4',
            'status':'review_required' if any(s['status']!='accepted' for s in results) else 'verified',
            'findings':findings,'evidence_catalog':build_catalog(report),
            'statements':results,'published_statements':published,
            'limitations':proposal.get('limitations',[]),
            'provenance':{'provider':client.config.provider,'model':client.config.model,
                          'generated_at':datetime.now(timezone.utc).isoformat(),
                          'input_sha256':hashlib.sha256(canonical.encode()).hexdigest()},
            'validation_note':'Semantic support and paraphrase equivalence are model assessments, not formal proofs.'}
