"""Retrain the e-bike vs moped classifier from NEISS 2024+ files and save it as JSON.

    python scripts/train_classifier.py --data-dir data --years 2024-2025

Training labels come from CPSC's product codes: 5045 (e-bikes) vs 5046 (other power-assisted
cycles). Records carrying both codes are dropped.
"""
import argparse

from neissai.classifier import EbikeMopedClassifier
from neissai.io import read_neiss

ap = argparse.ArgumentParser()
ap.add_argument("--data-dir", default="data")
ap.add_argument("--years", default="2024-2025")
ap.add_argument("--out", default="src/neissai/model/ebike_moped_v1.json")
a = ap.parse_args()

df = read_neiss(a.data_dir, a.years)
codes = df[["Product_1", "Product_2", "Product_3"]]
eb, mo = codes.isin(["5045"]).any(axis=1), codes.isin(["5046"]).any(axis=1)
train = df[eb ^ mo]
clf = EbikeMopedClassifier.fit(train["Narrative"].str.upper().tolist(), eb[train.index].astype(int).tolist())
clf.meta["years"] = a.years
clf.to_json(a.out)
print(f"Trained on {clf.meta['n_train']:,} narratives ({clf.meta['n_ebike']:,} e-bikes); "
      f"5-fold cross-validated AUC = {clf.meta['cv_auc']}. Saved {a.out}")
