"""Issuer-neutral evidence planning from disclosed SEC SIC classification.

No ticker-specific rules. Unknown issuers receive generic questions.
"""

def _sic(analysis):
    candidates = [analysis.get('industry_resolution'), analysis.get('industry_context'),
                  analysis.get('company_profile'), analysis.get('company'), analysis.get('issuer')]
    for obj in candidates:
        if not isinstance(obj, dict):
            continue
        for key in ('sic', 'sic_code', 'sec_sic'):
            value = obj.get(key)
            if value is not None and str(value).strip().isdigit():
                return str(value).strip().zfill(4)
        for key in ('issuer', 'classification', 'sec_classification'):
            if isinstance(obj.get(key), dict):
                candidates.append(obj[key])
    return None


def capital_evidence_plan(analysis):
    sic = _sic(analysis)
    # SIC groups, not individual issuer names or tickers.
    if sic and (sic.startswith('367') or sic.startswith('366')):
        kind = 'semiconductor_or_electronics'
        specific = [
            ('How much capital spending supports internal facilities versus outsourced manufacturing and supplier commitments?',
             'Cash-flow capex categories, facilities disclosures, purchase obligations and manufacturing agreements'),
            ('Do inventory, receivables and supplier commitments indicate a sustainable cash conversion cycle?',
             'Inventory turns, receivable aging, supplier prepayments, purchase obligations and quarterly cash flows'),
            ('Is product demand converting into cash without excessive channel inventory?',
             'Segment revenue, customer concentration, inventory disclosures and independent demand indicators')]
    elif sic and (sic.startswith('737') or sic.startswith('738')):
        kind = 'software_or_services'
        specific = [
            ('How much capital spending supports capacity expansion versus maintenance and replacement?',
             'Issuer PP&E disclosures, equipment additions, leases and asset useful lives'),
            ('Does infrastructure utilization support future cash returns?',
             'Disclosed capacity utilization, segment margins, contract conversion and cash flows'),
            ('How do contract obligations and capital leases affect reported free cash flow?',
             'Remaining performance obligations, deferred revenue and lease cash-flow disclosures')]
    else:
        kind = 'unclassified'
        specific = [
            ('What is the composition of capital spending, including maintenance and growth investment?',
             'Issuer capital-spending disclosures, PP&E and intangible asset additions'),
            ('Does incremental investment generate attributable cash returns over time?',
             'Segment cash generation, invested capital and lagged returns'),
            ('Do financing structures or accounting policies affect measured cash investment?',
             'Lease cash flows, depreciation policy and relevant commitments')]
    common = [('Can invested capital generate sufficient cash returns over a measurable horizon?',
               'Multi-year operating profit, invested capital and cash flow by available segment'),
              ('Could capital leases or asset-life assumptions distort comparisons?',
               'Lease cash flows, asset additions and depreciation policies')]
    return {'business_model':kind, 'classification_basis':'sec_sic' if sic else 'unknown',
            'sic':sic, 'questions':[{'question':q,'needed':n,'status':'not_verified'} for q,n in specific+common]}
