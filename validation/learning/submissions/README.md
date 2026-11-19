Put CSV files that reviewers email from docs/label.html here (one file per reviewer and batch),
then run:

    python validation/ingest_human_labels.py
    python validation/check_learning.py

Only reviewers listed with approved = yes in ../trusted_labellers.csv are used.
