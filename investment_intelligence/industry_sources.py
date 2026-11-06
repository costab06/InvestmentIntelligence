"""Industry-source candidate discovery, NOT an automatic claim of comparability.

A candidate requires dataset-level review before retrieval. Registry contains
public provider documentation endpoints, not invented series identifiers.
"""

SOURCE_CANDIDATES = {
    '3674': [
      {'provider':'BEA','dataset':'GDPbyIndustry','documentation_url':'https://apps.bea.gov/api/','topic':'US semiconductor manufacturing output','status':'candidate_requires_series_review', 'limitations':['US real output differs from global nominal company revenue','Broader industry classification may include products not sold by issuer']},
      {'provider':'Federal Reserve','dataset':'G.17 Industrial Production','documentation_url':'https://www.federalreserve.gov/releases/g17/','topic':'Semiconductor and related electronic components production','status':'candidate_requires_series_review','limitations':['Production volume is not issuer revenue or market share']},
      {'provider':'Census Bureau','dataset':'Annual Survey of Manufactures','documentation_url':'https://www.census.gov/programs-surveys/asm.html','topic':'Semiconductor manufacturing shipments','status':'candidate_requires_series_review','limitations':['US establishments are not global fabless designer revenue']},
    ],
}

def discover_industry_sources(resolution):
    sic = str(resolution.get('sic') or '')
    candidates=[dict(item) for item in SOURCE_CANDIDATES.get(sic, [])]
    return {'schema_version':'1.0.0','ticker':resolution.get('ticker'),'sic':sic or None,
            'status':'candidates_found_review_required' if candidates else 'no_reviewed_candidates',
            'candidates':candidates,'retrieval_performed':False,
            'limitations':['Candidate discovery is not dataset retrieval or corroboration.',
                           'Dataset identifiers, measurement, geography, frequency and segment applicability require review before retrieval.']}
