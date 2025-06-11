# Legal XAI Compliance Checking

> **Goal:** provide a lightweight, transparent benchmark to assess how well popular XAI (eXplainable AI) techniques satisfy *legal* explainability obligations in the European Union (GDPR, AI Act, Digital Services Act, etc.).

The script **`assess_xai_compliance.py`** scores each algorithm against finely‑grained legal properties (e.g. *faithfulness – no false positives*, *robustness – adversarial stability*, *responsibility – fairness*, …) and maps them to the **questions** a data subject, regulator or auditor is entitled to ask. It then recommends the *best‑fit* algorithm for every regulation × question pair.

---

## ✨ Features

| Feature                     | Description                                                                                               |
| --------------------------- | --------------------------------------------------------------------------------------------------------- |
| **Regulation catalogue**    | Built‑in scoring templates for `GDPR+AIA86+MiFID25`, `DSA17`, `DSA27+P2B5`, `AIA13‑14` (expandable)       |
| **Two algorithm families**  | *Model‑agnostic* (Decision Trees, SHAP, LIME, …) and *model‑specific* (Grad‑CAM, Integrated Gradients, …) |
| **Multi‑criterion scoring** | Weighted sum over 6 high‑level categories and ∼15 sub‑properties                                          |
| **Question coverage check** | Verifies how well an XAI algorithm can answer *all* question types the regulation requires                        |
| **One‑click report**        | Prints a tidy summary of the top algorithm per regulation‑question                               |

---

## 📂 Repository layout

```
legal_xai_compliance/
├── assess_xai_compliance.py  # main CLI / library entry‑point
├── requirements.txt          # Python dependencies (very light!)
└── README.md                 # you are here
```

> **Why so small?** The logic lives entirely in the Python script; no training data, models or notebooks are bundled so that the repo remains audit‑friendly.

---

## 🚀 Quick‑start

### 1. Install

```bash
# Python ≥ 3.9 is recommended
python -m venv .venv && source .venv/bin/activate  # optional but encouraged
pip install -r requirements.txt
```

### 2. Run the benchmark

```bash
python assess_xai_compliance.py
```

The script prints two tables:

1. **Model‑agnostic algorithms**
2. **All algorithms (agnostic + specific)**

Each table lists, for every *regulation* × *question* combination:

* the *best* algorithm(s), and
* the *fit‑score* (0–1).

### 3. Interpret the numbers

A *fit‑score* close to 1 means the algorithm satisfies mandatory properties and covers all required questions. Lower scores indicate partial or no compliance; investigate the weight matrix in the script for details.

---

## 🛠️ Extending the framework

1. **Add a new regulation:**

   * Inside `assess_xai_compliance.py`, append to the `regulations` dict:

     ```python
     'MyLaw42': {
         'required': {
             'no_fp':1, 'stability':0.5, ...
         },
         'scope_stage': 'local-expost',
         'question_types': {'what_rule', 'how_differs'}
     }
     ```
2. **Add an algorithm:**

   * Update one of the `algorithms_model_agnostic` or `algorithms_model_specific` dicts with its sub‑property scores, scope stage and supported question set.
3. **Re‑run** the script; that’s it!  The assessment logic is generic.

> **Tip:** keep algorithm sub‑property scores in [0-5] and regulation sub-property scores ≤ 1 so that scores remain on a comparable 0–1 scale.

---

## 🤝 Contributing

Contributions are welcome!  Please open an issue first to discuss major changes.  When submitting a PR:

1. Follow **PEP 8** and run `ruff`/`black`.
2. Add unit tests for new functionality.
3. Update this README where appropriate.

---

## 📜 License

Distributed under the **MIT License**. See `LICENSE` for full text.

---

## 👥 Maintainers

* **Francesco Sovrano** – [@francesco.sovrano](mailto:cesco.sovrano@gmail.com)

---

## 📖 Citation

If you use this tool in academic work, please cite:

```text
@software{legal_xai_2025,
  author = {Francesco Sovrano, Giulia Vilone, Michael Lognoul},
  title  = {Legal XAI: A Systematic Review of XAI and Law, Interdisciplinary Mapping for Legal Compli-
ance, and a Responsible Research Agenda},
  year   = 2025,
}
```

---

## ✉️ Questions?

Open an [issue](https://github.com/Francesco-Sovrano/Legal-XAI-Compliance-Checking/issues) or reach out via email.
