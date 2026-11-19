# E-bike vs moped classifier: train / validation / test results (v2)

Data: NEISS 2024-2025, records coded 5045 (e-bike) or 5046 (other power-assisted cycle), not both: 5,500 stories (3,646 e-bikes).

| Split | Stories | Share | E-bikes |
| --- | --- | --- | --- |
| Train | 3,791 | 69% | 2,508 |
| Validation | 876 | 16% | 572 |
| Test (locked) | 833 | 15% | 566 |

Tuning on validation (AUC by regularisation strength C):

| C | Validation AUC |
| --- | --- |
| 0.25 | 0.9915 |
| 0.5 | 0.9947 |
| 1.0 | 0.9963 |
| 2.0 | 0.9970 |
| 4.0 | 0.9972 |
| 8.0 | 0.9972 |
| 16.0 | 0.9970 |

Chosen C = 8.0. Final model retrained on train + validation, then scored once on the test set.

| Test result | Value | 95% CI |
| --- | --- | --- |
| AUC | 0.998 | 0.996-0.999 |
| Accuracy (cut-off 0.5) | 0.980 | 0.970-0.988 |
| Sensitivity (e-bikes found) | 0.986 | 0.975-0.995 |
| Specificity (mopeds kept out) | 0.966 | 0.944-0.985 |
