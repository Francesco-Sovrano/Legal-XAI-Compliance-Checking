# XAI method scoring

This directory contains the canonical method-property catalogue, the seven legal contexts, the shared scoring functions, the joint sensitivity analysis, the deterministic legal-task sensitivity analysis, and the static figure renderer used by the replication package.

## Canonical inputs

`inputs/paper_inputs.json` is the canonical machine-readable input for the manuscript's numerical comparisons. It contains:

- 12 interpretability properties in a fixed order;
- 26 XAI method profiles and their 1–5 method-property ratings;
- procedural attributes for each XAI method profile;
- seven legal contexts and their legal weights;
- random seed `20261005` and default draw count `10000`; and
- the legal-expert validation context definitions.

The first 14 method profiles are the model-agnostic catalogue. Three concept-bottleneck profiles require predictor replacement and one LLM-neuron profile explains internal components; these four profiles are excluded from output-explanation ranking. The remaining 22 profiles enter the joint sensitivity analysis before question-specific procedural eligibility is applied.

`inputs/score_evidence.json` contains the 312 method-property evidence records. `inputs/literature_sources.json` maps source keys to URLs. `inputs/legal_task_variants.json` and `inputs/legal_task_cases.json` define the deterministic legal-task sensitivity analysis. `inputs/survey_counts.json` and `inputs/figures/` provide figure inputs.

## Interpretability properties

The documentation uses the manuscript labels: no false positives, no false negatives, completeness, stability, adversarial robustness, run-to-run consistency, explainer-parameter robustness, sparsity, level of detail, confidentiality, traceability, and runtime performance.

The corresponding internal keys are documented in `assess_xai_compliance_documentation.md`.

## Main scripts

| Script | Function |
| :--- | :--- |
| `scoring.py` | Shared score functions, procedural eligibility, mandatory-property gate, joint perturbation draws, and Kendall tau-b helper. |
| `sensitivity_analysis.py` | Default scores, joint sensitivity analysis, context-level winning probabilities, winner retention, and sensitivity figure. |
| `question_sensitivity.py` | Question-level top-rank probabilities and sensitivity figure. Requires the output of `sensitivity_analysis.py`. |
| `legal_task_sensitivity.py` | Deterministic legal-task sensitivity analysis. |
| `render_figures.py` | Static diagrams, survey figures, and legal-expert explanation-stimulus figures. |
| `assess_xai_compliance.py` | Standalone catalogue example. Its method ratings match `paper_inputs.json`, but its embedded legal vectors are not the manuscript's default legal-weight matrix. |

## Environment

From the package root:

```sh
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -r methods_scoring/requirements.txt
```

The requirements are NumPy 2.3.5, pandas 2.2.3, SciPy 1.17.0, Matplotlib 3.10.8, Pillow 11 or later, and PyMuPDF 1.25 or later.

## Reproduce the scoring outputs

From the package root:

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

`run_scoring.sh` performs the same sequence after `.venv` has been created. It also executes the standalone catalogue example before the canonical analyses.

## Default scoring rules

For legal weight `lambda`, method-property rating `x` on the 1–5 scale, normalized rating `z = x/5`, threshold `T`, and technical priority factor `omega`:

```text
soft        = sum(lambda * z) / sum(lambda)
thresholded = sum(lambda * 1[x >= T]) / sum(lambda)
geometric   = exp(sum(lambda * omega * log(z)) / sum(lambda * omega))
```

The default threshold is `3`; the default technical priority factor is `1`. A legal weight of `1` denotes a requirement, `0.5` a qualified requirement, and `0` a property that is not scored. Procedural eligibility is applied before scoring.

The mandatory-property gate is separate from the comparative legal weights. `hard_gate` returns zero if any mandatory criterion is not established.

## Joint sensitivity analysis

Each of the 10,000 default draws perturbs method-property ratings by an integer from `-2` to `+2`, positive legal weights by an independent multiplier from `[0.75, 1.25]`, technical priority factors log-uniformly from `[0.5, 2]`, and thresholds independently from `{2, 3, 4}`. Ratings and legal weights are clipped to their valid ranges. The same perturbed method-property profile is shared across legal contexts within a draw.

The draw-level ranking value is the arithmetic mean of the soft, thresholded, and geometric scores. `analysis/joint_draw_scores.npz` stores these composite values.

## Deterministic legal-task sensitivity

`inputs/legal_task_variants.json` defines seven two-point alternatives and four MDR task profiles. `inputs/legal_task_cases.json` contains the resulting 128 endpoint combinations and four MDR cases. Method-property ratings, procedural eligibility, threshold `3`, and technical priority factor `1` remain fixed.

The deterministic outputs are `analysis/legal_task_sensitivity.csv` and `analysis/legal_task_sensitivity_summary.json`.

## Static figures

From the package root:

```sh
python - <<'PY'
from methods_scoring.render_figures import render
render("methods_scoring/inputs/figures", "methods_scoring/figures")
PY
```

The sensitivity figures are generated by the sensitivity scripts rather than `render_figures.py`.

## Tests

```sh
python -m unittest discover -s methods_scoring/tests -v
```

The detailed computation, legal-weight matrix, data structures, evidence records, and output schemas are specified in `assess_xai_compliance_documentation.md`.
