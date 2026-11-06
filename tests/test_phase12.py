from investment_intelligence.evidence_orchestration import orchestrate_evidence


def sample():
    return {'investigation_registry': {'investigations': [
        {'id': 'earnings_quality', 'status': 'triggered', 'investigator': None},
        {'id': 'capital_investment_economics', 'status': 'triggered', 'investigator': 'capital_investigation'},
        {'id': 'revenue_margin_divergence', 'status': 'not_triggered'}]},
        'earnings_quality_investigation': {'observations': [{'id': 'EQ-O3', 'status': 'calculated_from_filed_components'}],
            'next_evidence': [{'question': 'Which working-capital accounts explain cash conversion?'},
                              {'question': 'Is the gap temporary or persistent?'}]},
        'capital_investigation': {'observations': [{'code': 'cash_flow_bridge', 'status': 'verified'}],
            'next_evidence': [{'question': 'Does infrastructure utilization support future cash returns?'}]}}


def test_bounded_resolution_and_metadata():
    a = sample()
    out = orchestrate_evidence(a)
    assert out['summary'] == {'retrieved': 2, 'partial_evidence_retrieved': 1, 'insufficient_evidence': 0, 'not_attempted': 2}
    assert a['investigation_registry']['investigations'][0]['investigator'] == 'earnings_quality'
    assert all(t['investigation'] != 'revenue_margin_divergence' for t in out['tasks'])


def test_no_invented_retrieval():
    a = sample()
    a['earnings_quality_investigation']['observations'] = []
    out = orchestrate_evidence(a)
    assert out['tasks'][0]['status'] == 'insufficient_evidence'
    assert out['tasks'][1]['status'] == 'not_attempted'
    assert not out['tasks'][1]['attempted']


def test_no_trigger_means_no_tasks():
    a = sample()
    for item in a['investigation_registry']['investigations']:
        item['status'] = 'not_triggered'
    assert orchestrate_evidence(a)['tasks'] == []
