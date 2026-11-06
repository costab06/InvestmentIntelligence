import csv
import json
import tempfile
import unittest
from pathlib import Path
from benchmark.runner import load_questions, scaffold, score, DIMENSIONS

class BenchmarkTests(unittest.TestCase):
    def test_question_set(self):
        q=load_questions();self.assertEqual(len(q),10);self.assertEqual({x['ticker'] for x in q},{'NVDA','MSFT'})
    def test_scaffold_and_incomplete_report(self):
        with tempfile.TemporaryDirectory() as d:
            scaffold(d,load_questions());r=score(d)
            self.assertEqual(r['quality_pending'],30)
            self.assertEqual(r['status'],'partial')
            self.assertEqual(r['costs_with_complete_fields'],0)
    def test_complete_score_requires_reviewer_and_answer(self):
        with tempfile.TemporaryDirectory() as d:
            scaffold(d,load_questions());p=Path(d)/'quality-scores.csv'
            with p.open(newline='') as f: rows=list(csv.DictReader(f))
            for k in DIMENSIONS: rows[0][k]='4'
            rows[0]['reviewer']='human';rows[0]['answer_file']='reviewed.txt'
            with p.open('w',newline='') as f:
                w=csv.DictWriter(f,fieldnames=rows[0].keys());w.writeheader();w.writerows(rows)
            r=score(d);self.assertEqual(r['quality_scored'],1)
            self.assertEqual(r['by_tool']['InvestmentIntelligence']['mean_score_0_to_4'],4)
    def test_out_of_range_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            scaffold(d,load_questions());p=Path(d)/'quality-scores.csv'
            t=p.read_text().replace('NVDA-1,NVDA,InvestmentIntelligence,','NVDA-1,NVDA,InvestmentIntelligence,5,',1)
            p.write_text(t)
            with self.assertRaises(ValueError):score(d)

if __name__=='__main__':unittest.main()
