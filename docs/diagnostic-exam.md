# Diagnostic practice exam plan

**Goal:** Take a practice exam *before* studying so we can weight the study plan against your actual gaps, not generic exam weights.

## Step 1 — Take both official sample tests cold (≈90 min total)

These are free, written by Google, and re-scored each year.

- [Professional Cloud Architect sample questions](https://docs.google.com/forms/d/e/1FAIpQLSfexWKtXT2OSFJ-obA4iT3GmzgiOCqqUCYBpZ2Pk1pwivxHVw/viewform) — ~25 questions, ~45 min
- [Professional Cloud DevOps Engineer sample questions](https://docs.google.com/forms/d/e/1FAIpQLSdSYqHC0XGqz1gMfbA9-V5hfukhJ1BC9c1HWVKyRjgSWzdJaA/viewform) — ~20 questions, ~40 min

> If those URLs 404, navigate from each cert's landing page on cloud.google.com → "Sample questions". Google rotates form IDs.

**Rules:**
- No notes, no Google.
- Mark each question with a confidence flag: `confident` / `eliminated to 2` / `pure guess`.
- Don't peek at answers until done with both.

## Step 2 — Score & classify

For each missed/guessed question, tag it against the matching exam-guide subsection (e.g. `PCA-3.1`, `DevOps-4.3`). Use the table in [study-plan.md](study-plan.md).

Fill out:

```
Cert: PCA / DevOps
Score: __ / __
Domains where I missed >1 question:
  - [ ] PCA-1.x  Designing
  - [ ] PCA-2.x  Provisioning
  - [ ] PCA-3.x  Security/compliance
  - [ ] PCA-4.x  Processes
  - [ ] PCA-5.x  Implementation
  - [ ] PCA-6.x  Ops excellence
  - [ ] DevOps-1.x  Org bootstrapping
  - [ ] DevOps-2.x  CI/CD
  - [ ] DevOps-3.x  SRE
  - [ ] DevOps-4.x  Observability
  - [ ] DevOps-5.x  Cost
Domains where confidence ≥ 80%:
  ...
```

## Step 3 — Reweight the plan

- **Missed >40% in a domain** → expand to a full lab + read the linked Google docs end-to-end.
- **Missed 1–40%** → read the cheat sheet row + skim the official doc.
- **≥80% confidence, all correct** → skip; reconfirm with mock exam at the end.

## Step 4 — Re-take after each lab milestone

- Mock 1 — after labs 01–02 (bootstrapping + CI/CD)
- Mock 2 — after labs 03–04 (GKE + observability)
- Mock 3 — pre-exam, full-length

For full-length practice, the highest-quality paid options:

| Source | Notes |
|---|---|
| [Google Cloud Skills Boost — Professional Cloud Architect prep course](https://www.cloudskillsboost.google/paths/9) | Includes practice exam; first month often free with promo |
| [Google Cloud Skills Boost — Professional DevOps Engineer prep](https://www.cloudskillsboost.google/paths/20) | Same pattern |
| Whizlabs / Tutorials Dojo / ExamTopics | Quality varies; cross-check answers against official docs |

> ExamTopics often has incorrect "community" answers. Treat as flashcards, not truth.
