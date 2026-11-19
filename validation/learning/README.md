# How NEISS-AI learns from people

NEISS-AI's rules can be wrong on hard stories. This folder holds the loop that lets trusted human
reviewers correct them, with guardrails so careless or bad answers cannot get in. Every step is
deterministic: the same inputs always give the same result.

## The loop

1. **Hard stories.** `scripts/build_train_set.py` scores every e-bike story for how close a call
   it is (unclear e-bike type, a speed near 28 mph, a guessed speed, motor-type wording, a vehicle
   mentioned but not counted as a crash, swerving to avoid something, unclear helmet wording) and
   keeps the 200 hardest (ties broken by story id). These become **Set C** on `docs/label.html`.
   Files: `set_c_items.csv` (with the reasons), `set_c_spotcheck.csv` (known answers).
2. **Reviewers label Set C** and email the CSV. Save it in `submissions/` (kept out of git,
   because it holds names). Add approved reviewers to `trusted_labellers.csv` (also private; see
   `trusted_labellers.example.csv`).
3. **Ingest with guardrails:** `python validation/ingest_human_labels.py`
   - trusted reviewers only (name and organization on the approved list);
   - spot checks: 22 stories with clear, known answers are mixed into Set C (one after every 9
     hard stories). A reviewer must answer at least 5 spot-check questions and get 90% right,
     or none of their answers are used;
   - agreement: an answer is learned only if at least 2 trusted reviewers give it and they are
     at least 75% of the answers for that story and question;
   - locked test stories (the validation test and development sets) are never learned from.
   Output: `human_memory.json` (no names) and `ingest_report.md` (reviewers shown as numbers).
4. **Gate:** `python validation/check_learning.py` compares rules alone with rules + memory on the
   locked tests (240 e-bike/e-moto, 300 motor vehicle/helmet stories). If any accuracy drops, it
   fails and the memory must not be published. Report: `check_report.md`.
5. **Use:** `scripts/update_site.py` applies the memory (`neissai.learn.apply_human_memory`):
   the same story gets the reviewers' answer; a near-identical story (word and phrase similarity at
   least 0.90) gets the answer of its closest labelled story; everything else keeps the rule
   answer. With an empty memory nothing changes.
6. **Fix the rules.** Patterns in the reviewers' answers are also used to improve the rules
   themselves in the next version, then re-tested on stories the rules never saw.

Every memory version is in git history, so any change can be undone.

## Also

- The website's "How NEISS-AI reads a story" panel has an "Is an answer wrong? Tell me" button.
  Reports are reviewed by hand and, if useful, the story is added to a future Set C.
- Known issue logged 2026-11-18 (not fixed yet, because the story is in the locked test): the
  e-moto rule trusts guessed speeds ("BYSTANDERS THOUGHT HE WAS GOING 30 MPH").
