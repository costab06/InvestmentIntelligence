import asyncio
import pytest
from test_analyst_v050 import sample
from investment_intelligence.analyst_v060 import DIMENSIONS, analyze_v060, evaluate_statement, normalize_evidence


def statement():
    return {'id':'S001','statement':{'text':'Cash generation may weaken'},'status':'warning'}


def test_all_twelve_dimensions_always_present():
    row=evaluate_statement(statement(),{'F001'})
    assert list(row['dimensions'])==list(DIMENSIONS)
    assert row['summary']['counts']['insufficient_evidence']==12


def test_supplied_assessment_requires_evidence():
    with pytest.raises(ValueError):
        evaluate_statement(statement(),{'F001'},{'financial':{'assessment':'supports','confidence':'high','materiality':'high'}})


def test_supplied_assessment_and_summary():
    row=evaluate_statement(statement(),{'F001'},{'financial':{'assessment':'contradicts','confidence':'high','materiality':'high','evidence_ids':['F001'],'rationale':'Countervailing verified finding'}})
    assert row['summary']['high_materiality_contradictions']==['financial']
    assert row['summary']['counts']['insufficient_evidence']==11


def test_unknown_dimension_rejected():
    with pytest.raises(ValueError):evaluate_statement(statement(),set(),{'new_dimension':{}})


def test_document_provenance_required():
    with pytest.raises(ValueError):normalize_evidence([{'id':'D001','text':'No source'}])


def test_end_to_end_financial_only():
    result=asyncio.run(analyze_v060(sample()))
    assert result['schema_version']=='0.6.0'
    assert len(result['framework']['dimensions'])==12
    assert result['statement_evaluations']==[]
    assert 'Twelve-Dimension' in result['report_markdown']
    assert result['coverage']['cash_generation']
