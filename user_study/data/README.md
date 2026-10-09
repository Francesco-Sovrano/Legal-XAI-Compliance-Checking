# Legal-expert validation data and analysis

This directory contains the recorded response database and the statistical analysis for the legal-expert validation in two legal contexts: a GDPR automated credit-refusal case and an MDR medical-device case.

## Files

| Path | Content |
| :--- | :--- |
| `public-review.sqlite3` | Recorded response database used by `legal_expert_validation.py`. |
| `public-review.sqlite3.zip` | Compressed copy of the recorded response database. |
| `no_test_public-review.sqlite3.zip` | Compressed database containing the four-session analytic cohort only. |
| `legal_expert_validation.py` | Formula scores, primary-rating concordance, sensitivity concordance, comparison-stage concordance, exact permutation tests, and figures. |
| `data_audit.py` | Database, cohort, qualitative-coding, and instrument-hash audit code. The instrument-hash step requires UI files that are not present in this package. |
| `analysis/` | Legal-expert numerical outputs and figures. |
| `audit/` | Database schema, session export, qualitative-coding export, and audit summary. |
| `requirements.txt` | Python dependencies for the statistical analysis. |

## Analytic cohort

The recorded database contains six sessions. `legal_expert_validation.py` uses the fixed analytic cohort `E08`, `E11`, `E13`, and `E18`. These four sessions are complete and correspond to the four legal academics reported in the manuscript. Session `E01` is incomplete. Session `E02` reports zero years of legal experience and is not part of the analytic cohort.

Each included participant completed four primary judgments in each legal context, yielding 32 primary judgments.

The GDPR case contains Approximate local SHAP, PDP, CEM, and DiCE. PDP is procedurally ineligible because the legal task requires a local explanation of an individual decision. The MDR case contains Global SHAP, PDP, Decision Trees, and RuleSHAP; all four are procedurally eligible.

The primary numeric outcome is the 1–7 legal-goal rating. The analysis also uses the final ranking recorded at the comparison stage. Kendall tau-b is used for rank concordance because ties can occur.

## Environment

From the package root:

```sh
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -r user_study/data/requirements.txt
```

The dependency set is identical to `methods_scoring/requirements.txt`.

## Reproduce the statistical analysis

The analysis requires the joint sensitivity draws produced by `methods_scoring/sensitivity_analysis.py`:

```sh
python methods_scoring/sensitivity_analysis.py \
  --draws 10000 \
  --seed 20261005 \
  --outdir methods_scoring/analysis

python user_study/data/legal_expert_validation.py \
  user_study/data/public-review.sqlite3 \
  --drawdir methods_scoring/analysis \
  --outdir user_study/data/analysis
```

The database is opened read-only by the validation script.

## Statistical outputs

| File | Content |
| :--- | :--- |
| `locked_ratings_gdpr.csv` | Primary 1–7 legal-goal ratings for the GDPR case. |
| `locked_ratings_mdr.csv` | Primary 1–7 legal-goal ratings for the MDR case. |
| `formula_scores_gdpr.csv` | Soft, geometric, and thresholded scores for the four GDPR explanation packages. |
| `formula_scores_mdr.csv` | Soft, geometric, and thresholded scores for the four MDR explanation packages. |
| `expert_alignment_per_expert.csv` | Per-participant Kendall tau-b values for each scoring view and legal context. |
| `expert_alignment_metrics.csv` | Median primary concordance by legal context and across both contexts. |
| `sensitivity_concordance_gdpr.csv` | Draw-level GDPR concordance values used in the sensitivity summary. |
| `sensitivity_concordance_mdr.csv` | Draw-level MDR concordance values used in the sensitivity summary. |
| `comparison_stage_concordance.csv` | Concordance with the final comparison-stage rankings and counts of changed legal-goal ratings. |
| `exploratory_permutation_tests.csv` | One-sided exact permutation-test p-values and Benjamini–Hochberg adjusted q-values. |
| `expert_summary.json` | Compact summary of the primary, sensitivity, and comparison-stage results. |
| `expert_alignment_gdpr.pdf` | GDPR formula-ranking and expert-ranking figure. |
| `expert_alignment_mdr.pdf` | MDR formula-ranking and expert-ranking figure. |
| `expert_alignment_across_regulations.pdf` | Cross-context concordance figure. |

## Qualitative coding and audit files

`methods_scoring/inputs/qualitative_annotations.json` contains one manual binary coding record for each of the 32 primary rationales. The code marks whether the rationale uses language corresponding to the interpretability properties. `audit/qualitative_annotations.csv` is the tabular export of those records.

`data_audit.py` also exports the session table and database schema. Its final instrument-hash comparison imports `user_study/ui/study_core.py` and reads `user_study/ui/config/study.json`. Those files are not present, so the complete audit cannot be regenerated from this package alone. The statistical analysis in `legal_expert_validation.py` does not depend on the UI source files.

The full scoring and data specification is `methods_scoring/assess_xai_compliance_documentation.md` from the package root.
