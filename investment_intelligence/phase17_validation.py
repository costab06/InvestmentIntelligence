"""Phase 17: conservative cash-flow bridge and optional local SEC raw HTML audit.

Never infers missing values, overwrites SECAgents artifacts, or promotes hypotheses.
"""
from __future__ import annotations

from collections import Counter
from decimal import Decimal, InvalidOperation
from html.parser import HTMLParser
from pathlib import Path
import hashlib
import re


class _HTMLText(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.skip = 0
        self.parts = []
    def handle_starttag(self, tag, attrs):
        if tag in ('script', 'style', 'noscript'):
            self.skip += 1
        elif tag in ('p', 'div', 'h1', 'h2', 'h3', 'tr', 'li'):
            self.parts.append(' ')
    def handle_endtag(self, tag):
        if tag in ('script', 'style', 'noscript'):
            self.skip = max(0, self.skip - 1)
        elif tag in ('p', 'div', 'h1', 'h2', 'h3', 'tr', 'li'):
            self.parts.append(' ')
    def handle_data(self, data):
        if not self.skip:
            self.parts.append(data)


def _tokens(s):
    return set(re.findall(r'[a-z]{4,}', s.lower()))


def audit_local_raw_html(raw_path, parsed_path):
    """Compare token coverage, not document completeness, using caller-supplied local files."""
    import json
    raw_path, parsed_path = Path(raw_path), Path(parsed_path)
    raw_bytes = raw_path.read_bytes()
    parsed_bytes = parsed_path.read_bytes()
    doc = json.loads(parsed_bytes)
    parser = _HTMLText()
    parser.feed(raw_bytes.decode('utf-8', errors='replace'))
    raw_text = ' '.join(parser.parts)
    blocks = doc.get('document', {}).get('blocks', [])
    parsed_text = ' '.join(str(b.get('text') or '') for b in blocks if isinstance(b, dict))
    raw_tokens = _tokens(raw_text)
    parsed_tokens = _tokens(parsed_text)
    missing = raw_tokens - parsed_tokens
    types = Counter(str(b.get('type', 'unknown')) for b in blocks if isinstance(b, dict))
    return {'status':'local_raw_comparison_completed',
            'raw_sha256':hashlib.sha256(raw_bytes).hexdigest(),
            'parsed_sha256':hashlib.sha256(parsed_bytes).hexdigest(),
            'raw_file':str(raw_path), 'parsed_file':str(parsed_path),
            'raw_distinct_tokens':len(raw_tokens),
            'parsed_distinct_tokens':len(parsed_tokens),
            'raw_token_recall':str(Decimal(len(raw_tokens & parsed_tokens))/Decimal(len(raw_tokens))) if raw_tokens else None,
            'sample_missing_tokens':sorted(missing)[:30],
            'block_type_counts':dict(types),
            'narrative_missing_suspected':bool(types and types.get('table', 0)==sum(types.values()) and missing),
            'limitations':['Token recall is a diagnostic, not semantic or section-level completeness.',
                           'HTML may contain exhibits, navigation, XBRL metadata or other non-narrative text.',
                           'Verify accession and CIK identity externally before interpreting coverage.']}


def build_cash_flow_reconciliation(cash_flow):
    """Recompute signed components and explicit residual using existing sourced evidence."""
    periods = []
    for p in (cash_flow or {}).get('periods', []):
        try:
            ni = Decimal(str(p['net_income_usd']))
            ocf = Decimal(str(p['operating_cash_flow_usd']))
        except (KeyError, TypeError, InvalidOperation):
            continue
        selected = []
        missing = []
        by_category = {}
        for key, item in (p.get('components') or {}).items():
            if item.get('status') != 'selected' or item.get('cash_flow_contribution_usd') is None:
                missing.append(key)
                continue
            try:
                amount = Decimal(str(item['cash_flow_contribution_usd']))
            except InvalidOperation:
                missing.append(key)
                continue
            category = item.get('category') or 'unclassified'
            by_category[category] = by_category.get(category, Decimal(0)) + amount
            selected.append({'component':key,'category':category,'cash_flow_contribution_usd':str(amount),
                             'provenance':item.get('provenance')})
        total = sum((Decimal(x['cash_flow_contribution_usd']) for x in selected), Decimal(0))
        gap = ocf - ni
        residual = gap - total
        periods.append({'period_end':p.get('period_end'),'net_income_usd':str(ni),
                        'operating_cash_flow_usd':str(ocf),'observed_gap_usd':str(gap),
                        'selected_components':selected,'missing_components':missing,
                        'category_totals_usd':{k:str(v) for k,v in by_category.items()},
                        'selected_total_usd':str(total),'unexplained_residual_usd':str(residual),
                        'arithmetic_identity_verified':gap == total + residual,
                        'complete_reconciliation':bool(p.get('complete_reconciliation')) and not missing and residual == 0,
                        'source_residual_agrees': (str(residual)==str(p['unexplained_residual_usd']) if 'unexplained_residual_usd' in p else None)})
    return {'schema_version':'1.0.0','status':'partial_reconciliation' if periods else 'no_periods',
            'periods':periods,'hypothesis_status_changed':False,'publication_eligible':False,
            'limitations':['An arithmetic residual is not a financial explanation.',
                           'Missing issuer-specific and untagged line items remain unknown.',
                           'Components are inherited from existing CompanyFacts evidence; sign and period mapping require source verification.',
                           'Do not add narrative table values to structured components without de-duplication.']}
