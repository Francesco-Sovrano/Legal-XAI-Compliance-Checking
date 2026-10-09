# Legal XAI replication package

This package contains the data, code, and output files for the quantitative analyses in *Legal XAI: a Systematic Review and Interdisciplinary Mapping of XAI and EU Law, Towards a Research Agenda for Legally Responsible AI*.

The executable analyses cover:

1. property-based comparison of XAI method profiles across seven EU-law article bundles;
2. joint sensitivity analysis of method-property ratings, legal weights, technical priority factors, and thresholds;
3. deterministic legal-task sensitivity analysis for recipient- and delivery-time alternatives; and
4. legal-expert validation for a GDPR automated credit-refusal case and an MDR medical-device case.

The package also contains the method-property evidence records, the legal-weight matrix, the recorded legal-expert response database, the study-stimulus assets used for figures, and the numerical output files used by the manuscript.

## Core terminology

The documentation uses the following terms consistently.

| Term | Meaning |
| :--- | :--- |
| **XAI method profile** | One method representation in `methods_scoring/inputs/paper_inputs.json`, including its procedural attributes and 12 interpretability-property ratings. |
| **Interpretability property** | A technical property of the information extracted by an XAI method from an AI system. The 12 properties are listed below. |
| **Legal context** | One article bundle represented by a vector of legal weights over the 12 interpretability properties. |
| **Legal weight** | The coded strength of an interpretability-property requirement in a legal context: 1 for a requirement, 0.5 for a qualified requirement, and 0 when the property is not scored. |
| **XAI question type** | The type of information an XAI method must produce, such as `what_feature`, `what_rule`, or `what_if`. |
| **Procedural eligibility** | The pre-scoring check implemented in `scoring.eligible`: profile exclusions, XAI question type, combined explanatory scope/explanation stage, a nonzero runtime-performance rating, and optional model-access filtering. |
| **Soft score** | Weighted arithmetic mean of normalized method-property ratings. |
| **Thresholded score** | Share of legal weight assigned to properties whose method-property rating reaches the threshold. |
| **Geometric score** | Weighted geometric mean of normalized method-property ratings, with optional technical priority factors. |
| **Winner retention** | Probability that at least one default soft-score winner remains top-ranked under the joint sensitivity analysis. |
| **Legal-goal rating** | The 1–7 expert rating of whether an explanation enables the legal explanatory goal in the legal-expert validation. |

The 12 interpretability properties are **no false positives**, **no false negatives**, **completeness**, **stability**, **adversarial robustness**, **run-to-run consistency**, **explainer-parameter robustness**, **sparsity**, **level of detail**, **confidentiality**, **traceability**, and **runtime performance**. The JSON and Python files use machine-readable identifiers for some of these labels; the mapping is documented in `methods_scoring/assess_xai_compliance_documentation.md`.

## Package structure

| Path | Purpose |
| :--- | :--- |
| `methods_scoring/scoring.py` | Shared scoring equations, procedural eligibility, mandatory-property gate, joint perturbation draws, and Kendall tau-b helper. |
| `methods_scoring/sensitivity_analysis.py` | Joint sensitivity analysis, default scores, winner retention, winning probabilities, and context-level sensitivity figure. |
| `methods_scoring/question_sensitivity.py` | Question-level top-rank probabilities and question-level sensitivity figure. |
| `methods_scoring/legal_task_sensitivity.py` | Deterministic legal-task sensitivity analysis. |
| `methods_scoring/assess_xai_compliance.py` | Standalone catalogue example with embedded legal vectors. Its method ratings match the canonical catalogue, but its embedded legal vectors are not the manuscript's default legal-weight matrix. |
| `methods_scoring/inputs/paper_inputs.json` | Canonical property order, 26 method profiles, method-property ratings, procedural attributes, seven legal contexts, seed, draw count, and legal-expert study configuration. |
| `methods_scoring/inputs/score_evidence.json` | The 312 method-property evidence records and source locations supporting the 26 × 12 rating matrix. |
| `methods_scoring/inputs/literature_sources.json` | Source-key to URL mapping for the evidence records. |
| `methods_scoring/inputs/legal_task_variants.json` | Legal-task sensitivity intervals and four MDR task profiles. |
| `methods_scoring/inputs/legal_task_cases.json` | The 128 endpoint combinations and four MDR task cases evaluated by `legal_task_sensitivity.py`. |
| `methods_scoring/inputs/survey_counts.json` | Survey-count data used for the survey figures. |
| `methods_scoring/inputs/qualitative_annotations.json` | Manual coding of the 32 primary legal-expert rationales. |
| `methods_scoring/inputs/figures/` | Source assets for the static diagrams, survey figures, and legal-expert explanation stimuli. |
| `methods_scoring/analysis/` | Numerical outputs and sensitivity figures generated by the scoring scripts. |
| `methods_scoring/figures/` | Static figures and copies of analysis figures used by the manuscript. |
| `user_study/data/public-review.sqlite3` | Recorded legal-expert response database. |
| `user_study/data/public-review.sqlite3.zip` | Compressed copy of the recorded response database. |
| `user_study/data/no_test_public-review.sqlite3.zip` | Compressed database containing the four-session analytic cohort only. |
| `user_study/data/legal_expert_validation.py` | Legal-expert formula scores, Kendall tau-b concordance, sensitivity concordance, exact permutation tests, and validation figures. |
| `user_study/data/data_audit.py` | Database and qualitative-coding audit code. Its instrument-hash step requires files under `user_study/ui/` that are not present in this package. |
| `user_study/data/analysis/` | Legal-expert analysis outputs. |
| `user_study/data/audit/` | Database schema, session export, qualitative-coding export, and audit summary. |
| `methods_scoring/assess_xai_compliance_documentation.md` | Detailed computation, data, evidence, and output specification. |

`user_study/ui/` contains directory placeholders but no application source files. The legal-expert response database and its statistical analysis are present. The collection application, instrument configuration, and technical benchmark code are not present.

## Environment

The scoring and legal-expert analysis requirement files contain the same dependency set:

```text
numpy==2.3.5
pandas==2.2.3
scipy==1.17.0
matplotlib==3.10.8
Pillow>=11
PyMuPDF>=1.25
```

Python 3.11 or later is required by the package scripts. Create an environment from the package root:

```sh
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -r methods_scoring/requirements.txt
```

`setup.sh` additionally expects `user_study/ui/requirements-runtime.txt`, which is not present. Use the installation command above for the executable analyses in this package.

## Reproduce the scoring analyses

Run the commands from the package root in this order:

```sh
python methods_scoring/sensitivity_analysis.py \
  --draws 10000 \
  --seed 20261005 \
  --outdir methods_scoring/analysis

python methods_scoring/question_sensitivity.py \
  --outdir methods_scoring/analysis

python methods_scoring/legal_task_sensitivity.py \
  --outdir methods_scoring/analysis
```

The default joint sensitivity analysis uses 10,000 draws and random seed `20261005`. `question_sensitivity.py` reads `sensitivity_summary.json` and `joint_draw_scores.npz`, so `sensitivity_analysis.py` must run first. `legal_task_sensitivity.py` is deterministic and does not use the joint perturbation draws.

`run_scoring.sh` performs the same scoring sequence after a usable `.venv` has been created. It also runs `assess_xai_compliance.py`, whose embedded legal vectors are separate from the canonical legal contexts in `paper_inputs.json`.

## Reproduce the legal-expert validation

The validation script reads the recorded response database, the canonical method-property ratings and legal weights, and the joint sensitivity draws:

```sh
python user_study/data/legal_expert_validation.py \
  user_study/data/public-review.sqlite3 \
  --drawdir methods_scoring/analysis \
  --outdir user_study/data/analysis
```

Run `methods_scoring/sensitivity_analysis.py` first so that `joint_draw_scores.npz` and `sensitivity_summary.json` are available in the draw directory.

The analytic cohort is fixed in the script as sessions `E08`, `E11`, `E13`, and `E18`. Each participant supplied four primary judgments in each of two legal contexts, yielding 32 primary judgments. The GDPR case contains Approximate local SHAP, PDP, CEM, and DiCE; PDP is procedurally ineligible because the task requires a local explanation. The MDR case contains Global SHAP, PDP, Decision Trees, and RuleSHAP; all four are procedurally eligible. The primary numeric outcome is the 1–7 legal-goal rating. Kendall tau-b is used because rankings can contain ties.

The script also computes one-sided exact permutation tests and applies Benjamini–Hochberg adjustment across the 15 context-by-formula comparisons.

## Scoring model

For method `a`, legal context `r`, and interpretability property `s`, let `x[a,s]` be the method-property rating from 1 to 5, `z[a,s] = x[a,s] / 5`, and `lambda[r,s]` the legal weight.

The **soft score** is:

```text
S_soft(a,r) = sum_s lambda[r,s] z[a,s] / sum_s lambda[r,s]
```

The **thresholded score** is:

```text
S_thr(a,r) = sum_s lambda[r,s] 1[x[a,s] >= T_s] / sum_s lambda[r,s]
```

The default threshold is `T_s = 3` for every property.

The **geometric score** is:

```text
S_geo(a,r) = exp(
    sum_s lambda[r,s] omega[r,s] log(z[a,s])
    / sum_s lambda[r,s] omega[r,s]
)
```

The default technical priority factor is `omega[r,s] = 1`.

A method is scored only if it is procedurally eligible for the XAI question type and legal context. The default analyses do not pass `available_access`, so model access is assumed. The `explanation_target` metadata are stored in the method profiles but are not separately tested by `scoring.eligible`. The mandatory-property gate is separate from the comparative legal weights: if a mandatory criterion is not established, `hard_gate` sets the corresponding fit value to zero.

## Legal contexts

The seven legal contexts correspond to the manuscript's article bundles.

| Bundle | Package key | Legal provisions |
| :--- | :--- | :--- |
| B1 | `GDPR+AIA86+MiFID25` | GDPR Articles 13–15 and 22; AIA Article 86; MiFID II Article 25 |
| B2 | `DSA17` | DSA Article 17 |
| B3 | `DSA27+P2B5` | DSA Article 27; P2B Regulation Article 5 |
| B4 | `AIA13-14` | AIA Articles 13–14 |
| B5 | `MDR` | MDR Article 10(11) and Annex I |
| B6 | `MiFID17` | MiFID II Article 17 |
| B7 | `AIA11` | AIA Article 11 and Annex IV |

The canonical legal-weight matrix is stored in `methods_scoring/inputs/paper_inputs.json` and reproduced in `methods_scoring/assess_xai_compliance_documentation.md`.

## Method catalogue and procedural eligibility

`paper_inputs.json` contains 26 XAI method profiles and 12 ratings per profile. The first 14 profiles are the model-agnostic catalogue; the remaining 12 are model-specific or explainable-by-design profiles.

The comparative ranking analyses exclude four profiles before question-level eligibility is evaluated:

- `Supervised CBM`, `Post-hoc CBM (concept-only)`, and `LaBo (LLM-guided CBM)` require replacement of the predictor;
- `LLM neuron explanations (Bills et al.)` explains internal components rather than the deployed predictor's output.

The remaining 22 profiles enter the joint sensitivity analysis. Further filtering is question- and context-specific. For example, a global PDP is not eligible for a legal task that requires a local explanation of an individual decision.

## Joint sensitivity analysis

For each draw:

- every method-property rating receives an independent integer perturbation from `-2` to `+2` and is clipped to `[1,5]`;
- every positive legal weight is multiplied by an independent uniform factor from `[0.75,1.25]` and clipped to `[0,1]`; zero legal weights remain zero;
- every technical priority factor is drawn log-uniformly from `[0.5,2]`;
- every threshold is drawn independently from `{2,3,4}`; and
- the draw score used for ranking is the arithmetic mean of the soft, thresholded, and geometric scores.

The same perturbed method-property profile is used across legal contexts within a draw. Legal-weight, threshold, and technical-priority perturbations are context-specific. Procedural eligibility remains fixed.

`joint_draw_scores.npz` stores the draw-level composite scores. `sensitivity_summary.json` records the seed, draw count, method order, legal-context order, and winner-retention summaries.

## Deterministic legal-task sensitivity analysis

`legal_task_variants.json` defines seven two-point alternatives: runtime performance for B1, B4, and B6; sparsity and level of detail for B5; and stability for B1 and B2. Their Cartesian product produces 128 endpoint cases. Four additional B5 cases represent patient instructions, healthcare-professional instructions, and two runtime-performance weights for interactive instructions.

The deterministic analysis keeps method-property ratings, procedural eligibility, threshold `3`, and technical priority factor `1` fixed. It evaluates soft, thresholded, and geometric winner sets for the full eligible catalogue and the model-agnostic catalogue.

## Static figures

The static diagrams, survey figures, and legal-expert explanation-stimulus figures can be rendered from `methods_scoring/inputs/figures/`:

```sh
python - <<'PY'
from methods_scoring.render_figures import render
render("methods_scoring/inputs/figures", "methods_scoring/figures")
PY
```

The sensitivity scripts generate `sensitivity_stability.pdf` and `sensitivity_stability_questions.pdf`. The legal-expert validation script generates the three expert-alignment PDFs.

## Tests

Run the scoring-analysis test suite from the package root:

```sh
python -m unittest discover -s methods_scoring/tests -v
```

The tests cover property-weighted aggregation, procedural eligibility, the mandatory-property gate, shared perturbation draws, tie-aware Kendall tau-b, legal-weight handling, and the permutation-test adjustment family.

UI tests are not executable because the UI source files are not present in this package.

## Output files

`methods_scoring/analysis/` contains:

| File | Content |
| :--- | :--- |
| `method_scores.csv` | Default soft, thresholded, and geometric scores for every ranked method and legal context. |
| `question_scores.csv` | Question-specific soft- and thresholded-score winners, scores, and soft-winner retention for the full and model-agnostic catalogues. |
| `winning_probabilities.csv` | Context-level mean top-rank probabilities by method. |
| `question_winning_probabilities.csv` | Question-level top-rank probabilities by method. |
| `winner_retention.csv` | Mean, minimum, and maximum winner retention by legal context and catalogue. |
| `eligibility_counts.csv` | Number of eligible XAI question types for each method and legal context. |
| `joint_draw_scores.npz` | Composite score arrays from the joint sensitivity draws. |
| `sensitivity_summary.json` | Joint sensitivity metadata and retention summaries. |
| `legal_task_sensitivity.csv` | Deterministic legal-task case scores and winner sets. |
| `legal_task_sensitivity_summary.json` | Aggregate legal-task sensitivity summaries. |
| `sensitivity_stability.pdf` | Context-level sensitivity figure. |
| `sensitivity_stability_questions.pdf` | Question-level sensitivity figure. |

`user_study/data/analysis/` contains the locked primary ratings, formula scores, per-expert concordances, sensitivity concordances, comparison-stage concordances, exact permutation tests, summary JSON, and three expert-alignment figures.

## Data audit boundary

`user_study/data/data_audit.py` can read the response database and qualitative annotations, but its instrument-hash comparison imports `user_study/ui/study_core.py` and reads `user_study/ui/config/study.json`. Those files are not present. The audit outputs in `user_study/data/audit/` therefore document the recorded package state but cannot be regenerated completely from this package alone.

`run_user_study_analysis.sh` runs the legal-expert analysis and then invokes this audit step. Use `user_study/data/legal_expert_validation.py` directly for the reproducible statistical analysis.

## Licence

The software is distributed under the MIT License in `LICENSE`. `methods_scoring/LICENSE` contains the same licence for the scoring component.
