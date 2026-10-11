"""A small, dependency-light text classifier: e-bike vs moped, from NEISS injury narratives.

The model is TF-IDF (words and two-word phrases) + logistic regression, trained on NEISS
2024-2025 records where CPSC's codes separate e-bikes (5045) from other power-assisted
cycles (5046). It is stored as plain JSON (vocabulary, IDF weights, coefficients), so it
runs with numpy only and does not depend on a scikit-learn version. Retrain with
``scripts/train_classifier.py``.
"""
from __future__ import annotations

import json
import math
import re
from collections import Counter
from dataclasses import dataclass, field
from importlib import resources
from pathlib import Path
from typing import Iterable, Union

import numpy as np

_TOKEN = re.compile(r"(?u)\b\w\w+\b")  # scikit-learn's default token pattern


def _features(text: str, ngram_max: int = 2) -> Counter:
    tokens = _TOKEN.findall(text.lower())
    feats: Counter = Counter(tokens)
    for n in range(2, ngram_max + 1):
        feats.update(" ".join(tokens[i:i + n]) for i in range(len(tokens) - n + 1))
    return feats


@dataclass
class EbikeMopedClassifier:
    idf: dict[str, float]
    coef: dict[str, float]
    intercept: float
    ngram_max: int = 2
    sublinear_tf: bool = True
    meta: dict = field(default_factory=dict)

    # ---------- prediction ----------
    def decision(self, text: str) -> float:
        feats = _features(text, self.ngram_max)
        weights = {}
        for term, tf in feats.items():
            idf = self.idf.get(term)
            if idf is None:
                continue
            weights[term] = (1.0 + math.log(tf) if self.sublinear_tf else float(tf)) * idf
        norm = math.sqrt(sum(w * w for w in weights.values())) or 1.0
        return self.intercept + sum(w / norm * self.coef.get(t, 0.0) for t, w in weights.items())

    def predict_proba(self, texts: Iterable[str]) -> np.ndarray:
        """Probability that each narrative describes an e-bike (vs a moped or similar)."""
        z = np.array([self.decision(t) for t in texts], dtype=float)
        return 1.0 / (1.0 + np.exp(-z))

    # ---------- storage ----------
    def to_json(self, path: Union[str, Path]) -> None:
        terms = sorted(self.idf)
        payload = {"meta": self.meta, "ngram_max": self.ngram_max, "sublinear_tf": self.sublinear_tf,
                   "intercept": round(self.intercept, 8),
                   "terms": terms,
                   "idf": [round(self.idf[t], 6) for t in terms],
                   "coef": [round(self.coef.get(t, 0.0), 6) for t in terms]}
        Path(path).write_text(json.dumps(payload, separators=(",", ":")))

    @classmethod
    def from_json(cls, path_or_text: Union[str, Path]) -> "EbikeMopedClassifier":
        s = str(path_or_text)
        text = s if s.lstrip().startswith("{") else Path(s).read_text()
        p = json.loads(text)
        idf = dict(zip(p["terms"], p["idf"]))
        coef = {t: c for t, c in zip(p["terms"], p["coef"]) if c != 0.0}
        return cls(idf=idf, coef=coef, intercept=p["intercept"], ngram_max=p.get("ngram_max", 2),
                   sublinear_tf=p.get("sublinear_tf", True), meta=p.get("meta", {}))

    @classmethod
    def load_default(cls) -> "EbikeMopedClassifier":
        text = resources.files("neissai").joinpath("model/ebike_moped_v1.json").read_text()
        return cls.from_json(text)

    # ---------- training (needs scikit-learn) ----------
    @classmethod
    def fit(cls, texts: list[str], is_ebike: list[int], min_df: int = 3, C: float = 4.0,
            cv_folds: int = 5) -> "EbikeMopedClassifier":
        from sklearn.feature_extraction.text import TfidfVectorizer
        from sklearn.linear_model import LogisticRegression
        from sklearn.model_selection import cross_val_score

        vec = TfidfVectorizer(ngram_range=(1, 2), min_df=min_df, sublinear_tf=True)
        X = vec.fit_transform(texts)
        lr = LogisticRegression(max_iter=2000, C=C, class_weight="balanced")
        auc = float(cross_val_score(lr, X, is_ebike, cv=cv_folds, scoring="roc_auc").mean())
        lr.fit(X, is_ebike)
        vocab = vec.get_feature_names_out()
        idf = dict(zip(vocab, vec.idf_.tolist()))
        coef = dict(zip(vocab, lr.coef_[0].tolist()))
        meta = {"n_train": len(texts), "n_ebike": int(sum(is_ebike)), "cv_auc": round(auc, 4),
                "model": "TF-IDF (1-2 grams, sublinear) + logistic regression (balanced)"}
        return cls(idf=idf, coef=coef, intercept=float(lr.intercept_[0]), meta=meta)
