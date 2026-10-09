# Legal XAI computation and data specification

Paths are relative to the package root unless stated otherwise. The canonical machine-readable inputs are in `methods_scoring/inputs/`.

## Analysis scope

The numerical workflow implements the property-based comparison in the paper. It represents each XAI method by a vector of 12 interpretability-property ratings, each legal context by a vector of legal weights over the same properties, and each legal task by one or more XAI question types plus explanatory scope and explanation stage. Procedural eligibility is applied before comparative scoring.

The package contains 26 XAI method profiles. The first 14 profiles form the model-agnostic catalogue. Twelve profiles are model-specific or explainable-by-design. Three concept-bottleneck profiles require predictor replacement and one LLM-neuron profile explains internal components; these four profiles are excluded from output-explanation ranking. The remaining 22 profiles enter the joint sensitivity analysis before question-specific procedural eligibility is applied.

The seven legal contexts correspond to article bundles B1–B7 in the paper. The legal-expert validation uses two of those contexts: B1 for the GDPR automated credit-refusal case and B5 for the MDR medical-device case.

## Canonical data files

| File | Role |
| :--- | :--- |
| `methods_scoring/inputs/paper_inputs.json` | Property order, method profiles, method-property ratings, procedural attributes, legal weights, random seed, draw count, and legal-expert validation configuration. |
| `methods_scoring/inputs/score_evidence.json` | One evidence record for each of the 312 method-property ratings. |
| `methods_scoring/inputs/literature_sources.json` | Source-key to URL mapping used by the evidence records. |
| `methods_scoring/inputs/legal_task_variants.json` | Seven legal-task sensitivity intervals and four MDR task profiles. |
| `methods_scoring/inputs/legal_task_cases.json` | The 128 endpoint combinations and four MDR task cases. |
| `methods_scoring/inputs/survey_counts.json` | Survey-count data used for survey figures. |
| `methods_scoring/inputs/qualitative_annotations.json` | Manual binary coding of the 32 primary legal-expert rationales. |
| `methods_scoring/inputs/figures/` | Source assets for static diagrams, survey figures, and explanation-stimulus figures. |

`methods_scoring/scoring.py`, `methods_scoring/sensitivity_analysis.py`, `methods_scoring/legal_task_sensitivity.py`, and `user_study/data/legal_expert_validation.py` read the canonical inputs from `paper_inputs.json` directly or through `scoring.py`.

`methods_scoring/assess_xai_compliance.py` is a standalone catalogue example. Its 26 method profiles and 312 ratings agree with the canonical catalogue, but its embedded legal vectors are separate from the default legal-weight matrix in `paper_inputs.json`. It is not the source for the manuscript's default legal-context comparisons.

## Interpretability properties and internal identifiers

The documentation uses the manuscript labels below. The internal identifiers are retained in JSON and Python files.

| Interpretability property | Internal identifier |
| :--- | :--- |
| no false positives | `no_false_positives` |
| no false negatives | `no_false_negatives` |
| completeness | `completeness` |
| stability | `stability` |
| adversarial robustness | `adversarial_robustness` |
| run-to-run consistency | `consistency` |
| explainer-parameter robustness | `hyperparameters_perturbation_robustness` |
| sparsity | `sparsity` |
| level of detail | `level_of_detail` |
| confidentiality | `confidentiality` |
| traceability | `traceability` |
| runtime performance | `runtime_performance_and_implementation_constraints` |

The properties belong to five property families: faithfulness, robustness, complexity, non-functional constraints, and efficiency. Faithfulness contains no false positives, no false negatives, and completeness. Robustness contains stability, adversarial robustness, run-to-run consistency, and explainer-parameter robustness. Complexity contains sparsity and level of detail. Non-functional constraints contain confidentiality and traceability. Efficiency contains runtime performance.

The comparative rating scale is ordinal:

| Rating | Comparative interpretation |
| ---: | :--- |
| 1 | lowest rating on the comparative scale; limited |
| 2 | below the middle rating on the comparative scale; limited |
| 3 | middle rating on the comparative scale; moderate |
| 4 | strong comparative assessment |
| 5 | highest rating on the comparative scale; very strong |

The rating is a literature-grounded comparative judgment for the defined XAI method profile and interpretability property. It is not a deployment-specific measurement. Uncertainty and method qualifications are recorded in the evidence material rather than encoded as a second numeric scale.

## XAI method profile names

`paper_inputs.json` uses package keys as method identifiers. Three display labels differ from manuscript typography:

| Manuscript label | Package key |
| :--- | :--- |
| DeepLIFT | `DeepLift` |
| Global SHAP | `Global SHAP summaries` |
| LLM-assisted behavioural RuleSHAP (MechaRule stage 1) | `LLM-assisted behavioral RuleSHAP (MechaRule stage 1)` |

All other method names can be read directly from the package keys.

The four profiles excluded from output-explanation ranking are:

| Package key | Reason for exclusion |
| :--- | :--- |
| `Supervised CBM` | requires model replacement |
| `Post-hoc CBM (concept-only)` | requires model replacement |
| `LaBo (LLM-guided CBM)` | requires model replacement |
| `LLM neuron explanations (Bills et al.)` | component-only explanation |

## Legal contexts and legal weights

A legal context is the property profile represented by one article bundle. The default legal weights are `1` for a requirement, `0.5` for a qualified requirement, and `0` when the interpretability property is not scored.

| Bundle | Package key | Legal provisions |
| :--- | :--- | :--- |
| B1 | `GDPR+AIA86+MiFID25` | GDPR Articles 13–15 and 22; AIA Article 86; MiFID II Article 25 |
| B2 | `DSA17` | DSA Article 17 |
| B3 | `DSA27+P2B5` | DSA Article 27; P2B Regulation Article 5 |
| B4 | `AIA13-14` | AIA Articles 13–14 |
| B5 | `MDR` | MDR Article 10(11) and Annex I |
| B6 | `MiFID17` | MiFID II Article 17 |
| B7 | `AIA11` | AIA Article 11 and Annex IV |

The default legal-weight matrix is:

| Interpretability property | B1 | B2 | B3 | B4 | B5 | B6 | B7 |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| no false positives | 1 | 1 | 1 | 1 | 1 | 1 | 1 |
| no false negatives | 1 | 1 | 0 | 1 | 1 | 1 | 1 |
| completeness | 0 | 1 | 0 | 1 | 1 | 1 | 1 |
| stability | 0 | 0 | 1 | 1 | 1 | 1 | 1 |
| adversarial robustness | 0.5 | 0.5 | 0.5 | 1 | 1 | 1 | 1 |
| run-to-run consistency | 1 | 1 | 1 | 1 | 1 | 1 | 1 |
| explainer-parameter robustness | 1 | 1 | 1 | 1 | 1 | 1 | 1 |
| sparsity | 1 | 0 | 1 | 0 | 0.5 | 0 | 0 |
| level of detail | 0 | 0 | 0 | 1 | 0.5 | 1 | 1 |
| confidentiality | 0.5 | 0.5 | 1 | 0 | 0.5 | 0 | 0 |
| traceability | 1 | 1 | 0 | 1 | 1 | 1 | 1 |
| runtime performance | 1 | 1 | 0 | 1 | 0 | 1 | 0 |

The B1 and B2 legal tasks concern fixed individual outputs. Stability is therefore not scored by default for those bundles; run-to-run consistency and explainer-parameter robustness remain scored. B5 assigns qualified weights to sparsity, level of detail, and confidentiality. Runtime performance is not scored for B5 instructions supplied before use.

Mandatory legal criteria are represented separately through the mandatory-property gate. A legal weight does not convert a mandatory criterion into a compensable score component.

## Procedural eligibility

Procedural eligibility is applied before scoring. `scoring.eligible(method, regulation, question, available_access=None)` requires all of the following:

1. the method profile is not marked `requires_model_replacement` or `component_only`;
2. the requested XAI question type is listed for the method profile;
3. the method's explanatory scope and explanation stage match the legal context, unless either profile is marked `both`;
4. runtime performance has a positive method-property rating; and
5. when `available_access` is supplied, the method's required access is available.

The canonical XAI question types are `what_rule`, `how_computed`, `what_feature`, `how_differs`, `why_instead_of`, `what_if`, and `how_modify_input`. `scoring.QUESTION_MAP` translates the legal-question labels stored in the legal-context profiles to these canonical question types.

Procedural eligibility is binary. An ineligible method is excluded from the comparison for that XAI question type. The default analyses do not pass `available_access`, so the code assumes the required model access is available. `explanation_target` is stored in each method profile but is not separately tested by `scoring.eligible`; model architecture and data modality are also not passed as separate default eligibility inputs. For the GDPR legal-expert case, PDP is ineligible because the task concerns a local explanation of an individual refusal and PDP has global explanatory scope.

## Scoring equations

For method `a`, legal context `r`, and interpretability property `s`, let:

- `x[a,s]` be the ordinal method-property rating in `{1,2,3,4,5}`;
- `z[a,s] = x[a,s] / 5`;
- `lambda[r,s]` be the legal weight; and
- `P_r = {s : lambda[r,s] > 0}`.

The soft score is:

```text
S_soft(a,r) =
    sum_{s in P_r} lambda[r,s] z[a,s]
    / sum_{s in P_r} lambda[r,s]
```

The thresholded score is:

```text
S_thr(a,r) =
    sum_{s in P_r} lambda[r,s] 1[x[a,s] >= T_s]
    / sum_{s in P_r} lambda[r,s]
```

The default threshold is `T_s = 3` for every property.

The geometric score is:

```text
S_geo(a,r) = exp(
    sum_{s in P_r} lambda[r,s] omega[r,s] log(z[a,s])
    / sum_{s in P_r} lambda[r,s] omega[r,s]
)
```

The default technical priority factor is `omega[r,s] = 1`.

`scoring.score_views` rounds returned scores to 12 decimal places. Winner ties use an absolute tolerance of `1e-10`. Interpretability properties enter the formulas directly; property-family means are not computed before aggregation.

For XAI question type `q`, the comparative fit is the selected score multiplied by procedural eligibility. `scoring.hard_gate(values, evidence)` applies the separate mandatory-property gate: if any mandatory criterion is false or unestablished, the gated value is zero.

## Joint sensitivity analysis

`methods_scoring/sensitivity_analysis.py` performs the joint sensitivity analysis. The defaults are 10,000 draws and random seed `20261005`.

Within each draw:

- each method-property rating receives an independent integer perturbation from `-2` through `+2` and is clipped to `[1,5]`;
- each positive legal weight is multiplied by an independent uniform draw from `[0.75,1.25]` and clipped to `[0,1]`; zero legal weights remain zero;
- each technical priority factor is drawn log-uniformly from `[0.5,2]`;
- each threshold is drawn independently from `{2,3,4}`; and
- the ranking value is `(S_soft + S_thr + S_geo) / 3`.

The perturbed method-property vector for a method is shared across legal contexts within the same draw. Legal weights, technical priority factors, and thresholds are drawn independently by legal context. Procedural eligibility remains fixed.

For each legal context and XAI question type, the script computes the top-rank probability of each eligible method. Ties count every tied method as top-ranked. The full-catalogue comparison uses all procedurally eligible profiles among the 22 ranked profiles. The model-agnostic comparison uses the first 14 catalogue profiles.

Winner retention is the probability that at least one default soft-score winner remains top-ranked in a perturbation draw. `winner_retention.csv` reports the mean, minimum, and maximum retention across XAI question types within each legal context and catalogue.

`joint_draw_scores.npz` stores one draws-by-method composite-score array per legal context. The method and legal-context orders are recorded in `sensitivity_summary.json`.

## Deterministic legal-task sensitivity analysis

`methods_scoring/inputs/legal_task_variants.json` defines seven two-point alternatives:

| Legal context | Interpretability property | Values |
| :--- | :--- | :--- |
| B1 | runtime performance | 0.5, 1 |
| B4 | runtime performance | 0.75, 1 |
| B6 | runtime performance | 0.5, 1 |
| B5 | sparsity | 0.25, 0.75 |
| B5 | level of detail | 0.25, 0.75 |
| B1 | stability | 0, 1 |
| B2 | stability | 0, 1 |

Their Cartesian product produces 128 endpoint cases. Four additional B5 cases are defined:

| Case | Non-default B5 legal weights |
| :--- | :--- |
| MDR patient instructions | sparsity 0.75; level of detail 0.25; confidentiality 0.5; runtime performance 0 |
| MDR professional instructions | sparsity 0.25; level of detail 0.75; confidentiality 0.5; runtime performance 0 |
| MDR interactive instructions, lower runtime priority | runtime performance 0.75; confidentiality 0.5 |
| MDR interactive instructions, full runtime priority | runtime performance 1; confidentiality 0.5 |

`methods_scoring/legal_task_sensitivity.py` keeps method-property ratings, procedural eligibility, threshold `3`, and technical priority factor `1` fixed. It evaluates the soft, thresholded, and geometric winner sets for each legal context, XAI question type, and catalogue.

`analysis/legal_task_sensitivity.csv` records the default winner set, case-specific winner set, maximum score, exact winner-set agreement, and retention of at least one default winner. `analysis/legal_task_sensitivity_summary.json` aggregates these comparisons.

## Legal-expert validation

`user_study/data/public-review.sqlite3` is the response database used by `user_study/data/legal_expert_validation.py`. The database contains six sessions. The fixed analytic cohort is `E08`, `E11`, `E13`, and `E18`. Session `E01` is incomplete. Session `E02` reports zero years of legal experience and is outside the analytic cohort.

Each included participant completed four primary judgments in each of two legal contexts, yielding 32 primary judgments.

### GDPR case

The four explanation packages are Approximate local SHAP, PDP, CEM, and DiCE. Approximate local SHAP, CEM, and DiCE are procedurally eligible. PDP is procedurally ineligible because the legal task requires local explanatory scope.

### MDR case

The four explanation packages are Global SHAP, PDP, Decision Trees, and RuleSHAP. All four are procedurally eligible because the legal task concerns system-level information.

### Recorded measures and concordance

The primary numeric outcome is the 1–7 legal-goal rating. The database also records the legal-assessment-question rating, confidence, overall legal disposition, written rationale, comparison-stage responses, and final ranking.

For each participant and legal context, formula scores are compared with the four primary legal-goal ratings using Kendall tau-b. The legal-context statistic is the median of the four participant-specific coefficients. The cross-context statistic averages the two legal-context coefficients within each participant and then takes the median across participants.

For sensitivity concordance, each participant's Kendall tau-b is calculated for every draw. The participant-specific median across draws is calculated first, followed by the median across participants. Cross-context sensitivity averages the two legal-context coefficients within participant and draw before the medians are taken.

The one-sided exact permutation tests permute method labels within participant and legal context. Four alternatives produce 24 permutations per participant and legal context. The cross-context test uses independent label permutations for the two method sets. Benjamini–Hochberg adjustment is applied across five scoring configurations and three context summaries, for 15 comparisons.

`comparison_stage_concordance.csv` uses the final ranking rather than the primary 1–7 legal-goal ratings.

## Qualitative coding and audit files

`methods_scoring/inputs/qualitative_annotations.json` contains 32 manually coded primary rationales. The binary field marks whether the rationale uses language corresponding to the interpretability properties. One coding record corresponds to each primary judgment.

`user_study/data/audit/` contains the session export, database schema, qualitative-coding export, and audit summary. `user_study/data/data_audit.py` can reproduce the database and qualitative-coding portions, but its instrument-hash comparison requires `user_study/ui/study_core.py` and `user_study/ui/config/study.json`. Those files are not present in the package.

The legal-expert statistical analysis does not require the UI source files.

## Output files

### Scoring analysis

`methods_scoring/analysis/` contains:

| File | Content |
| :--- | :--- |
| `method_scores.csv` | Default soft, thresholded, and geometric scores by legal context and method. |
| `question_scores.csv` | Question-specific soft- and thresholded-score winners and scores, plus soft-winner retention. |
| `winning_probabilities.csv` | Context-level mean top-rank probabilities. |
| `question_winning_probabilities.csv` | Question-level top-rank probabilities. |
| `winner_retention.csv` | Mean, minimum, and maximum winner retention by legal context and catalogue. |
| `eligibility_counts.csv` | Number of eligible XAI question types by method and legal context. |
| `joint_draw_scores.npz` | Joint-sensitivity composite score arrays. |
| `sensitivity_summary.json` | Seed, draw count, method order, legal-context order, and retention summaries. |
| `legal_task_sensitivity.csv` | Deterministic legal-task case scores and winner sets. |
| `legal_task_sensitivity_summary.json` | Aggregated deterministic legal-task summaries. |
| `sensitivity_stability.pdf` | Context-level sensitivity figure. |
| `sensitivity_stability_questions.pdf` | Question-level sensitivity figure. |

### Legal-expert analysis

`user_study/data/analysis/` contains:

| File | Content |
| :--- | :--- |
| `locked_ratings_gdpr.csv` | Primary legal-goal ratings for the GDPR case. |
| `locked_ratings_mdr.csv` | Primary legal-goal ratings for the MDR case. |
| `formula_scores_gdpr.csv` | Formula scores for the GDPR case. |
| `formula_scores_mdr.csv` | Formula scores for the MDR case. |
| `expert_alignment_per_expert.csv` | Participant-specific Kendall tau-b values. |
| `expert_alignment_metrics.csv` | Median concordance summaries. |
| `sensitivity_concordance_gdpr.csv` | GDPR draw-level concordance values. |
| `sensitivity_concordance_mdr.csv` | MDR draw-level concordance values. |
| `comparison_stage_concordance.csv` | Concordance with final rankings and changed-rating counts. |
| `exploratory_permutation_tests.csv` | Exact p-values and Benjamini–Hochberg q-values. |
| `expert_summary.json` | Compact numerical summary. |
| `expert_alignment_gdpr.pdf` | GDPR ranking figure. |
| `expert_alignment_mdr.pdf` | MDR ranking figure. |
| `expert_alignment_across_regulations.pdf` | Cross-context concordance figure. |

## Reproduction commands

Install the dependency set from the package root:

```sh
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -r methods_scoring/requirements.txt
```

Run the numerical analyses:

```sh
python methods_scoring/sensitivity_analysis.py \
  --draws 10000 \
  --seed 20261005 \
  --outdir methods_scoring/analysis

python methods_scoring/question_sensitivity.py \
  --outdir methods_scoring/analysis

python methods_scoring/legal_task_sensitivity.py \
  --outdir methods_scoring/analysis

python user_study/data/legal_expert_validation.py \
  user_study/data/public-review.sqlite3 \
  --drawdir methods_scoring/analysis \
  --outdir user_study/data/analysis
```

Run the scoring-analysis tests:

```sh
python -m unittest discover -s methods_scoring/tests -v
```

Render the static diagrams, survey figures, and explanation-stimulus figures:

```sh
python - <<'PY'
from methods_scoring.render_figures import render
render("methods_scoring/inputs/figures", "methods_scoring/figures")
PY
```

`setup.sh` and `run_ui.sh` require UI files that are not present. `run_user_study_analysis.sh` runs the legal-expert analysis and then invokes the audit step that depends on those UI files. The direct commands above reproduce the executable scoring and legal-expert analyses in the package.

## Numerical checks

At the default legal weights, the legal-expert analysis produces the following primary median Kendall tau-b values:

| Context | Soft | Geometric | T=2 | T=3 | T=4 | Joint-sensitivity median |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: |
| GDPR | 0.183 | 0.183 | 0.183 | 0.200 | 0.387 | 0.365 |
| MDR | 0.441 | 0.441 | 0.118 | 0.474 | 0.742 | 0.258 |
| Across both | 0.266 | 0.266 | 0.097 | 0.358 | 0.505 | 0.255 |

For the thresholded score at `T=4`, the one-sided exact permutation-test p-values are `0.1953125` for GDPR, `0.0104166667` for MDR, and `0.0080728413` across both contexts. The corresponding Benjamini–Hochberg q-values are `0.3255208333`, `0.078125`, and `0.078125`.

## Score-specific evidence

Each entry below gives the property, score, interpretation and primary-source location. Bibliography keys match the manuscript. URLs are resolved through `methods_scoring/inputs/literature_sources.json`.

### Decision Trees

- **no false positives (3/5):** Surrogate agreement requires validation; predictive overfitting does not establish explanation false positives. Source: `scoreTreeDocs`, classification, complexity and practical tips. https://scikit-learn.org/stable/modules/tree.html
- **no false negatives (3/5):** A compressed surrogate can omit black-box effects; no general recall ranking against RuleFit is established. Source: `scoreTreeDocs`, classification, complexity and practical tips. https://scikit-learn.org/stable/modules/tree.html
- **completeness (3/5):** Surrogate paths cover the fitted tree; agreement with the explained predictor determines rationale coverage. Source: `scoreTreeDocs`, classification, complexity and practical tips. https://scikit-learn.org/stable/modules/tree.html
- **stability (1/5):** Crossing a split abruptly changes the path, giving low input stability for path-based use of surrogate rules. Source: `scoreTreeDocs`, classification, complexity and practical tips. https://scikit-learn.org/stable/modules/tree.html
- **adversarial robustness (2/5):** Threshold discontinuities create sensitivity; this is a structural inference, not a universal attack benchmark. Source: `scoreTreeDocs`, classification, complexity and practical tips. https://scikit-learn.org/stable/modules/tree.html
- **run-to-run consistency (2/5):** Resampling outputs from a fixed predictor can change the fitted surrogate structure. Source: `scoreTreeDocs`, classification, complexity and practical tips. https://scikit-learn.org/stable/modules/tree.html
- **explainer-parameter robustness (2/5):** Depth, pruning and leaf-size changes can materially change explanations. Source: `scoreTreeDocs`, classification, complexity and practical tips. https://scikit-learn.org/stable/modules/tree.html
- **sparsity (3/5):** A pruned tree can be compact, but path and tree size remain tunable. Source: `scoreTreeDocs`, classification, complexity and practical tips. https://scikit-learn.org/stable/modules/tree.html
- **level of detail (5/5):** Explicit predicates and leaf outcomes provide the catalogue's highest rule-level detail. Source: `scoreTreeDocs`, classification, complexity and practical tips. https://scikit-learn.org/stable/modules/tree.html
- **confidentiality (2/5):** Publishing splits exposes proprietary logic; this threat-model assumption is not a measured privacy loss. Source: `scoreTreeDocs`, classification, complexity and practical tips. https://scikit-learn.org/stable/modules/tree.html
- **traceability (4/5):** Stored tree, training data, seed and parameters permit reconstruction. Source: `scoreTreeDocs`, classification, complexity and practical tips. https://scikit-learn.org/stable/modules/tree.html
- **runtime performance (4/5):** Ordinary tree fitting and inference are comparatively inexpensive; surrogate-data collection cost still matters. Source: `scoreTreeDocs`, classification, complexity and practical tips. https://scikit-learn.org/stable/modules/tree.html

### RuleFit

- **no false positives (3/5):** Surrogate training does not guarantee agreement with the target model. Source: `friedman2008predictive`, rule-ensemble construction and regularised fitting. https://arxiv.org/abs/0811.1679
- **no false negatives (3/5):** Sparse term selection can omit influences of the explained predictor. Source: `friedman2008predictive`, rule-ensemble construction and regularised fitting. https://arxiv.org/abs/0811.1679
- **completeness (4/5):** Rules and linear terms express interactions and linear trends; broader representational coverage than a simple tree is plausible. Source: `friedman2008predictive`, rule-ensemble construction and regularised fitting. https://arxiv.org/abs/0811.1679
- **stability (3/5):** Regularisation constrains fitting, while selected rules remain data-dependent. Source: `friedman2008predictive`, rule-ensemble construction and regularised fitting. https://arxiv.org/abs/0811.1679
- **adversarial robustness (3/5):** Predictive performance does not establish attack resistance; no general advantage is established. Source: `friedman2008predictive`, rule-ensemble construction and regularised fitting. https://arxiv.org/abs/0811.1679
- **run-to-run consistency (3/5):** Different samples can select different rules; deterministic optimization alone is insufficient. Source: `friedman2008predictive`, rule-ensemble construction and regularised fitting. https://arxiv.org/abs/0811.1679
- **explainer-parameter robustness (3/5):** Penalty strength and rule-generation choices affect the selected ensemble. Source: `friedman2008predictive`, rule-ensemble construction and regularised fitting. https://arxiv.org/abs/0811.1679
- **sparsity (3/5):** The final L1-selected ensemble can be compact, although many terms may remain. Source: `friedman2008predictive`, rule-ensemble construction and regularised fitting. https://arxiv.org/abs/0811.1679
- **level of detail (4/5):** Predicates and coefficients reveal detailed surrogate structure. Source: `friedman2008predictive`, rule-ensemble construction and regularised fitting. https://arxiv.org/abs/0811.1679
- **confidentiality (2/5):** Disclosed rules expose model logic; use the same threat-model assumption as the surrogate tree. Source: `friedman2008predictive`, rule-ensemble construction and regularised fitting. https://arxiv.org/abs/0811.1679
- **traceability (4/5):** The fitted rule list and pipeline can be archived and inspected. Source: `friedman2008predictive`, rule-ensemble construction and regularised fitting. https://arxiv.org/abs/0811.1679
- **runtime performance (3/5):** Rule generation plus sparse regression adds work relative to a single tree. Source: `friedman2008predictive`, rule-ensemble construction and regularised fitting. https://arxiv.org/abs/0811.1679

### RuleSHAP

- **no false positives (3/5):** Injected-rule recovery evaluates known-rule ranking; the validity of every returned predicate remains unresolved. Source: `scoreRuleSHAP2025`, Secs. 4--6, Table 2 and Appendix G. https://arxiv.org/html/2505.11189v1
- **no false negatives (4/5):** Known-rule recovery ranks improve over RuleFit in the injected-bias experiment, supporting a qualified comparative 4 versus 3. Source: `scoreRuleSHAP2025`, Secs. 4--6, Table 2 and Appendix G. https://arxiv.org/html/2505.11189v1
- **completeness (4/5):** Rule ensembles represent compound conditions and linear trends more extensively than a single surrogate tree. Source: `scoreRuleSHAP2025`, Secs. 4--6, Table 2 and Appendix G. https://arxiv.org/html/2505.11189v1
- **stability (3/5):** Matched input-stability evidence for the rule-induction pipeline is limited. Source: `scoreRuleSHAP2025`, Secs. 4--6, Table 2 and Appendix G. https://arxiv.org/html/2505.11189v1
- **adversarial robustness (3/5):** Attack-resistance evidence for SHAP-guided rule induction is limited. Source: `scoreRuleSHAP2025`, Secs. 4--6, Table 2 and Appendix G. https://arxiv.org/html/2505.11189v1
- **run-to-run consistency (3/5):** Sampling and attribution steps create multiple sources of repeated-fit variation. Source: `scoreRuleSHAP2025`, Secs. 4--6, Table 2 and Appendix G. https://arxiv.org/html/2505.11189v1
- **explainer-parameter robustness (3/5):** Rule and attribution choices affect induction; comparative parameter-sweep evidence is limited. Source: `scoreRuleSHAP2025`, Secs. 4--6, Table 2 and Appendix G. https://arxiv.org/html/2505.11189v1
- **sparsity (3/5):** Selected rules improve compactness, but no universal minimal-rule guarantee follows. Source: `scoreRuleSHAP2025`, Secs. 4--6, Table 2 and Appendix G. https://arxiv.org/html/2505.11189v1
- **level of detail (4/5):** Explicit learned predicates retain rule-level detail. Source: `scoreRuleSHAP2025`, Secs. 4--6, Table 2 and Appendix G. https://arxiv.org/html/2505.11189v1
- **confidentiality (2/5):** Rule disclosure exposes logic; confidentiality depends on access and disclosure controls. Source: `scoreRuleSHAP2025`, Secs. 4--6, Table 2 and Appendix G. https://arxiv.org/html/2505.11189v1
- **traceability (3/5):** Reconstruction requires linking attribution, rule generation and weighting records across the pipeline. Source: `scoreRuleSHAP2025`, Secs. 4--6, Table 2 and Appendix G. https://arxiv.org/html/2505.11189v1
- **runtime performance (2/5):** SHAP computation adds cost to the rule-fitting pipeline. Source: `scoreRuleSHAP2025`, Secs. 4--6, Table 2 and Appendix G. https://arxiv.org/html/2505.11189v1

### PDP

- **no false positives (3/5):** Model evaluations reflect marginal responses, but correlated-feature extrapolation can mislead interpretation. Source: `goldstein2015peeking`, Secs. 2--4. https://arxiv.org/html/1309.6392v2
- **no false negatives (3/5):** Population averaging hides effects that differ among examples, supporting a neutral contributor-coverage judgment. Source: `goldstein2015peeking`, Secs. 2--4. https://arxiv.org/html/1309.6392v2
- **completeness (3/5):** Low-dimensional response curves cover selected effects; their coverage matches ICE when features and reference examples match. Source: `goldstein2015peeking`, Secs. 2--4. https://arxiv.org/html/1309.6392v2
- **stability (4/5):** Averaging smooths individual response variation relative to ICE over a fixed reference population. Source: `goldstein2015peeking`, Secs. 2--4. https://arxiv.org/html/1309.6392v2
- **adversarial robustness (3/5):** Population aggregation has limited attack-resistance evidence. Source: `goldstein2015peeking`, Secs. 2--4. https://arxiv.org/html/1309.6392v2
- **run-to-run consistency (4/5):** The fixed model is evaluated directly over a declared grid/reference cohort, with no fitted stochastic surrogate. Source: `goldstein2015peeking`, Secs. 2--4. https://arxiv.org/html/1309.6392v2
- **explainer-parameter robustness (4/5):** Ordinary fixed grids have few tuning choices relative to fitted local surrogates. Source: `goldstein2015peeking`, Secs. 2--4. https://arxiv.org/html/1309.6392v2
- **sparsity (2/5):** Showing response functions for many features produces an extensive display. Source: `goldstein2015peeking`, Secs. 2--4. https://arxiv.org/html/1309.6392v2
- **level of detail (4/5):** One- and two-way response surfaces expose response shape and selected interactions; the rating does not describe full decision rules. Source: `goldstein2015peeking`, Secs. 2--4. https://arxiv.org/html/1309.6392v2
- **confidentiality (3/5):** Aggregate outputs are not inherently private; neutral is not a privacy assurance. Source: `goldstein2015peeking`, Secs. 2--4. https://arxiv.org/html/1309.6392v2
- **traceability (4/5):** Logged grid, model and reference dataset permit straightforward recomputation. Source: `goldstein2015peeking`, Secs. 2--4. https://arxiv.org/html/1309.6392v2
- **runtime performance (4/5):** Low-dimensional grids require fewer evaluations than repeated counterfactual optimisation. Source: `goldstein2015peeking`, Secs. 2--4. https://arxiv.org/html/1309.6392v2

### ICE

- **no false positives (3/5):** Direct model queries give feature-response information; impossible feature combinations remain a limitation. Source: `goldstein2015peeking`, Secs. 2--4. https://arxiv.org/html/1309.6392v2
- **no false negatives (4/5):** Individual curves reveal heterogeneous effects hidden by PDP averaging. Source: `goldstein2015peeking`, Secs. 2--4. https://arxiv.org/html/1309.6392v2
- **completeness (3/5):** ICE retains the individual curves whose mean produces PDP, giving equal partial-effect coverage under matched inputs. Source: `goldstein2015peeking`, Secs. 2--4. https://arxiv.org/html/1309.6392v2
- **stability (3/5):** Curve changes follow the model; stochastic noise is not inherent in fixed-grid ICE. Source: `goldstein2015peeking`, Secs. 2--4. https://arxiv.org/html/1309.6392v2
- **adversarial robustness (3/5):** Direct evaluation alone supplies no general protection against malicious perturbations. Source: `goldstein2015peeking`, Secs. 2--4. https://arxiv.org/html/1309.6392v2
- **run-to-run consistency (4/5):** The fixed model is evaluated directly over a declared grid/reference cohort, with no fitted stochastic surrogate. Source: `goldstein2015peeking`, Secs. 2--4. https://arxiv.org/html/1309.6392v2
- **explainer-parameter robustness (4/5):** Fixed-grid construction has few tuning choices, as in PDP. Source: `goldstein2015peeking`, Secs. 2--4. https://arxiv.org/html/1309.6392v2
- **sparsity (2/5):** Many overlaid individual curves are dense. Source: `goldstein2015peeking`, Secs. 2--4. https://arxiv.org/html/1309.6392v2
- **level of detail (4/5):** Per-record response trajectories reveal more detail than population averaging. Source: `goldstein2015peeking`, Secs. 2--4. https://arxiv.org/html/1309.6392v2
- **confidentiality (2/5):** Individual records or response trajectories can expose sensitive information; contextual disclosure-risk inference. Source: `goldstein2015peeking`, Secs. 2--4. https://arxiv.org/html/1309.6392v2
- **traceability (4/5):** No inherent randomness prevents tracing fixed-grid model evaluations. Source: `goldstein2015peeking`, Secs. 2--4. https://arxiv.org/html/1309.6392v2
- **runtime performance (4/5):** PDP and ICE share prediction evaluations for matched grids and reference examples. Source: `goldstein2015peeking`, Secs. 2--4. https://arxiv.org/html/1309.6392v2

### LIME

- **no false positives (2/5):** Imperfect local fitting and correlated proxies can assign misleading feature contributions. Source: `DBLP:conf/kdd/Ribeiro0G16`, Sec. 3. https://arxiv.org/abs/1602.04938
- **no false negatives (2/5):** Sparse local fitting can miss nonlinear effects and omitted contributors. Source: `DBLP:conf/kdd/Ribeiro0G16`, Sec. 3. https://arxiv.org/abs/1602.04938
- **completeness (2/5):** The explanation covers a neighborhood, not the full decision function. Source: `DBLP:conf/kdd/Ribeiro0G16`, Sec. 3. https://arxiv.org/abs/1602.04938
- **stability (1/5):** Unstabilised local fitting shows severe input sensitivity in nonlinear image experiments; the low ordinal anchor follows that variant. Source: `scoreRobust2018`, Secs. 2--3, Figures 2--6. https://arxiv.org/pdf/1806.08049
- **adversarial robustness (1/5):** Off-distribution sampling enables demonstrated manipulation of LIME explanations. Source: `DBLP:conf/aies/SlackHJSL20`, scaffolded-classifier experiments. https://arxiv.org/pdf/1911.02508
- **run-to-run consistency (2/5):** Sampled fitting varies across runs; repeated-rank experiments support the same below-neutral bin as sampled SHAP. Source: `man2020best`, Secs. 2--3 and 5. https://arxiv.org/pdf/2005.12483
- **explainer-parameter robustness (1/5):** Neighbourhood and feature-selection choices strongly affect the fitted surrogate. Source: `DBLP:conf/kdd/Ribeiro0G16`, Sec. 3. https://arxiv.org/abs/1602.04938
- **sparsity (3/5):** User-selected feature counts constrain size while allowing a range of fit-size trade-offs. Source: `DBLP:conf/kdd/Ribeiro0G16`, Sec. 3. https://arxiv.org/abs/1602.04938
- **level of detail (2/5):** Sparse linear coefficients give less interaction and predicate detail than explicit rules. Source: `DBLP:conf/kdd/Ribeiro0G16`, Sec. 3. https://arxiv.org/abs/1602.04938
- **confidentiality (3/5):** Local outputs can reveal sensitive behavior; neutral does not assert confidentiality. Source: `DBLP:conf/kdd/Ribeiro0G16`, Sec. 3. https://arxiv.org/abs/1602.04938
- **traceability (3/5):** Reconstruction requires the sampled neighbourhood, random state and fitted surrogate as well as the predictor and input. Source: `DBLP:conf/kdd/Ribeiro0G16`, Sec. 3. https://arxiv.org/abs/1602.04938
- **runtime performance (3/5):** Repeated queries and a small regression are moderately costly; no fixed runtime ratio to KernelSHAP is asserted. Source: `DBLP:conf/kdd/Ribeiro0G16`, Sec. 3. https://arxiv.org/abs/1602.04938

### Anchors

- **no false positives (3/5):** Conditional rule precision concerns prediction retention; necessity of each predicate remains unresolved. Source: `DBLP:conf/aaai/Ribeiro0G18`, anchor definition and search procedure. https://homes.cs.washington.edu/~marcotcr/aaai18.pdf
- **no false negatives (3/5):** A sufficient rule need not enumerate all contributors; conditional precision is not feature-recall evidence. Source: `DBLP:conf/aaai/Ribeiro0G18`, anchor definition and search procedure. https://homes.cs.washington.edu/~marcotcr/aaai18.pdf
- **completeness (3/5):** The rule describes the region it covers, giving partial decision-rationale coverage. Source: `DBLP:conf/aaai/Ribeiro0G18`, anchor definition and search procedure. https://homes.cs.washington.edu/~marcotcr/aaai18.pdf
- **stability (1/5):** Local rule selection changes with the sampled neighbourhood. Source: `DBLP:conf/aaai/Ribeiro0G18`, anchor definition and search procedure. https://homes.cs.washington.edu/~marcotcr/aaai18.pdf
- **adversarial robustness (3/5):** A probabilistic precision target is not an adversarial robustness guarantee. Source: `DBLP:conf/aaai/Ribeiro0G18`, anchor definition and search procedure. https://homes.cs.washington.edu/~marcotcr/aaai18.pdf
- **run-to-run consistency (1/5):** Stochastic rule search can return different conditions across runs. Source: `DBLP:conf/aaai/Ribeiro0G18`, anchor definition and search procedure. https://homes.cs.washington.edu/~marcotcr/aaai18.pdf
- **explainer-parameter robustness (2/5):** Precision target, discretization and sampling budget influence rule selection. Source: `DBLP:conf/aaai/Ribeiro0G18`, anchor definition and search procedure. https://homes.cs.washington.edu/~marcotcr/aaai18.pdf
- **sparsity (4/5):** Search favors concise rules; 4 replaces an unsupported universal minimality score of 5. Source: `DBLP:conf/aaai/Ribeiro0G18`, anchor definition and search procedure. https://homes.cs.washington.edu/~marcotcr/aaai18.pdf
- **level of detail (3/5):** A conjunction provides feature predicates, but not the model's complete branching structure. Source: `DBLP:conf/aaai/Ribeiro0G18`, anchor definition and search procedure. https://homes.cs.washington.edu/~marcotcr/aaai18.pdf
- **confidentiality (3/5):** Released local rules expose behaviour; protection depends on disclosure controls. Source: `DBLP:conf/aaai/Ribeiro0G18`, anchor definition and search procedure. https://homes.cs.washington.edu/~marcotcr/aaai18.pdf
- **traceability (3/5):** Reconstruction requires the sampled neighbourhood, random state and fitted surrogate as well as the predictor and input. Source: `DBLP:conf/aaai/Ribeiro0G18`, anchor definition and search procedure. https://homes.cs.washington.edu/~marcotcr/aaai18.pdf
- **runtime performance (3/5):** Precision estimation and rule search require repeated prediction queries. Source: `DBLP:conf/aaai/Ribeiro0G18`, anchor definition and search procedure. https://homes.cs.washington.edu/~marcotcr/aaai18.pdf

### CEM

- **no false positives (3/5):** Prediction retention by pertinent positives concerns sufficiency; necessity of each selected factor remains unresolved. Source: `DBLP:conf/nips/DhurandharCLTTS18`, Sec. 3.3 and Appendix A. https://arxiv.org/pdf/1802.07623
- **no false negatives (3/5):** Omissions depend on the contrast and feature representation. Source: `DBLP:conf/nips/DhurandharCLTTS18`, Sec. 3.3 and Appendix A. https://arxiv.org/pdf/1802.07623
- **completeness (4/5):** Pertinent positives and negatives provide two complementary contrasts. Source: `DBLP:conf/nips/DhurandharCLTTS18`, Sec. 3.3 and Appendix A. https://arxiv.org/pdf/1802.07623
- **stability (2/5):** the sparse optimum can switch under nearby inputs, supporting below-neutral stability. Source: `DBLP:conf/nips/DhurandharCLTTS18`, Sec. 3.3 and Appendix A. https://arxiv.org/pdf/1802.07623
- **adversarial robustness (3/5):** Prediction validity is distinct from attack resistance; neutral replaces an unsupported strength. Source: `DBLP:conf/nips/DhurandharCLTTS18`, Sec. 3.3 and Appendix A. https://arxiv.org/pdf/1802.07623
- **run-to-run consistency (3/5):** The published solver starts at zero, reducing random variation; comparative repeated-fit evidence is limited. Source: `DBLP:conf/nips/DhurandharCLTTS18`, Sec. 3.3 and Appendix A. https://arxiv.org/pdf/1802.07623
- **explainer-parameter robustness (1/5):** Loss weight, sparsity penalty, manifold regularization, margin, and optimization budget can change which PP/PN set is returned. Source: `DBLP:conf/nips/DhurandharCLTTS18`, Sec. 3.3 and Appendix A. https://arxiv.org/pdf/1802.07623
- **sparsity (4/5):** Regularized perturbations favor compact evidence; sparsity is optimized rather than guaranteed. Source: `DBLP:conf/nips/DhurandharCLTTS18`, Sec. 3.3 and Appendix A. https://arxiv.org/pdf/1802.07623
- **level of detail (3/5):** Changed or retained features give a concrete contrast rather than full model structure. Source: `DBLP:conf/nips/DhurandharCLTTS18`, Sec. 3.3 and Appendix A. https://arxiv.org/pdf/1802.07623
- **confidentiality (3/5):** Local evidence lacks inherent privacy protection. Source: `DBLP:conf/nips/DhurandharCLTTS18`, Sec. 3.3 and Appendix A. https://arxiv.org/pdf/1802.07623
- **traceability (3/5):** Reconstruction requires the sampled neighbourhood, random state and fitted surrogate as well as the predictor and input. Source: `DBLP:conf/nips/DhurandharCLTTS18`, Sec. 3.3 and Appendix A. https://arxiv.org/pdf/1802.07623
- **runtime performance (2/5):** Two optimization tasks and possible manifold regularization impose substantial explanation cost. Source: `DBLP:conf/nips/DhurandharCLTTS18`, Sec. 3.3 and Appendix A. https://arxiv.org/pdf/1802.07623

### DiCE

- **no false positives (3/5):** Counterfactual validity establishes an output-changing edit; factor necessity depends on the selected contrast. Source: `DBLP:conf/fat/MothilalST20`, Secs. 3--5. https://arxiv.org/html/1905.07697v2
- **no false negatives (3/5):** Diverse valid counterfactuals explore alternative outcomes but do not identify every influence on the actual prediction. Source: `DBLP:conf/fat/MothilalST20`, Secs. 3--5. https://arxiv.org/html/1905.07697v2
- **completeness (3/5):** Diversity improves local boundary coverage but is not a complete model rationale. Source: `DBLP:conf/fat/MothilalST20`, Secs. 3--5. https://arxiv.org/html/1905.07697v2
- **stability (1/5):** Sampling or optimization choices can produce substantially different outputs. Source: `DBLP:conf/fat/MothilalST20`, Secs. 3--5. https://arxiv.org/html/1905.07697v2
- **adversarial robustness (3/5):** A valid counterfactual can fail under model change; adversarial robustness is not established by its validity objective. Source: `DBLP:conf/fat/MothilalST20`, Secs. 3--5. https://arxiv.org/html/1905.07697v2
- **run-to-run consistency (1/5):** Sampling or optimization choices can produce substantially different outputs. Source: `DBLP:conf/fat/MothilalST20`, Secs. 3--5. https://arxiv.org/html/1905.07697v2
- **explainer-parameter robustness (1/5):** Sampling or optimization choices can produce substantially different outputs. Source: `DBLP:conf/fat/MothilalST20`, Secs. 3--5. https://arxiv.org/html/1905.07697v2
- **sparsity (4/5):** Proximity and postprocessing favor few changes; minimality is conditional, not guaranteed. Source: `DBLP:conf/fat/MothilalST20`, Secs. 3--5. https://arxiv.org/html/1905.07697v2
- **level of detail (3/5):** Concrete feature changes give feature-level explanatory detail. Source: `DBLP:conf/fat/MothilalST20`, Secs. 3--5. https://arxiv.org/html/1905.07697v2
- **confidentiality (3/5):** Candidate outputs can reveal sensitive behavior; no default privacy guarantee. Source: `DBLP:conf/fat/MothilalST20`, Secs. 3--5. https://arxiv.org/html/1905.07697v2
- **traceability (3/5):** Reconstruction requires the sampled neighbourhood, random state and fitted surrogate as well as the predictor and input. Source: `DBLP:conf/fat/MothilalST20`, Secs. 3--5. https://arxiv.org/html/1905.07697v2
- **runtime performance (3/5):** Finite candidate generation has moderate assumed cost; algorithm and dimensionality can change this rating. Source: `DBLP:conf/fat/MothilalST20`, Secs. 3--5. https://arxiv.org/html/1905.07697v2

### ProtoDash

- **no false positives (3/5):** Prototype representativeness concerns feature-space similarity; asserted model influence requires behavioural evidence. Source: `DBLP:conf/icdm/GurumoorthyDCA19`, weighted prototype objective and greedy algorithm. https://arxiv.org/abs/1707.01212
- **no false negatives (3/5):** A finite prototype set can miss rare patterns, and distributional coverage is not recall of all model influences. Source: `DBLP:conf/icdm/GurumoorthyDCA19`, weighted prototype objective and greedy algorithm. https://arxiv.org/abs/1707.01212
- **completeness (2/5):** Distributional representation is partial, not full decision rationale. Source: `DBLP:conf/icdm/GurumoorthyDCA19`, weighted prototype objective and greedy algorithm. https://arxiv.org/abs/1707.01212
- **stability (3/5):** Approximation guarantees for selection quality do not imply input stability. Source: `DBLP:conf/icdm/GurumoorthyDCA19`, weighted prototype objective and greedy algorithm. https://arxiv.org/abs/1707.01212
- **adversarial robustness (3/5):** No general explanation attack evaluation establishes high or low resistance. Source: `DBLP:conf/icdm/GurumoorthyDCA19`, weighted prototype objective and greedy algorithm. https://arxiv.org/abs/1707.01212
- **run-to-run consistency (3/5):** Fixed inputs and tie rules enable repeatability, without guaranteeing sample-to-sample consistency. Source: `DBLP:conf/icdm/GurumoorthyDCA19`, weighted prototype objective and greedy algorithm. https://arxiv.org/abs/1707.01212
- **explainer-parameter robustness (3/5):** Kernel, bandwidth and prototype count alter the selected representatives. Source: `DBLP:conf/icdm/GurumoorthyDCA19`, weighted prototype objective and greedy algorithm. https://arxiv.org/abs/1707.01212
- **sparsity (4/5):** A small weighted subset explicitly promotes compact representation. Source: `DBLP:conf/icdm/GurumoorthyDCA19`, weighted prototype objective and greedy algorithm. https://arxiv.org/abs/1707.01212
- **level of detail (3/5):** Representative records show examples, not full decision rules. Source: `DBLP:conf/icdm/GurumoorthyDCA19`, weighted prototype objective and greedy algorithm. https://arxiv.org/abs/1707.01212
- **confidentiality (2/5):** Releasing actual prototypes can disclose source records; assumes unprotected examples are shown. Source: `DBLP:conf/icdm/GurumoorthyDCA19`, weighted prototype objective and greedy algorithm. https://arxiv.org/abs/1707.01212
- **traceability (4/5):** Selection steps, weights, kernel and candidates can be archived. Source: `DBLP:conf/icdm/GurumoorthyDCA19`, weighted prototype objective and greedy algorithm. https://arxiv.org/abs/1707.01212
- **runtime performance (3/5):** Greedy selection avoids exhaustive subset search; no universal quadratic-cost verdict is justified. Source: `DBLP:conf/icdm/GurumoorthyDCA19`, weighted prototype objective and greedy algorithm. https://arxiv.org/abs/1707.01212

### Exact local SHAP

- **no false positives (3/5):** Exact allocation concerns the coalition game; feature relevance can differ under decision-based relevance definitions. Source: `scoreRelevance2023`, Secs. 6--7. https://arxiv.org/pdf/2302.08160
- **no false negatives (3/5):** Exact allocation can assign zero to decision-relevant features, motivating neutral contributor coverage. Source: `scoreRelevance2023`, Secs. 6--7. https://arxiv.org/pdf/2302.08160
- **completeness (3/5):** Additive allocation covers the output difference; interactions are compressed into feature contributions. Source: `DBLP:conf/nips/LundbergL17`, Secs. 2--5. https://arxiv.org/html/1705.07874v2
- **stability (3/5):** Exact computation does not imply continuity under changes to inputs or background. Source: `DBLP:conf/nips/LundbergL17`, Secs. 2--5. https://arxiv.org/html/1705.07874v2
- **adversarial robustness (3/5):** No general adversarial guarantee follows from Shapley axioms; neutral remains evidence-limited. Source: `DBLP:conf/nips/LundbergL17`, Secs. 2--5. https://arxiv.org/html/1705.07874v2
- **run-to-run consistency (3/5):** Exact enumeration is repeatable for fixed inputs; matched cross-method repeatability evidence is limited. Source: `DBLP:conf/nips/LundbergL17`, Secs. 2--5. https://arxiv.org/html/1705.07874v2
- **explainer-parameter robustness (3/5):** Masker and background define the allocation problem; neutral does not imply invariance to their choice. Source: `DBLP:conf/nips/LundbergL17`, Secs. 2--5. https://arxiv.org/html/1705.07874v2
- **sparsity (3/5):** Feature attributions can be dense or truncated for presentation. Source: `DBLP:conf/nips/LundbergL17`, Secs. 2--5. https://arxiv.org/html/1705.07874v2
- **level of detail (3/5):** Feature allocations provide intermediate detail, not explicit decision rules. Source: `DBLP:conf/nips/LundbergL17`, Secs. 2--5. https://arxiv.org/html/1705.07874v2
- **confidentiality (3/5):** Local exact attribution supplies no inherent privacy protection. Source: `DBLP:conf/nips/LundbergL17`, Secs. 2--5. https://arxiv.org/html/1705.07874v2
- **traceability (4/5):** A specified computation can be reconstructed if model, input, reference or propagation parameters and software versions are retained. Source: `DBLP:conf/nips/LundbergL17`, Secs. 2--5. https://arxiv.org/html/1705.07874v2
- **runtime performance (1/5):** Generic enumeration is exponentially expensive; specialized exact tree/linear methods are excluded from this profile. Source: `scoreExactSHAPDocs`, ExactExplainer, computational complexity. https://shap.readthedocs.io/en/latest/generated/shap.ExactExplainer.html

### Approximate local SHAP

- **no false positives (3/5):** Approximation error and reference semantics affect assigned factors. Source: `scoreRelevance2023`, Secs. 6--7. https://arxiv.org/pdf/2302.08160
- **no false negatives (3/5):** Sampling can suppress contributions; exact allocation also has relevance counterexamples, leaving both variants in the neutral bin. Source: `scoreRelevance2023`, Secs. 6--7. https://arxiv.org/pdf/2302.08160
- **completeness (3/5):** Local reconstruction does not establish full explanatory coverage. Source: `scoreKernelSHAPDocs`, KernelExplainer, sampling and regression. https://shap.readthedocs.io/en/latest/generated/shap.KernelExplainer.html
- **stability (2/5):** Sampling introduces variation in addition to input and background sensitivity. Source: `scoreRobust2018`, Secs. 2--3, Figures 2--6. https://arxiv.org/pdf/1806.08049
- **adversarial robustness (2/5):** Published perturbation-based attacks support a below-neutral rating for the sampled scenario. Source: `DBLP:conf/aies/SlackHJSL20`, scaffolded-classifier experiments. https://arxiv.org/pdf/1911.02508
- **run-to-run consistency (2/5):** Finite-sample estimates can differ across runs; fixed-seed replay does not guarantee general consistency. Source: `man2020best`, Secs. 2--3 and 5. https://arxiv.org/pdf/2005.12483
- **explainer-parameter robustness (2/5):** Budget, regularization and background can materially affect estimates. Source: `scoreKernelSHAPDocs`, KernelExplainer, sampling and regression. https://shap.readthedocs.io/en/latest/generated/shap.KernelExplainer.html
- **sparsity (3/5):** Approximate and exact outputs use feature vectors with tunable display size. Source: `scoreKernelSHAPDocs`, KernelExplainer, sampling and regression. https://shap.readthedocs.io/en/latest/generated/shap.KernelExplainer.html
- **level of detail (3/5):** Approximation preserves feature-level granularity. Source: `scoreKernelSHAPDocs`, KernelExplainer, sampling and regression. https://shap.readthedocs.io/en/latest/generated/shap.KernelExplainer.html
- **confidentiality (3/5):** Approximation supplies no confidentiality mechanism. Source: `scoreKernelSHAPDocs`, KernelExplainer, sampling and regression. https://shap.readthedocs.io/en/latest/generated/shap.KernelExplainer.html
- **traceability (4/5):** Stored sample masks, random state, predictor and parameters permit reconstruction. Source: `scoreKernelSHAPDocs`, KernelExplainer, sampling and regression. https://shap.readthedocs.io/en/latest/generated/shap.KernelExplainer.html
- **runtime performance (2/5):** Sampling reduces generic exact enumeration cost but still requires repeated model evaluations. Source: `scoreKernelSHAPDocs`, KernelExplainer, sampling and regression. https://shap.readthedocs.io/en/latest/generated/shap.KernelExplainer.html

### Global SHAP

- **no false positives (3/5):** Aggregation does not repair local relevance errors; neutral is conditional on representative inputs. Source: `scoreGlobalSHAPDocs`, global bar plots. https://shap.readthedocs.io/en/latest/example_notebooks/api_examples/plots/bar.html
- **no false negatives (3/5):** Population averaging may hide rare influential patterns. Source: `scoreGlobalSHAPDocs`, global bar plots. https://shap.readthedocs.io/en/latest/example_notebooks/api_examples/plots/bar.html
- **completeness (2/5):** Summary statistics omit individual configurations and interactions. Source: `scoreGlobalSHAPDocs`, global bar plots. https://shap.readthedocs.io/en/latest/example_notebooks/api_examples/plots/bar.html
- **stability (3/5):** Averaging may reduce variability, but cohort shifts remain; no universal stability guarantee. Source: `scoreGlobalSHAPDocs`, global bar plots. https://shap.readthedocs.io/en/latest/example_notebooks/api_examples/plots/bar.html
- **adversarial robustness (3/5):** Attack-resistance evidence for population summaries is limited. Source: `scoreGlobalSHAPDocs`, global bar plots. https://shap.readthedocs.io/en/latest/example_notebooks/api_examples/plots/bar.html
- **run-to-run consistency (3/5):** Changing the cohort can alter importance rankings even with reproducible local values. Source: `scoreGlobalSHAPDocs`, global bar plots. https://shap.readthedocs.io/en/latest/example_notebooks/api_examples/plots/bar.html
- **explainer-parameter robustness (2/5):** Cohort, background, estimator and aggregation choices all affect results. Source: `scoreGlobalSHAPDocs`, global bar plots. https://shap.readthedocs.io/en/latest/example_notebooks/api_examples/plots/bar.html
- **sparsity (2/5):** Many-feature, many-observation displays are dense under this scenario. Source: `scoreGlobalSHAPDocs`, global bar plots. https://shap.readthedocs.io/en/latest/example_notebooks/api_examples/plots/bar.html
- **level of detail (3/5):** Aggregation preserves feature-level importance while compressing individual combinations. Source: `scoreGlobalSHAPDocs`, global bar plots. https://shap.readthedocs.io/en/latest/example_notebooks/api_examples/plots/bar.html
- **confidentiality (3/5):** Aggregation alone is not a privacy guarantee. Source: `scoreGlobalSHAPDocs`, global bar plots. https://shap.readthedocs.io/en/latest/example_notebooks/api_examples/plots/bar.html
- **traceability (4/5):** Stored cohort, local attributions and summary procedure permit reconstruction. Source: `scoreGlobalSHAPDocs`, global bar plots. https://shap.readthedocs.io/en/latest/example_notebooks/api_examples/plots/bar.html
- **runtime performance (1/5):** Repeated local estimation across many records has high assumed cost; exact-input or optimized summaries require separate profiles. Source: `scoreGlobalSHAPDocs`, global bar plots. https://shap.readthedocs.io/en/latest/example_notebooks/api_examples/plots/bar.html

### LLM-assisted behavioural RuleSHAP (MechaRule stage 1)

- **no false positives (3/5):** Hypothesis scoring supports association, not causal necessity. Source: `sovrano2026mecharule`, Secs. 4 and 8. https://arxiv.org/html/2605.03058v1
- **no false negatives (3/5):** Proposed predicates can miss unrepresented behavioral triggers. Source: `sovrano2026mecharule`, Secs. 4 and 8. https://arxiv.org/html/2605.03058v1
- **completeness (3/5):** Selected rules cover task behavior, not all model logic. Source: `sovrano2026mecharule`, Secs. 4 and 8. https://arxiv.org/html/2605.03058v1
- **stability (2/5):** Feature proposals and fitted rules may vary. Source: `sovrano2026mecharule`, Secs. 4 and 8. https://arxiv.org/html/2605.03058v1
- **adversarial robustness (3/5):** No explanation attack-resistance guarantee is established. Source: `sovrano2026mecharule`, Secs. 4 and 8. https://arxiv.org/html/2605.03058v1
- **run-to-run consistency (2/5):** LLM proposals can change between runs. Source: `sovrano2026mecharule`, Secs. 4 and 8. https://arxiv.org/html/2605.03058v1
- **explainer-parameter robustness (2/5):** Prompt, filtering and rule-selection parameters matter. Source: `sovrano2026mecharule`, Secs. 4 and 8. https://arxiv.org/html/2605.03058v1
- **sparsity (3/5):** Greedy selection promotes compactness without minimality guarantees. Source: `sovrano2026mecharule`, Secs. 4 and 8. https://arxiv.org/html/2605.03058v1
- **level of detail (4/5):** Executable predicates expose detailed behavioral conditions. Source: `sovrano2026mecharule`, Secs. 4 and 8. https://arxiv.org/html/2605.03058v1
- **confidentiality (2/5):** Prompts, outputs and extracted rules may be sensitive. Source: `sovrano2026mecharule`, Secs. 4 and 8. https://arxiv.org/html/2605.03058v1
- **traceability (3/5):** Stored proposals, predicate code and evaluation data link the rule to the sampled behaviour. Source: `sovrano2026mecharule`, Secs. 4 and 8. https://arxiv.org/html/2605.03058v1
- **runtime performance (2/5):** LLM calls and rule fitting add computation. Source: `sovrano2026mecharule`, Secs. 4 and 8. https://arxiv.org/html/2605.03058v1

### CAVs

- **no false positives (3/5):** A fitted direction associates concept examples with activations; semantic confounding leaves concept relevance uncertain. Source: `DBLP:conf/icml/KimWGCWVS18`, CAV construction and directional derivatives. https://arxiv.org/abs/1711.11279
- **no false negatives (2/5):** Only supplied concepts are tested; unspecified concepts can be missed. Source: `DBLP:conf/icml/KimWGCWVS18`, CAV construction and directional derivatives. https://arxiv.org/abs/1711.11279
- **completeness (2/5):** Concept directions do not recover the whole model rationale. Source: `DBLP:conf/icml/KimWGCWVS18`, CAV construction and directional derivatives. https://arxiv.org/abs/1711.11279
- **stability (2/5):** Concept examples and learned directions can change measured sensitivity. Source: `DBLP:conf/icml/KimWGCWVS18`, CAV construction and directional derivatives. https://arxiv.org/abs/1711.11279
- **adversarial robustness (2/5):** Attacks on concept examples can alter directional sensitivity. Source: `brown2022corgis`, attacks on concept examples. https://arxiv.org/abs/2110.07120
- **run-to-run consistency (3/5):** Repeated concept-set trials and significance checks help, but do not guarantee cross-dataset consistency. Source: `DBLP:conf/icml/KimWGCWVS18`, CAV construction and directional derivatives. https://arxiv.org/abs/1711.11279
- **explainer-parameter robustness (1/5):** Concept-bank and layer choices strongly determine the measured direction. Source: `DBLP:conf/icml/KimWGCWVS18`, CAV construction and directional derivatives. https://arxiv.org/abs/1711.11279
- **sparsity (3/5):** Few concepts can be concise, but CAVs do not enforce a minimal concept set. Source: `DBLP:conf/icml/KimWGCWVS18`, CAV construction and directional derivatives. https://arxiv.org/abs/1711.11279
- **level of detail (2/5):** Concept-level abstraction is coarser than feature predicates; low detail is not a claim of low usefulness. Source: `DBLP:conf/icml/KimWGCWVS18`, CAV construction and directional derivatives. https://arxiv.org/abs/1711.11279
- **confidentiality (3/5):** Concept examples and scores require contextual disclosure controls. Source: `DBLP:conf/icml/KimWGCWVS18`, CAV construction and directional derivatives. https://arxiv.org/abs/1711.11279
- **traceability (3/5):** Reconstruction requires the sampled neighbourhood, random state and fitted surrogate as well as the predictor and input. Source: `DBLP:conf/icml/KimWGCWVS18`, CAV construction and directional derivatives. https://arxiv.org/abs/1711.11279
- **runtime performance (3/5):** Fits concept classifiers on frozen activations; it does not require training the underlying neural network. Source: `DBLP:conf/icml/KimWGCWVS18`, CAV construction and directional derivatives. https://arxiv.org/abs/1711.11279

### DeepLIFT

- **no false positives (3/5):** Reference-based contributions are useful but do not establish absence of irrelevant features. Source: `DBLP:conf/icml/ShrikumarGK17`, reference differences and propagation rules. https://arxiv.org/abs/1704.02685
- **no false negatives (3/5):** Summation-to-delta does not prove every relevant factor is recovered. Source: `DBLP:conf/icml/ShrikumarGK17`, reference differences and propagation rules. https://arxiv.org/abs/1704.02685
- **completeness (3/5):** An additive decomposition relative to a reference is not the complete decision rationale. Source: `DBLP:conf/icml/ShrikumarGK17`, reference differences and propagation rules. https://arxiv.org/abs/1704.02685
- **stability (3/5):** Fixed references remove sampling variation; sensitivity to input and representation remains. Source: `DBLP:conf/icml/ShrikumarGK17`, reference differences and propagation rules. https://arxiv.org/abs/1704.02685
- **adversarial robustness (2/5):** Reference and representation changes can alter contributions, supporting a below-neutral design-based robustness judgment. Source: `DBLP:series/lncs/KindermansHAASDEK19`, input-invariance counterexamples. https://arxiv.org/abs/1711.00867
- **run-to-run consistency (3/5):** Fixed execution can repeat; cross-model consistency is not guaranteed by the attribution definition. Source: `DBLP:conf/icml/ShrikumarGK17`, reference differences and propagation rules. https://arxiv.org/abs/1704.02685
- **explainer-parameter robustness (1/5):** Reference choice materially changes contribution allocation. Source: `DBLP:conf/icml/ShrikumarGK17`, reference differences and propagation rules. https://arxiv.org/abs/1704.02685
- **sparsity (3/5):** Feature attribution can be dense or truncated through display selection. Source: `DBLP:conf/icml/ShrikumarGK17`, reference differences and propagation rules. https://arxiv.org/abs/1704.02685
- **level of detail (3/5):** Feature contributions provide intermediate detail. Source: `DBLP:conf/icml/ShrikumarGK17`, reference differences and propagation rules. https://arxiv.org/abs/1704.02685
- **confidentiality (3/5):** Feature maps have no inherent privacy guarantee. Source: `DBLP:conf/icml/ShrikumarGK17`, reference differences and propagation rules. https://arxiv.org/abs/1704.02685
- **traceability (4/5):** Model, reference and propagation records support direct reconstruction of contributions. Source: `DBLP:conf/icml/ShrikumarGK17`, reference differences and propagation rules. https://arxiv.org/abs/1704.02685
- **runtime performance (4/5):** A contribution backpropagation pass is cheaper than multi-baseline or multi-step integration approaches. Source: `DBLP:conf/icml/ShrikumarGK17`, reference differences and propagation rules. https://arxiv.org/abs/1704.02685

### DeepSHAP

- **no false positives (3/5):** Approximate propagation has no blanket guarantee of identifying only influential features. Source: `scoreDeepSHAPDocs`, DeepExplainer, background samples. https://shap.readthedocs.io/en/latest/generated/shap.DeepExplainer.html
- **no false negatives (3/5):** Approximation and reference choice can miss effects; no universal advantage over DeepLIFT is established. Source: `scoreDeepSHAPDocs`, DeepExplainer, background samples. https://shap.readthedocs.io/en/latest/generated/shap.DeepExplainer.html
- **completeness (3/5):** Expected-output reconstruction is distinct from complete explanatory coverage. Source: `scoreDeepSHAPDocs`, DeepExplainer, background samples. https://shap.readthedocs.io/en/latest/generated/shap.DeepExplainer.html
- **stability (3/5):** Fixed background execution need not be stochastic; background and input sensitivity remain. Source: `scoreDeepSHAPDocs`, DeepExplainer, background samples. https://shap.readthedocs.io/en/latest/generated/shap.DeepExplainer.html
- **adversarial robustness (3/5):** Comparative attack-resistance evidence for the approximate propagation procedure is limited. Source: `scoreDeepSHAPDocs`, DeepExplainer, background samples. https://shap.readthedocs.io/en/latest/generated/shap.DeepExplainer.html
- **run-to-run consistency (3/5):** Fixed references support repeatability; comparative repeated-computation evidence is limited. Source: `scoreDeepSHAPDocs`, DeepExplainer, background samples. https://shap.readthedocs.io/en/latest/generated/shap.DeepExplainer.html
- **explainer-parameter robustness (2/5):** Background set and supported propagation operations affect results. Source: `scoreDeepSHAPDocs`, DeepExplainer, background samples. https://shap.readthedocs.io/en/latest/generated/shap.DeepExplainer.html
- **sparsity (3/5):** Feature attribution can be dense or truncated through display selection. Source: `scoreDeepSHAPDocs`, DeepExplainer, background samples. https://shap.readthedocs.io/en/latest/generated/shap.DeepExplainer.html
- **level of detail (3/5):** Per-feature contributions have comparable detail to DeepLIFT. Source: `scoreDeepSHAPDocs`, DeepExplainer, background samples. https://shap.readthedocs.io/en/latest/generated/shap.DeepExplainer.html
- **confidentiality (3/5):** No inherent privacy guarantee follows from background averaging. Source: `scoreDeepSHAPDocs`, DeepExplainer, background samples. https://shap.readthedocs.io/en/latest/generated/shap.DeepExplainer.html
- **traceability (4/5):** Stored background examples, predictor and propagation operators permit reconstruction. Source: `scoreDeepSHAPDocs`, DeepExplainer, background samples. https://shap.readthedocs.io/en/latest/generated/shap.DeepExplainer.html
- **runtime performance (3/5):** Work scales with background examples; typically more than single-reference DeepLIFT. Source: `scoreDeepSHAPDocs`, DeepExplainer, background samples. https://shap.readthedocs.io/en/latest/generated/shap.DeepExplainer.html

### LRP

- **no false positives (3/5):** Conservation allocates a score; relevance of highlighted factors depends on the chosen propagation variant. Source: `bach2015pixel`, Methods, relevance propagation. https://journals.plos.org/plosone/article?id=10.1371/journal.pone.0130140
- **no false negatives (3/5):** A conserved score can coexist with omitted influential factors; variant-specific failures leave broad-family coverage uncertain. Source: `bach2015pixel`, Methods, relevance propagation. https://journals.plos.org/plosone/article?id=10.1371/journal.pone.0130140
- **completeness (3/5):** Redistributing an output quantity does not supply a complete rationale; conservation depends on propagation rule. Source: `bach2015pixel`, Methods, relevance propagation. https://journals.plos.org/plosone/article?id=10.1371/journal.pone.0130140
- **stability (1/5):** Unstabilised relevance maps change sharply under input perturbations. Source: `scoreRobust2018`, Secs. 2--3, Figures 2--6. https://arxiv.org/pdf/1806.08049
- **adversarial robustness (1/5):** Saliency manipulation motivates a low robustness judgment for unstabilised relevance propagation. Source: `bach2015pixel`, Methods, relevance propagation. https://journals.plos.org/plosone/article?id=10.1371/journal.pone.0130140
- **run-to-run consistency (3/5):** Fixed rules can repeat, but rule and model changes can alter the explanation. Source: `bach2015pixel`, Methods, relevance propagation. https://journals.plos.org/plosone/article?id=10.1371/journal.pone.0130140
- **explainer-parameter robustness (1/5):** Redistribution rules and stabilisers materially change relevance maps. Source: `bach2015pixel`, Methods, relevance propagation. https://journals.plos.org/plosone/article?id=10.1371/journal.pone.0130140
- **sparsity (2/5):** Pixel or feature relevance is usually dense. Source: `bach2015pixel`, Methods, relevance propagation. https://journals.plos.org/plosone/article?id=10.1371/journal.pone.0130140
- **level of detail (3/5):** Feature-resolution relevance is intermediate detail, not full logic. Source: `bach2015pixel`, Methods, relevance propagation. https://journals.plos.org/plosone/article?id=10.1371/journal.pone.0130140
- **confidentiality (3/5):** No inherent privacy protection is supplied by relevance conservation. Source: `bach2015pixel`, Methods, relevance propagation. https://journals.plos.org/plosone/article?id=10.1371/journal.pone.0130140
- **traceability (4/5):** Stored model, input and propagation rules permit reconstruction. Source: `bach2015pixel`, Methods, relevance propagation. https://journals.plos.org/plosone/article?id=10.1371/journal.pone.0130140
- **runtime performance (4/5):** Layerwise backpropagation is comparatively efficient. Source: `bach2015pixel`, Methods, relevance propagation. https://journals.plos.org/plosone/article?id=10.1371/journal.pone.0130140

### Grad-CAM

- **no false positives (3/5):** Coarse localization can identify useful regions, without establishing pixel-level necessity. Source: `DBLP:journals/ijcv/SelvarajuCDVPB20`, gradient weighting and class localisation. https://ar5iv.labs.arxiv.org/html/1610.02391
- **no false negatives (2/5):** Positive-only localization omits negative evidence and finer feature contributions. Source: `DBLP:journals/ijcv/SelvarajuCDVPB20`, gradient weighting and class localisation. https://ar5iv.labs.arxiv.org/html/1610.02391
- **completeness (2/5):** A coarse region map does not conserve all evidence or explain the full decision. Source: `DBLP:journals/ijcv/SelvarajuCDVPB20`, gradient weighting and class localisation. https://ar5iv.labs.arxiv.org/html/1610.02391
- **stability (2/5):** Layer and gradient changes can alter localization. Source: `scoreRobust2018`, Secs. 2--3, Figures 2--6. https://arxiv.org/pdf/1806.08049
- **adversarial robustness (2/5):** Model manipulation can alter Grad-CAM maps while preserving predictions. Source: `scoreGradCAMAttack2019`, model-manipulation experiments. https://arxiv.org/abs/1907.10901
- **run-to-run consistency (3/5):** Fixed inference repeats, but model and sample changes can alter maps. Source: `DBLP:journals/ijcv/SelvarajuCDVPB20`, gradient weighting and class localisation. https://ar5iv.labs.arxiv.org/html/1610.02391
- **explainer-parameter robustness (2/5):** Chosen layer and aggregation conventions materially affect localization. Source: `DBLP:journals/ijcv/SelvarajuCDVPB20`, gradient weighting and class localisation. https://ar5iv.labs.arxiv.org/html/1610.02391
- **sparsity (3/5):** Localized regions can be compact but do not enforce a minimal feature set. Source: `DBLP:journals/ijcv/SelvarajuCDVPB20`, gradient weighting and class localisation. https://ar5iv.labs.arxiv.org/html/1610.02391
- **level of detail (3/5):** Layer resolution provides regional rather than individual-input detail. Source: `DBLP:journals/ijcv/SelvarajuCDVPB20`, gradient weighting and class localisation. https://ar5iv.labs.arxiv.org/html/1610.02391
- **confidentiality (3/5):** Heatmaps do not inherently protect information about inputs or models. Source: `DBLP:journals/ijcv/SelvarajuCDVPB20`, gradient weighting and class localisation. https://ar5iv.labs.arxiv.org/html/1610.02391
- **traceability (4/5):** Stored model, input, gradients and selected layer permit reconstruction. Source: `DBLP:journals/ijcv/SelvarajuCDVPB20`, gradient weighting and class localisation. https://ar5iv.labs.arxiv.org/html/1610.02391
- **runtime performance (5/5):** For a fixed network, one gradient pass and pooling give a top relative runtime rating; memory remains architecture-dependent. Source: `DBLP:journals/ijcv/SelvarajuCDVPB20`, gradient weighting and class localisation. https://ar5iv.labs.arxiv.org/html/1610.02391

### Integrated Gradients

- **no false positives (4/5):** Sensitivity(b) assigns zero contribution to functionally independent features, supporting a qualified necessity advantage. Source: `DBLP:conf/icml/SundararajanTY17`, Sec. 4.1, Sensitivity(b) and Proposition 2. https://arxiv.org/html/1703.01365v2
- **no false negatives (3/5):** Sensitivity(a) covers a single changed feature; general contributor coverage depends on baseline and multifeature interactions. Source: `DBLP:conf/icml/SundararajanTY17`, Secs. 2--4. https://arxiv.org/html/1703.01365v2
- **completeness (3/5):** Path completeness is a mathematical allocation identity, not complete decision rationale. Source: `DBLP:conf/icml/SundararajanTY17`, Secs. 2--4. https://arxiv.org/html/1703.01365v2
- **stability (3/5):** Integration does not guarantee input or baseline stability; neutral remains appropriate. Source: `scoreRobust2018`, Secs. 2--3, Figures 2--6. https://arxiv.org/pdf/1806.08049
- **adversarial robustness (3/5):** Fixed-baseline gradient attribution has mixed robustness results under worst-case input perturbations. Source: `DBLP:conf/icml/SundararajanTY17`, Secs. 2--4. https://arxiv.org/html/1703.01365v2
- **run-to-run consistency (3/5):** Fixed paths support repeatability; matched repeated-computation evidence is limited. Source: `DBLP:conf/icml/SundararajanTY17`, Secs. 2--4. https://arxiv.org/html/1703.01365v2
- **explainer-parameter robustness (3/5):** Baseline and quadrature choices affect attribution, with limited common-scale comparative calibration. Source: `DBLP:conf/icml/SundararajanTY17`, Secs. 2--4. https://arxiv.org/html/1703.01365v2
- **sparsity (3/5):** Feature attribution can be dense or truncated through display selection. Source: `DBLP:conf/icml/SundararajanTY17`, Secs. 2--4. https://arxiv.org/html/1703.01365v2
- **level of detail (3/5):** Feature-level contributions have intermediate detail. Source: `DBLP:conf/icml/SundararajanTY17`, Secs. 2--4. https://arxiv.org/html/1703.01365v2
- **confidentiality (3/5):** No inherent confidentiality guarantee is supplied. Source: `DBLP:conf/icml/SundararajanTY17`, Secs. 2--4. https://arxiv.org/html/1703.01365v2
- **traceability (4/5):** Stored baseline, integration path and predictor permit reconstruction. Source: `DBLP:conf/icml/SundararajanTY17`, Secs. 2--4. https://arxiv.org/html/1703.01365v2
- **runtime performance (2/5):** Path integration requires more gradient evaluations than single-pass attribution. Source: `DBLP:conf/icml/SundararajanTY17`, Secs. 2--4. https://arxiv.org/html/1703.01365v2

### Attention

- **no false positives (2/5):** Attention weights alone can disagree with output influence; contextual explanatory value remains debated. Source: `jain2019attention`, attention-correlation and counterfactual experiments. https://aclanthology.org/N19-1357/
- **no false negatives (2/5):** Relevant factors outside displayed attention can be missed. Source: `jain2019attention`, attention-correlation and counterfactual experiments. https://aclanthology.org/N19-1357/
- **completeness (1/5):** Attention weights omit downstream computations required to cover the decision rationale. Source: `jain2019attention`, attention-correlation and counterfactual experiments. https://aclanthology.org/N19-1357/
- **stability (3/5):** Comparative input-stability evidence for extracted attention weights is limited. Source: `jain2019attention`, attention-correlation and counterfactual experiments. https://aclanthology.org/N19-1357/
- **adversarial robustness (3/5):** No universal attack-resistance ranking for all attention architectures is established. Source: `jain2019attention`, attention-correlation and counterfactual experiments. https://aclanthology.org/N19-1357/
- **run-to-run consistency (3/5):** Repeatable weights in evaluation mode do not guarantee consistency across models or time. Source: `jain2019attention`, attention-correlation and counterfactual experiments. https://aclanthology.org/N19-1357/
- **explainer-parameter robustness (2/5):** Layer, head and aggregation choices change the displayed explanation. Source: `jain2019attention`, attention-correlation and counterfactual experiments. https://aclanthology.org/N19-1357/
- **sparsity (3/5):** Head and layer aggregation determine whether the weight display is compact or dense. Source: `jain2019attention`, attention-correlation and counterfactual experiments. https://aclanthology.org/N19-1357/
- **level of detail (2/5):** Head-level associations are coarser than a complete feature or rule-level rationale. Source: `jain2019attention`, attention-correlation and counterfactual experiments. https://aclanthology.org/N19-1357/
- **confidentiality (3/5):** Attention displays are not privacy mechanisms. Source: `jain2019attention`, attention-correlation and counterfactual experiments. https://aclanthology.org/N19-1357/
- **traceability (3/5):** Reconstruction requires the sampled neighbourhood, random state and fitted surrogate as well as the predictor and input. Source: `jain2019attention`, attention-correlation and counterfactual experiments. https://aclanthology.org/N19-1357/
- **runtime performance (5/5):** Extraction from an existing forward pass is inexpensive; this excludes training and additional attention-attribution algorithms. Source: `jain2019attention`, attention-correlation and counterfactual experiments. https://aclanthology.org/N19-1357/

### Supervised CBM

- **no false positives (3/5):** Concept labels need not match encoded information; no automatic necessity guarantee. Source: `scoreConceptLimits2021`, concept representation and semantic alignment. https://arxiv.org/abs/2105.04289
- **no false negatives (3/5):** Concept coordinates expose the prediction interface; imperfect semantics can leave encoded influences unnamed. Source: `scoreConceptLimits2021`, concept representation and semantic alignment. https://arxiv.org/abs/2105.04289
- **completeness (4/5):** Concept-only routing exposes all inputs to the constructed prediction head. Source: `DBLP:conf/icml/KohNTMPKL20`, concept-to-label architecture and interventions. https://proceedings.mlr.press/v119/koh20a.html
- **stability (3/5):** Concept predictions remain sensitive to model and data. Source: `DBLP:conf/icml/KohNTMPKL20`, concept-to-label architecture and interventions. https://proceedings.mlr.press/v119/koh20a.html
- **adversarial robustness (3/5):** Concept intervention is not a general attack defense. Source: `DBLP:conf/icml/KohNTMPKL20`, concept-to-label architecture and interventions. https://proceedings.mlr.press/v119/koh20a.html
- **run-to-run consistency (3/5):** Fixed concepts aid comparison; learned encoders can vary. Source: `DBLP:conf/icml/KohNTMPKL20`, concept-to-label architecture and interventions. https://proceedings.mlr.press/v119/koh20a.html
- **explainer-parameter robustness (2/5):** Concept bank and training scheme influence representations. Source: `DBLP:conf/icml/KohNTMPKL20`, concept-to-label architecture and interventions. https://proceedings.mlr.press/v119/koh20a.html
- **sparsity (3/5):** Few concepts help, but no minimal set is enforced. Source: `DBLP:conf/icml/KohNTMPKL20`, concept-to-label architecture and interventions. https://proceedings.mlr.press/v119/koh20a.html
- **level of detail (3/5):** Concept values and head behavior expose intermediate computation. Source: `DBLP:conf/icml/KohNTMPKL20`, concept-to-label architecture and interventions. https://proceedings.mlr.press/v119/koh20a.html
- **confidentiality (3/5):** Concept annotations can be sensitive; no privacy mechanism. Source: `DBLP:conf/icml/KohNTMPKL20`, concept-to-label architecture and interventions. https://proceedings.mlr.press/v119/koh20a.html
- **traceability (4/5):** Stored encoder, concept labels and prediction head permit reconstruction. Source: `DBLP:conf/icml/KohNTMPKL20`, concept-to-label architecture and interventions. https://proceedings.mlr.press/v119/koh20a.html
- **runtime performance (2/5):** Concept supervision and training add substantial implementation cost. Source: `DBLP:conf/icml/KohNTMPKL20`, concept-to-label architecture and interventions. https://proceedings.mlr.press/v119/koh20a.html

### Post-hoc CBM (concept-only)

- **no false positives (3/5):** Head contributions are explicit; concept semantics may remain imperfect. Source: `scoreConceptLimits2021`, concept representation and semantic alignment. https://arxiv.org/abs/2105.04289
- **no false negatives (3/5):** Concept coordinates expose the replacement predictor; imperfect semantics can leave encoded influences unnamed. Source: `scoreConceptLimits2021`, concept representation and semantic alignment. https://arxiv.org/abs/2105.04289
- **completeness (4/5):** Concept-only routing exposes all inputs to the constructed prediction head. Source: `yuksekgonul2023pcbm`, Sec. 2, concept-only prediction head. https://arxiv.org/pdf/2205.15480
- **stability (3/5):** Frozen embeddings help repeatability but do not guarantee stability. Source: `yuksekgonul2023pcbm`, Sec. 2, concept-only prediction head. https://arxiv.org/pdf/2205.15480
- **adversarial robustness (3/5):** No general adversarial resistance follows from concept projection. Source: `yuksekgonul2023pcbm`, Sec. 2, concept-only prediction head. https://arxiv.org/pdf/2205.15480
- **run-to-run consistency (3/5):** Stored concepts aid repeatability; refitted heads may differ. Source: `yuksekgonul2023pcbm`, Sec. 2, concept-only prediction head. https://arxiv.org/pdf/2205.15480
- **explainer-parameter robustness (2/5):** Concept bank and sparsity penalty influence the predictor. Source: `yuksekgonul2023pcbm`, Sec. 2, concept-only prediction head. https://arxiv.org/pdf/2205.15480
- **sparsity (4/5):** Sparse linear head promotes compact concept contributions. Source: `yuksekgonul2023pcbm`, Sec. 2, concept-only prediction head. https://arxiv.org/pdf/2205.15480
- **level of detail (3/5):** Coefficients and concept scores expose head-level computation. Source: `yuksekgonul2023pcbm`, Sec. 2, concept-only prediction head. https://arxiv.org/pdf/2205.15480
- **confidentiality (3/5):** Published concepts and weights may reveal sensitive behavior. Source: `yuksekgonul2023pcbm`, Sec. 2, concept-only prediction head. https://arxiv.org/pdf/2205.15480
- **traceability (4/5):** Stored backbone, projection, concepts and head weights permit reconstruction. Source: `yuksekgonul2023pcbm`, Sec. 2, concept-only prediction head. https://arxiv.org/pdf/2205.15480
- **runtime performance (3/5):** Reuse of a frozen backbone reduces training overhead. Source: `yuksekgonul2023pcbm`, Sec. 2, concept-only prediction head. https://arxiv.org/pdf/2205.15480

### LaBo (LLM-guided CBM)

- **no false positives (3/5):** Generated concepts and visual grounding need validation. Source: `scoreConceptLimits2021`, concept representation and semantic alignment. https://arxiv.org/abs/2105.04289
- **no false negatives (3/5):** Generated concepts expose the prediction interface; imperfect semantics can leave encoded influences unnamed. Source: `scoreConceptLimits2021`, concept representation and semantic alignment. https://arxiv.org/abs/2105.04289
- **completeness (4/5):** Concept-only routing exposes all inputs to the constructed prediction head. Source: `yang2023labo`, Secs. 3.2--3.3 and 4.3. https://arxiv.org/pdf/2211.11158
- **stability (3/5):** Fixed selected concepts help; input sensitivity remains. Source: `yang2023labo`, Secs. 3.2--3.3 and 4.3. https://arxiv.org/pdf/2211.11158
- **adversarial robustness (3/5):** Language-generated concepts do not establish attack resistance. Source: `yang2023labo`, Secs. 3.2--3.3 and 4.3. https://arxiv.org/pdf/2211.11158
- **run-to-run consistency (2/5):** LLM sampling and concept selection can change representations. Source: `yang2023labo`, Secs. 3.2--3.3 and 4.3. https://arxiv.org/pdf/2211.11158
- **explainer-parameter robustness (2/5):** Prompts, bottleneck size and selection weights affect output. Source: `yang2023labo`, Secs. 3.2--3.3 and 4.3. https://arxiv.org/pdf/2211.11158
- **sparsity (3/5):** The default vocabulary uses 50 concepts per class and dense normalised weights, giving neutral compactness. Source: `yang2023labo`, Secs. 3.2--3.3 and 4.3. https://arxiv.org/pdf/2211.11158
- **level of detail (3/5):** Concept scores and head weights expose intermediate detail. Source: `yang2023labo`, Secs. 3.2--3.3 and 4.3. https://arxiv.org/pdf/2211.11158
- **confidentiality (3/5):** Prompts and data require contextual confidentiality controls. Source: `yang2023labo`, Secs. 3.2--3.3 and 4.3. https://arxiv.org/pdf/2211.11158
- **traceability (4/5):** Stored concept candidates, selected descriptions and model versions permit reconstruction. Source: `yang2023labo`, Secs. 3.2--3.3 and 4.3. https://arxiv.org/pdf/2211.11158
- **runtime performance (3/5):** Concept generation and alignment add cost; encoders are reused. Source: `yang2023labo`, Secs. 3.2--3.3 and 4.3. https://arxiv.org/pdf/2211.11158

### LLM neuron explanations (Bills et al.)

- **no false positives (2/5):** Descriptions are imperfect correlations with activation patterns. Source: `scoreNeuronPaper2023`, explanation and simulation pipeline. https://openaipublic.blob.core.windows.net/neuron-explainer/paper/index.html
- **no false negatives (2/5):** Polysemantic behavior can escape concise descriptions. Source: `scoreNeuronPaper2023`, explanation and simulation pipeline. https://openaipublic.blob.core.windows.net/neuron-explainer/paper/index.html
- **completeness (2/5):** The declared target is neuron activation behavior. Source: `scoreNeuronPaper2023`, explanation and simulation pipeline. https://openaipublic.blob.core.windows.net/neuron-explainer/paper/index.html
- **stability (3/5):** Input-stability evidence for generated activation descriptions is limited; generation variation is assessed through consistency. Source: `scoreNeuronPaper2023`, explanation and simulation pipeline. https://openaipublic.blob.core.windows.net/neuron-explainer/paper/index.html
- **adversarial robustness (3/5):** No general adversarial-resistance evaluation establishes a strength. Source: `scoreNeuronPaper2023`, explanation and simulation pipeline. https://openaipublic.blob.core.windows.net/neuron-explainer/paper/index.html
- **run-to-run consistency (2/5):** Generated descriptions can vary across models or runs. Source: `scoreNeuronPaper2023`, explanation and simulation pipeline. https://openaipublic.blob.core.windows.net/neuron-explainer/paper/index.html
- **explainer-parameter robustness (2/5):** Prompts, examples and simulator choices affect explanations. Source: `scoreNeuronPaper2023`, explanation and simulation pipeline. https://openaipublic.blob.core.windows.net/neuron-explainer/paper/index.html
- **sparsity (3/5):** Short descriptions compress behavior without proving minimality. Source: `scoreNeuronPaper2023`, explanation and simulation pipeline. https://openaipublic.blob.core.windows.net/neuron-explainer/paper/index.html
- **level of detail (3/5):** Neuron-level linguistic patterns offer intermediate descriptive detail. Source: `scoreNeuronPaper2023`, explanation and simulation pipeline. https://openaipublic.blob.core.windows.net/neuron-explainer/paper/index.html
- **confidentiality (3/5):** Activation examples may contain sensitive text. Source: `scoreNeuronPaper2023`, explanation and simulation pipeline. https://openaipublic.blob.core.windows.net/neuron-explainer/paper/index.html
- **traceability (4/5):** Stored examples, prompts, activations and descriptions permit reconstruction. Source: `scoreNeuronPaper2023`, explanation and simulation pipeline. https://openaipublic.blob.core.windows.net/neuron-explainer/paper/index.html
- **runtime performance (2/5):** Repeated generation and simulation are compute-intensive. Source: `scoreNeuronPaper2023`, explanation and simulation pipeline. https://openaipublic.blob.core.windows.net/neuron-explainer/paper/index.html

### MechaRule

- **no false positives (4/5):** Ablation provides conditional necessity evidence, not uniquely symbolic mechanisms. Source: `sovrano2026mecharule`, Secs. 4 and 8. https://arxiv.org/html/2605.03058v1
- **no false negatives (3/5):** Candidate reduction and weak-effect search can miss neurons. Source: `sovrano2026mecharule`, Secs. 4 and 8. https://arxiv.org/html/2605.03058v1
- **completeness (3/5):** Coverage is restricted to task, candidates and intervention basis. Source: `sovrano2026mecharule`, Secs. 4 and 8. https://arxiv.org/html/2605.03058v1
- **stability (3/5):** Baseline and task regime affect localized explanations. Source: `sovrano2026mecharule`, Secs. 4 and 8. https://arxiv.org/html/2605.03058v1
- **adversarial robustness (3/5):** Jailbreak suppression is not robustness of the explanation itself. Source: `sovrano2026mecharule`, Secs. 4 and 8. https://arxiv.org/html/2605.03058v1
- **run-to-run consistency (3/5):** Cross-model and temporal consistency remain unestablished. Source: `sovrano2026mecharule`, Secs. 4 and 8. https://arxiv.org/html/2605.03058v1
- **explainer-parameter robustness (2/5):** Candidate budget, thresholds and baselines affect localization. Source: `sovrano2026mecharule`, Secs. 4 and 8. https://arxiv.org/html/2605.03058v1
- **sparsity (4/5):** Sparse neurons and compact rules are explicit objectives. Source: `sovrano2026mecharule`, Secs. 4 and 8. https://arxiv.org/html/2605.03058v1
- **level of detail (4/5):** Rules linked to neuron coordinates add mechanistic detail. Source: `sovrano2026mecharule`, Secs. 4 and 8. https://arxiv.org/html/2605.03058v1
- **confidentiality (2/5):** Internal coordinates and rules can expose proprietary mechanisms. Source: `sovrano2026mecharule`, Secs. 4 and 8. https://arxiv.org/html/2605.03058v1
- **traceability (4/5):** Stored rules, intervention traces, candidates and baselines permit reconstruction. Source: `sovrano2026mecharule`, Secs. 4 and 8. https://arxiv.org/html/2605.03058v1
- **runtime performance (2/5):** Hierarchical search saves interventions but requires costly internal access. Source: `sovrano2026mecharule`, Secs. 4 and 8. https://arxiv.org/html/2605.03058v1
