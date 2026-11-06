"""Deterministic BM25 passage retrieval with dimension-aware queries.

No external model or new dependency required. Returns only supplied evidence.
"""
from __future__ import annotations
from collections import Counter
import math
import re

TOKEN = re.compile(r"[a-z][a-z0-9]{2,}")
STOP = frozenset('the and for with from this that are was were have has into could would should suggests indicates about between relative more less than based company financial performance'.split())
DIMENSION_TERMS = {
    'historical': 'prior year historical trend previous period growth',
    'industry': 'industry sector market industry trends',
    'competitive': 'competitor competition market share competitive position',
    'financial': 'revenue earnings margin cash flow capital expenditures liquidity',
    'valuation': 'share price market capitalization valuation multiples earnings yield',
    'macroeconomic': 'inflation interest rates exchange currency economic demand',
    'management_strategy': 'management strategy investment capital allocation priorities',
    'operational': 'capacity infrastructure operations efficiency datacenter utilization',
    'risk': 'risk uncertainty adverse exposure liquidity obligations',
    'temporal': 'fiscal year reporting period future previous quarter',
    'forward_looking': 'outlook expect anticipate guidance forecast future',
    'evidence_quality': 'accounting methodology estimate uncertainty audit',
}

def tokens(s):
    return [w for w in TOKEN.findall(s.lower()) if w not in STOP]

def retrieve(statement, dimension, documents, limit=5):
    """Return ranked evidence passages, stable by original position on ties.

    A zero-overlap passage is not considered relevant. This is lexical BM25,
    not embedding-based semantic retrieval; results are auditable and offline.
    """
    if limit < 1:
        raise ValueError('limit must be positive')
    if not documents:
        return []
    query = Counter(tokens(statement + ' ' + DIMENSION_TERMS.get(dimension, '')))
    corpus = [Counter(tokens(d['text'])) for d in documents]
    df = Counter(w for doc in corpus for w in doc)
    n = len(corpus)
    avgdl = sum(sum(doc.values()) for doc in corpus) / n or 1
    scored = []
    for index, (document, tf) in enumerate(zip(documents, corpus)):
        dl = sum(tf.values())
        score = 0.0
        for word, qf in query.items():
            freq = tf.get(word, 0)
            if not freq:
                continue
            idf = math.log(1 + (n - df[word] + .5) / (df[word] + .5))
            score += idf * freq * 2.2 / (freq + 1.2 * (.25 + .75 * dl / avgdl)) * min(qf, 2)
        if score > 0:
            scored.append((score, index, document))
    scored.sort(key=lambda item: (-item[0], item[1]))
    return [doc for _, _, doc in scored[:limit]]
