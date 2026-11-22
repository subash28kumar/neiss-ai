# E-bike vs moped model on HARD notes (the kind it decides before 2024)

Notes coded 5045 (e-bike) or 5046 (moped) in 2024-2025, in the model's locked test split, that name neither device. The hospital's code is the answer key. Same model the site uses.

| Notes | Number (e-bikes) | Accuracy | E-bikes found | Mopeds kept out | AUC |
| --- | --- | --- | --- | --- | --- |
| all test notes | 833 (566) | 98.0% [97.0%-98.8%] | 98.6% [97.6%-99.5%] | 96.6% [94.4%-98.5%] | 0.998 |
| HARD test notes (no e-bike or moped words) | 54 (37) | 74.1% [61.1%-85.2%] | 83.8% [70.6%-94.3%] | 52.9% [27.3%-76.5%] | 0.763 |
| easy test notes (name the device) | 779 (529) | 99.6% [99.1%-100.0%] | 99.6% [99.0%-100.0%] | 99.6% [98.7%-100.0%] | 1.000 |

Hard stories are 7.2% of all 2024-2025 5045/5046 notes.

Limit: these are 2024-2025 notes. Notes written before 2024 may differ (for example, staff may have written 'moped' or 'e-bike' less often when one code covered both). This is the closest test possible without a hand-checked answer key for older notes.

Run: `python validation/classifier_v2/hard_notes.py --data-dir data` (needs CPSC's 2024-2025 files).
