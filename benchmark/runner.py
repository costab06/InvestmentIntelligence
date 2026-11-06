"""Independent, stdlib-only cost/quality benchmark. Never fabricates vendor results or dollars."""
import argparse
import csv
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import resource
import subprocess
import sys
import time

HERE = Path(__file__).resolve().parent
DIMENSIONS = ('evidence_discovery', 'observation_vs_inference', 'contradiction_handling', 'numerical_integrity', 'uncertainty_calibration', 'decision_usefulness')

def load_questions(path=HERE / 'questions.json'):
    obj = json.loads(Path(path).read_text())
    qs = obj['questions']
    assert len(qs) == 10 and len({q['id'] for q in qs}) == 10
    return qs

def run_pipeline(ticker, output, model, sec_stream, as_of, log):
    """Subprocess timing and CPU accounting; no claim of measured power or token usage."""
    output = Path(output); output.mkdir(parents=True, exist_ok=True)
    before = resource.getrusage(resource.RUSAGE_CHILDREN)
    start = time.perf_counter()
    command = [sys.executable, '-m', 'investment_intelligence.run', '--ticker', ticker,
               '--output', str(output), '--model', model, '--sec-stream', sec_stream]
    if as_of: command.extend(['--as-of', as_of])
    with Path(log).open('w') as fp:
        proc = subprocess.run(command, stdout=fp, stderr=subprocess.STDOUT, check=False)
    after = resource.getrusage(resource.RUSAGE_CHILDREN)
    return {'ticker':ticker, 'command':command, 'exit_code':proc.returncode,
            'elapsed_seconds':round(time.perf_counter()-start, 3),
            'child_cpu_user_seconds':round(after.ru_utime-before.ru_utime,3),
            'child_cpu_system_seconds':round(after.ru_stime-before.ru_stime,3),
            'log':str(log), 'measured_electricity_kwh':None, 'measured_api_cost_usd':None,
            'measured_gpu_seconds':None, 'measured_tokens':None,
            'cost_status':'unmeasured', 'timestamp_utc':dt.datetime.now(dt.timezone.utc).isoformat()}

def scaffold(root, questions):
    root = Path(root); root.mkdir(parents=True, exist_ok=True)
    rows = []
    for q in questions:
        for tool in ('InvestmentIntelligence','Comparator-A','Comparator-B'):
            rows.append({'question_id':q['id'],'ticker':q['ticker'],'tool':tool,
                         'evidence_discovery':'','observation_vs_inference':'',
                         'contradiction_handling':'','numerical_integrity':'',
                         'uncertainty_calibration':'','decision_usefulness':'',
                         'answer_file':'','source_refs':'','reviewer':'','review_notes':''})
    with (root/'quality-scores.csv').open('w', newline='') as fp:
        writer=csv.DictWriter(fp,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
    (root/'cost-ledger.csv').write_text('tool,question_id,elapsed_seconds,cpu_seconds,electricity_kwh,electricity_usd,api_usd,paid_data_usd,hardware_usd,other_usd,notes\n')
    (root/'questions.json').write_text(json.dumps({'questions':questions},indent=2)+'\n')
    return root

def score(root):
    root=Path(root)
    with (root/'quality-scores.csv').open(newline='') as fp: rows=list(csv.DictReader(fp))
    bytool={}; incomplete=0
    for row in rows:
        vals=[]
        for k in DIMENSIONS:
            v=row[k].strip()
            if not v: continue
            n=int(v)
            if not 0<=n<=4: raise ValueError(f'{row["question_id"]}: {k} outside 0..4')
            vals.append(n)
        if len(vals)!=len(DIMENSIONS) or not row['reviewer'].strip() or not row['answer_file'].strip():
            incomplete+=1;continue
        bytool.setdefault(row['tool'],[]).append({'question_id':row['question_id'], 'score':sum(vals)/len(vals)})
    costs={}; cost_rows=[]
    with (root/'cost-ledger.csv').open(newline='') as fp:
        for row in csv.DictReader(fp):
            numeric=('electricity_usd','api_usd','paid_data_usd','hardware_usd','other_usd')
            if not all(row[k].strip() for k in numeric): continue
            amount=sum(float(row[k]) for k in numeric)
            if amount<0: raise ValueError('Negative cost')
            costs.setdefault(row['tool'],[]).append(amount)
            cost_rows.append(row)
    return {'status':'complete' if incomplete==0 and len(cost_rows)>=len(rows) else 'partial',
            'quality_scored':sum(map(len,bytool.values())), 'quality_pending':incomplete,
            'by_tool':{k:{'scored_questions':len(v),'mean_score_0_to_4':round(sum(x['score'] for x in v)/len(v),3),
                          'scores':v, 'cost_record_count':len(costs.get(k,[])),
                          'recorded_cost_total_usd':round(sum(costs.get(k,[])),4) if costs.get(k) else None}
                       for k,v in bytool.items()},
            'costs_with_complete_fields':len(cost_rows),
            'limitations':['Manual blinded scoring required; no automatic claims of answer correctness.',
                           'Recorded costs are not comparable until scope and included categories match.',
                           'Missing values are unknown, never treated as zero.']}

def main(argv=None):
    p=argparse.ArgumentParser()
    sub=p.add_subparsers(dest='cmd',required=True)
    init=sub.add_parser('init');init.add_argument('--output',default='reports/benchmark-v1')
    run=sub.add_parser('run');run.add_argument('--output',default='reports/benchmark-v1');run.add_argument('--model',default='qwen3:8b');run.add_argument('--sec-stream',default='investment.sec.events');run.add_argument('--as-of',default=None)
    report=sub.add_parser('report');report.add_argument('--output',default='reports/benchmark-v1')
    args=p.parse_args(argv)
    if args.cmd=='init': print(scaffold(args.output,load_questions()))
    elif args.cmd=='run':
        root=Path(args.output);root.mkdir(parents=True,exist_ok=True)
        results=[]
        for ticker in ('NVDA','MSFT'):
            results.append(run_pipeline(ticker,root/ticker.lower(),args.model,args.sec_stream,args.as_of,root/f'{ticker.lower()}.log'))
        (root/'run-metrics.json').write_text(json.dumps({'runs':results},indent=2)+'\n')
        print(json.dumps(results,indent=2))
        if any(x['exit_code']!=0 for x in results):sys.exit(1)
    else:
        result=score(args.output);(Path(args.output)/'benchmark-report.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
if __name__=='__main__':main()
