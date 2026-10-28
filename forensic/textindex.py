"""A small TF-IDF vector index in numpy (word 1-2 grams, sublinear tf, smoothed idf, L2-normalised).

Kept dependency-free so the API fits in a serverless function bundle. Rows are L2-normalised,
so cosine similarity is a plain dot product.
"""
from __future__ import annotations

import math
import re
from collections import Counter

import numpy as np

STOP_WORDS = frozenset("""
a about above after again against all also am an and any are as at be because been before being below between
both but by can could did do does doing down during each few for from further had has have having he her here
hers herself him himself his how i if in into is it its itself just me more most my myself no nor not now of
off on once only or other our ours ourselves out over own same she should so some such than that the their
theirs them themselves then there these they this those through to too under until up very was we were what
when where which while who whom why will with would you your yours yourself yourselves per via within
""".split())
_TOKEN = re.compile(r"(?u)\b\w\w+\b")


def _terms(text: str) -> list:
    words = [w for w in _TOKEN.findall(text.lower()) if w not in STOP_WORDS]
    return words + [f"{a} {b}" for a, b in zip(words, words[1:])]


class TfidfIndex:
    def __init__(self, texts: list) -> None:
        docs = [Counter(_terms(t)) for t in texts]
        df = Counter(term for d in docs for term in d)
        self.vocab = {term: i for i, term in enumerate(sorted(df))}
        n = len(docs)
        self.idf = np.array([math.log((1 + n) / (1 + df[t])) + 1 for t in sorted(df)])
        self.matrix = np.vstack([self._vector(d) for d in docs]) if docs else np.zeros((0, len(self.vocab)))

    def _vector(self, counts: Counter) -> np.ndarray:
        v = np.zeros(len(self.vocab))
        for term, c in counts.items():
            i = self.vocab.get(term)
            if i is not None:
                v[i] = (1 + math.log(c)) * self.idf[i]
        norm = np.linalg.norm(v)
        return v / norm if norm else v

    def similarity(self, query: str) -> np.ndarray:
        # Element-wise rather than `@`: numpy 2.0 + macOS Accelerate emits spurious matmul warnings.
        return (self.matrix * self._vector(Counter(_terms(query)))).sum(axis=1)
