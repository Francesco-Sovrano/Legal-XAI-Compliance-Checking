#!/usr/bin/env python3
"""Literature-based Legal XAI catalogue with property-specific evidence.

Run python assess_xai_compliance.py to compare procedurally eligible methods.
Ratings are ordinal inputs; legal fit uses direct property weighting.
"""

__version__ = "3.3.12"

import pandas as pd
from itertools import combinations
import math

# -------------------------------------------------------------------
# 0. Helper: define canonical question categories
# -------------------------------------------------------------------
# Canonical question kinds that we will track. A regulation "requires"
# a subset; an algorithm "supports" a subset.  A match occurs iff
# at least one requested question is supported. Winners are then selected
# separately for each supported regulation/question pair.
QUESTION_KINDS = {
	'what_feature',  # "What specific features…"
	'what_rule',     # "What rule / threshold…"
	'how_computed',     # "How is the output approximately computed?" # not necessarily how is it computed in every details is too complex: we have execution traces but they're useless, we need a high-level representation of the computation
	'how_differs',   # "How does this decision differ from…"
	'what_if',       # "What if parameter X changed…"
	'how_modify_input',  # "What input values should I adjust…"
	'why_instead_of',  # "Why did I get outcome A instead of B?"
}

# map from the exact phrase (or a close synonym) to our canonical question key
TEXT_TO_QUESTION_KIND = {
	'what rule':           'what_rule',
	'what general logic':  'what_rule',
	'how model decides':   'how_computed',

	'what features':         'what_feature',
	'what are top features': 'what_feature',
	'what reasons':          'why_instead_of',
	'what feature importance': 'what_feature',

	'why those top features': 'how_computed', # think about it

	'how output differs from others': 'how_differs',

	'what if':                    'what_if',
	'how sensitive to outliers': 'what_if',

	'how to change':                'how_modify_input',
	'what inputs have wrong outcomes': 'what_feature',
	'what best input format and ranges': 'what_rule', # not sure about format

	'how output is computed':      'how_computed',
	'is input problematic':        'what_rule',
	'what input quality':          'how_modify_input', # similar to 'what best input format and ranges'
	'how robust is output':      'how_differs', # think about it, maybe not about XAI but rather confidence scoring
}

SUBPROP_TO_CAT = {
	# Faithfulness
	# Semantic distinction used throughout the catalogue:
	# - no_false_positives: element-level false inclusion.
	# - no_false_negatives: element-level false omission within the declared explanatory target/representation.
	# - completeness: rationale-level coverage of what the explanation claims to explain.
	'no_false_positives': 'Faithfulness',
	'no_false_negatives': 'Faithfulness',
	'completeness': 'Faithfulness',
	# Robustness
	'stability': 'Robustness',
	'adversarial_robustness': 'Robustness',
	'consistency': 'Robustness',
	'hyperparameters_perturbation_robustness': 'Robustness',
	# Complexity
	'sparsity': 'Complexity',
	'level_of_detail': 'Complexity',
	# Responsibility
	'confidentiality': 'Non-functional constraints',
	'traceability': 'Non-functional constraints',
	# Efficiency
	'runtime_performance_and_implementation_constraints': 'Efficiency',
}

CAT_WEIGHTS = {
	'Faithfulness': 1, # Equal category weights reproduce the retained methodology.
	'Robustness': 1,
	'Complexity': 1,
	'Non-functional constraints': 1,
	'Efficiency': 1,
}

# -------------------------------------------------------------------
# 1.  Regulation‑level metadata
# -------------------------------------------------------------------
regulations = {
	'GDPR+AIA86+MiFID25': {
		# ---------- legal property requirements (sub‑property granularity) ----------
		'required': {
			'no_false_positives':1, 'no_false_negatives':1, 'completeness':0,
			'stability':1, 'adversarial_robustness':0.5, 'consistency':1, 'hyperparameters_perturbation_robustness': 0, 
			'sparsity': 1, 'level_of_detail': 0,
			'confidentiality':0.5, 'traceability':1,
			'runtime_performance_and_implementation_constraints':0,
		},
		# ---------- procedure ----------
		'scope_stage': 'local-expost',
		# ---------- questions ----------
		'question_types': ['what rule', 'how output differs from others', 'what features', 'what reasons', 'is input problematic', 'how to change'],
	},

	'DSA17': {
		'required': {
			'no_false_positives':1, 'no_false_negatives':1, 'completeness':1,
			'stability':1, 'adversarial_robustness':0.5, 'consistency':1, 'hyperparameters_perturbation_robustness': 0, 
			'sparsity': 0, 'level_of_detail': 0,
			'confidentiality':0.5, 'traceability':1,
			'runtime_performance_and_implementation_constraints':0,
		},
		'scope_stage': 'local-expost',
		'question_types': ['what rule', 'how output differs from others', 'what features', 'what reasons', 'is input problematic', 'how to change'],
	},

	'DSA27+P2B5': {
		'required': {
			'no_false_positives':1, 'no_false_negatives':0, 'completeness':0,
			'stability':1, 'adversarial_robustness':0.5, 'consistency':1, 'hyperparameters_perturbation_robustness': 1, 
			'sparsity': 1, 'level_of_detail': 0.75,
			'confidentiality':1, 'traceability':0,
			'runtime_performance_and_implementation_constraints':0,
		},
		'scope_stage': 'global-exante',
		'question_types': ['what are top features', 'why those top features', 'what general logic', 'what if'],
	},

	'AIA13-14': {
		'required': {
			'no_false_positives':0.75, 'no_false_negatives':1, 'completeness':0.75,
			'stability':1, 'adversarial_robustness':1, 'consistency':1, 'hyperparameters_perturbation_robustness': 1, 
			'sparsity': 0, 'level_of_detail': 0,
			'confidentiality':0, 'traceability':1,
			'runtime_performance_and_implementation_constraints':1, # we assume the worst-case scenario
		},
		'scope_stage': 'both',  # accepts both local/ex‑post and global/ex‑ante
		'question_types': ['what input quality', 'how output is computed', 'how sensitive to outliers', 'what rule', 'how robust is output'],
	},

	'MDR': {
		'required': {
			'no_false_positives':1, 'no_false_negatives':1, 'completeness':1,
			'stability':1, 'adversarial_robustness':1, 'consistency':1, 'hyperparameters_perturbation_robustness': 1, 
			'sparsity': 1, 'level_of_detail': 0,
			'confidentiality':0.5, 'traceability':1, # partial confidentiality: protect third-party data while supplying required information
			'runtime_performance_and_implementation_constraints':1, # we assume the worst-case scenario
		},
		'scope_stage': 'both',
		'question_types': ['what rule', 'what general logic', 'is input problematic', 'what inputs have wrong outcomes', 'what best input format and ranges', 'how robust is output'],
	},

	'MiFID17': {
		'required': {
			'no_false_positives':1, 'no_false_negatives':1, 'completeness':1,
			'stability':1, 'adversarial_robustness':1, 'consistency':1, 'hyperparameters_perturbation_robustness': 1, 
			'sparsity': 0, 'level_of_detail': 0,
			'confidentiality':0, 'traceability':1, 
			'runtime_performance_and_implementation_constraints':1, # we assume the worst-case scenario
		},
		'scope_stage': 'both',
		'question_types': [
			'how model decides', 'what feature importance', 
			# 'how regulatory compliance implemented', # not about XAI
			'how robust is output', 'what inputs have wrong outcomes'],
	},

	'AIA11': {
		'required': {
			'no_false_positives':1, 'no_false_negatives':1, 'completeness':1,
			'stability':1, 'adversarial_robustness':1, 'consistency':1, 'hyperparameters_perturbation_robustness': 1, 
			'sparsity': 0, 'level_of_detail': 1,
			'confidentiality':0, 'traceability':1, 
			'runtime_performance_and_implementation_constraints':0,
		},
		'scope_stage': 'global-exante',
		'question_types': [
			'how model decides', 'what feature importance', 
			# 'how regulatory compliance implemented', # not about XAI
			'how robust is output', 'what inputs have wrong outcomes'],
	},
}

# -------------------------------------------------------------------
# 2.  Algorithm‑level metadata
#     For brevity we include all algorithms in Tables 2 & 3.
# -------------------------------------------------------------------
# Ratings are ordinal author judgments, not measured compliance or universal rankings.
# Exact Shapley axioms do not prove causal relevance, robustness, or superior
# predictive generalization. The non-SHAP catalogue below is retained from the
# source and still needs context-specific validation (e.g. surrogate vs intrinsic trees).
# All 312 cells documented using the paper's Table 4 and comparative 1-5 methodology.
# 3 is neutral; neither citations nor axioms make these judgments measured facts.
# Source keys are resolved in LITERATURE_SOURCES; full evidence and uncertainty:
# algorithm_profiles.json and RECHECK_AND_EXTENSIONS.md.
# Source identifiers used in the inline rating comments.
LITERATURE_SOURCES = {'TREE': 'https://scikit-learn.org/stable/modules/tree.html', 'RULEFIT': 'https://arxiv.org/abs/0811.1679', 'RULESHAP': 'https://arxiv.org/html/2505.11189v1', 'ICE': 'https://arxiv.org/html/1309.6392v2', 'LIME': 'https://arxiv.org/abs/1602.04938', 'ANCHORS': 'https://homes.cs.washington.edu/~marcotcr/aaai18.pdf', 'CEM': 'https://arxiv.org/pdf/1802.07623', 'DICE': 'https://arxiv.org/html/1905.07697v2', 'PROTO': 'https://arxiv.org/abs/1707.01212', 'TCAV': 'https://arxiv.org/abs/1711.11279', 'DEEPLIFT': 'https://arxiv.org/abs/1704.02685', 'DEEPSHAP': 'https://shap.readthedocs.io/en/latest/generated/shap.DeepExplainer.html', 'LRP': 'https://journals.plos.org/plosone/article?id=10.1371/journal.pone.0130140', 'GRADCAM': 'https://ar5iv.labs.arxiv.org/html/1610.02391', 'IG': 'https://arxiv.org/html/1703.01365v2', 'ATTENTION': 'https://aclanthology.org/N19-1357/', 'ATTENTION_DEBATE': 'https://aclanthology.org/D19-1002/', 'SHAP': 'https://arxiv.org/html/1705.07874v2', 'EXACT': 'https://shap.readthedocs.io/en/latest/generated/shap.ExactExplainer.html', 'KERNEL': 'https://shap.readthedocs.io/en/latest/generated/shap.KernelExplainer.html', 'GLOBAL': 'https://shap.readthedocs.io/en/latest/example_notebooks/api_examples/plots/bar.html', 'ROBUST': 'https://arxiv.org/pdf/1806.08049', 'ATTACK': 'https://arxiv.org/pdf/1911.02508', 'SALIENCY': 'https://arxiv.org/abs/1711.00867', 'RELEVANCE': 'https://arxiv.org/pdf/2302.08160', 'SHIFT': 'https://arxiv.org/abs/2403.03773', 'CBM': 'https://proceedings.mlr.press/v119/koh20a.html', 'CBM_LIMIT': 'https://arxiv.org/abs/2105.04289', 'PCBM': 'https://arxiv.org/pdf/2205.15480', 'LABO': 'https://arxiv.org/pdf/2211.11158', 'LLM_NEURON': 'https://openaipublic.blob.core.windows.net/neuron-explainer/paper/index.html', 'MECHARULE': 'https://arxiv.org/html/2605.03058v1', 'TCAV_ATTACK': 'https://arxiv.org/abs/2110.07120', 'GRADCAM_ATTACK': 'https://arxiv.org/abs/1907.10901', 'LLM_NEURON_OVERVIEW': 'https://openai.com/index/language-models-can-explain-neurons-in-language-models/', 'METHODOLOGY_2026': 'https://arxiv.org/html/2604.09628v1', 'MAN_CHAN': 'https://arxiv.org/pdf/2005.12483', 'SIXT': 'https://proceedings.mlr.press/v119/sixt20a.html', 'PRIVACY': 'https://arxiv.org/pdf/1907.00164', 'MANY_SHAP': 'https://proceedings.mlr.press/v119/sundararajan20b.html', 'ANCHORS_THEORY': 'https://arxiv.org/abs/2303.08806', 'METRIC_LIMITS': 'https://arxiv.org/abs/1912.01451'}

algorithms_model_agnostic = {
    # Global surrogate tree, not an intrinsically deployed decision tree.
    'Decision Trees': {
        "subprops": {
            # Rating 3/5; original=2; v3.3.11=3. retained after comparative review.
            # Reason: Surrogate agreement requires validation; predictive overfitting does not
            # establish explanation false positives.
            # Comparison: Decision Trees (3/5) ties RuleFit (3/5): the former a fitted surrogate can
            # invent influential splits; the latter surrogate rules need independent agreement
            # checks.
            # Comparison: Decision Trees (3/5) ties RuleSHAP (3/5): the former a fitted surrogate
            # can invent influential splits; the latter rule recovery is not a test of every
            # predicate’s necessity.
            # Calibration: Neutral bin: the evidence does not warrant a general stronger or weaker
            # claim on this exact property. A tie is not demonstrated empirical equivalence.
            # Evidence: qualitative comparative inference; see study cards for direct endpoints and
            # counterevidence. Confidence: moderate.
            # Sources: TREE, RULEFIT, RULESHAP. Comparative studies: E04. See documentation §6 for
            # endpoints and limits.
            # Primary locations: TREE: Advantages/disadvantages; complexity and practical
            # implementation notes
            'no_false_positives': 3,
            # Rating 3/5; original=3; v3.3.11=3. retained after comparative review.
            # Reason: A compressed surrogate can omit black-box effects; no general recall ranking
            # against RuleFit is established.
            # Comparison: Decision Trees (3/5) ties RuleFit (3/5): the former a compact surrogate
            # may omit target effects; the latter sparse selection can omit target influences.
            # Comparison: Decision Trees (3/5) scores below RuleSHAP (4/5): the former a compact
            # surrogate may omit target effects; the latter injected-rule ranking improves over
            # RuleFit in the reported benchmark.
            # Calibration: Neutral bin: the evidence does not warrant a general stronger or weaker
            # claim on this exact property. A tie is not demonstrated empirical equivalence.
            # Evidence: qualitative comparative inference; see study cards for direct endpoints and
            # counterevidence. Confidence: moderate.
            # Sources: TREE, RULEFIT, RULESHAP. Comparative studies: E04. See documentation §6 for
            # endpoints and limits.
            # Primary locations: TREE: Advantages/disadvantages; complexity and practical
            # implementation notes
            'no_false_negatives': 3,
            # Rating 3/5; original=3; v3.3.11=3. retained after comparative review.
            # Reason: Paths cover surrogate logic but need not cover the original model rationale.
            # Comparison: Decision Trees (3/5) scores below RuleFit (4/5): the former one tree has
            # limited interaction and linear-trend capacity; the latter rules plus linear terms
            # cover both interactions and trends.
            # Comparison: Decision Trees (3/5) scores below RuleSHAP (4/5): the former one tree has
            # limited interaction and linear-trend capacity; the latter a weighted rule ensemble can
            # represent compound conditions.
            # Calibration: Neutral bin: the evidence does not warrant a general stronger or weaker
            # claim on this exact property. A tie is not demonstrated empirical equivalence.
            # Evidence: qualitative comparative inference; see study cards for direct endpoints and
            # counterevidence. Confidence: moderate.
            # Sources: TREE, RULEFIT, RULESHAP. Comparative studies: E04. See documentation §6 for
            # endpoints and limits.
            # Primary locations: TREE: Advantages/disadvantages; complexity and practical
            # implementation notes
            'completeness': 3,
            # Rating 1/5; original=1; v3.3.11=1. retained after comparative review.
            # Reason: A path explanation can jump when a small input change crosses a split. The
            # inherited 1 is a low-confidence worst-bin code for such discontinuous paths.
            # Training-data instability concerns consistency instead; it is not direct evidence for
            # this input-stability score. A fixed whole-tree display is a different output and
            # should be re-rated.
            # Comparison: Decision Trees (1/5) scores below RuleFit (3/5): the former a local path
            # can change abruptly at a split; the latter regularization may temper variation without
            # fixing selected rules.
            # Comparison: Decision Trees (1/5) scores below RuleSHAP (3/5): the former a local path
            # can change abruptly at a split; the latter the combined estimator still depends on its
            # data and settings.
            # Calibration: An inherited endpoint under the stated output/configuration, not a
            # universal guarantee or universal failure. The exact endpoint is low-confidence outside
            # that setting.
            # Evidence: qualitative comparative inference; see study cards for direct endpoints and
            # counterevidence. Confidence: low.
            # Sources: TREE, RULEFIT, RULESHAP. Comparative studies: no matched direct study
            # located; mechanism/threat-model inference. See documentation §6 for endpoints and
            # limits.
            # Primary locations: TREE: Advantages/disadvantages; complexity and practical
            # implementation notes
            'stability': 1,
            # Rating 2/5; original=2; v3.3.11=2. retained after comparative review.
            # Reason: Threshold discontinuities create sensitivity; this is a structural inference,
            # not a universal attack benchmark.
            # Comparison: Decision Trees (2/5) scores below RuleFit (3/5): the former threshold
            # boundaries are attack surfaces; the latter regularization is not an explanation-attack
            # defense.
            # Comparison: Decision Trees (2/5) scores below RuleSHAP (3/5): the former threshold
            # boundaries are attack surfaces; the latter SHAP weighting supplies no
            # attack-resistance guarantee.
            # Calibration: A below-neutral limitation. The integer is an ordinal coding decision;
            # neither the unit gap nor universal superiority/inferiority is measured.
            # Evidence: qualitative comparative inference; see study cards for direct endpoints and
            # counterevidence. Confidence: low.
            # Sources: TREE, RULEFIT, RULESHAP. Comparative studies: no matched direct study
            # located; mechanism/threat-model inference. See documentation §6 for endpoints and
            # limits.
            # Primary locations: TREE: Advantages/disadvantages; complexity and practical
            # implementation notes
            'adversarial_robustness': 2,
            # Rating 2/5; original=2; v3.3.11=2. retained after comparative review.
            # Reason: Different training samples can yield different tree structures; retain 2 for
            # that across-run interpretation, not for identical-seed replay.
            # Comparison: Decision Trees (2/5) scores below RuleFit (3/5): the former refitting can
            # replace the rule structure; the latter fitted rules can vary across data and seeds.
            # Comparison: Decision Trees (2/5) scores below RuleSHAP (3/5): the former refitting can
            # replace the rule structure; the latter sampling and surrogate fitting both affect
            # repeatability.
            # Calibration: A below-neutral limitation. The integer is an ordinal coding decision;
            # neither the unit gap nor universal superiority/inferiority is measured.
            # Evidence: qualitative comparative inference; see study cards for direct endpoints and
            # counterevidence. Confidence: low.
            # Sources: TREE, RULEFIT, RULESHAP. Comparative studies: no matched direct study
            # located; mechanism/threat-model inference. See documentation §6 for endpoints and
            # limits.
            # Primary locations: TREE: Advantages/disadvantages; complexity and practical
            # implementation notes
            'consistency': 2,
            # Rating 2/5; original=2; v3.3.11=2. retained after comparative review.
            # Reason: Depth, pruning and leaf-size changes can materially change explanations.
            # Comparison: Decision Trees (2/5) scores below RuleFit (3/5): the former depth and
            # pruning control the explanation structure; the latter tree settings and L1 selection
            # both matter.
            # Comparison: Decision Trees (2/5) scores below RuleSHAP (3/5): the former depth and
            # pruning control the explanation structure; the latter both attribution settings and
            # rule selection can change results.
            # Calibration: A below-neutral limitation. The integer is an ordinal coding decision;
            # neither the unit gap nor universal superiority/inferiority is measured.
            # Evidence: qualitative comparative inference; see study cards for direct endpoints and
            # counterevidence. Confidence: low.
            # Sources: TREE, RULEFIT, RULESHAP. Comparative studies: no matched direct study
            # located; mechanism/threat-model inference. See documentation §6 for endpoints and
            # limits.
            # Primary locations: TREE: Advantages/disadvantages; complexity and practical
            # implementation notes
            'hyperparameters_perturbation_robustness': 2,
            # Rating 3/5; original=3; v3.3.11=3. retained after comparative review.
            # Reason: A pruned tree can be compact, but path and tree size remain tunable.
            # Comparison: Decision Trees (3/5) ties RuleFit (3/5): the former pruning can shorten
            # paths, but a global tree can be large; the latter the final selected terms, not the
            # candidate forest, determine size.
            # Comparison: Decision Trees (3/5) ties RuleSHAP (3/5): the former pruning can shorten
            # paths, but a global tree can be large; the latter reported rule sets are smaller than
            # RuleFit but remain numerous.
            # Calibration: Neutral bin: the evidence does not warrant a general stronger or weaker
            # claim on this exact property. A tie is not demonstrated empirical equivalence.
            # Evidence: qualitative comparative inference; see study cards for direct endpoints and
            # counterevidence. Confidence: moderate.
            # Sources: TREE, RULEFIT, RULESHAP. Comparative studies: E04. See documentation §6 for
            # endpoints and limits.
            # Primary locations: TREE: Advantages/disadvantages; complexity and practical
            # implementation notes
            'sparsity': 3,
            # Rating 5/5; original=5; v3.3.11=5. retained after comparative review.
            # Reason: Explicit predicates and leaf outcomes provide the catalogue's highest
            # rule-level detail.
            # Comparison: Decision Trees (5/5) scores above RuleFit (4/5): the former full paths
            # expose explicit predicates and leaf outcomes; the latter rules and coefficients expose
            # explicit conditional structure.
            # Comparison: Decision Trees (5/5) scores above RuleSHAP (4/5): the former full paths
            # expose explicit predicates and leaf outcomes; the latter weighted predicates expose
            # more structure than an importance vector.
            # Calibration: An inherited endpoint under the stated output/configuration, not a
            # universal guarantee or universal failure. The exact endpoint is low-confidence outside
            # that setting.
            # Evidence: qualitative comparative inference; see study cards for direct endpoints and
            # counterevidence. Confidence: low.
            # Sources: TREE, RULEFIT, RULESHAP. Comparative studies: E04. See documentation §6 for
            # endpoints and limits.
            # Primary locations: TREE: Advantages/disadvantages; complexity and practical
            # implementation notes
            'level_of_detail': 5,
            # Rating 2/5; original=2; v3.3.11=2. retained after comparative review.
            # Reason: Publishing splits exposes proprietary logic; this threat-model assumption is
            # not a measured privacy loss.
            # Comparison: Decision Trees (2/5) ties RuleFit (2/5): the former published splits
            # expose reusable decision logic; the latter the rule set discloses reusable model
            # logic.
            # Comparison: Decision Trees (2/5) ties RuleSHAP (2/5): the former published splits
            # expose reusable decision logic; the latter the output discloses reusable rules and
            # behavioral patterns.
            # Calibration: A below-neutral limitation. The integer is an ordinal coding decision;
            # neither the unit gap nor universal superiority/inferiority is measured.
            # Evidence: qualitative comparative inference; see study cards for direct endpoints and
            # counterevidence. Confidence: low.
            # Sources: TREE, PRIVACY, RULEFIT, RULESHAP. Comparative studies: no matched direct
            # study located; mechanism/threat-model inference. See documentation §6 for endpoints
            # and limits.
            # Primary locations: TREE: Advantages/disadvantages; complexity and practical
            # implementation notes; PRIVACY: §§3–5; direct evidence for tested gradient/IG/LRP/LIME
            # configurations; threat-model context only for other methods
            'confidentiality': 2,
            # Rating 4/5; original=4; v3.3.11=4. retained after comparative review.
            # Reason: Stored tree, training data, seed and settings permit reconstruction; automatic
            # audit logging is not guaranteed.
            # Comparison: Decision Trees (4/5) ties RuleFit (4/5): the former the stored tree
            # directly records its predicates and outcomes; the latter saved rules and coefficients
            # make the fitted computation inspectable.
            # Comparison: Decision Trees (4/5) scores above RuleSHAP (3/5): the former the stored
            # tree directly records its predicates and outcomes; the latter both attribution
            # estimates and rule-fitting records are needed.
            # Calibration: A qualified comparative strength. The integer is an ordinal coding
            # decision; neither the unit gap nor universal superiority/inferiority is measured.
            # Evidence: qualitative comparative inference; see study cards for direct endpoints and
            # counterevidence. Confidence: moderate.
            # Sources: TREE, RULEFIT, RULESHAP. Comparative studies: no matched direct study
            # located; mechanism/threat-model inference. See documentation §6 for endpoints and
            # limits.
            # Primary locations: TREE: Advantages/disadvantages; complexity and practical
            # implementation notes
            'traceability': 4,
            # Rating 4/5; original=4; v3.3.11=4. retained after comparative review.
            # Reason: Ordinary tree fitting and inference are comparatively inexpensive;
            # surrogate-data collection cost still matters.
            # Comparison: Decision Trees (4/5) scores above RuleFit (3/5): the former one tree is
            # inexpensive to fit and traverse; the latter ensemble construction plus sparse fitting
            # exceeds one-tree cost.
            # Comparison: Decision Trees (4/5) scores above RuleSHAP (2/5): the former one tree is
            # inexpensive to fit and traverse; the latter attribution estimation adds work before
            # rule extraction.
            # Calibration: A qualified comparative strength. The integer is an ordinal coding
            # decision; neither the unit gap nor universal superiority/inferiority is measured.
            # Evidence: qualitative comparative inference; see study cards for direct endpoints and
            # counterevidence. Confidence: moderate.
            # Sources: TREE, RULEFIT, RULESHAP. Comparative studies: no matched direct study
            # located; mechanism/threat-model inference. See documentation §6 for endpoints and
            # limits.
            # Primary locations: TREE: Advantages/disadvantages; complexity and practical
            # implementation notes
            'runtime_performance_and_implementation_constraints': 4,
        },
        'scope_stage': 'global-exante',
        'explanation_target': 'model output',
        "question_types": {'how_computed', 'what_feature', 'what_if', 'what_rule'},
    },
    # L1-selected rule-plus-linear surrogate.
    'RuleFit': {
        "subprops": {
            # Rating 3/5; original=3; v3.3.11=3. retained after comparative review.
            # Reason: Surrogate training does not guarantee agreement with the target model.
            # Comparison: RuleFit (3/5) ties Decision Trees (3/5): the former surrogate rules need
            # independent agreement checks; the latter a fitted surrogate can invent influential
            # splits.
            # Comparison: RuleFit (3/5) ties RuleSHAP (3/5): the former surrogate rules need
            # independent agreement checks; the latter rule recovery is not a test of every
            # predicate’s necessity.
            # Calibration: Neutral bin: the evidence does not warrant a general stronger or weaker
            # claim on this exact property. A tie is not demonstrated empirical equivalence.
            # Evidence: qualitative comparative inference; see study cards for direct endpoints and
            # counterevidence. Confidence: moderate.
            # Sources: RULEFIT, TREE, RULESHAP. Comparative studies: E04. See documentation §6 for
            # endpoints and limits.
            # Primary locations: RULEFIT: Rule ensemble construction, regularized fitting and
            # interpretability
            'no_false_positives': 3,
            # Rating 3/5; original=3; v3.3.11=3. retained after comparative review.
            # Reason: Sparse selection can omit influential terms; retain neutral coverage of
            # contributors.
            # Comparison: RuleFit (3/5) ties Decision Trees (3/5): the former sparse selection can
            # omit target influences; the latter a compact surrogate may omit target effects.
            # Comparison: RuleFit (3/5) scores below RuleSHAP (4/5): the former sparse selection can
            # omit target influences; the latter injected-rule ranking improves over RuleFit in the
            # reported benchmark.
            # Calibration: Neutral bin: the evidence does not warrant a general stronger or weaker
            # claim on this exact property. A tie is not demonstrated empirical equivalence.
            # Evidence: qualitative comparative inference; see study cards for direct endpoints and
            # counterevidence. Confidence: low.
            # Sources: RULEFIT, TREE, RULESHAP. Comparative studies: E04. See documentation §6 for
            # endpoints and limits.
            # Primary locations: RULEFIT: Rule ensemble construction, regularized fitting and
            # interpretability
            'no_false_negatives': 3,
            # Rating 4/5; original=4; v3.3.11=4. retained after comparative review.
            # Reason: Rules and linear terms express interactions and linear trends; broader
            # representational coverage than a simple tree is plausible.
            # Comparison: RuleFit (4/5) scores above Decision Trees (3/5): the former rules plus
            # linear terms cover both interactions and trends; the latter one tree has limited
            # interaction and linear-trend capacity.
            # Comparison: RuleFit (4/5) ties RuleSHAP (4/5): the former rules plus linear terms
            # cover both interactions and trends; the latter a weighted rule ensemble can represent
            # compound conditions.
            # Calibration: A qualified comparative strength. The integer is an ordinal coding
            # decision; neither the unit gap nor universal superiority/inferiority is measured.
            # Evidence: qualitative comparative inference; see study cards for direct endpoints and
            # counterevidence. Confidence: moderate.
            # Sources: RULEFIT, TREE, RULESHAP. Comparative studies: E04. See documentation §6 for
            # endpoints and limits.
            # Primary locations: RULEFIT: Rule ensemble construction, regularized fitting and
            # interpretability
            'completeness': 4,
            # Rating 3/5; original=3; v3.3.11=3. retained after comparative review.
            # Reason: Regularization supports a neutral prior, not a theorem of stable selected
            # rules.
            # Comparison: RuleFit (3/5) scores above Decision Trees (1/5): the former regularization
            # may temper variation without fixing selected rules; the latter a local path can change
            # abruptly at a split.
            # Comparison: RuleFit (3/5) ties RuleSHAP (3/5): the former regularization may temper
            # variation without fixing selected rules; the latter the combined estimator still
            # depends on its data and settings.
            # Calibration: Neutral bin: the evidence does not warrant a general stronger or weaker
            # claim on this exact property. A tie is not demonstrated empirical equivalence.
            # Evidence: qualitative comparative inference; see study cards for direct endpoints and
            # counterevidence. Confidence: low.
            # Sources: RULEFIT, TREE, RULESHAP. Comparative studies: no matched direct study
            # located; mechanism/threat-model inference. See documentation §6 for endpoints and
            # limits.
            # Primary locations: RULEFIT: Rule ensemble construction, regularized fitting and
            # interpretability
            'stability': 3,
            # Rating 3/5; original=3; v3.3.11=3. retained after comparative review.
            # Reason: Predictive performance does not establish attack resistance; no general
            # advantage is established.
            # Comparison: RuleFit (3/5) scores above Decision Trees (2/5): the former regularization
            # is not an explanation-attack defense; the latter threshold boundaries are attack
            # surfaces.
            # Comparison: RuleFit (3/5) ties RuleSHAP (3/5): the former regularization is not an
            # explanation-attack defense; the latter SHAP weighting supplies no attack-resistance
            # guarantee.
            # Calibration: Neutral bin: the evidence does not warrant a general stronger or weaker
            # claim on this exact property. A tie is not demonstrated empirical equivalence.
            # Evidence: qualitative comparative inference; see study cards for direct endpoints and
            # counterevidence. Confidence: low.
            # Sources: RULEFIT, TREE, RULESHAP. Comparative studies: no matched direct study
            # located; mechanism/threat-model inference. See documentation §6 for endpoints and
            # limits.
            # Primary locations: RULEFIT: Rule ensemble construction, regularized fitting and
            # interpretability
            'adversarial_robustness': 3,
            # Rating 3/5; original=3; v3.3.11=3. retained after comparative review.
            # Reason: Different samples can select different rules; deterministic optimization alone
            # is insufficient.
            # Comparison: RuleFit (3/5) scores above Decision Trees (2/5): the former fitted rules
            # can vary across data and seeds; the latter refitting can replace the rule structure.
            # Comparison: RuleFit (3/5) ties RuleSHAP (3/5): the former fitted rules can vary across
            # data and seeds; the latter sampling and surrogate fitting both affect repeatability.
            # Calibration: Neutral bin: the evidence does not warrant a general stronger or weaker
            # claim on this exact property. A tie is not demonstrated empirical equivalence.
            # Evidence: qualitative comparative inference; see study cards for direct endpoints and
            # counterevidence. Confidence: low.
            # Sources: RULEFIT, TREE, RULESHAP. Comparative studies: no matched direct study
            # located; mechanism/threat-model inference. See documentation §6 for endpoints and
            # limits.
            # Primary locations: RULEFIT: Rule ensemble construction, regularized fitting and
            # interpretability
            'consistency': 3,
            # Rating 3/5; original=3; v3.3.11=3. retained after comparative review.
            # Reason: Regularization constrains the fit, but penalty and rule settings still matter.
            # The original neutral rating is defensible without assuming invariance.
            # Comparison: RuleFit (3/5) scores above Decision Trees (2/5): the former tree settings
            # and L1 selection both matter; the latter depth and pruning control the explanation
            # structure.
            # Comparison: RuleFit (3/5) ties RuleSHAP (3/5): the former tree settings and L1
            # selection both matter; the latter both attribution settings and rule selection can
            # change results.
            # Calibration: Neutral bin: the evidence does not warrant a general stronger or weaker
            # claim on this exact property. A tie is not demonstrated empirical equivalence.
            # Evidence: qualitative comparative inference; see study cards for direct endpoints and
            # counterevidence. Confidence: low.
            # Sources: RULEFIT, TREE, RULESHAP. Comparative studies: no matched direct study
            # located; mechanism/threat-model inference. See documentation §6 for endpoints and
            # limits.
            # Primary locations: RULEFIT: Rule ensemble construction, regularized fitting and
            # interpretability
            'hyperparameters_perturbation_robustness': 3,
            # Rating 3/5; original=2; v3.3.11=3. retained after comparative review.
            # Reason: The final L1-selected ensemble can be compact, although many terms may remain.
            # Correct candidate-pool counting; neutral 3 is the smallest justified adjustment.
            # Comparison: RuleFit (3/5) ties Decision Trees (3/5): the former the final selected
            # terms, not the candidate forest, determine size; the latter pruning can shorten paths,
            # but a global tree can be large.
            # Comparison: RuleFit (3/5) ties RuleSHAP (3/5): the former the final selected terms,
            # not the candidate forest, determine size; the latter reported rule sets are smaller
            # than RuleFit but remain numerous.
            # Calibration: Neutral bin: the evidence does not warrant a general stronger or weaker
            # claim on this exact property. A tie is not demonstrated empirical equivalence.
            # Evidence: qualitative comparative inference; see study cards for direct endpoints and
            # counterevidence. Confidence: moderate.
            # Sources: RULEFIT, TREE, RULESHAP. Comparative studies: E04. See documentation §6 for
            # endpoints and limits.
            # Primary locations: RULEFIT: Rule ensemble construction, regularized fitting and
            # interpretability
            'sparsity': 3,
            # Rating 4/5; original=4; v3.3.11=4. retained after comparative review.
            # Reason: Predicates and coefficients reveal detailed surrogate structure.
            # Comparison: RuleFit (4/5) scores below Decision Trees (5/5): the former rules and
            # coefficients expose explicit conditional structure; the latter full paths expose
            # explicit predicates and leaf outcomes.
            # Comparison: RuleFit (4/5) ties RuleSHAP (4/5): the former rules and coefficients
            # expose explicit conditional structure; the latter weighted predicates expose more
            # structure than an importance vector.
            # Calibration: A qualified comparative strength. The integer is an ordinal coding
            # decision; neither the unit gap nor universal superiority/inferiority is measured.
            # Evidence: qualitative comparative inference; see study cards for direct endpoints and
            # counterevidence. Confidence: moderate.
            # Sources: RULEFIT, TREE, RULESHAP. Comparative studies: E04. See documentation §6 for
            # endpoints and limits.
            # Primary locations: RULEFIT: Rule ensemble construction, regularized fitting and
            # interpretability
            'level_of_detail': 4,
            # Rating 2/5; original=2; v3.3.11=2. retained after comparative review.
            # Reason: Disclosed rules expose model logic; use the same threat-model assumption as
            # the surrogate tree.
            # Comparison: RuleFit (2/5) ties Decision Trees (2/5): the former the rule set discloses
            # reusable model logic; the latter published splits expose reusable decision logic.
            # Comparison: RuleFit (2/5) ties RuleSHAP (2/5): the former the rule set discloses
            # reusable model logic; the latter the output discloses reusable rules and behavioral
            # patterns.
            # Calibration: A below-neutral limitation. The integer is an ordinal coding decision;
            # neither the unit gap nor universal superiority/inferiority is measured.
            # Evidence: qualitative comparative inference; see study cards for direct endpoints and
            # counterevidence. Confidence: low.
            # Sources: RULEFIT, PRIVACY, TREE, RULESHAP. Comparative studies: no matched direct
            # study located; mechanism/threat-model inference. See documentation §6 for endpoints
            # and limits.
            # Primary locations: RULEFIT: Rule ensemble construction, regularized fitting and
            # interpretability; PRIVACY: §§3–5; direct evidence for tested gradient/IG/LRP/LIME
            # configurations; threat-model context only for other methods
            'confidentiality': 2,
            # Rating 4/5; original=4; v3.3.11=4. retained after comparative review.
            # Reason: The fitted rule list and pipeline can be archived and inspected.
            # Comparison: RuleFit (4/5) ties Decision Trees (4/5): the former saved rules and
            # coefficients make the fitted computation inspectable; the latter the stored tree
            # directly records its predicates and outcomes.
            # Comparison: RuleFit (4/5) scores above RuleSHAP (3/5): the former saved rules and
            # coefficients make the fitted computation inspectable; the latter both attribution
            # estimates and rule-fitting records are needed.
            # Calibration: A qualified comparative strength. The integer is an ordinal coding
            # decision; neither the unit gap nor universal superiority/inferiority is measured.
            # Evidence: qualitative comparative inference; see study cards for direct endpoints and
            # counterevidence. Confidence: moderate.
            # Sources: RULEFIT, TREE, RULESHAP. Comparative studies: no matched direct study
            # located; mechanism/threat-model inference. See documentation §6 for endpoints and
            # limits.
            # Primary locations: RULEFIT: Rule ensemble construction, regularized fitting and
            # interpretability
            'traceability': 4,
            # Rating 3/5; original=3; v3.3.11=3. retained after comparative review.
            # Reason: Rule generation plus sparse regression adds work relative to a single tree.
            # Comparison: RuleFit (3/5) scores below Decision Trees (4/5): the former ensemble
            # construction plus sparse fitting exceeds one-tree cost; the latter one tree is
            # inexpensive to fit and traverse.
            # Comparison: RuleFit (3/5) scores above RuleSHAP (2/5): the former ensemble
            # construction plus sparse fitting exceeds one-tree cost; the latter attribution
            # estimation adds work before rule extraction.
            # Calibration: Neutral bin: the evidence does not warrant a general stronger or weaker
            # claim on this exact property. A tie is not demonstrated empirical equivalence.
            # Evidence: qualitative comparative inference; see study cards for direct endpoints and
            # counterevidence. Confidence: moderate.
            # Sources: RULEFIT, TREE, RULESHAP. Comparative studies: no matched direct study
            # located; mechanism/threat-model inference. See documentation §6 for endpoints and
            # limits.
            # Primary locations: RULEFIT: Rule ensemble construction, regularized fitting and
            # interpretability
            'runtime_performance_and_implementation_constraints': 3,
        },
        'scope_stage': 'global-exante',
        'explanation_target': 'model output',
        "question_types": {'how_computed', 'what_feature', 'what_if', 'what_rule'},
    },
    # RuleSHAP v1, extrapolating cautiously from injected-bias experiments.
    'RuleSHAP': {
        "subprops": {
            # Rating 3/5; original=4; v3.3.11=4. corrected in this review.
            # Reason: Corrected 4 to 3: better injected-rule reciprocal ranks establish
            # recovery/ranking of known rules, not the absence of spurious predicates among all
            # returned rules. The evidence supports the separate recall advantage over RuleFit, but
            # does not justify a necessity advantage. Tie RuleFit at 3 on this property.
            # Comparison: RuleSHAP (3/5) ties Decision Trees (3/5): the former rule recovery is not
            # a test of every predicate’s necessity; the latter a fitted surrogate can invent
            # influential splits.
            # Comparison: RuleSHAP (3/5) ties RuleFit (3/5): the former rule recovery is not a test
            # of every predicate’s necessity; the latter surrogate rules need independent agreement
            # checks.
            # Calibration: Neutral bin: the evidence does not warrant a general stronger or weaker
            # claim on this exact property. A tie is not demonstrated empirical equivalence.
            # Evidence: qualitative comparative inference; see study cards for direct endpoints and
            # counterevidence. Confidence: low.
            # Sources: RULESHAP, RULEFIT, TREE. Comparative studies: E04. See documentation §6 for
            # endpoints and limits.
            # Primary locations: RULESHAP: RuleSHAP §§5–6, Table 2 and Appendix G; distinguish
            # reciprocal rank from predicate precision; RULEFIT: RuleSHAP §§5–6, Table 2 and
            # Appendix G; distinguish reciprocal rank from predicate precision
            'no_false_positives': 3,
            # Rating 4/5; original=4; v3.3.11=4. retained after comparative review.
            # Reason: Known-rule recovery ranks improve over RuleFit in the injected-bias
            # experiment, supporting a qualified comparative 4 versus 3. This proxy does not count
            # every influential factor; subgroup reversals and abstracted behavioral features limit
            # transport to new models.
            # Comparison: RuleSHAP (4/5) scores above RuleFit (3/5): the former injected-rule
            # ranking improves over RuleFit in the reported benchmark; the latter sparse selection
            # can omit target influences.
            # Comparison: RuleSHAP (4/5) scores above Decision Trees (3/5): the former injected-rule
            # ranking improves over RuleFit in the reported benchmark; the latter a compact
            # surrogate may omit target effects.
            # Calibration: A qualified comparative strength. The integer is an ordinal coding
            # decision; neither the unit gap nor universal superiority/inferiority is measured.
            # Evidence: qualitative comparative inference; see study cards for direct endpoints and
            # counterevidence. Confidence: low.
            # Sources: RULESHAP, RULEFIT, TREE. Comparative studies: E04. See documentation §6 for
            # endpoints and limits.
            # Primary locations: RULESHAP: §4 method; §6 injected-bias results and §7 limits
            'no_false_negatives': 4,
            # Rating 4/5; original=4; v3.3.11=4. retained after comparative review.
            # Reason: Retain expressive rule coverage; the original model can still exceed the
            # surrogate.
            # Comparison: RuleSHAP (4/5) scores above Decision Trees (3/5): the former a weighted
            # rule ensemble can represent compound conditions; the latter one tree has limited
            # interaction and linear-trend capacity.
            # Comparison: RuleSHAP (4/5) ties RuleFit (4/5): the former a weighted rule ensemble can
            # represent compound conditions; the latter rules plus linear terms cover both
            # interactions and trends.
            # Calibration: A qualified comparative strength. The integer is an ordinal coding
            # decision; neither the unit gap nor universal superiority/inferiority is measured.
            # Evidence: qualitative comparative inference; see study cards for direct endpoints and
            # counterevidence. Confidence: moderate.
            # Sources: RULESHAP, TREE, RULEFIT. Comparative studies: E04. See documentation §6 for
            # endpoints and limits.
            # Primary locations: RULESHAP: §4 method; §6 injected-bias results and §7 limits
            'completeness': 4,
            # Rating 3/5; original=3; v3.3.11=3. retained after comparative review.
            # Reason: No general stability study establishes superiority; retain neutral rather than
            # infer it from regularization.
            # Comparison: RuleSHAP (3/5) scores above Decision Trees (1/5): the former the combined
            # estimator still depends on its data and settings; the latter a local path can change
            # abruptly at a split.
            # Comparison: RuleSHAP (3/5) ties RuleFit (3/5): the former the combined estimator still
            # depends on its data and settings; the latter regularization may temper variation
            # without fixing selected rules.
            # Calibration: Neutral bin: the evidence does not warrant a general stronger or weaker
            # claim on this exact property. A tie is not demonstrated empirical equivalence.
            # Evidence: qualitative comparative inference; see study cards for direct endpoints and
            # counterevidence. Confidence: low.
            # Sources: RULESHAP, TREE, RULEFIT. Comparative studies: no matched direct study
            # located; mechanism/threat-model inference. See documentation §6 for endpoints and
            # limits.
            # Primary locations: RULESHAP: §4 method; §6 injected-bias results and §7 limits
            'stability': 3,
            # Rating 3/5; original=3; v3.3.11=3. retained after comparative review.
            # Reason: SHAP-guided extraction supplies no general adversarial guarantee; neutral
            # evidence-limited rating.
            # Comparison: RuleSHAP (3/5) scores above Decision Trees (2/5): the former SHAP
            # weighting supplies no attack-resistance guarantee; the latter threshold boundaries are
            # attack surfaces.
            # Comparison: RuleSHAP (3/5) ties RuleFit (3/5): the former SHAP weighting supplies no
            # attack-resistance guarantee; the latter regularization is not an explanation-attack
            # defense.
            # Calibration: Neutral bin: the evidence does not warrant a general stronger or weaker
            # claim on this exact property. A tie is not demonstrated empirical equivalence.
            # Evidence: qualitative comparative inference; see study cards for direct endpoints and
            # counterevidence. Confidence: low.
            # Sources: RULESHAP, TREE, RULEFIT. Comparative studies: no matched direct study
            # located; mechanism/threat-model inference. See documentation §6 for endpoints and
            # limits.
            # Primary locations: RULESHAP: §4 method; §6 injected-bias results and §7 limits
            'adversarial_robustness': 3,
            # Rating 3/5; original=4; v3.3.11=3. retained after comparative review.
            # Reason: LASSO and SHAP do not prove the retained rubric consistency across samples or
            # time.
            # Comparison: RuleSHAP (3/5) scores above Decision Trees (2/5): the former sampling and
            # surrogate fitting both affect repeatability; the latter refitting can replace the rule
            # structure.
            # Comparison: RuleSHAP (3/5) ties RuleFit (3/5): the former sampling and surrogate
            # fitting both affect repeatability; the latter fitted rules can vary across data and
            # seeds.
            # Calibration: Neutral bin: the evidence does not warrant a general stronger or weaker
            # claim on this exact property. A tie is not demonstrated empirical equivalence.
            # Evidence: qualitative comparative inference; see study cards for direct endpoints and
            # counterevidence. Confidence: low.
            # Sources: RULESHAP, TREE, RULEFIT. Comparative studies: no matched direct study
            # located; mechanism/threat-model inference. See documentation §6 for endpoints and
            # limits.
            # Primary locations: RULESHAP: §4 method; §6 injected-bias results and §7 limits
            'consistency': 3,
            # Rating 3/5; original=3; v3.3.11=3. retained after comparative review.
            # Reason: Rule and attribution settings matter; neutral 3 is retained because the
            # evidence does not establish a generally below-neutral comparative ranking.
            # Comparison: RuleSHAP (3/5) scores above Decision Trees (2/5): the former both
            # attribution settings and rule selection can change results; the latter depth and
            # pruning control the explanation structure.
            # Comparison: RuleSHAP (3/5) ties RuleFit (3/5): the former both attribution settings
            # and rule selection can change results; the latter tree settings and L1 selection both
            # matter.
            # Calibration: Neutral bin: the evidence does not warrant a general stronger or weaker
            # claim on this exact property. A tie is not demonstrated empirical equivalence.
            # Evidence: qualitative comparative inference; see study cards for direct endpoints and
            # counterevidence. Confidence: low.
            # Sources: RULESHAP, TREE, RULEFIT. Comparative studies: no matched direct study
            # located; mechanism/threat-model inference. See documentation §6 for endpoints and
            # limits.
            # Primary locations: RULESHAP: §4 method; §6 injected-bias results and §7 limits
            'hyperparameters_perturbation_robustness': 3,
            # Rating 3/5; original=3; v3.3.11=3. retained after comparative review.
            # Reason: Selected rules improve compactness, but no universal minimal-rule guarantee
            # follows.
            # Comparison: RuleSHAP (3/5) ties RuleFit (3/5): the former reported rule sets are
            # smaller than RuleFit but remain numerous; the latter the final selected terms, not the
            # candidate forest, determine size.
            # Comparison: RuleSHAP (3/5) scores below Anchors (4/5): the former reported rule sets
            # are smaller than RuleFit but remain numerous; the latter short sufficient conjunctions
            # are the explicit search target.
            # Calibration: Neutral bin: the evidence does not warrant a general stronger or weaker
            # claim on this exact property. A tie is not demonstrated empirical equivalence.
            # Evidence: qualitative comparative inference; see study cards for direct endpoints and
            # counterevidence. Confidence: moderate.
            # Sources: RULESHAP, RULEFIT, ANCHORS. Comparative studies: E04. See documentation §6
            # for endpoints and limits.
            # Primary locations: RULESHAP: §4 method; §6 injected-bias results and §7 limits
            'sparsity': 3,
            # Rating 4/5; original=4; v3.3.11=4. retained after comparative review.
            # Reason: Explicit learned predicates retain rule-level detail.
            # Comparison: RuleSHAP (4/5) scores below Decision Trees (5/5): the former weighted
            # predicates expose more structure than an importance vector; the latter full paths
            # expose explicit predicates and leaf outcomes.
            # Comparison: RuleSHAP (4/5) ties RuleFit (4/5): the former weighted predicates expose
            # more structure than an importance vector; the latter rules and coefficients expose
            # explicit conditional structure.
            # Calibration: A qualified comparative strength. The integer is an ordinal coding
            # decision; neither the unit gap nor universal superiority/inferiority is measured.
            # Evidence: qualitative comparative inference; see study cards for direct endpoints and
            # counterevidence. Confidence: moderate.
            # Sources: RULESHAP, TREE, RULEFIT. Comparative studies: E04. See documentation §6 for
            # endpoints and limits.
            # Primary locations: RULESHAP: §4 method; §6 injected-bias results and §7 limits
            'level_of_detail': 4,
            # Rating 2/5; original=2; v3.3.11=2. retained after comparative review.
            # Reason: Rule disclosure exposes logic; confidentiality depends on access and
            # disclosure controls.
            # Comparison: RuleSHAP (2/5) ties Decision Trees (2/5): the former the output discloses
            # reusable rules and behavioral patterns; the latter published splits expose reusable
            # decision logic.
            # Comparison: RuleSHAP (2/5) ties RuleFit (2/5): the former the output discloses
            # reusable rules and behavioral patterns; the latter the rule set discloses reusable
            # model logic.
            # Calibration: A below-neutral limitation. The integer is an ordinal coding decision;
            # neither the unit gap nor universal superiority/inferiority is measured.
            # Evidence: qualitative comparative inference; see study cards for direct endpoints and
            # counterevidence. Confidence: low.
            # Sources: RULESHAP, PRIVACY, TREE, RULEFIT. Comparative studies: no matched direct
            # study located; mechanism/threat-model inference. See documentation §6 for endpoints
            # and limits.
            # Primary locations: RULESHAP: §4 method; §6 injected-bias results and §7 limits;
            # PRIVACY: §§3–5; direct evidence for tested gradient/IG/LRP/LIME configurations;
            # threat-model context only for other methods
            'confidentiality': 2,
            # Rating 3/5; original=3; v3.3.11=3. retained after comparative review.
            # Reason: Retain neutral 3 for the multi-stage attribution/rule pipeline; logging
            # permits audit, but does not by itself establish superior traceability.
            # Comparison: RuleSHAP (3/5) scores below Decision Trees (4/5): the former both
            # attribution estimates and rule-fitting records are needed; the latter the stored tree
            # directly records its predicates and outcomes.
            # Comparison: RuleSHAP (3/5) scores below RuleFit (4/5): the former both attribution
            # estimates and rule-fitting records are needed; the latter saved rules and coefficients
            # make the fitted computation inspectable.
            # Calibration: Neutral bin: the evidence does not warrant a general stronger or weaker
            # claim on this exact property. A tie is not demonstrated empirical equivalence.
            # Evidence: qualitative comparative inference; see study cards for direct endpoints and
            # counterevidence. Confidence: moderate.
            # Sources: RULESHAP, TREE, RULEFIT. Comparative studies: no matched direct study
            # located; mechanism/threat-model inference. See documentation §6 for endpoints and
            # limits.
            # Primary locations: RULESHAP: §4 method; §6 injected-bias results and §7 limits
            'traceability': 3,
            # Rating 2/5; original=2; v3.3.11=2. retained after comparative review.
            # Reason: SHAP computation adds cost to the rule-fitting pipeline.
            # Comparison: RuleSHAP (2/5) scores below Decision Trees (4/5): the former attribution
            # estimation adds work before rule extraction; the latter one tree is inexpensive to fit
            # and traverse.
            # Comparison: RuleSHAP (2/5) scores below RuleFit (3/5): the former attribution
            # estimation adds work before rule extraction; the latter ensemble construction plus
            # sparse fitting exceeds one-tree cost.
            # Calibration: A below-neutral limitation. The integer is an ordinal coding decision;
            # neither the unit gap nor universal superiority/inferiority is measured.
            # Evidence: qualitative comparative inference; see study cards for direct endpoints and
            # counterevidence. Confidence: moderate.
            # Sources: RULESHAP, TREE, RULEFIT. Comparative studies: no matched direct study
            # located; mechanism/threat-model inference. See documentation §6 for endpoints and
            # limits.
            # Primary locations: RULESHAP: §4 method; §6 injected-bias results and §7 limits
            'runtime_performance_and_implementation_constraints': 2,
        },
        'scope_stage': 'global-exante',
        'explanation_target': 'model output',
        "question_types": {'how_computed', 'what_feature', 'what_if', 'what_rule'},
    },
    # Ordinary one- or two-way population PDP on fixed, feasible grids; not full model logic.
    'PDP': {
        "subprops": {
            # Rating 3/5; original=3; v3.3.11=3. retained after comparative review.
            # Reason: Model evaluations reflect marginal responses, but correlated-feature
            # extrapolation can mislead interpretation.
            # Comparison: PDP (3/5) ties ICE (3/5): the former marginal responses can involve
            # infeasible feature combinations; the latter direct queries still risk infeasible
            # feature combinations.
            # Comparison: PDP (3/5) ties Global SHAP summaries (3/5): the former marginal responses
            # can involve infeasible feature combinations; the latter aggregation does not repair
            # local relevance errors.
            # Calibration: Neutral bin: the evidence does not warrant a general stronger or weaker
            # claim on this exact property. A tie is not demonstrated empirical equivalence.
            # Evidence: qualitative comparative inference; see study cards for direct endpoints and
            # counterevidence. Confidence: moderate.
            # Sources: ICE, GLOBAL. Comparative studies: no matched direct study located;
            # mechanism/threat-model inference. See documentation §6 for endpoints and limits.
            # Primary locations: ICE: ICE definition and examples of heterogeneous effects hidden by
            # PDPs
            'no_false_positives': 3,
            # Rating 3/5; original=3; v3.3.11=3. retained after comparative review.
            # Reason: Averaging can hide heterogeneous effects. Retain neutral 3 relative to the
            # more informative individual curves, rather than impose an uncalibrated extra penalty.
            # Comparison: PDP (3/5) scores below ICE (4/5): the former averages can conceal
            # heterogeneous effects; the latter individual curves expose heterogeneity hidden by a
            # mean.
            # Comparison: PDP (3/5) ties Global SHAP summaries (3/5): the former averages can
            # conceal heterogeneous effects; the latter population averages can conceal rare
            # influential patterns.
            # Calibration: Neutral bin: the evidence does not warrant a general stronger or weaker
            # claim on this exact property. A tie is not demonstrated empirical equivalence.
            # Evidence: qualitative comparative inference; see study cards for direct endpoints and
            # counterevidence. Confidence: moderate.
            # Sources: ICE, GLOBAL. Comparative studies: E05. See documentation §6 for endpoints and
            # limits.
            # Primary locations: ICE: ICE definition and examples of heterogeneous effects hidden by
            # PDPs
            'no_false_negatives': 3,
            # Rating 3/5; original=3; v3.3.11=3. retained after comparative review.
            # Reason: A collection of low-dimensional response curves covers partial effects, not
            # the full model rationale. Retain neutral 3, now tied with ICE under matched features;
            # averaging does not create explanatory coverage absent from individual curves.
            # Comparison: PDP (3/5) ties ICE (3/5): the former low-dimensional mean curves omit
            # other interactions; the latter individual curves retain the information used to form
            # matched PDPs.
            # Comparison: PDP (3/5) scores above Global SHAP summaries (2/5): the former
            # low-dimensional mean curves omit other interactions; the latter summary statistics
            # discard instance configurations and interactions.
            # Calibration: Neutral bin: the evidence does not warrant a general stronger or weaker
            # claim on this exact property. A tie is not demonstrated empirical equivalence.
            # Evidence: qualitative comparative inference; see study cards for direct endpoints and
            # counterevidence. Confidence: low.
            # Sources: ICE, GLOBAL. Comparative studies: E05. See documentation §6 for endpoints and
            # limits.
            # Primary locations: ICE: ICE definition and examples of heterogeneous effects hidden by
            # PDPs
            'completeness': 3,
            # Rating 4/5; original=4; v3.3.11=4. retained after comparative review.
            # Reason: Population averaging can reduce individual variation relative to ICE. Retain
            # comparative 4 under a fixed population; neither smoothness nor universal continuity is
            # guaranteed.
            # Comparison: PDP (4/5) scores above ICE (3/5): the former population averaging may damp
            # individual variation; the latter curves retain the underlying model’s input
            # sensitivity.
            # Comparison: PDP (4/5) scores above Global SHAP summaries (3/5): the former population
            # averaging may damp individual variation; the latter aggregation may damp noise but
            # depends on cohort composition.
            # Calibration: A qualified comparative strength. The integer is an ordinal coding
            # decision; neither the unit gap nor universal superiority/inferiority is measured.
            # Evidence: qualitative comparative inference; see study cards for direct endpoints and
            # counterevidence. Confidence: low.
            # Sources: ICE, GLOBAL. Comparative studies: E05. See documentation §6 for endpoints and
            # limits.
            # Primary locations: ICE: ICE definition and examples of heterogeneous effects hidden by
            # PDPs
            'stability': 4,
            # Rating 3/5; original=3; v3.3.11=3. retained after comparative review.
            # Reason: No general attack-resistance guarantee follows from aggregation; retain
            # neutral with low confidence.
            # Comparison: PDP (3/5) ties ICE (3/5): the former averaging is not a privacy or
            # adversarial defense; the latter direct querying is not an adversarial defense.
            # Comparison: PDP (3/5) ties Global SHAP summaries (3/5): the former averaging is not a
            # privacy or adversarial defense; the latter aggregation of manipulable local values is
            # not a defense.
            # Calibration: Neutral bin: the evidence does not warrant a general stronger or weaker
            # claim on this exact property. A tie is not demonstrated empirical equivalence.
            # Evidence: qualitative comparative inference; see study cards for direct endpoints and
            # counterevidence. Confidence: low.
            # Sources: ICE, GLOBAL. Comparative studies: no matched direct study located;
            # mechanism/threat-model inference. See documentation §6 for endpoints and limits.
            # Primary locations: ICE: ICE definition and examples of heterogeneous effects hidden by
            # PDPs
            'adversarial_robustness': 3,
            # Rating 4/5; original=4; v3.3.11=4. retained after comparative review.
            # Reason: The fixed model is evaluated directly over a declared grid/reference cohort,
            # with no fitted stochastic surrogate. This supports comparative repeatability across
            # runs under a fixed setup; it does not establish invariance to changing models, cohorts
            # or time.
            # Comparison: PDP (4/5) ties ICE (4/5): the former a fixed model, cohort and grid give
            # repeatable means; the latter fixed inputs and grids are repeatable without explainer
            # sampling.
            # Comparison: PDP (4/5) scores above Global SHAP summaries (3/5): the former a fixed
            # model, cohort and grid give repeatable means; the latter repeatability depends on the
            # local estimator and reference cohort.
            # Calibration: A qualified comparative strength. The integer is an ordinal coding
            # decision; neither the unit gap nor universal superiority/inferiority is measured.
            # Evidence: qualitative comparative inference; see study cards for direct endpoints and
            # counterevidence. Confidence: low.
            # Sources: ICE, GLOBAL. Comparative studies: no matched direct study located;
            # mechanism/threat-model inference. See documentation §6 for endpoints and limits.
            # Primary locations: ICE: ICE definition and examples of heterogeneous effects hidden by
            # PDPs
            'consistency': 4,
            # Rating 4/5; original=4; v3.3.11=4. retained after comparative review.
            # Reason: Few explainer tuning choices support the original comparative strength for
            # ordinary grids; changed reference populations are a separate sensitivity.
            # Comparison: PDP (4/5) ties ICE (4/5): the former few explainer settings remain once
            # cohort and grid are fixed; the latter grid choice remains, without local surrogate
            # tuning.
            # Comparison: PDP (4/5) scores above Global SHAP summaries (2/5): the former few
            # explainer settings remain once cohort and grid are fixed; the latter background, local
            # estimator and aggregation rule all matter.
            # Calibration: A qualified comparative strength. The integer is an ordinal coding
            # decision; neither the unit gap nor universal superiority/inferiority is measured.
            # Evidence: qualitative comparative inference; see study cards for direct endpoints and
            # counterevidence. Confidence: low.
            # Sources: ICE, GLOBAL. Comparative studies: no matched direct study located;
            # mechanism/threat-model inference. See documentation §6 for endpoints and limits.
            # Primary locations: ICE: ICE definition and examples of heterogeneous effects hidden by
            # PDPs
            'hyperparameters_perturbation_robustness': 4,
            # Rating 2/5; original=2; v3.3.11=2. retained after comparative review.
            # Reason: Showing response functions across many features can create a dense output
            # collection; retain the original catalogue-level presentation assumption.
            # Comparison: PDP (2/5) ties ICE (2/5): the former a full collection of curves is not
            # feature selection; the latter many individual curves can produce a large explanation.
            # Comparison: PDP (2/5) ties Global SHAP summaries (2/5): the former a full collection
            # of curves is not feature selection; the latter a population-wide feature display is
            # not a minimal local explanation.
            # Calibration: A below-neutral limitation. The integer is an ordinal coding decision;
            # neither the unit gap nor universal superiority/inferiority is measured.
            # Evidence: qualitative comparative inference; see study cards for direct endpoints and
            # counterevidence. Confidence: low.
            # Sources: ICE, GLOBAL. Comparative studies: no matched direct study located;
            # mechanism/threat-model inference. See documentation §6 for endpoints and limits.
            # Primary locations: ICE: ICE definition and examples of heterogeneous effects hidden by
            # PDPs
            'sparsity': 2,
            # Rating 4/5; original=4; v3.3.11=4. retained after comparative review.
            # Reason: One- and two-way response surfaces expose response shape and selected
            # interactions; the rating does not describe full decision rules.
            # Comparison: PDP (4/5) ties ICE (4/5): the former response curves expose direction,
            # shape and thresholds; the latter curves expose feature-response shape for individual
            # contexts.
            # Comparison: PDP (4/5) scores above Global SHAP summaries (3/5): the former response
            # curves expose direction, shape and thresholds; the latter summary statistics are
            # coarser than explicit decision rules.
            # Calibration: A qualified comparative strength. The integer is an ordinal coding
            # decision; neither the unit gap nor universal superiority/inferiority is measured.
            # Evidence: qualitative comparative inference; see study cards for direct endpoints and
            # counterevidence. Confidence: moderate.
            # Sources: ICE, GLOBAL. Comparative studies: E05. See documentation §6 for endpoints and
            # limits.
            # Primary locations: ICE: ICE definition and examples of heterogeneous effects hidden by
            # PDPs
            'level_of_detail': 4,
            # Rating 3/5; original=3; v3.3.11=3. retained after comparative review.
            # Reason: Aggregate outputs are not inherently private; neutral is not a privacy
            # assurance.
            # Comparison: PDP (3/5) scores above ICE (2/5): the former aggregate responses conceal
            # individual records but reveal behavior; the latter individual response profiles expose
            # more record-specific information.
            # Comparison: PDP (3/5) ties Global SHAP summaries (3/5): the former aggregate responses
            # conceal individual records but reveal behavior; the latter aggregation still exposes
            # population behavior without a privacy proof.
            # Calibration: Neutral bin: the evidence does not warrant a general stronger or weaker
            # claim on this exact property. A tie is not demonstrated empirical equivalence.
            # Evidence: qualitative comparative inference; see study cards for direct endpoints and
            # counterevidence. Confidence: low.
            # Sources: ICE, PRIVACY, GLOBAL. Comparative studies: no matched direct study located;
            # mechanism/threat-model inference. See documentation §6 for endpoints and limits.
            # Primary locations: ICE: ICE definition and examples of heterogeneous effects hidden by
            # PDPs; PRIVACY: §§3–5; direct evidence for tested gradient/IG/LRP/LIME configurations;
            # threat-model context only for other methods
            'confidentiality': 3,
            # Rating 4/5; original=4; v3.3.11=4. retained after comparative review.
            # Reason: Logged grid, model and reference dataset permit straightforward recomputation.
            # Comparison: PDP (4/5) ties ICE (4/5): the former query grids and averages can be
            # directly reproduced; the latter saved queries reconstruct every curve.
            # Comparison: PDP (4/5) ties Global SHAP summaries (4/5): the former query grids and
            # averages can be directly reproduced; the latter the cohort, local values and
            # aggregation function can be saved.
            # Calibration: A qualified comparative strength. The integer is an ordinal coding
            # decision; neither the unit gap nor universal superiority/inferiority is measured.
            # Evidence: qualitative comparative inference; see study cards for direct endpoints and
            # counterevidence. Confidence: moderate.
            # Sources: ICE, GLOBAL. Comparative studies: no matched direct study located;
            # mechanism/threat-model inference. See documentation §6 for endpoints and limits.
            # Primary locations: ICE: ICE definition and examples of heterogeneous effects hidden by
            # PDPs
            'traceability': 4,
            # Rating 4/5; original=4; v3.3.11=4. retained after comparative review.
            # Reason: Retain 4 for standard low-dimensional grids and feasible reference sets,
            # relative to repeated optimization methods; cost is workload-dependent.
            # Comparison: PDP (4/5) ties ICE (4/5): the former fixed small grids require batches of
            # prediction calls; the latter cost follows instances times grid points, without
            # optimization.
            # Comparison: PDP (4/5) scores above Global SHAP summaries (1/5): the former fixed small
            # grids require batches of prediction calls; the latter many local explanation costs
            # accumulate across the cohort.
            # Calibration: A qualified comparative strength. The integer is an ordinal coding
            # decision; neither the unit gap nor universal superiority/inferiority is measured.
            # Evidence: qualitative comparative inference; see study cards for direct endpoints and
            # counterevidence. Confidence: low.
            # Sources: ICE, GLOBAL. Comparative studies: no matched direct study located;
            # mechanism/threat-model inference. See documentation §6 for endpoints and limits.
            # Primary locations: ICE: ICE definition and examples of heterogeneous effects hidden by
            # PDPs
            'runtime_performance_and_implementation_constraints': 4,
        },
        'scope_stage': 'global-exante',
        'explanation_target': 'model output',
        "question_types": {'how_computed', 'what_if', 'what_rule'},
    },
    # Individual conditional expectation curves on a fixed evaluation grid.
    'ICE': {
        "subprops": {
            # Rating 3/5; original=3; v3.3.11=3. retained after comparative review.
            # Reason: Direct model queries give feature-response information; impossible feature
            # combinations remain a limitation.
            # Comparison: ICE (3/5) ties PDP (3/5): the former direct queries still risk infeasible
            # feature combinations; the latter marginal responses can involve infeasible feature
            # combinations.
            # Comparison: ICE (3/5) ties Global SHAP summaries (3/5): the former direct queries
            # still risk infeasible feature combinations; the latter aggregation does not repair
            # local relevance errors.
            # Calibration: Neutral bin: the evidence does not warrant a general stronger or weaker
            # claim on this exact property. A tie is not demonstrated empirical equivalence.
            # Evidence: qualitative comparative inference; see study cards for direct endpoints and
            # counterevidence. Confidence: moderate.
            # Sources: ICE, GLOBAL. Comparative studies: no matched direct study located;
            # mechanism/threat-model inference. See documentation §6 for endpoints and limits.
            # Primary locations: ICE: ICE definition and examples of heterogeneous effects hidden by
            # PDPs
            'no_false_positives': 3,
            # Rating 4/5; original=4; v3.3.11=4. retained after comparative review.
            # Reason: Individual curves reveal heterogeneity hidden by PDP averages; retain the
            # relative 4 versus 3 without claiming complete contributor recall.
            # Comparison: ICE (4/5) scores above PDP (3/5): the former individual curves expose
            # heterogeneity hidden by a mean; the latter averages can conceal heterogeneous effects.
            # Comparison: ICE (4/5) scores above Global SHAP summaries (3/5): the former individual
            # curves expose heterogeneity hidden by a mean; the latter population averages can
            # conceal rare influential patterns.
            # Calibration: A qualified comparative strength. The integer is an ordinal coding
            # decision; neither the unit gap nor universal superiority/inferiority is measured.
            # Evidence: qualitative comparative inference; see study cards for direct endpoints and
            # counterevidence. Confidence: moderate.
            # Sources: ICE, GLOBAL. Comparative studies: E05. See documentation §6 for endpoints and
            # limits.
            # Primary locations: ICE: ICE definition and examples of heterogeneous effects hidden by
            # PDPs
            'no_false_negatives': 4,
            # Rating 3/5; original=2; v3.3.11=2. corrected in this review.
            # Reason: Corrected 2 to 3: the original comment penalized human perceptual limits,
            # outside this model-centred criterion. For matched features and population, ICE retains
            # individual response curves whose average gives PDP. Tie PDP at 3 for partial response
            # coverage; neither supplies the full model rationale. Keep ICE’s separate advantage for
            # revealing heterogeneous effects.
            # Comparison: ICE (3/5) ties PDP (3/5): the former individual curves retain the
            # information used to form matched PDPs; the latter low-dimensional mean curves omit
            # other interactions.
            # Comparison: ICE (3/5) scores above Global SHAP summaries (2/5): the former individual
            # curves retain the information used to form matched PDPs; the latter summary statistics
            # discard instance configurations and interactions.
            # Calibration: Neutral bin: the evidence does not warrant a general stronger or weaker
            # claim on this exact property. A tie is not demonstrated empirical equivalence.
            # Evidence: qualitative comparative inference; see study cards for direct endpoints and
            # counterevidence. Confidence: low.
            # Sources: ICE, GLOBAL. Comparative studies: E05. See documentation §6 for endpoints and
            # limits.
            # Primary locations: ICE: §§2.2–4, PDP as an average of ICE curves; interaction examples
            'completeness': 3,
            # Rating 3/5; original=3; v3.3.11=3. retained after comparative review.
            # Reason: Curve changes follow the model; stochastic noise is not inherent in fixed-grid
            # ICE.
            # Comparison: ICE (3/5) scores below PDP (4/5): the former curves retain the underlying
            # model’s input sensitivity; the latter population averaging may damp individual
            # variation.
            # Comparison: ICE (3/5) ties Global SHAP summaries (3/5): the former curves retain the
            # underlying model’s input sensitivity; the latter aggregation may damp noise but
            # depends on cohort composition.
            # Calibration: Neutral bin: the evidence does not warrant a general stronger or weaker
            # claim on this exact property. A tie is not demonstrated empirical equivalence.
            # Evidence: qualitative comparative inference; see study cards for direct endpoints and
            # counterevidence. Confidence: low.
            # Sources: ICE, GLOBAL. Comparative studies: E05. See documentation §6 for endpoints and
            # limits.
            # Primary locations: ICE: ICE definition and examples of heterogeneous effects hidden by
            # PDPs
            'stability': 3,
            # Rating 3/5; original=3; v3.3.11=3. retained after comparative review.
            # Reason: Direct evaluation alone supplies no general protection against malicious
            # perturbations.
            # Comparison: ICE (3/5) ties PDP (3/5): the former direct querying is not an adversarial
            # defense; the latter averaging is not a privacy or adversarial defense.
            # Comparison: ICE (3/5) ties Global SHAP summaries (3/5): the former direct querying is
            # not an adversarial defense; the latter aggregation of manipulable local values is not
            # a defense.
            # Calibration: Neutral bin: the evidence does not warrant a general stronger or weaker
            # claim on this exact property. A tie is not demonstrated empirical equivalence.
            # Evidence: qualitative comparative inference; see study cards for direct endpoints and
            # counterevidence. Confidence: low.
            # Sources: ICE, GLOBAL. Comparative studies: no matched direct study located;
            # mechanism/threat-model inference. See documentation §6 for endpoints and limits.
            # Primary locations: ICE: ICE definition and examples of heterogeneous effects hidden by
            # PDPs
            'adversarial_robustness': 3,
            # Rating 4/5; original=3; v3.3.11=4. retained after comparative review.
            # Reason: The fixed model is evaluated directly over a declared grid/reference cohort,
            # with no fitted stochastic surrogate. This supports comparative repeatability across
            # runs under a fixed setup; it does not establish invariance to changing models, cohorts
            # or time.
            # Comparison: ICE (4/5) ties PDP (4/5): the former fixed inputs and grids are repeatable
            # without explainer sampling; the latter a fixed model, cohort and grid give repeatable
            # means.
            # Comparison: ICE (4/5) scores above Global SHAP summaries (3/5): the former fixed
            # inputs and grids are repeatable without explainer sampling; the latter repeatability
            # depends on the local estimator and reference cohort.
            # Calibration: A qualified comparative strength. The integer is an ordinal coding
            # decision; neither the unit gap nor universal superiority/inferiority is measured.
            # Evidence: qualitative comparative inference; see study cards for direct endpoints and
            # counterevidence. Confidence: low.
            # Sources: ICE, GLOBAL. Comparative studies: no matched direct study located;
            # mechanism/threat-model inference. See documentation §6 for endpoints and limits.
            # Primary locations: ICE: ICE definition and examples of heterogeneous effects hidden by
            # PDPs
            'consistency': 4,
            # Rating 4/5; original=4; v3.3.11=4. retained after comparative review.
            # Reason: Like PDP, few tuning choices support the original relative 4 for standard
            # fixed-grid use; reference selection still matters.
            # Comparison: ICE (4/5) ties PDP (4/5): the former grid choice remains, without local
            # surrogate tuning; the latter few explainer settings remain once cohort and grid are
            # fixed.
            # Comparison: ICE (4/5) scores above Global SHAP summaries (2/5): the former grid choice
            # remains, without local surrogate tuning; the latter background, local estimator and
            # aggregation rule all matter.
            # Calibration: A qualified comparative strength. The integer is an ordinal coding
            # decision; neither the unit gap nor universal superiority/inferiority is measured.
            # Evidence: qualitative comparative inference; see study cards for direct endpoints and
            # counterevidence. Confidence: low.
            # Sources: ICE, GLOBAL. Comparative studies: no matched direct study located;
            # mechanism/threat-model inference. See documentation §6 for endpoints and limits.
            # Primary locations: ICE: ICE definition and examples of heterogeneous effects hidden by
            # PDPs
            'hyperparameters_perturbation_robustness': 4,
            # Rating 2/5; original=2; v3.3.11=2. retained after comparative review.
            # Reason: Many overlaid individual curves are dense.
            # Comparison: ICE (2/5) ties PDP (2/5): the former many individual curves can produce a
            # large explanation; the latter a full collection of curves is not feature selection.
            # Comparison: ICE (2/5) ties Global SHAP summaries (2/5): the former many individual
            # curves can produce a large explanation; the latter a population-wide feature display
            # is not a minimal local explanation.
            # Calibration: A below-neutral limitation. The integer is an ordinal coding decision;
            # neither the unit gap nor universal superiority/inferiority is measured.
            # Evidence: qualitative comparative inference; see study cards for direct endpoints and
            # counterevidence. Confidence: moderate.
            # Sources: ICE, GLOBAL. Comparative studies: no matched direct study located;
            # mechanism/threat-model inference. See documentation §6 for endpoints and limits.
            # Primary locations: ICE: ICE definition and examples of heterogeneous effects hidden by
            # PDPs
            'sparsity': 2,
            # Rating 4/5; original=4; v3.3.11=4. retained after comparative review.
            # Reason: Per-record response trajectories reveal more detail than population averaging.
            # Comparison: ICE (4/5) ties PDP (4/5): the former curves expose feature-response shape
            # for individual contexts; the latter response curves expose direction, shape and
            # thresholds.
            # Comparison: ICE (4/5) scores above Global SHAP summaries (3/5): the former curves
            # expose feature-response shape for individual contexts; the latter summary statistics
            # are coarser than explicit decision rules.
            # Calibration: A qualified comparative strength. The integer is an ordinal coding
            # decision; neither the unit gap nor universal superiority/inferiority is measured.
            # Evidence: qualitative comparative inference; see study cards for direct endpoints and
            # counterevidence. Confidence: moderate.
            # Sources: ICE, GLOBAL. Comparative studies: E05. See documentation §6 for endpoints and
            # limits.
            # Primary locations: ICE: ICE definition and examples of heterogeneous effects hidden by
            # PDPs
            'level_of_detail': 4,
            # Rating 2/5; original=2; v3.3.11=2. retained after comparative review.
            # Reason: Individual records or response trajectories can expose sensitive information;
            # contextual disclosure-risk inference.
            # Comparison: ICE (2/5) scores below PDP (3/5): the former individual response profiles
            # expose more record-specific information; the latter aggregate responses conceal
            # individual records but reveal behavior.
            # Comparison: ICE (2/5) scores below Global SHAP summaries (3/5): the former individual
            # response profiles expose more record-specific information; the latter aggregation
            # still exposes population behavior without a privacy proof.
            # Calibration: A below-neutral limitation. The integer is an ordinal coding decision;
            # neither the unit gap nor universal superiority/inferiority is measured.
            # Evidence: qualitative comparative inference; see study cards for direct endpoints and
            # counterevidence. Confidence: low.
            # Sources: ICE, PRIVACY, GLOBAL. Comparative studies: no matched direct study located;
            # mechanism/threat-model inference. See documentation §6 for endpoints and limits.
            # Primary locations: ICE: ICE definition and examples of heterogeneous effects hidden by
            # PDPs; PRIVACY: §§3–5; direct evidence for tested gradient/IG/LRP/LIME configurations;
            # threat-model context only for other methods
            'confidentiality': 2,
            # Rating 4/5; original=3; v3.3.11=4. retained after comparative review.
            # Reason: No inherent randomness prevents tracing fixed-grid model evaluations.
            # Comparison: ICE (4/5) ties PDP (4/5): the former saved queries reconstruct every
            # curve; the latter query grids and averages can be directly reproduced.
            # Comparison: ICE (4/5) ties Global SHAP summaries (4/5): the former saved queries
            # reconstruct every curve; the latter the cohort, local values and aggregation function
            # can be saved.
            # Calibration: A qualified comparative strength. The integer is an ordinal coding
            # decision; neither the unit gap nor universal superiority/inferiority is measured.
            # Evidence: qualitative comparative inference; see study cards for direct endpoints and
            # counterevidence. Confidence: moderate.
            # Sources: ICE, GLOBAL. Comparative studies: no matched direct study located;
            # mechanism/threat-model inference. See documentation §6 for endpoints and limits.
            # Primary locations: ICE: ICE definition and examples of heterogeneous effects hidden by
            # PDPs
            'traceability': 4,
            # Rating 4/5; original=4; v3.3.11=4. retained after comparative review.
            # Reason: Retain the same efficiency prior as PDP for the same grid and reference
            # workload; neither has universally constant cost.
            # Comparison: ICE (4/5) ties PDP (4/5): the former cost follows instances times grid
            # points, without optimization; the latter fixed small grids require batches of
            # prediction calls.
            # Comparison: ICE (4/5) scores above Global SHAP summaries (1/5): the former cost
            # follows instances times grid points, without optimization; the latter many local
            # explanation costs accumulate across the cohort.
            # Calibration: A qualified comparative strength. The integer is an ordinal coding
            # decision; neither the unit gap nor universal superiority/inferiority is measured.
            # Evidence: qualitative comparative inference; see study cards for direct endpoints and
            # counterevidence. Confidence: moderate.
            # Sources: ICE, GLOBAL. Comparative studies: no matched direct study located;
            # mechanism/threat-model inference. See documentation §6 for endpoints and limits.
            # Primary locations: ICE: ICE definition and examples of heterogeneous effects hidden by
            # PDPs
            'runtime_performance_and_implementation_constraints': 4,
        },
        'scope_stage': 'global-exante',
        'explanation_target': 'model output',
        "question_types": {'how_differs', 'what_rule'},
    },
    # Standard sampled local sparse surrogate; stabilized variants excluded.
    'LIME': {
        "subprops": {
            # Rating 2/5; original=2; v3.3.11=2. retained after comparative review.
            # Reason: A local surrogate can fit imperfectly and select misleading features; lower
            # prior than exact attribution.
            # Comparison: LIME (2/5) scores below Approximate local SHAP (3/5): the former an
            # imperfect local fit can select misleading features; the latter sampling error and game
            # semantics both require validation.
            # Comparison: LIME (2/5) scores below Exact local SHAP (3/5): the former an imperfect
            # local fit can select misleading features; the latter exact game allocation is not
            # generic decision-feature necessity.
            # Calibration: A below-neutral limitation. The integer is an ordinal coding decision;
            # neither the unit gap nor universal superiority/inferiority is measured.
            # Evidence: qualitative comparative inference; see study cards for direct endpoints and
            # counterevidence. Confidence: moderate.
            # Sources: LIME, KERNEL, RELEVANCE, SHAP, MANY_SHAP. Comparative studies: E01, E02, E06,
            # E07, E08, E11. See documentation §6 for endpoints and limits.
            # Primary locations: LIME: Local surrogate objective, perturbation sampling and feature
            # selection
            'no_false_positives': 2,
            # Rating 2/5; original=2; v3.3.11=2. retained after comparative review.
            # Reason: Sparse local fitting can miss nonlinear effects and omitted contributors.
            # Comparison: LIME (2/5) scores below Approximate local SHAP (3/5): the former local
            # sparsification can omit nonlinear influences; the latter regularized finite sampling
            # can suppress contributions.
            # Comparison: LIME (2/5) scores below Exact local SHAP (3/5): the former local
            # sparsification can omit nonlinear influences; the latter coalition averaging can
            # assign zero to decision-relevant features.
            # Calibration: A below-neutral limitation. The integer is an ordinal coding decision;
            # neither the unit gap nor universal superiority/inferiority is measured.
            # Evidence: qualitative comparative inference; see study cards for direct endpoints and
            # counterevidence. Confidence: moderate.
            # Sources: LIME, KERNEL, RELEVANCE, SHAP. Comparative studies: E01, E02, E06, E07, E08,
            # E11. See documentation §6 for endpoints and limits.
            # Primary locations: LIME: Local surrogate objective, perturbation sampling and feature
            # selection
            'no_false_negatives': 2,
            # Rating 2/5; original=2; v3.3.11=2. retained after comparative review.
            # Reason: The explanation covers a neighborhood, not the full decision function.
            # Comparison: LIME (2/5) scores below Approximate local SHAP (3/5): the former a sparse
            # local approximation covers only part of the rationale; the latter approximate
            # additivity is not complete rationale coverage.
            # Comparison: LIME (2/5) scores below Exact local SHAP (3/5): the former a sparse local
            # approximation covers only part of the rationale; the latter an additive allocation is
            # not a complete rationale.
            # Calibration: A below-neutral limitation. The integer is an ordinal coding decision;
            # neither the unit gap nor universal superiority/inferiority is measured.
            # Evidence: qualitative comparative inference; see study cards for direct endpoints and
            # counterevidence. Confidence: moderate.
            # Sources: LIME, KERNEL, SHAP. Comparative studies: E01, E06, E07, E08. See
            # documentation §6 for endpoints and limits.
            # Primary locations: LIME: Local surrogate objective, perturbation sampling and feature
            # selection
            'completeness': 2,
            # Rating 1/5; original=1; v3.3.11=1. retained after comparative review.
            # Reason: Retain the inherited lowest bin for the standard unstabilized local surrogate
            # in demanding nonlinear settings. The direct robustness study reports severe MNIST
            # sensitivity but also settings favoring LIME over SHAP. Thus 1 versus approximate
            # SHAP’s 2 is a disputed low-confidence prior, not a universal empirical ordering.
            # Comparison: LIME (1/5) scores below Approximate local SHAP (2/5): the former local
            # sampling and neighborhood fitting can be highly sensitive; the latter sampling adds
            # variation to the game’s input dependence.
            # Comparison: LIME (1/5) scores below Integrated Gradients (3/5): the former local
            # sampling and neighborhood fitting can be highly sensitive; the latter path integration
            # does not ensure local input continuity.
            # Calibration: An inherited endpoint under the stated output/configuration, not a
            # universal guarantee or universal failure. The exact endpoint is low-confidence outside
            # that setting.
            # Evidence: qualitative comparative inference; see study cards for direct endpoints and
            # counterevidence. Confidence: low.
            # Sources: LIME, ROBUST, MAN_CHAN, KERNEL, IG, SALIENCY. Comparative studies: E02, E03.
            # See documentation §6 for endpoints and limits.
            # Primary locations: LIME: Local surrogate objective, perturbation sampling and feature
            # selection; ROBUST: §§2–3 neighborhood sensitivity and worst-case perturbations; §4
            # interpretation; MAN_CHAN: §§2–3: repeated-rank variability, not small-input continuity
            'stability': 1,
            # Rating 1/5; original=1; v3.3.11=1. retained after comparative review.
            # Reason: Demonstrated manipulation of sampled LIME supports retaining the original weak
            # comparative anchor; it does not prove every deployment is fooled.
            # Comparison: LIME (1/5) scores below Approximate local SHAP (2/5): the former published
            # deceptive-wrapper attacks can redirect its attributions; the latter finite-budget
            # perturbation explainers have published attacks.
            # Comparison: LIME (1/5) scores below Exact local SHAP (3/5): the former published
            # deceptive-wrapper attacks can redirect its attributions; the latter exactness is not a
            # manipulation-resistance theorem.
            # Calibration: An inherited endpoint under the stated output/configuration, not a
            # universal guarantee or universal failure. The exact endpoint is low-confidence outside
            # that setting.
            # Evidence: qualitative comparative inference; see study cards for direct endpoints and
            # counterevidence. Confidence: low.
            # Sources: LIME, ATTACK, ROBUST, KERNEL, SHAP. Comparative studies: E03, E11. See
            # documentation §6 for endpoints and limits.
            # Primary locations: LIME: Local surrogate objective, perturbation sampling and feature
            # selection; ATTACK: Scaffolded classifiers exploiting off-distribution perturbation
            # queries; ROBUST: §§2–3 neighborhood sensitivity and worst-case perturbations; §4
            # interpretation
            'adversarial_robustness': 1,
            # Rating 2/5; original=1; v3.3.11=1. corrected in this review.
            # Reason: Corrected 1 to 2: sampled LIME is seed-sensitive, but the paper’s cited
            # Man–Chan study finds top-feature rankings at least as repeatable as sampled
            # permutation SHAP on its random-forest tasks. Tie approximate local SHAP at 2. The
            # study concerns repeated feature rankings, not local input continuity or universal
            # fidelity.
            # Comparison: LIME (2/5) ties Approximate local SHAP (2/5): the former random
            # perturbations vary ranks, with mixed head-to-head evidence; the latter finite sampling
            # makes repeated estimates vary.
            # Comparison: LIME (2/5) scores below Exact local SHAP (3/5): the former random
            # perturbations vary ranks, with mixed head-to-head evidence; the latter fixed-game
            # repeatability is narrower than temporal consistency.
            # Calibration: A below-neutral limitation. The integer is an ordinal coding decision;
            # neither the unit gap nor universal superiority/inferiority is measured.
            # Evidence: qualitative comparative inference; see study cards for direct endpoints and
            # counterevidence. Confidence: low.
            # Sources: LIME, MAN_CHAN, KERNEL, SHAP. Comparative studies: E02, E06. See
            # documentation §6 for endpoints and limits.
            # Primary locations: LIME: Man & Chan §§2–3 and 5; permutation-SHAP implementation and
            # repeated-rank instability; MAN_CHAN: §§2–3: repeated-rank variability, not small-input
            # continuity
            'consistency': 2,
            # Rating 1/5; original=1; v3.3.11=1. retained after comparative review.
            # Reason: Neighborhood and feature-selection choices can strongly affect the surrogate;
            # retaining the original weak prior avoids unsupported numerical recalibration.
            # Comparison: LIME (1/5) scores below Approximate local SHAP (2/5): the former kernel
            # width, representation and feature count can dominate output; the latter sample budget,
            # regularization and background affect attribution.
            # Comparison: LIME (1/5) scores below Exact local SHAP (3/5): the former kernel width,
            # representation and feature count can dominate output; the latter background and
            # coalition-game choices still matter.
            # Calibration: An inherited endpoint under the stated output/configuration, not a
            # universal guarantee or universal failure. The exact endpoint is low-confidence outside
            # that setting.
            # Evidence: qualitative comparative inference; see study cards for direct endpoints and
            # counterevidence. Confidence: low.
            # Sources: LIME, KERNEL, SHAP. Comparative studies: no matched direct study located;
            # mechanism/threat-model inference. See documentation §6 for endpoints and limits.
            # Primary locations: LIME: Local surrogate objective, perturbation sampling and feature
            # selection
            'hyperparameters_perturbation_robustness': 1,
            # Rating 3/5; original=3; v3.3.11=3. retained after comparative review.
            # Reason: User-controlled feature selection supports compact output, but not inherently
            # minimal explanations; original neutral 3 remains defensible.
            # Comparison: LIME (3/5) ties Approximate local SHAP (3/5): the former an explicit
            # feature budget controls the delivered explanation; the latter full values or a
            # selected display are not guaranteed minimal.
            # Comparison: LIME (3/5) ties Exact local SHAP (3/5): the former an explicit feature
            # budget controls the delivered explanation; the latter exact allocation typically
            # returns a full feature vector.
            # Calibration: Neutral bin: the evidence does not warrant a general stronger or weaker
            # claim on this exact property. A tie is not demonstrated empirical equivalence.
            # Evidence: qualitative comparative inference; see study cards for direct endpoints and
            # counterevidence. Confidence: low.
            # Sources: LIME, KERNEL, SHAP. Comparative studies: E06, E07, E08. See documentation §6
            # for endpoints and limits.
            # Primary locations: LIME: Local surrogate objective, perturbation sampling and feature
            # selection
            'sparsity': 3,
            # Rating 2/5; original=2; v3.3.11=2. retained after comparative review.
            # Reason: Sparse coefficients describe a local approximation without rules or
            # interactions; retain the paper's low-detail comparative prior.
            # Comparison: LIME (2/5) scores below Approximate local SHAP (3/5): the former a local
            # linear coefficient list omits explicit nonlinear rules; the latter feature allocations
            # retain the same output form as exact SHAP.
            # Comparison: LIME (2/5) scores below Exact local SHAP (3/5): the former a local linear
            # coefficient list omits explicit nonlinear rules; the latter per-feature values do not
            # expose the whole interaction mechanism.
            # Calibration: A below-neutral limitation. The integer is an ordinal coding decision;
            # neither the unit gap nor universal superiority/inferiority is measured.
            # Evidence: qualitative comparative inference; see study cards for direct endpoints and
            # counterevidence. Confidence: moderate.
            # Sources: LIME, KERNEL, SHAP. Comparative studies: E06, E07. See documentation §6 for
            # endpoints and limits.
            # Primary locations: LIME: Local surrogate objective, perturbation sampling and feature
            # selection
            'level_of_detail': 2,
            # Rating 3/5; original=3; v3.3.11=3. retained after comparative review.
            # Reason: Local outputs can reveal sensitive behavior; neutral does not assert
            # confidentiality.
            # Comparison: LIME (3/5) ties Approximate local SHAP (3/5): the former a local summary
            # still has no confidentiality guarantee; the latter local estimated values are not
            # privacy-protected.
            # Comparison: LIME (3/5) ties Exact local SHAP (3/5): the former a local summary still
            # has no confidentiality guarantee; the latter local values have no inherent
            # confidentiality guarantee.
            # Calibration: Neutral bin: the evidence does not warrant a general stronger or weaker
            # claim on this exact property. A tie is not demonstrated empirical equivalence.
            # Evidence: qualitative comparative inference; see study cards for direct endpoints and
            # counterevidence. Confidence: low.
            # Sources: LIME, PRIVACY, KERNEL, SHAP. Comparative studies: E12. See documentation §6
            # for endpoints and limits.
            # Primary locations: LIME: Local surrogate objective, perturbation sampling and feature
            # selection; PRIVACY: §§3–5; direct evidence for tested gradient/IG/LRP/LIME
            # configurations; threat-model context only for other methods
            'confidentiality': 3,
            # Rating 3/5; original=2; v3.3.11=3. retained after comparative review.
            # Reason: Recording the model, input, random state and settings makes reconstruction
            # possible; use 3 rather than assuming either complete or inherently poor auditability.
            # Comparison: LIME (3/5) scores below Approximate local SHAP (4/5): the former queries,
            # seeds, neighborhood and fitted surrogate must be recorded; the latter seeds, coalition
            # queries and regression settings can be logged.
            # Comparison: LIME (3/5) scores below Exact local SHAP (4/5): the former queries, seeds,
            # neighborhood and fitted surrogate must be recorded; the latter a fixed value function
            # and coalitions allow reconstruction.
            # Calibration: Neutral bin: the evidence does not warrant a general stronger or weaker
            # claim on this exact property. A tie is not demonstrated empirical equivalence.
            # Evidence: qualitative comparative inference; see study cards for direct endpoints and
            # counterevidence. Confidence: moderate.
            # Sources: LIME, KERNEL, SHAP. Comparative studies: no matched direct study located;
            # mechanism/threat-model inference. See documentation §6 for endpoints and limits.
            # Primary locations: LIME: Local surrogate objective, perturbation sampling and feature
            # selection
            'traceability': 3,
            # Rating 3/5; original=3; v3.3.11=3. retained after comparative review.
            # Reason: Repeated queries and a small regression are moderately costly; no fixed
            # runtime ratio to KernelSHAP is asserted.
            # Comparison: LIME (3/5) scores above Approximate local SHAP (2/5): the former thousands
            # of prediction calls are typical, without gradient access; the latter finite coalition
            # sampling avoids full exponential enumeration.
            # Comparison: LIME (3/5) scores above Exact local SHAP (1/5): the former thousands of
            # prediction calls are typical, without gradient access; the latter generic exact
            # evaluation scales exponentially in varying features.
            # Calibration: Neutral bin: the evidence does not warrant a general stronger or weaker
            # claim on this exact property. A tie is not demonstrated empirical equivalence.
            # Evidence: qualitative comparative inference; see study cards for direct endpoints and
            # counterevidence. Confidence: moderate.
            # Sources: LIME, KERNEL, SHAP, EXACT. Comparative studies: E01. See documentation §6 for
            # endpoints and limits.
            # Primary locations: LIME: Local surrogate objective, perturbation sampling and feature
            # selection
            'runtime_performance_and_implementation_constraints': 3,
        },
        'scope_stage': 'local-expost',
        'explanation_target': 'model output',
        "question_types": {'how_computed', 'what_feature', 'what_if'},
    },
    # Sampled high-precision local rule under its declared perturbation distribution.
    'Anchors': {
        "subprops": {
            # Rating 3/5; original=4; v3.3.11=3. retained after comparative review.
            # Reason: High rule precision does not prove every predicate is necessary; the retained
            # rubric necessity remains neutral.
            # Comparison: Anchors (3/5) scores above LIME (2/5): the former conditional rule
            # precision does not prove predicate necessity; the latter an imperfect local fit can
            # select misleading features.
            # Comparison: Anchors (3/5) ties Approximate local SHAP (3/5): the former conditional
            # rule precision does not prove predicate necessity; the latter sampling error and game
            # semantics both require validation.
            # Calibration: Neutral bin: the evidence does not warrant a general stronger or weaker
            # claim on this exact property. A tie is not demonstrated empirical equivalence.
            # Evidence: qualitative comparative inference; see study cards for direct endpoints and
            # counterevidence. Confidence: low.
            # Sources: ANCHORS, LIME, KERNEL, RELEVANCE. Comparative studies: E06. See documentation
            # §6 for endpoints and limits.
            # Primary locations: ANCHORS: Anchor definition, perturbation-distribution precision and
            # search procedure
            'no_false_positives': 3,
            # Rating 3/5; original=3; v3.3.11=3. retained after comparative review.
            # Reason: A sufficient rule need not enumerate all contributors; conditional precision
            # is not feature-recall evidence.
            # Comparison: Anchors (3/5) scores above LIME (2/5): the former one sufficient rule need
            # not enumerate all influences; the latter local sparsification can omit nonlinear
            # influences.
            # Comparison: Anchors (3/5) ties Approximate local SHAP (3/5): the former one sufficient
            # rule need not enumerate all influences; the latter regularized finite sampling can
            # suppress contributions.
            # Calibration: Neutral bin: the evidence does not warrant a general stronger or weaker
            # claim on this exact property. A tie is not demonstrated empirical equivalence.
            # Evidence: qualitative comparative inference; see study cards for direct endpoints and
            # counterevidence. Confidence: moderate.
            # Sources: ANCHORS, LIME, KERNEL, RELEVANCE. Comparative studies: E06. See documentation
            # §6 for endpoints and limits.
            # Primary locations: ANCHORS: Anchor definition, perturbation-distribution precision and
            # search procedure
            'no_false_negatives': 3,
            # Rating 3/5; original=3; v3.3.11=3. retained after comparative review.
            # Reason: Retain the original comparative rating: The rule applies within its covered
            # region; it does not express the full rationale.
            # Comparison: Anchors (3/5) scores above LIME (2/5): the former a validated region
            # supplies more coverage information than an unqualified local fit; the latter a sparse
            # local approximation covers only part of the rationale.
            # Comparison: Anchors (3/5) ties Approximate local SHAP (3/5): the former a validated
            # region supplies more coverage information than an unqualified local fit; the latter
            # approximate additivity is not complete rationale coverage.
            # Calibration: Neutral bin: the evidence does not warrant a general stronger or weaker
            # claim on this exact property. A tie is not demonstrated empirical equivalence.
            # Evidence: qualitative comparative inference; see study cards for direct endpoints and
            # counterevidence. Confidence: moderate.
            # Sources: ANCHORS, LIME, KERNEL. Comparative studies: E06. See documentation §6 for
            # endpoints and limits.
            # Primary locations: ANCHORS: Anchor definition, perturbation-distribution precision and
            # search procedure
            'completeness': 3,
            # Rating 1/5; original=1; v3.3.11=1. retained after comparative review.
            # Reason: Sampling or optimization choices can produce substantially different outputs.
            # Retain the original weakest comparative anchor for the standard unstabilized method;
            # this is not a universal failure claim.
            # Comparison: Anchors (1/5) ties LIME (1/5): the former sampled rule search can change
            # the selected conjunction; the latter local sampling and neighborhood fitting can be
            # highly sensitive.
            # Comparison: Anchors (1/5) scores below Approximate local SHAP (2/5): the former
            # sampled rule search can change the selected conjunction; the latter sampling adds
            # variation to the game’s input dependence.
            # Calibration: An inherited endpoint under the stated output/configuration, not a
            # universal guarantee or universal failure. The exact endpoint is low-confidence outside
            # that setting.
            # Evidence: qualitative comparative inference; see study cards for direct endpoints and
            # counterevidence. Confidence: low.
            # Sources: ANCHORS, LIME, ROBUST, MAN_CHAN, KERNEL. Comparative studies: no matched
            # direct study located; mechanism/threat-model inference. See documentation §6 for
            # endpoints and limits.
            # Primary locations: ANCHORS: Anchor definition, perturbation-distribution precision and
            # search procedure
            'stability': 1,
            # Rating 3/5; original=3; v3.3.11=3. retained after comparative review.
            # Reason: A probabilistic precision target is not an adversarial robustness guarantee.
            # Comparison: Anchors (3/5) scores above LIME (1/5): the former the precision guarantee
            # is distributional, not adversarial; the latter published deceptive-wrapper attacks can
            # redirect its attributions.
            # Comparison: Anchors (3/5) scores above Approximate local SHAP (2/5): the former the
            # precision guarantee is distributional, not adversarial; the latter finite-budget
            # perturbation explainers have published attacks.
            # Calibration: Neutral bin: the evidence does not warrant a general stronger or weaker
            # claim on this exact property. A tie is not demonstrated empirical equivalence.
            # Evidence: qualitative comparative inference; see study cards for direct endpoints and
            # counterevidence. Confidence: low.
            # Sources: ANCHORS, LIME, ATTACK, ROBUST, KERNEL. Comparative studies: no matched direct
            # study located; mechanism/threat-model inference. See documentation §6 for endpoints
            # and limits.
            # Primary locations: ANCHORS: Anchor definition, perturbation-distribution precision and
            # search procedure
            'adversarial_robustness': 3,
            # Rating 1/5; original=1; v3.3.11=1. retained after comparative review.
            # Reason: Sampling or optimization choices can produce substantially different outputs.
            # Retain the original weakest comparative anchor for the standard unstabilized method;
            # this is not a universal failure claim.
            # Comparison: Anchors (1/5) scores below LIME (2/5): the former sampling may select
            # different qualifying rules; the latter random perturbations vary ranks, with mixed
            # head-to-head evidence.
            # Comparison: Anchors (1/5) scores below Approximate local SHAP (2/5): the former
            # sampling may select different qualifying rules; the latter finite sampling makes
            # repeated estimates vary.
            # Calibration: An inherited endpoint under the stated output/configuration, not a
            # universal guarantee or universal failure. The exact endpoint is low-confidence outside
            # that setting.
            # Evidence: qualitative comparative inference; see study cards for direct endpoints and
            # counterevidence. Confidence: low.
            # Sources: ANCHORS, LIME, MAN_CHAN, KERNEL. Comparative studies: E06. See documentation
            # §6 for endpoints and limits.
            # Primary locations: ANCHORS: Anchor definition, perturbation-distribution precision and
            # search procedure
            'consistency': 1,
            # Rating 2/5; original=2; v3.3.11=2. retained after comparative review.
            # Reason: Precision target, discretization and sampling budget influence rule selection.
            # Comparison: Anchors (2/5) scores above LIME (1/5): the former precision threshold and
            # perturbation distribution shape the rule; the latter kernel width, representation and
            # feature count can dominate output.
            # Comparison: Anchors (2/5) ties Approximate local SHAP (2/5): the former precision
            # threshold and perturbation distribution shape the rule; the latter sample budget,
            # regularization and background affect attribution.
            # Calibration: A below-neutral limitation. The integer is an ordinal coding decision;
            # neither the unit gap nor universal superiority/inferiority is measured.
            # Evidence: qualitative comparative inference; see study cards for direct endpoints and
            # counterevidence. Confidence: low.
            # Sources: ANCHORS, LIME, KERNEL. Comparative studies: no matched direct study located;
            # mechanism/threat-model inference. See documentation §6 for endpoints and limits.
            # Primary locations: ANCHORS: Anchor definition, perturbation-distribution precision and
            # search procedure
            'hyperparameters_perturbation_robustness': 2,
            # Rating 4/5; original=5; v3.3.11=4. retained after comparative review.
            # Reason: Search favors concise rules; 4 replaces an unsupported universal minimality
            # score of 5.
            # Comparison: Anchors (4/5) scores above LIME (3/5): the former short sufficient
            # conjunctions are the explicit search target; the latter an explicit feature budget
            # controls the delivered explanation.
            # Comparison: Anchors (4/5) scores above Approximate local SHAP (3/5): the former short
            # sufficient conjunctions are the explicit search target; the latter full values or a
            # selected display are not guaranteed minimal.
            # Calibration: A qualified comparative strength. The integer is an ordinal coding
            # decision; neither the unit gap nor universal superiority/inferiority is measured.
            # Evidence: qualitative comparative inference; see study cards for direct endpoints and
            # counterevidence. Confidence: moderate.
            # Sources: ANCHORS, LIME, KERNEL, SHAP. Comparative studies: E06. See documentation §6
            # for endpoints and limits.
            # Primary locations: ANCHORS: Anchor definition, perturbation-distribution precision and
            # search procedure
            'sparsity': 4,
            # Rating 3/5; original=3; v3.3.11=3. retained after comparative review.
            # Reason: A conjunction provides feature predicates, but not the model's complete
            # branching structure.
            # Comparison: Anchors (3/5) scores above LIME (2/5): the former a local conjunction
            # exposes conditions but not a full decision function; the latter a local linear
            # coefficient list omits explicit nonlinear rules.
            # Comparison: Anchors (3/5) ties Approximate local SHAP (3/5): the former a local
            # conjunction exposes conditions but not a full decision function; the latter feature
            # allocations retain the same output form as exact SHAP.
            # Calibration: Neutral bin: the evidence does not warrant a general stronger or weaker
            # claim on this exact property. A tie is not demonstrated empirical equivalence.
            # Evidence: qualitative comparative inference; see study cards for direct endpoints and
            # counterevidence. Confidence: moderate.
            # Sources: ANCHORS, LIME, KERNEL. Comparative studies: E06. See documentation §6 for
            # endpoints and limits.
            # Primary locations: ANCHORS: Anchor definition, perturbation-distribution precision and
            # search procedure
            'level_of_detail': 3,
            # Rating 3/5; original=3; v3.3.11=3. retained after comparative review.
            # Reason: Local rules still disclose model behavior; neutral is a contextual prior.
            # Comparison: Anchors (3/5) ties LIME (3/5): the former a short local rule can still
            # reveal sensitive decision criteria; the latter a local summary still has no
            # confidentiality guarantee.
            # Comparison: Anchors (3/5) ties Approximate local SHAP (3/5): the former a short local
            # rule can still reveal sensitive decision criteria; the latter local estimated values
            # are not privacy-protected.
            # Calibration: Neutral bin: the evidence does not warrant a general stronger or weaker
            # claim on this exact property. A tie is not demonstrated empirical equivalence.
            # Evidence: qualitative comparative inference; see study cards for direct endpoints and
            # counterevidence. Confidence: low.
            # Sources: ANCHORS, PRIVACY, LIME, KERNEL. Comparative studies: no matched direct study
            # located; mechanism/threat-model inference. See documentation §6 for endpoints and
            # limits.
            # Primary locations: ANCHORS: Anchor definition, perturbation-distribution precision and
            # search procedure; PRIVACY: §§3–5; direct evidence for tested gradient/IG/LRP/LIME
            # configurations; threat-model context only for other methods
            'confidentiality': 3,
            # Rating 3/5; original=2; v3.3.11=3. retained after comparative review.
            # Reason: Recording the model, input, random state and settings makes reconstruction
            # possible; use 3 rather than assuming either complete or inherently poor auditability.
            # Comparison: Anchors (3/5) ties LIME (3/5): the former sampling and rule-selection
            # records are required for reconstruction; the latter queries, seeds, neighborhood and
            # fitted surrogate must be recorded.
            # Comparison: Anchors (3/5) scores below Approximate local SHAP (4/5): the former
            # sampling and rule-selection records are required for reconstruction; the latter seeds,
            # coalition queries and regression settings can be logged.
            # Calibration: Neutral bin: the evidence does not warrant a general stronger or weaker
            # claim on this exact property. A tie is not demonstrated empirical equivalence.
            # Evidence: qualitative comparative inference; see study cards for direct endpoints and
            # counterevidence. Confidence: moderate.
            # Sources: ANCHORS, LIME, KERNEL. Comparative studies: no matched direct study located;
            # mechanism/threat-model inference. See documentation §6 for endpoints and limits.
            # Primary locations: ANCHORS: Anchor definition, perturbation-distribution precision and
            # search procedure
            'traceability': 3,
            # Rating 3/5; original=3; v3.3.11=3. retained after comparative review.
            # Reason: Retain the original comparative rating: Precision estimation and combinatorial
            # search can require many queries, exceeding a simple local fit.
            # Comparison: Anchors (3/5) ties LIME (3/5): the former adaptive sampling avoids
            # exhaustive rule enumeration but can be costly; the latter thousands of prediction
            # calls are typical, without gradient access.
            # Comparison: Anchors (3/5) scores above Approximate local SHAP (2/5): the former
            # adaptive sampling avoids exhaustive rule enumeration but can be costly; the latter
            # finite coalition sampling avoids full exponential enumeration.
            # Calibration: Neutral bin: the evidence does not warrant a general stronger or weaker
            # claim on this exact property. A tie is not demonstrated empirical equivalence.
            # Evidence: qualitative comparative inference; see study cards for direct endpoints and
            # counterevidence. Confidence: moderate.
            # Sources: ANCHORS, LIME, KERNEL. Comparative studies: no matched direct study located;
            # mechanism/threat-model inference. See documentation §6 for endpoints and limits.
            # Primary locations: ANCHORS: Anchor definition, perturbation-distribution precision and
            # search procedure
            'runtime_performance_and_implementation_constraints': 3,
        },
        'scope_stage': 'local-expost',
        'explanation_target': 'model output',
        "question_types": {'how_computed', 'what_feature', 'what_rule'},
    },
    # Original optimization-based pertinent-positive/negative explanation; returned validity
    # checked.
    'CEM': {
        "subprops": {
            # Rating 3/5; original=5; v3.3.11=4. corrected in this review.
            # Reason: Corrected 4 to 3: checking a retained set or a class-changing addition
            # validates the set-level contrast, not the influence of every selected element. The
            # non-convex sparse search is not a per-feature minimality certificate. Tie DiCE at 3;
            # neither method receives extra necessity credit only for a valid returned contrast.
            # Comparison: CEM (3/5) ties DiCE (3/5): the former a valid sparse contrast need not
            # make every edit influential; the latter valid diverse examples can contain redundant
            # edits.
            # Comparison: CEM (3/5) scores above LIME (2/5): the former a valid sparse contrast need
            # not make every edit influential; the latter an imperfect local fit can select
            # misleading features.
            # Calibration: Neutral bin: the evidence does not warrant a general stronger or weaker
            # claim on this exact property. A tie is not demonstrated empirical equivalence.
            # Evidence: qualitative comparative inference; see study cards for direct endpoints and
            # counterevidence. Confidence: low.
            # Sources: CEM, DICE, LIME. Comparative studies: E07, E08. See documentation §6 for
            # endpoints and limits.
            # Primary locations: CEM: CEM §3 optimization and §4 comparisons; DiCE §§3–5 validity
            # and sparsity; DICE: CEM §3 optimization and §4 comparisons; DiCE §§3–5 validity and
            # sparsity
            'no_false_positives': 3,
            # Rating 3/5; original=3; v3.3.11=3. retained after comparative review.
            # Reason: A selected PP/PN set describes a particular contrast; it need not recover
            # every influence on the original prediction. Neutral 3 concerns this incomplete
            # accounting, not a requirement to enumerate every possible alternative explanation.
            # Comparison: CEM (3/5) ties DiCE (3/5): the former one pertinent-positive/negative pair
            # omits other influences; the latter multiple contrasts still need not list all
            # influences.
            # Comparison: CEM (3/5) scores above LIME (2/5): the former one
            # pertinent-positive/negative pair omits other influences; the latter local
            # sparsification can omit nonlinear influences.
            # Calibration: Neutral bin: the evidence does not warrant a general stronger or weaker
            # claim on this exact property. A tie is not demonstrated empirical equivalence.
            # Evidence: qualitative comparative inference; see study cards for direct endpoints and
            # counterevidence. Confidence: moderate.
            # Sources: CEM, DICE, LIME. Comparative studies: E07, E08. See documentation §6 for
            # endpoints and limits.
            # Primary locations: CEM: Pertinent-positive/negative optimization objectives and
            # empirical examples
            'no_false_negatives': 3,
            # Rating 4/5; original=4; v3.3.11=4. retained after comparative review.
            # Reason: Pertinent positives and negatives provide two complementary contrasts; retain
            # comparative 4 versus a single counterfactual set, not full logical coverage.
            # Comparison: CEM (4/5) scores above DiCE (3/5): the former present and absent evidence
            # provide complementary contrasts; the latter diverse examples cover more boundary
            # alternatives than one local fit.
            # Comparison: CEM (4/5) scores above LIME (2/5): the former present and absent evidence
            # provide complementary contrasts; the latter a sparse local approximation covers only
            # part of the rationale.
            # Calibration: A qualified comparative strength. The integer is an ordinal coding
            # decision; neither the unit gap nor universal superiority/inferiority is measured.
            # Evidence: qualitative comparative inference; see study cards for direct endpoints and
            # counterevidence. Confidence: moderate.
            # Sources: CEM, DICE, LIME. Comparative studies: E07, E08. See documentation §6 for
            # endpoints and limits.
            # Primary locations: CEM: Pertinent-positive/negative optimization objectives and
            # empirical examples
            'completeness': 4,
            # Rating 2/5; original=1; v3.3.11=1. corrected in this review.
            # Reason: Corrected 1 to 2: the sparse optimum can switch under nearby inputs,
            # supporting below-neutral stability. The cited original evaluation does not establish
            # the catalogue’s worst instability tier. Its fixed zero initialization must not be
            # confused with DiCE’s random-start variability; 2 is a cautious structural judgment,
            # not an observed Lipschitz score.
            # Comparison: CEM (2/5) scores above DiCE (1/5): the former a non-convex sparse optimum
            # can switch under input changes; the latter randomized non-convex search may select
            # very different recourse sets.
            # Comparison: CEM (2/5) scores below Integrated Gradients (3/5): the former a non-convex
            # sparse optimum can switch under input changes; the latter path integration does not
            # ensure local input continuity.
            # Calibration: A below-neutral limitation. The integer is an ordinal coding decision;
            # neither the unit gap nor universal superiority/inferiority is measured.
            # Evidence: qualitative comparative inference; see study cards for direct endpoints and
            # counterevidence. Confidence: low.
            # Sources: CEM, DICE, IG, SALIENCY, ROBUST. Comparative studies: no matched direct study
            # located; mechanism/threat-model inference. See documentation §6 for endpoints and
            # limits.
            # Primary locations: CEM: §3.3 solver initialization; §4 examples, which are not a
            # local-stability benchmark
            'stability': 2,
            # Rating 3/5; original=4; v3.3.11=3. retained after comparative review.
            # Reason: Prediction validity is distinct from attack resistance; neutral replaces an
            # unsupported strength.
            # Comparison: CEM (3/5) ties DiCE (3/5): the former contrast validity is not resistance
            # to adversarial manipulation; the latter validity at one model is not explanation
            # robustness.
            # Comparison: CEM (3/5) scores above LIME (1/5): the former contrast validity is not
            # resistance to adversarial manipulation; the latter published deceptive-wrapper attacks
            # can redirect its attributions.
            # Calibration: Neutral bin: the evidence does not warrant a general stronger or weaker
            # claim on this exact property. A tie is not demonstrated empirical equivalence.
            # Evidence: qualitative comparative inference; see study cards for direct endpoints and
            # counterevidence. Confidence: low.
            # Sources: CEM, SHIFT, DICE, LIME, ATTACK, ROBUST. Comparative studies: no matched
            # direct study located; mechanism/threat-model inference. See documentation §6 for
            # endpoints and limits.
            # Primary locations: CEM: Pertinent-positive/negative optimization objectives and
            # empirical examples; SHIFT: Counterfactual robustness under data shift; not a general
            # adversarial guarantee
            'adversarial_robustness': 3,
            # Rating 3/5; original=1; v3.3.11=3. retained after comparative review.
            # Reason: The published projected-FISTA solver starts from a zero perturbation and
            # specifies its updates. With the model and settings fixed, random-start variation is
            # not intrinsic. Replace the unsupported lowest rating with neutral 3: this
            # repeatability does not establish consistency across changed inputs, models, or time.
            # Comparison: CEM (3/5) scores above DiCE (1/5): the former the specified solver starts
            # at zero rather than randomly; the latter random starts and alternative solutions
            # affect repeatability.
            # Comparison: CEM (3/5) scores above LIME (2/5): the former the specified solver starts
            # at zero rather than randomly; the latter random perturbations vary ranks, with mixed
            # head-to-head evidence.
            # Calibration: Neutral bin: the evidence does not warrant a general stronger or weaker
            # claim on this exact property. A tie is not demonstrated empirical equivalence.
            # Evidence: qualitative comparative inference; see study cards for direct endpoints and
            # counterevidence. Confidence: low.
            # Sources: CEM, DICE, SHIFT, LIME, MAN_CHAN. Comparative studies: no matched direct
            # study located; mechanism/threat-model inference. See documentation §6 for endpoints
            # and limits.
            # Primary locations: CEM: Section 3.3, equations (5)–(6), zero initial iterate; Appendix
            # A solver details
            'consistency': 3,
            # Rating 1/5; original=1; v3.3.11=1. retained after comparative review.
            # Reason: Loss weight, sparsity penalty, manifold regularization, margin, and
            # optimization budget can change which PP/PN set is returned. Retain the original low
            # prior for unconstrained settings; its severity is not an empirical 1–5 measurement,
            # and the method need not use random initialization.
            # Comparison: CEM (1/5) ties DiCE (1/5): the former regularization and autoencoder
            # choices can alter selected sets; the latter diversity, proximity and sparsity weights
            # alter outputs.
            # Comparison: CEM (1/5) ties LIME (1/5): the former regularization and autoencoder
            # choices can alter selected sets; the latter kernel width, representation and feature
            # count can dominate output.
            # Calibration: An inherited endpoint under the stated output/configuration, not a
            # universal guarantee or universal failure. The exact endpoint is low-confidence outside
            # that setting.
            # Evidence: qualitative comparative inference; see study cards for direct endpoints and
            # counterevidence. Confidence: low.
            # Sources: CEM, DICE, LIME. Comparative studies: no matched direct study located;
            # mechanism/threat-model inference. See documentation §6 for endpoints and limits.
            # Primary locations: CEM: Equations (1) and (3); Section 3.3 and Appendix A: objective
            # coefficients, solver and iteration choices
            'hyperparameters_perturbation_robustness': 1,
            # Rating 4/5; original=4; v3.3.11=4. retained after comparative review.
            # Reason: Regularized perturbations favor compact evidence; sparsity is optimized rather
            # than guaranteed.
            # Comparison: CEM (4/5) ties DiCE (4/5): the former sparse optimization favors few
            # retained or added elements; the latter sparse recourse is encouraged although several
            # examples add size.
            # Comparison: CEM (4/5) scores above LIME (3/5): the former sparse optimization favors
            # few retained or added elements; the latter an explicit feature budget controls the
            # delivered explanation.
            # Calibration: A qualified comparative strength. The integer is an ordinal coding
            # decision; neither the unit gap nor universal superiority/inferiority is measured.
            # Evidence: qualitative comparative inference; see study cards for direct endpoints and
            # counterevidence. Confidence: moderate.
            # Sources: CEM, DICE, LIME. Comparative studies: E07, E08. See documentation §6 for
            # endpoints and limits.
            # Primary locations: CEM: Pertinent-positive/negative optimization objectives and
            # empirical examples
            'sparsity': 4,
            # Rating 3/5; original=3; v3.3.11=3. retained after comparative review.
            # Reason: Changed or retained features give a concrete contrast rather than full model
            # structure.
            # Comparison: CEM (3/5) ties DiCE (3/5): the former changed and retained elements
            # explain a contrast without full rules; the latter edited values convey counterfactual
            # direction but not full mechanisms.
            # Comparison: CEM (3/5) scores above LIME (2/5): the former changed and retained
            # elements explain a contrast without full rules; the latter a local linear coefficient
            # list omits explicit nonlinear rules.
            # Calibration: Neutral bin: the evidence does not warrant a general stronger or weaker
            # claim on this exact property. A tie is not demonstrated empirical equivalence.
            # Evidence: qualitative comparative inference; see study cards for direct endpoints and
            # counterevidence. Confidence: moderate.
            # Sources: CEM, DICE, LIME. Comparative studies: E07. See documentation §6 for endpoints
            # and limits.
            # Primary locations: CEM: Pertinent-positive/negative optimization objectives and
            # empirical examples
            'level_of_detail': 3,
            # Rating 3/5; original=3; v3.3.11=3. retained after comparative review.
            # Reason: Local evidence lacks inherent privacy protection.
            # Comparison: CEM (3/5) ties DiCE (3/5): the former a contrast may reveal sensitive
            # inputs and decision boundaries; the latter counterfactuals can expose private records
            # or boundaries.
            # Comparison: CEM (3/5) ties LIME (3/5): the former a contrast may reveal sensitive
            # inputs and decision boundaries; the latter a local summary still has no
            # confidentiality guarantee.
            # Calibration: Neutral bin: the evidence does not warrant a general stronger or weaker
            # claim on this exact property. A tie is not demonstrated empirical equivalence.
            # Evidence: qualitative comparative inference; see study cards for direct endpoints and
            # counterevidence. Confidence: low.
            # Sources: CEM, PRIVACY, DICE, LIME. Comparative studies: no matched direct study
            # located; mechanism/threat-model inference. See documentation §6 for endpoints and
            # limits.
            # Primary locations: CEM: Pertinent-positive/negative optimization objectives and
            # empirical examples; PRIVACY: §§3–5; direct evidence for tested gradient/IG/LRP/LIME
            # configurations; threat-model context only for other methods
            'confidentiality': 3,
            # Rating 3/5; original=2; v3.3.11=3. retained after comparative review.
            # Reason: Recording the model, input, random state and settings makes reconstruction
            # possible; use 3 rather than assuming either complete or inherently poor auditability.
            # Comparison: CEM (3/5) ties DiCE (3/5): the former optimization states, constraints and
            # references must be retained; the latter seeds, constraints, objectives and candidate
            # outputs can be logged.
            # Comparison: CEM (3/5) ties LIME (3/5): the former optimization states, constraints and
            # references must be retained; the latter queries, seeds, neighborhood and fitted
            # surrogate must be recorded.
            # Calibration: Neutral bin: the evidence does not warrant a general stronger or weaker
            # claim on this exact property. A tie is not demonstrated empirical equivalence.
            # Evidence: qualitative comparative inference; see study cards for direct endpoints and
            # counterevidence. Confidence: moderate.
            # Sources: CEM, DICE, LIME. Comparative studies: no matched direct study located;
            # mechanism/threat-model inference. See documentation §6 for endpoints and limits.
            # Primary locations: CEM: Pertinent-positive/negative optimization objectives and
            # empirical examples
            'traceability': 3,
            # Rating 2/5; original=2; v3.3.11=2. retained after comparative review.
            # Reason: Two optimization tasks and possible manifold regularization impose substantial
            # explanation cost.
            # Comparison: CEM (2/5) scores below DiCE (3/5): the former iterative optimization and
            # optional autoencoder training add burden; the latter repeated optimization costs more
            # than a direct forward/backward pass.
            # Comparison: CEM (2/5) scores below LIME (3/5): the former iterative optimization and
            # optional autoencoder training add burden; the latter thousands of prediction calls are
            # typical, without gradient access.
            # Calibration: A below-neutral limitation. The integer is an ordinal coding decision;
            # neither the unit gap nor universal superiority/inferiority is measured.
            # Evidence: qualitative comparative inference; see study cards for direct endpoints and
            # counterevidence. Confidence: moderate.
            # Sources: CEM, DICE, LIME. Comparative studies: no matched direct study located;
            # mechanism/threat-model inference. See documentation §6 for endpoints and limits.
            # Primary locations: CEM: Pertinent-positive/negative optimization objectives and
            # empirical examples
            'runtime_performance_and_implementation_constraints': 2,
        },
        'scope_stage': 'local-expost',
        'explanation_target': 'model output',
        "question_types": {'what_feature', 'why_instead_of'},
    },
    # Original diverse-counterfactual generation; successful candidates checked against a fixed
    # model.
    'DiCE': {
        "subprops": {
            # Rating 3/5; original=5; v3.3.11=3. retained after comparative review.
            # Reason: A counterfactual can change the prediction while containing redundant edits.
            # Diversity, proximity and post-hoc sparsity do not verify that every changed feature
            # truly influences the outcome; prediction validity alone did not justify the previous
            # 4.
            # Comparison: DiCE (3/5) ties CEM (3/5): the former valid diverse examples can contain
            # redundant edits; the latter a valid sparse contrast need not make every edit
            # influential.
            # Comparison: DiCE (3/5) scores above LIME (2/5): the former valid diverse examples can
            # contain redundant edits; the latter an imperfect local fit can select misleading
            # features.
            # Calibration: Neutral bin: the evidence does not warrant a general stronger or weaker
            # claim on this exact property. A tie is not demonstrated empirical equivalence.
            # Evidence: qualitative comparative inference; see study cards for direct endpoints and
            # counterevidence. Confidence: moderate.
            # Sources: DICE, CEM, LIME. Comparative studies: E08. See documentation §6 for endpoints
            # and limits.
            # Primary locations: DICE: Diversity/proximity objectives, sparsity enhancement and
            # evaluated counterfactuals
            'no_false_positives': 3,
            # Rating 3/5; original=3; v3.3.11=3. retained after comparative review.
            # Reason: Diverse valid counterfactuals explore alternative outcomes but do not identify
            # every influence on the original prediction. Retain neutral 3 for contributor
            # accounting; diversity is not a feature-recall guarantee.
            # Comparison: DiCE (3/5) ties CEM (3/5): the former multiple contrasts still need not
            # list all influences; the latter one pertinent-positive/negative pair omits other
            # influences.
            # Comparison: DiCE (3/5) scores above LIME (2/5): the former multiple contrasts still
            # need not list all influences; the latter local sparsification can omit nonlinear
            # influences.
            # Calibration: Neutral bin: the evidence does not warrant a general stronger or weaker
            # claim on this exact property. A tie is not demonstrated empirical equivalence.
            # Evidence: qualitative comparative inference; see study cards for direct endpoints and
            # counterevidence. Confidence: moderate.
            # Sources: DICE, CEM, LIME. Comparative studies: E08. See documentation §6 for endpoints
            # and limits.
            # Primary locations: DICE: Diversity/proximity objectives, sparsity enhancement and
            # evaluated counterfactuals
            'no_false_negatives': 3,
            # Rating 3/5; original=3; v3.3.11=3. retained after comparative review.
            # Reason: Diversity improves local boundary coverage but is not a complete model
            # rationale.
            # Comparison: DiCE (3/5) scores below CEM (4/5): the former diverse examples cover more
            # boundary alternatives than one local fit; the latter present and absent evidence
            # provide complementary contrasts.
            # Comparison: DiCE (3/5) scores above LIME (2/5): the former diverse examples cover more
            # boundary alternatives than one local fit; the latter a sparse local approximation
            # covers only part of the rationale.
            # Calibration: Neutral bin: the evidence does not warrant a general stronger or weaker
            # claim on this exact property. A tie is not demonstrated empirical equivalence.
            # Evidence: qualitative comparative inference; see study cards for direct endpoints and
            # counterevidence. Confidence: moderate.
            # Sources: DICE, CEM, LIME. Comparative studies: E08. See documentation §6 for endpoints
            # and limits.
            # Primary locations: DICE: Diversity/proximity objectives, sparsity enhancement and
            # evaluated counterfactuals
            'completeness': 3,
            # Rating 1/5; original=1; v3.3.11=1. retained after comparative review.
            # Reason: Sampling or optimization choices can produce substantially different outputs.
            # Retain the original weakest comparative anchor for the standard unstabilized method;
            # this is not a universal failure claim.
            # Comparison: DiCE (1/5) scores below CEM (2/5): the former randomized non-convex search
            # may select very different recourse sets; the latter a non-convex sparse optimum can
            # switch under input changes.
            # Comparison: DiCE (1/5) ties LIME (1/5): the former randomized non-convex search may
            # select very different recourse sets; the latter local sampling and neighborhood
            # fitting can be highly sensitive.
            # Calibration: An inherited endpoint under the stated output/configuration, not a
            # universal guarantee or universal failure. The exact endpoint is low-confidence outside
            # that setting.
            # Evidence: qualitative comparative inference; see study cards for direct endpoints and
            # counterevidence. Confidence: low.
            # Sources: DICE, CEM, LIME, ROBUST, MAN_CHAN. Comparative studies: no matched direct
            # study located; mechanism/threat-model inference. See documentation §6 for endpoints
            # and limits.
            # Primary locations: DICE: Diversity/proximity objectives, sparsity enhancement and
            # evaluated counterfactuals
            'stability': 1,
            # Rating 3/5; original=4; v3.3.11=3. retained after comparative review.
            # Reason: A valid counterfactual can fail under model change; adversarial robustness is
            # not established by its validity objective.
            # Comparison: DiCE (3/5) ties CEM (3/5): the former validity at one model is not
            # explanation robustness; the latter contrast validity is not resistance to adversarial
            # manipulation.
            # Comparison: DiCE (3/5) scores above LIME (1/5): the former validity at one model is
            # not explanation robustness; the latter published deceptive-wrapper attacks can
            # redirect its attributions.
            # Calibration: Neutral bin: the evidence does not warrant a general stronger or weaker
            # claim on this exact property. A tie is not demonstrated empirical equivalence.
            # Evidence: qualitative comparative inference; see study cards for direct endpoints and
            # counterevidence. Confidence: low.
            # Sources: DICE, SHIFT, CEM, LIME, ATTACK, ROBUST. Comparative studies: no matched
            # direct study located; mechanism/threat-model inference. See documentation §6 for
            # endpoints and limits.
            # Primary locations: DICE: Diversity/proximity objectives, sparsity enhancement and
            # evaluated counterfactuals; SHIFT: Counterfactual robustness under data shift; not a
            # general adversarial guarantee
            'adversarial_robustness': 3,
            # Rating 1/5; original=1; v3.3.11=1. retained after comparative review.
            # Reason: Sampling or optimization choices can produce substantially different outputs.
            # Retain the original weakest comparative anchor for the standard unstabilized method;
            # this is not a universal failure claim.
            # Comparison: DiCE (1/5) scores below CEM (3/5): the former random starts and
            # alternative solutions affect repeatability; the latter the specified solver starts at
            # zero rather than randomly.
            # Comparison: DiCE (1/5) scores below LIME (2/5): the former random starts and
            # alternative solutions affect repeatability; the latter random perturbations vary
            # ranks, with mixed head-to-head evidence.
            # Calibration: An inherited endpoint under the stated output/configuration, not a
            # universal guarantee or universal failure. The exact endpoint is low-confidence outside
            # that setting.
            # Evidence: qualitative comparative inference; see study cards for direct endpoints and
            # counterevidence. Confidence: low.
            # Sources: DICE, SHIFT, CEM, LIME, MAN_CHAN. Comparative studies: no matched direct
            # study located; mechanism/threat-model inference. See documentation §6 for endpoints
            # and limits.
            # Primary locations: DICE: Diversity/proximity objectives, sparsity enhancement and
            # evaluated counterfactuals; SHIFT: Counterfactual robustness under data shift; not a
            # general adversarial guarantee
            'consistency': 1,
            # Rating 1/5; original=1; v3.3.11=1. retained after comparative review.
            # Reason: Sampling or optimization choices can produce substantially different outputs.
            # Retain the original weakest comparative anchor for the standard unstabilized method;
            # this is not a universal failure claim.
            # Comparison: DiCE (1/5) ties CEM (1/5): the former diversity, proximity and sparsity
            # weights alter outputs; the latter regularization and autoencoder choices can alter
            # selected sets.
            # Comparison: DiCE (1/5) ties LIME (1/5): the former diversity, proximity and sparsity
            # weights alter outputs; the latter kernel width, representation and feature count can
            # dominate output.
            # Calibration: An inherited endpoint under the stated output/configuration, not a
            # universal guarantee or universal failure. The exact endpoint is low-confidence outside
            # that setting.
            # Evidence: qualitative comparative inference; see study cards for direct endpoints and
            # counterevidence. Confidence: low.
            # Sources: DICE, CEM, LIME. Comparative studies: no matched direct study located;
            # mechanism/threat-model inference. See documentation §6 for endpoints and limits.
            # Primary locations: DICE: Diversity/proximity objectives, sparsity enhancement and
            # evaluated counterfactuals
            'hyperparameters_perturbation_robustness': 1,
            # Rating 4/5; original=4; v3.3.11=4. retained after comparative review.
            # Reason: Proximity and postprocessing favor few changes; minimality is conditional, not
            # guaranteed.
            # Comparison: DiCE (4/5) ties CEM (4/5): the former sparse recourse is encouraged
            # although several examples add size; the latter sparse optimization favors few retained
            # or added elements.
            # Comparison: DiCE (4/5) scores above LIME (3/5): the former sparse recourse is
            # encouraged although several examples add size; the latter an explicit feature budget
            # controls the delivered explanation.
            # Calibration: A qualified comparative strength. The integer is an ordinal coding
            # decision; neither the unit gap nor universal superiority/inferiority is measured.
            # Evidence: qualitative comparative inference; see study cards for direct endpoints and
            # counterevidence. Confidence: moderate.
            # Sources: DICE, CEM, LIME. Comparative studies: E08. See documentation §6 for endpoints
            # and limits.
            # Primary locations: DICE: Diversity/proximity objectives, sparsity enhancement and
            # evaluated counterfactuals
            'sparsity': 4,
            # Rating 3/5; original=3; v3.3.11=3. retained after comparative review.
            # Reason: Concrete feature changes give feature-level explanatory detail.
            # Comparison: DiCE (3/5) ties CEM (3/5): the former edited values convey counterfactual
            # direction but not full mechanisms; the latter changed and retained elements explain a
            # contrast without full rules.
            # Comparison: DiCE (3/5) scores above LIME (2/5): the former edited values convey
            # counterfactual direction but not full mechanisms; the latter a local linear
            # coefficient list omits explicit nonlinear rules.
            # Calibration: Neutral bin: the evidence does not warrant a general stronger or weaker
            # claim on this exact property. A tie is not demonstrated empirical equivalence.
            # Evidence: qualitative comparative inference; see study cards for direct endpoints and
            # counterevidence. Confidence: moderate.
            # Sources: DICE, CEM, LIME. Comparative studies: no matched direct study located;
            # mechanism/threat-model inference. See documentation §6 for endpoints and limits.
            # Primary locations: DICE: Diversity/proximity objectives, sparsity enhancement and
            # evaluated counterfactuals
            'level_of_detail': 3,
            # Rating 3/5; original=3; v3.3.11=3. retained after comparative review.
            # Reason: Candidate outputs can reveal sensitive behavior; no default privacy guarantee.
            # Comparison: DiCE (3/5) ties CEM (3/5): the former counterfactuals can expose private
            # records or boundaries; the latter a contrast may reveal sensitive inputs and decision
            # boundaries.
            # Comparison: DiCE (3/5) ties LIME (3/5): the former counterfactuals can expose private
            # records or boundaries; the latter a local summary still has no confidentiality
            # guarantee.
            # Calibration: Neutral bin: the evidence does not warrant a general stronger or weaker
            # claim on this exact property. A tie is not demonstrated empirical equivalence.
            # Evidence: qualitative comparative inference; see study cards for direct endpoints and
            # counterevidence. Confidence: low.
            # Sources: DICE, PRIVACY, CEM, LIME. Comparative studies: no matched direct study
            # located; mechanism/threat-model inference. See documentation §6 for endpoints and
            # limits.
            # Primary locations: DICE: Diversity/proximity objectives, sparsity enhancement and
            # evaluated counterfactuals; PRIVACY: §§3–5; direct evidence for tested
            # gradient/IG/LRP/LIME configurations; threat-model context only for other methods
            'confidentiality': 3,
            # Rating 3/5; original=2; v3.3.11=3. retained after comparative review.
            # Reason: Recording the model, input, random state and settings makes reconstruction
            # possible; use 3 rather than assuming either complete or inherently poor auditability.
            # Comparison: DiCE (3/5) ties CEM (3/5): the former seeds, constraints, objectives and
            # candidate outputs can be logged; the latter optimization states, constraints and
            # references must be retained.
            # Comparison: DiCE (3/5) ties LIME (3/5): the former seeds, constraints, objectives and
            # candidate outputs can be logged; the latter queries, seeds, neighborhood and fitted
            # surrogate must be recorded.
            # Calibration: Neutral bin: the evidence does not warrant a general stronger or weaker
            # claim on this exact property. A tie is not demonstrated empirical equivalence.
            # Evidence: qualitative comparative inference; see study cards for direct endpoints and
            # counterevidence. Confidence: moderate.
            # Sources: DICE, CEM, LIME. Comparative studies: no matched direct study located;
            # mechanism/threat-model inference. See documentation §6 for endpoints and limits.
            # Primary locations: DICE: Diversity/proximity objectives, sparsity enhancement and
            # evaluated counterfactuals
            'traceability': 3,
            # Rating 3/5; original=3; v3.3.11=3. retained after comparative review.
            # Reason: Finite candidate generation has moderate assumed cost; algorithm and
            # dimensionality can change this rating.
            # Comparison: DiCE (3/5) scores above CEM (2/5): the former repeated optimization costs
            # more than a direct forward/backward pass; the latter iterative optimization and
            # optional autoencoder training add burden.
            # Comparison: DiCE (3/5) ties LIME (3/5): the former repeated optimization costs more
            # than a direct forward/backward pass; the latter thousands of prediction calls are
            # typical, without gradient access.
            # Calibration: Neutral bin: the evidence does not warrant a general stronger or weaker
            # claim on this exact property. A tie is not demonstrated empirical equivalence.
            # Evidence: qualitative comparative inference; see study cards for direct endpoints and
            # counterevidence. Confidence: moderate.
            # Sources: DICE, CEM, LIME. Comparative studies: no matched direct study located;
            # mechanism/threat-model inference. See documentation §6 for endpoints and limits.
            # Primary locations: DICE: Diversity/proximity objectives, sparsity enhancement and
            # evaluated counterfactuals
            'runtime_performance_and_implementation_constraints': 3,
        },
        'scope_stage': 'local-expost',
        'explanation_target': 'model output',
        "question_types": {'how_modify_input', 'what_feature', 'what_if'},
    },
    # Weighted prototype selection summarizes data or a representation. Use for a model-output
    # question requires an explicit link between that reference representation and the predictor;
    # raw representativeness is not a decision explanation.
    'ProtoDash': {
        "subprops": {
            # Rating 3/5; original=3; v3.3.11=3. retained after comparative review.
            # Reason: Weighted prototypes summarize a selected distribution or representation;
            # representativeness alone does not establish which factors influenced a model output.
            # The retained 3 is an evidence-limited prior for model-linked use, not evidence of
            # feature necessity.
            # Comparison: ProtoDash (3/5) ties Anchors (3/5): the former representativeness is not a
            # proof of model influence; the latter conditional rule precision does not prove
            # predicate necessity.
            # Comparison: ProtoDash (3/5) ties DiCE (3/5): the former representativeness is not a
            # proof of model influence; the latter valid diverse examples can contain redundant
            # edits.
            # Calibration: Neutral bin: the evidence does not warrant a general stronger or weaker
            # claim on this exact property. A tie is not demonstrated empirical equivalence.
            # Evidence: qualitative comparative inference; see study cards for direct endpoints and
            # counterevidence. Confidence: low.
            # Sources: PROTO, ANCHORS, DICE. Comparative studies: no matched direct study located;
            # mechanism/threat-model inference. See documentation §6 for endpoints and limits.
            # Primary locations: PROTO: Weighted prototype objective and greedy algorithm guarantees
            'no_false_positives': 3,
            # Rating 3/5; original=3; v3.3.11=3. retained after comparative review.
            # Reason: A finite prototype set can miss rare patterns, and distributional coverage is
            # not recall of all model influences. Retain evidence-limited 3; an application must
            # first connect the reference distribution or representation to the model output being
            # explained.
            # Comparison: ProtoDash (3/5) ties Anchors (3/5): the former finite representatives can
            # omit rare model-linked patterns; the latter one sufficient rule need not enumerate all
            # influences.
            # Comparison: ProtoDash (3/5) ties DiCE (3/5): the former finite representatives can
            # omit rare model-linked patterns; the latter multiple contrasts still need not list all
            # influences.
            # Calibration: Neutral bin: the evidence does not warrant a general stronger or weaker
            # claim on this exact property. A tie is not demonstrated empirical equivalence.
            # Evidence: qualitative comparative inference; see study cards for direct endpoints and
            # counterevidence. Confidence: low.
            # Sources: PROTO, ANCHORS, DICE. Comparative studies: no matched direct study located;
            # mechanism/threat-model inference. See documentation §6 for endpoints and limits.
            # Primary locations: PROTO: Weighted prototype objective and greedy algorithm guarantees
            'no_false_negatives': 3,
            # Rating 2/5; original=2; v3.3.11=2. retained after comparative review.
            # Reason: Distributional representation is partial, not full decision rationale.
            # Comparison: ProtoDash (2/5) scores below Anchors (3/5): the former a weighted sample
            # is a partial representation of behavior; the latter a validated region supplies more
            # coverage information than an unqualified local fit.
            # Comparison: ProtoDash (2/5) scores below DiCE (3/5): the former a weighted sample is a
            # partial representation of behavior; the latter diverse examples cover more boundary
            # alternatives than one local fit.
            # Calibration: A below-neutral limitation. The integer is an ordinal coding decision;
            # neither the unit gap nor universal superiority/inferiority is measured.
            # Evidence: qualitative comparative inference; see study cards for direct endpoints and
            # counterevidence. Confidence: moderate.
            # Sources: PROTO, ANCHORS, DICE. Comparative studies: E16. See documentation §6 for
            # endpoints and limits.
            # Primary locations: PROTO: Weighted prototype objective and greedy algorithm guarantees
            'completeness': 2,
            # Rating 3/5; original=3; v3.3.11=3. retained after comparative review.
            # Reason: Approximation guarantees for selection quality do not imply input stability.
            # Comparison: ProtoDash (3/5) scores above Anchors (1/5): the former selection
            # guarantees concern fit quality, not local continuity; the latter sampled rule search
            # can change the selected conjunction.
            # Comparison: ProtoDash (3/5) scores above DiCE (1/5): the former selection guarantees
            # concern fit quality, not local continuity; the latter randomized non-convex search may
            # select very different recourse sets.
            # Calibration: Neutral bin: the evidence does not warrant a general stronger or weaker
            # claim on this exact property. A tie is not demonstrated empirical equivalence.
            # Evidence: qualitative comparative inference; see study cards for direct endpoints and
            # counterevidence. Confidence: low.
            # Sources: PROTO, ANCHORS, DICE. Comparative studies: no matched direct study located;
            # mechanism/threat-model inference. See documentation §6 for endpoints and limits.
            # Primary locations: PROTO: Weighted prototype objective and greedy algorithm guarantees
            'stability': 3,
            # Rating 3/5; original=3; v3.3.11=3. retained after comparative review.
            # Reason: No general explanation attack evaluation establishes high or low resistance;
            # retain neutral.
            # Comparison: ProtoDash (3/5) ties Anchors (3/5): the former no general
            # explanation-attack protection is established; the latter the precision guarantee is
            # distributional, not adversarial.
            # Comparison: ProtoDash (3/5) ties DiCE (3/5): the former no general explanation-attack
            # protection is established; the latter validity at one model is not explanation
            # robustness.
            # Calibration: Neutral bin: the evidence does not warrant a general stronger or weaker
            # claim on this exact property. A tie is not demonstrated empirical equivalence.
            # Evidence: qualitative comparative inference; see study cards for direct endpoints and
            # counterevidence. Confidence: low.
            # Sources: PROTO, ANCHORS, DICE, SHIFT. Comparative studies: no matched direct study
            # located; mechanism/threat-model inference. See documentation §6 for endpoints and
            # limits.
            # Primary locations: PROTO: Weighted prototype objective and greedy algorithm guarantees
            'adversarial_robustness': 3,
            # Rating 3/5; original=3; v3.3.11=3. retained after comparative review.
            # Reason: Fixed inputs and tie rules enable repeatability, without guaranteeing
            # sample-to-sample consistency.
            # Comparison: ProtoDash (3/5) scores above Anchors (1/5): the former fixed candidates
            # permit reproducible selection, subject to ties; the latter sampling may select
            # different qualifying rules.
            # Comparison: ProtoDash (3/5) scores above DiCE (1/5): the former fixed candidates
            # permit reproducible selection, subject to ties; the latter random starts and
            # alternative solutions affect repeatability.
            # Calibration: Neutral bin: the evidence does not warrant a general stronger or weaker
            # claim on this exact property. A tie is not demonstrated empirical equivalence.
            # Evidence: qualitative comparative inference; see study cards for direct endpoints and
            # counterevidence. Confidence: low.
            # Sources: PROTO, ANCHORS, DICE, SHIFT. Comparative studies: no matched direct study
            # located; mechanism/threat-model inference. See documentation §6 for endpoints and
            # limits.
            # Primary locations: PROTO: Weighted prototype objective and greedy algorithm guarantees
            'consistency': 3,
            # Rating 3/5; original=3; v3.3.11=3. retained after comparative review.
            # Reason: Retain the original comparative rating: Kernel, bandwidth and prototype count
            # alter the selected representatives.
            # Comparison: ProtoDash (3/5) scores above Anchors (2/5): the former kernel choice and
            # prototype budget affect selection; the latter precision threshold and perturbation
            # distribution shape the rule.
            # Comparison: ProtoDash (3/5) scores above DiCE (1/5): the former kernel choice and
            # prototype budget affect selection; the latter diversity, proximity and sparsity
            # weights alter outputs.
            # Calibration: Neutral bin: the evidence does not warrant a general stronger or weaker
            # claim on this exact property. A tie is not demonstrated empirical equivalence.
            # Evidence: qualitative comparative inference; see study cards for direct endpoints and
            # counterevidence. Confidence: low.
            # Sources: PROTO, ANCHORS, DICE. Comparative studies: no matched direct study located;
            # mechanism/threat-model inference. See documentation §6 for endpoints and limits.
            # Primary locations: PROTO: Weighted prototype objective and greedy algorithm guarantees
            'hyperparameters_perturbation_robustness': 3,
            # Rating 4/5; original=4; v3.3.11=4. retained after comparative review.
            # Reason: A small weighted subset explicitly promotes compact representation.
            # Comparison: ProtoDash (4/5) ties Anchors (4/5): the former a small explicit prototype
            # budget controls output size; the latter short sufficient conjunctions are the explicit
            # search target.
            # Comparison: ProtoDash (4/5) ties DiCE (4/5): the former a small explicit prototype
            # budget controls output size; the latter sparse recourse is encouraged although several
            # examples add size.
            # Calibration: A qualified comparative strength. The integer is an ordinal coding
            # decision; neither the unit gap nor universal superiority/inferiority is measured.
            # Evidence: qualitative comparative inference; see study cards for direct endpoints and
            # counterevidence. Confidence: moderate.
            # Sources: PROTO, ANCHORS, DICE. Comparative studies: E16. See documentation §6 for
            # endpoints and limits.
            # Primary locations: PROTO: Weighted prototype objective and greedy algorithm guarantees
            'sparsity': 4,
            # Rating 3/5; original=3; v3.3.11=3. retained after comparative review.
            # Reason: Representative records show examples, not full decision rules.
            # Comparison: ProtoDash (3/5) ties Anchors (3/5): the former examples and weights
            # describe similarities rather than decision rules; the latter a local conjunction
            # exposes conditions but not a full decision function.
            # Comparison: ProtoDash (3/5) ties DiCE (3/5): the former examples and weights describe
            # similarities rather than decision rules; the latter edited values convey
            # counterfactual direction but not full mechanisms.
            # Calibration: Neutral bin: the evidence does not warrant a general stronger or weaker
            # claim on this exact property. A tie is not demonstrated empirical equivalence.
            # Evidence: qualitative comparative inference; see study cards for direct endpoints and
            # counterevidence. Confidence: moderate.
            # Sources: PROTO, ANCHORS, DICE. Comparative studies: no matched direct study located;
            # mechanism/threat-model inference. See documentation §6 for endpoints and limits.
            # Primary locations: PROTO: Weighted prototype objective and greedy algorithm guarantees
            'level_of_detail': 3,
            # Rating 2/5; original=2; v3.3.11=2. retained after comparative review.
            # Reason: Releasing actual prototypes can disclose source records; assumes unprotected
            # examples are shown.
            # Comparison: ProtoDash (2/5) scores below Anchors (3/5): the former releasing real
            # prototypes can disclose the represented records; the latter a short local rule can
            # still reveal sensitive decision criteria.
            # Comparison: ProtoDash (2/5) scores below DiCE (3/5): the former releasing real
            # prototypes can disclose the represented records; the latter counterfactuals can expose
            # private records or boundaries.
            # Calibration: A below-neutral limitation. The integer is an ordinal coding decision;
            # neither the unit gap nor universal superiority/inferiority is measured.
            # Evidence: qualitative comparative inference; see study cards for direct endpoints and
            # counterevidence. Confidence: low.
            # Sources: PROTO, PRIVACY, ANCHORS, DICE. Comparative studies: no matched direct study
            # located; mechanism/threat-model inference. See documentation §6 for endpoints and
            # limits.
            # Primary locations: PROTO: Weighted prototype objective and greedy algorithm
            # guarantees; PRIVACY: §§3–5; direct evidence for tested gradient/IG/LRP/LIME
            # configurations; threat-model context only for other methods
            'confidentiality': 2,
            # Rating 4/5; original=4; v3.3.11=4. retained after comparative review.
            # Reason: Selection steps, weights, kernel and candidates can be archived.
            # Comparison: ProtoDash (4/5) scores above Anchors (3/5): the former stored examples,
            # weights and selection records are inspectable; the latter sampling and rule-selection
            # records are required for reconstruction.
            # Comparison: ProtoDash (4/5) scores above DiCE (3/5): the former stored examples,
            # weights and selection records are inspectable; the latter seeds, constraints,
            # objectives and candidate outputs can be logged.
            # Calibration: A qualified comparative strength. The integer is an ordinal coding
            # decision; neither the unit gap nor universal superiority/inferiority is measured.
            # Evidence: qualitative comparative inference; see study cards for direct endpoints and
            # counterevidence. Confidence: moderate.
            # Sources: PROTO, ANCHORS, DICE. Comparative studies: no matched direct study located;
            # mechanism/threat-model inference. See documentation §6 for endpoints and limits.
            # Primary locations: PROTO: Weighted prototype objective and greedy algorithm guarantees
            'traceability': 4,
            # Rating 3/5; original=2; v3.3.11=3. retained after comparative review.
            # Reason: Greedy selection avoids exhaustive subset search; no universal quadratic-cost
            # verdict is justified.
            # Comparison: ProtoDash (3/5) ties DiCE (3/5): the former gradient-based greedy
            # selection reduces cost relative to ProtoGreedy; the latter repeated optimization costs
            # more than a direct forward/backward pass.
            # Comparison: ProtoDash (3/5) scores above Exact local SHAP (1/5): the former
            # gradient-based greedy selection reduces cost relative to ProtoGreedy; the latter
            # generic exact evaluation scales exponentially in varying features.
            # Calibration: Neutral bin: the evidence does not warrant a general stronger or weaker
            # claim on this exact property. A tie is not demonstrated empirical equivalence.
            # Evidence: qualitative comparative inference; see study cards for direct endpoints and
            # counterevidence. Confidence: moderate.
            # Sources: PROTO, DICE, SHAP, EXACT. Comparative studies: E16. See documentation §6 for
            # endpoints and limits.
            # Primary locations: PROTO: Weighted prototype objective and greedy algorithm guarantees
            'runtime_performance_and_implementation_constraints': 3,
        },
        'scope_stage': 'local-expost',
        'explanation_target': 'model output',
        "question_types": {'how_differs'},
    },
    # Exact allocation for one observation and specified coalition value function.
    'Exact local SHAP': {
        "subprops": {
            # Rating 3/5; original=5; v3.3.11=4. corrected in this review.
            # Reason: Corrected 4 to 3: exactness removes numerical estimation error for a chosen
            # coalition game, but the game can still allocate influence differently from the
            # model-decision relevance required here. Conditional and baseline games are not
            # interchangeable. Tie approximate SHAP at 3 for generic necessity; exactness remains an
            # advantage in numerical fidelity, which is not a separate property in this rubric.
            # Comparison: Exact local SHAP (3/5) ties Approximate local SHAP (3/5): the former exact
            # game allocation is not generic decision-feature necessity; the latter sampling error
            # and game semantics both require validation.
            # Comparison: Exact local SHAP (3/5) scores above LIME (2/5): the former exact game
            # allocation is not generic decision-feature necessity; the latter an imperfect local
            # fit can select misleading features.
            # Calibration: Neutral bin: the evidence does not warrant a general stronger or weaker
            # claim on this exact property. A tie is not demonstrated empirical equivalence.
            # Evidence: qualitative comparative inference; see study cards for direct endpoints and
            # counterevidence. Confidence: low.
            # Sources: SHAP, RELEVANCE, MANY_SHAP, KERNEL, LIME. Comparative studies: E01, E20. See
            # documentation §6 for endpoints and limits.
            # Primary locations: SHAP: SHAP §§2–4; relevance counterexamples; Many Shapley Values
            # §§3–4; RELEVANCE: SHAP §§2–4; relevance counterexamples; Many Shapley Values §§3–4;
            # MANY_SHAP: SHAP §§2–4; relevance counterexamples; Many Shapley Values §§3–4
            'no_false_positives': 3,
            # Rating 3/5; original=5; v3.3.11=4. corrected in this review.
            # Reason: Corrected 4 to 3: enumerating coalitions does not ensure a nonzero attribution
            # for every decision-relevant feature; averaging marginal effects can cancel. Tie
            # approximate SHAP and DeepLIFT at 3 for generic contributor recall. The absence of
            # sampling error alone does not establish their ordering on this different construct.
            # Comparison: Exact local SHAP (3/5) ties Approximate local SHAP (3/5): the former
            # coalition averaging can assign zero to decision-relevant features; the latter
            # regularized finite sampling can suppress contributions.
            # Comparison: Exact local SHAP (3/5) ties DeepLift (3/5): the former coalition averaging
            # can assign zero to decision-relevant features; the latter summation-to-delta does not
            # certify contributor recall.
            # Calibration: Neutral bin: the evidence does not warrant a general stronger or weaker
            # claim on this exact property. A tie is not demonstrated empirical equivalence.
            # Evidence: qualitative comparative inference; see study cards for direct endpoints and
            # counterevidence. Confidence: low.
            # Sources: SHAP, RELEVANCE, KERNEL, DEEPLIFT, SIXT. Comparative studies: E01, E20. See
            # documentation §6 for endpoints and limits.
            # Primary locations: SHAP: SHAP attribution definition; Huang & Marques-Silva
            # counterexamples and discussion; RELEVANCE: SHAP attribution definition; Huang &
            # Marques-Silva counterexamples and discussion
            'no_false_negatives': 3,
            # Rating 3/5; original=3; v3.3.11=3. retained after comparative review.
            # Reason: Additive local accuracy is not full decision rationale.
            # Comparison: Exact local SHAP (3/5) scores above LIME (2/5): the former an additive
            # allocation is not a complete rationale; the latter a sparse local approximation covers
            # only part of the rationale.
            # Comparison: Exact local SHAP (3/5) ties Approximate local SHAP (3/5): the former an
            # additive allocation is not a complete rationale; the latter approximate additivity is
            # not complete rationale coverage.
            # Calibration: Neutral bin: the evidence does not warrant a general stronger or weaker
            # claim on this exact property. A tie is not demonstrated empirical equivalence.
            # Evidence: qualitative comparative inference; see study cards for direct endpoints and
            # counterevidence. Confidence: moderate.
            # Sources: SHAP, LIME, KERNEL. Comparative studies: E01, E20. See documentation §6 for
            # endpoints and limits.
            # Primary locations: SHAP: Additive explanation definition, local accuracy, missingness
            # and consistency
            'completeness': 3,
            # Rating 3/5; original=4; v3.3.11=3. retained after comparative review.
            # Reason: Exact computation does not imply continuity under changes to inputs or
            # background.
            # Comparison: Exact local SHAP (3/5) scores above LIME (1/5): the former exactness
            # removes sampling noise, not input sensitivity; the latter local sampling and
            # neighborhood fitting can be highly sensitive.
            # Comparison: Exact local SHAP (3/5) scores above Approximate local SHAP (2/5): the
            # former exactness removes sampling noise, not input sensitivity; the latter sampling
            # adds variation to the game’s input dependence.
            # Calibration: Neutral bin: the evidence does not warrant a general stronger or weaker
            # claim on this exact property. A tie is not demonstrated empirical equivalence.
            # Evidence: qualitative comparative inference; see study cards for direct endpoints and
            # counterevidence. Confidence: low.
            # Sources: SHAP, LIME, ROBUST, MAN_CHAN, KERNEL. Comparative studies: no matched direct
            # study located; mechanism/threat-model inference. See documentation §6 for endpoints
            # and limits.
            # Primary locations: SHAP: Additive explanation definition, local accuracy, missingness
            # and consistency
            'stability': 3,
            # Rating 3/5; original=4; v3.3.11=3. retained after comparative review.
            # Reason: No general adversarial guarantee follows from Shapley axioms; neutral remains
            # evidence-limited.
            # Comparison: Exact local SHAP (3/5) scores above LIME (1/5): the former exactness is
            # not a manipulation-resistance theorem; the latter published deceptive-wrapper attacks
            # can redirect its attributions.
            # Comparison: Exact local SHAP (3/5) scores above Approximate local SHAP (2/5): the
            # former exactness is not a manipulation-resistance theorem; the latter finite-budget
            # perturbation explainers have published attacks.
            # Calibration: Neutral bin: the evidence does not warrant a general stronger or weaker
            # claim on this exact property. A tie is not demonstrated empirical equivalence.
            # Evidence: qualitative comparative inference; see study cards for direct endpoints and
            # counterevidence. Confidence: low.
            # Sources: SHAP, LIME, ATTACK, ROBUST, KERNEL. Comparative studies: no matched direct
            # study located; mechanism/threat-model inference. See documentation §6 for endpoints
            # and limits.
            # Primary locations: SHAP: Additive explanation definition, local accuracy, missingness
            # and consistency
            'adversarial_robustness': 3,
            # Rating 3/5; original=5; v3.3.11=3. retained after comparative review.
            # Reason: Shapley consistency is not the retained rubric consistency across instances,
            # model runs and time; correct 5 to 3.
            # Comparison: Exact local SHAP (3/5) scores above LIME (2/5): the former fixed-game
            # repeatability is narrower than temporal consistency; the latter random perturbations
            # vary ranks, with mixed head-to-head evidence.
            # Comparison: Exact local SHAP (3/5) scores above Approximate local SHAP (2/5): the
            # former fixed-game repeatability is narrower than temporal consistency; the latter
            # finite sampling makes repeated estimates vary.
            # Calibration: Neutral bin: the evidence does not warrant a general stronger or weaker
            # claim on this exact property. A tie is not demonstrated empirical equivalence.
            # Evidence: qualitative comparative inference; see study cards for direct endpoints and
            # counterevidence. Confidence: low.
            # Sources: SHAP, LIME, MAN_CHAN, KERNEL. Comparative studies: no matched direct study
            # located; mechanism/threat-model inference. See documentation §6 for endpoints and
            # limits.
            # Primary locations: SHAP: Additive explanation definition, local accuracy, missingness
            # and consistency
            'consistency': 3,
            # Rating 3/5; original=3; v3.3.11=3. retained after comparative review.
            # Reason: Masker and background define the allocation problem; neutral does not imply
            # invariance to their choice.
            # Comparison: Exact local SHAP (3/5) scores above LIME (1/5): the former background and
            # coalition-game choices still matter; the latter kernel width, representation and
            # feature count can dominate output.
            # Comparison: Exact local SHAP (3/5) scores above Approximate local SHAP (2/5): the
            # former background and coalition-game choices still matter; the latter sample budget,
            # regularization and background affect attribution.
            # Calibration: Neutral bin: the evidence does not warrant a general stronger or weaker
            # claim on this exact property. A tie is not demonstrated empirical equivalence.
            # Evidence: qualitative comparative inference; see study cards for direct endpoints and
            # counterevidence. Confidence: low.
            # Sources: SHAP, LIME, KERNEL. Comparative studies: E20. See documentation §6 for
            # endpoints and limits.
            # Primary locations: SHAP: Additive explanation definition, local accuracy, missingness
            # and consistency
            'hyperparameters_perturbation_robustness': 3,
            # Rating 3/5; original=3; v3.3.11=3. retained after comparative review.
            # Reason: Feature attributions can be dense or truncated for presentation. Retain the
            # original neutral rating; selection does not establish minimality.
            # Comparison: Exact local SHAP (3/5) ties LIME (3/5): the former exact allocation
            # typically returns a full feature vector; the latter an explicit feature budget
            # controls the delivered explanation.
            # Comparison: Exact local SHAP (3/5) ties Approximate local SHAP (3/5): the former exact
            # allocation typically returns a full feature vector; the latter full values or a
            # selected display are not guaranteed minimal.
            # Calibration: Neutral bin: the evidence does not warrant a general stronger or weaker
            # claim on this exact property. A tie is not demonstrated empirical equivalence.
            # Evidence: qualitative comparative inference; see study cards for direct endpoints and
            # counterevidence. Confidence: moderate.
            # Sources: SHAP, LIME, KERNEL. Comparative studies: no matched direct study located;
            # mechanism/threat-model inference. See documentation §6 for endpoints and limits.
            # Primary locations: SHAP: Additive explanation definition, local accuracy, missingness
            # and consistency
            'sparsity': 3,
            # Rating 3/5; original=3; v3.3.11=3. retained after comparative review.
            # Reason: Feature allocations provide intermediate detail, not explicit decision rules.
            # Comparison: Exact local SHAP (3/5) scores above LIME (2/5): the former per-feature
            # values do not expose the whole interaction mechanism; the latter a local linear
            # coefficient list omits explicit nonlinear rules.
            # Comparison: Exact local SHAP (3/5) ties Approximate local SHAP (3/5): the former
            # per-feature values do not expose the whole interaction mechanism; the latter feature
            # allocations retain the same output form as exact SHAP.
            # Calibration: Neutral bin: the evidence does not warrant a general stronger or weaker
            # claim on this exact property. A tie is not demonstrated empirical equivalence.
            # Evidence: qualitative comparative inference; see study cards for direct endpoints and
            # counterevidence. Confidence: moderate.
            # Sources: SHAP, LIME, KERNEL. Comparative studies: no matched direct study located;
            # mechanism/threat-model inference. See documentation §6 for endpoints and limits.
            # Primary locations: SHAP: Additive explanation definition, local accuracy, missingness
            # and consistency
            'level_of_detail': 3,
            # Rating 3/5; original=3; v3.3.11=3. retained after comparative review.
            # Reason: Local exact attribution supplies no inherent privacy protection.
            # Comparison: Exact local SHAP (3/5) ties LIME (3/5): the former local values have no
            # inherent confidentiality guarantee; the latter a local summary still has no
            # confidentiality guarantee.
            # Comparison: Exact local SHAP (3/5) ties Approximate local SHAP (3/5): the former local
            # values have no inherent confidentiality guarantee; the latter local estimated values
            # are not privacy-protected.
            # Calibration: Neutral bin: the evidence does not warrant a general stronger or weaker
            # claim on this exact property. A tie is not demonstrated empirical equivalence.
            # Evidence: qualitative comparative inference; see study cards for direct endpoints and
            # counterevidence. Confidence: low.
            # Sources: SHAP, PRIVACY, LIME, KERNEL. Comparative studies: no matched direct study
            # located; mechanism/threat-model inference. See documentation §6 for endpoints and
            # limits.
            # Primary locations: SHAP: Additive explanation definition, local accuracy, missingness
            # and consistency; PRIVACY: §§3–5; direct evidence for tested gradient/IG/LRP/LIME
            # configurations; threat-model context only for other methods
            'confidentiality': 3,
            # Rating 4/5; original=5; v3.3.11=4. retained after comparative review.
            # Reason: A specified computation can be reconstructed if model, input, reference or
            # propagation settings and software versions are retained. This supports strong
            # traceability, but the method supplies no complete audit trail or accountability
            # process; the retained rubric does not justify 5 from determinism alone.
            # Comparison: Exact local SHAP (4/5) scores above LIME (3/5): the former a fixed value
            # function and coalitions allow reconstruction; the latter queries, seeds, neighborhood
            # and fitted surrogate must be recorded.
            # Comparison: Exact local SHAP (4/5) ties Approximate local SHAP (4/5): the former a
            # fixed value function and coalitions allow reconstruction; the latter seeds, coalition
            # queries and regression settings can be logged.
            # Calibration: A qualified comparative strength. The integer is an ordinal coding
            # decision; neither the unit gap nor universal superiority/inferiority is measured.
            # Evidence: qualitative comparative inference; see study cards for direct endpoints and
            # counterevidence. Confidence: moderate.
            # Sources: SHAP, LIME, KERNEL. Comparative studies: no matched direct study located;
            # mechanism/threat-model inference. See documentation §6 for endpoints and limits.
            # Primary locations: SHAP: Additive explanation definition, local accuracy, missingness
            # and consistency
            'traceability': 4,
            # Rating 1/5; original=1; v3.3.11=1. retained after comparative review.
            # Reason: Generic enumeration is exponentially expensive; specialized exact tree/linear
            # methods are excluded from this profile.
            # Comparison: Exact local SHAP (1/5) scores below LIME (3/5): the former generic exact
            # evaluation scales exponentially in varying features; the latter thousands of
            # prediction calls are typical, without gradient access.
            # Comparison: Exact local SHAP (1/5) scores below Approximate local SHAP (2/5): the
            # former generic exact evaluation scales exponentially in varying features; the latter
            # finite coalition sampling avoids full exponential enumeration.
            # Calibration: An inherited endpoint under the stated output/configuration, not a
            # universal guarantee or universal failure. The exact endpoint is low-confidence outside
            # that setting.
            # Evidence: qualitative comparative inference; see study cards for direct endpoints and
            # counterevidence. Confidence: low.
            # Sources: SHAP, EXACT, LIME, KERNEL. Comparative studies: E01. See documentation §6 for
            # endpoints and limits.
            # Primary locations: SHAP: Additive explanation definition, local accuracy, missingness
            # and consistency; EXACT: ExactExplainer computational complexity and masking
            # assumptions
            'runtime_performance_and_implementation_constraints': 1,
        },
        'scope_stage': 'local-expost',
        'explanation_target': 'model output',
        "question_types": {'what_feature'},
    },
    # Finite-budget sampled KernelSHAP-like estimator, not a fully enumerated solution.
    'Approximate local SHAP': {
        "subprops": {
            # Rating 3/5; original=None; v3.3.11=3. retained after comparative review.
            # Reason: Sampling adds estimation error, but even exact coalition allocation is not a
            # generic feature-necessity certificate. Retain neutral 3, tied with exact SHAP on this
            # property; numerical accuracy and decision relevance must be evaluated separately.
            # Comparison: Approximate local SHAP (3/5) scores above LIME (2/5): the former sampling
            # error and game semantics both require validation; the latter an imperfect local fit
            # can select misleading features.
            # Comparison: Approximate local SHAP (3/5) ties Exact local SHAP (3/5): the former
            # sampling error and game semantics both require validation; the latter exact game
            # allocation is not generic decision-feature necessity.
            # Calibration: Neutral bin: the evidence does not warrant a general stronger or weaker
            # claim on this exact property. A tie is not demonstrated empirical equivalence.
            # Evidence: qualitative comparative inference; see study cards for direct endpoints and
            # counterevidence. Confidence: moderate.
            # Sources: KERNEL, RELEVANCE, LIME, SHAP, MANY_SHAP. Comparative studies: E01, E02, E11,
            # E20. See documentation §6 for endpoints and limits.
            # Primary locations: KERNEL: KernelExplainer weighted regression; nsamples and l1_reg
            # parameters; RELEVANCE: Formal relevance definitions and Shapley-value counterexamples
            'no_false_positives': 3,
            # Rating 3/5; original=None; v3.3.11=3. retained after comparative review.
            # Reason: Sampling and regularization may suppress effects; exact allocation can also
            # yield zero for a decision-relevant feature. Retain neutral 3, tied with exact SHAP for
            # generic contributor recall, without claiming equal numerical estimation accuracy.
            # Comparison: Approximate local SHAP (3/5) scores above LIME (2/5): the former
            # regularized finite sampling can suppress contributions; the latter local
            # sparsification can omit nonlinear influences.
            # Comparison: Approximate local SHAP (3/5) ties Exact local SHAP (3/5): the former
            # regularized finite sampling can suppress contributions; the latter coalition averaging
            # can assign zero to decision-relevant features.
            # Calibration: Neutral bin: the evidence does not warrant a general stronger or weaker
            # claim on this exact property. A tie is not demonstrated empirical equivalence.
            # Evidence: qualitative comparative inference; see study cards for direct endpoints and
            # counterevidence. Confidence: low.
            # Sources: KERNEL, RELEVANCE, LIME, SHAP. Comparative studies: E01, E02, E11, E20. See
            # documentation §6 for endpoints and limits.
            # Primary locations: KERNEL: KernelExplainer weighted regression; nsamples and l1_reg
            # parameters; RELEVANCE: Formal relevance definitions and Shapley-value counterexamples
            'no_false_negatives': 3,
            # Rating 3/5; original=None; v3.3.11=3. retained after comparative review.
            # Reason: Local reconstruction does not establish full explanatory coverage.
            # Comparison: Approximate local SHAP (3/5) scores above LIME (2/5): the former
            # approximate additivity is not complete rationale coverage; the latter a sparse local
            # approximation covers only part of the rationale.
            # Comparison: Approximate local SHAP (3/5) ties Exact local SHAP (3/5): the former
            # approximate additivity is not complete rationale coverage; the latter an additive
            # allocation is not a complete rationale.
            # Calibration: Neutral bin: the evidence does not warrant a general stronger or weaker
            # claim on this exact property. A tie is not demonstrated empirical equivalence.
            # Evidence: qualitative comparative inference; see study cards for direct endpoints and
            # counterevidence. Confidence: moderate.
            # Sources: KERNEL, LIME, SHAP. Comparative studies: E01, E20. See documentation §6 for
            # endpoints and limits.
            # Primary locations: KERNEL: KernelExplainer weighted regression; nsamples and l1_reg
            # parameters
            'completeness': 3,
            # Rating 2/5; original=None; v3.3.11=2. retained after comparative review.
            # Reason: Sampling introduces variation in addition to input and background sensitivity.
            # Comparison: Approximate local SHAP (2/5) scores above LIME (1/5): the former sampling
            # adds variation to the game’s input dependence; the latter local sampling and
            # neighborhood fitting can be highly sensitive.
            # Comparison: Approximate local SHAP (2/5) scores below Exact local SHAP (3/5): the
            # former sampling adds variation to the game’s input dependence; the latter exactness
            # removes sampling noise, not input sensitivity.
            # Calibration: A below-neutral limitation. The integer is an ordinal coding decision;
            # neither the unit gap nor universal superiority/inferiority is measured.
            # Evidence: qualitative comparative inference; see study cards for direct endpoints and
            # counterevidence. Confidence: low.
            # Sources: KERNEL, MAN_CHAN, LIME, ROBUST, SHAP. Comparative studies: E02, E03. See
            # documentation §6 for endpoints and limits.
            # Primary locations: KERNEL: KernelExplainer weighted regression; nsamples and l1_reg
            # parameters; MAN_CHAN: §§2–3: repeated-rank variability, not small-input continuity
            'stability': 2,
            # Rating 2/5; original=None; v3.3.11=2. retained after comparative review.
            # Reason: Published perturbation-based attacks support a below-neutral rating for the
            # sampled scenario.
            # Comparison: Approximate local SHAP (2/5) scores above LIME (1/5): the former
            # finite-budget perturbation explainers have published attacks; the latter published
            # deceptive-wrapper attacks can redirect its attributions.
            # Comparison: Approximate local SHAP (2/5) scores below Exact local SHAP (3/5): the
            # former finite-budget perturbation explainers have published attacks; the latter
            # exactness is not a manipulation-resistance theorem.
            # Calibration: A below-neutral limitation. The integer is an ordinal coding decision;
            # neither the unit gap nor universal superiority/inferiority is measured.
            # Evidence: qualitative comparative inference; see study cards for direct endpoints and
            # counterevidence. Confidence: low.
            # Sources: KERNEL, ATTACK, LIME, ROBUST, SHAP. Comparative studies: E03, E11. See
            # documentation §6 for endpoints and limits.
            # Primary locations: KERNEL: KernelExplainer weighted regression; nsamples and l1_reg
            # parameters; ATTACK: Scaffolded classifiers exploiting off-distribution perturbation
            # queries
            'adversarial_robustness': 2,
            # Rating 2/5; original=None; v3.3.11=2. retained after comparative review.
            # Reason: Finite-sample estimates can differ across runs; fixed-seed replay does not
            # guarantee general consistency.
            # Comparison: Approximate local SHAP (2/5) ties LIME (2/5): the former finite sampling
            # makes repeated estimates vary; the latter random perturbations vary ranks, with mixed
            # head-to-head evidence.
            # Comparison: Approximate local SHAP (2/5) scores below Exact local SHAP (3/5): the
            # former finite sampling makes repeated estimates vary; the latter fixed-game
            # repeatability is narrower than temporal consistency.
            # Calibration: A below-neutral limitation. The integer is an ordinal coding decision;
            # neither the unit gap nor universal superiority/inferiority is measured.
            # Evidence: qualitative comparative inference; see study cards for direct endpoints and
            # counterevidence. Confidence: low.
            # Sources: KERNEL, MAN_CHAN, LIME, SHAP. Comparative studies: E02. See documentation §6
            # for endpoints and limits.
            # Primary locations: KERNEL: KernelExplainer weighted regression; nsamples and l1_reg
            # parameters; MAN_CHAN: §§2–3: repeated-rank variability, not small-input continuity
            'consistency': 2,
            # Rating 2/5; original=None; v3.3.11=2. retained after comparative review.
            # Reason: Budget, regularization and background can materially affect estimates.
            # Comparison: Approximate local SHAP (2/5) scores above LIME (1/5): the former sample
            # budget, regularization and background affect attribution; the latter kernel width,
            # representation and feature count can dominate output.
            # Comparison: Approximate local SHAP (2/5) scores below Exact local SHAP (3/5): the
            # former sample budget, regularization and background affect attribution; the latter
            # background and coalition-game choices still matter.
            # Calibration: A below-neutral limitation. The integer is an ordinal coding decision;
            # neither the unit gap nor universal superiority/inferiority is measured.
            # Evidence: qualitative comparative inference; see study cards for direct endpoints and
            # counterevidence. Confidence: low.
            # Sources: KERNEL, LIME, SHAP. Comparative studies: E20. See documentation §6 for
            # endpoints and limits.
            # Primary locations: KERNEL: KernelExplainer weighted regression; nsamples and l1_reg
            # parameters
            'hyperparameters_perturbation_robustness': 2,
            # Rating 3/5; original=None; v3.3.11=3. retained after comparative review.
            # Reason: Use the same feature-vector presentation prior as exact local SHAP. Sampling
            # accuracy is a separate axis; KernelSHAP also offers L1 feature selection, so
            # approximation alone does not justify lower sparsity. Neither version guarantees a
            # minimal explanatory feature set.
            # Comparison: Approximate local SHAP (3/5) ties LIME (3/5): the former full values or a
            # selected display are not guaranteed minimal; the latter an explicit feature budget
            # controls the delivered explanation.
            # Comparison: Approximate local SHAP (3/5) ties Exact local SHAP (3/5): the former full
            # values or a selected display are not guaranteed minimal; the latter exact allocation
            # typically returns a full feature vector.
            # Calibration: Neutral bin: the evidence does not warrant a general stronger or weaker
            # claim on this exact property. A tie is not demonstrated empirical equivalence.
            # Evidence: qualitative comparative inference; see study cards for direct endpoints and
            # counterevidence. Confidence: moderate.
            # Sources: KERNEL, SHAP, LIME. Comparative studies: no matched direct study located;
            # mechanism/threat-model inference. See documentation §6 for endpoints and limits.
            # Primary locations: KERNEL: KernelExplainer weighted regression; nsamples and l1_reg
            # parameters; SHAP: Additive explanation definition, local accuracy, missingness and
            # consistency
            'sparsity': 3,
            # Rating 3/5; original=None; v3.3.11=3. retained after comparative review.
            # Reason: Feature contributions retain the detail level of exact local attribution.
            # Comparison: Approximate local SHAP (3/5) scores above LIME (2/5): the former feature
            # allocations retain the same output form as exact SHAP; the latter a local linear
            # coefficient list omits explicit nonlinear rules.
            # Comparison: Approximate local SHAP (3/5) ties Exact local SHAP (3/5): the former
            # feature allocations retain the same output form as exact SHAP; the latter per-feature
            # values do not expose the whole interaction mechanism.
            # Calibration: Neutral bin: the evidence does not warrant a general stronger or weaker
            # claim on this exact property. A tie is not demonstrated empirical equivalence.
            # Evidence: qualitative comparative inference; see study cards for direct endpoints and
            # counterevidence. Confidence: moderate.
            # Sources: KERNEL, LIME, SHAP. Comparative studies: no matched direct study located;
            # mechanism/threat-model inference. See documentation §6 for endpoints and limits.
            # Primary locations: KERNEL: KernelExplainer weighted regression; nsamples and l1_reg
            # parameters
            'level_of_detail': 3,
            # Rating 3/5; original=None; v3.3.11=3. retained after comparative review.
            # Reason: Approximation supplies no confidentiality mechanism.
            # Comparison: Approximate local SHAP (3/5) ties LIME (3/5): the former local estimated
            # values are not privacy-protected; the latter a local summary still has no
            # confidentiality guarantee.
            # Comparison: Approximate local SHAP (3/5) ties Exact local SHAP (3/5): the former local
            # estimated values are not privacy-protected; the latter local values have no inherent
            # confidentiality guarantee.
            # Calibration: Neutral bin: the evidence does not warrant a general stronger or weaker
            # claim on this exact property. A tie is not demonstrated empirical equivalence.
            # Evidence: qualitative comparative inference; see study cards for direct endpoints and
            # counterevidence. Confidence: low.
            # Sources: KERNEL, PRIVACY, LIME, SHAP. Comparative studies: no matched direct study
            # located; mechanism/threat-model inference. See documentation §6 for endpoints and
            # limits.
            # Primary locations: KERNEL: KernelExplainer weighted regression; nsamples and l1_reg
            # parameters; PRIVACY: §§3–5; direct evidence for tested gradient/IG/LRP/LIME
            # configurations; threat-model context only for other methods
            'confidentiality': 3,
            # Rating 4/5; original=None; v3.3.11=4. retained after comparative review.
            # Reason: Archive sample masks, random state, model and settings for reconstruction.
            # Comparison: Approximate local SHAP (4/5) scores above LIME (3/5): the former seeds,
            # coalition queries and regression settings can be logged; the latter queries, seeds,
            # neighborhood and fitted surrogate must be recorded.
            # Comparison: Approximate local SHAP (4/5) ties Exact local SHAP (4/5): the former
            # seeds, coalition queries and regression settings can be logged; the latter a fixed
            # value function and coalitions allow reconstruction.
            # Calibration: A qualified comparative strength. The integer is an ordinal coding
            # decision; neither the unit gap nor universal superiority/inferiority is measured.
            # Evidence: qualitative comparative inference; see study cards for direct endpoints and
            # counterevidence. Confidence: moderate.
            # Sources: KERNEL, LIME, SHAP. Comparative studies: no matched direct study located;
            # mechanism/threat-model inference. See documentation §6 for endpoints and limits.
            # Primary locations: KERNEL: KernelExplainer weighted regression; nsamples and l1_reg
            # parameters
            'traceability': 4,
            # Rating 2/5; original=None; v3.3.11=2. retained after comparative review.
            # Reason: Sampling reduces generic exact enumeration cost but still requires repeated
            # model evaluations.
            # Comparison: Approximate local SHAP (2/5) scores below LIME (3/5): the former finite
            # coalition sampling avoids full exponential enumeration; the latter thousands of
            # prediction calls are typical, without gradient access.
            # Comparison: Approximate local SHAP (2/5) scores above Exact local SHAP (1/5): the
            # former finite coalition sampling avoids full exponential enumeration; the latter
            # generic exact evaluation scales exponentially in varying features.
            # Calibration: A below-neutral limitation. The integer is an ordinal coding decision;
            # neither the unit gap nor universal superiority/inferiority is measured.
            # Evidence: qualitative comparative inference; see study cards for direct endpoints and
            # counterevidence. Confidence: moderate.
            # Sources: KERNEL, LIME, SHAP, EXACT. Comparative studies: E01. See documentation §6 for
            # endpoints and limits.
            # Primary locations: KERNEL: KernelExplainer weighted regression; nsamples and l1_reg
            # parameters
            'runtime_performance_and_implementation_constraints': 2,
        },
        'scope_stage': 'local-expost',
        'explanation_target': 'model output',
        "question_types": {'what_feature'},
    },
    # Many-observation summary of approximate local attributions; not all possible global SHAP
    # variants.
    'Global SHAP summaries': {
        "subprops": {
            # Rating 3/5; original=None; v3.3.11=3. retained after comparative review.
            # Reason: Aggregation does not repair local relevance errors; neutral is conditional on
            # representative inputs.
            # Comparison: Global SHAP summaries (3/5) ties PDP (3/5): the former aggregation does
            # not repair local relevance errors; the latter marginal responses can involve
            # infeasible feature combinations.
            # Comparison: Global SHAP summaries (3/5) ties ICE (3/5): the former aggregation does
            # not repair local relevance errors; the latter direct queries still risk infeasible
            # feature combinations.
            # Calibration: Neutral bin: the evidence does not warrant a general stronger or weaker
            # claim on this exact property. A tie is not demonstrated empirical equivalence.
            # Evidence: qualitative comparative inference; see study cards for direct endpoints and
            # counterevidence. Confidence: low.
            # Sources: GLOBAL, ICE. Comparative studies: E02, E04, E11. See documentation §6 for
            # endpoints and limits.
            # Primary locations: GLOBAL: Global bar plot: mean absolute SHAP values and cohort
            # summaries
            'no_false_positives': 3,
            # Rating 3/5; original=None; v3.3.11=3. retained after comparative review.
            # Reason: Population averaging may hide rare influential patterns. Mean absolute SHAP
            # values do not cancel opposite signs; signed means can. Neither summary guarantees
            # recovery of every contributor.
            # Comparison: Global SHAP summaries (3/5) ties PDP (3/5): the former population averages
            # can conceal rare influential patterns; the latter averages can conceal heterogeneous
            # effects.
            # Comparison: Global SHAP summaries (3/5) scores below ICE (4/5): the former population
            # averages can conceal rare influential patterns; the latter individual curves expose
            # heterogeneity hidden by a mean.
            # Calibration: Neutral bin: the evidence does not warrant a general stronger or weaker
            # claim on this exact property. A tie is not demonstrated empirical equivalence.
            # Evidence: qualitative comparative inference; see study cards for direct endpoints and
            # counterevidence. Confidence: moderate.
            # Sources: GLOBAL, ICE. Comparative studies: E02, E04, E11. See documentation §6 for
            # endpoints and limits.
            # Primary locations: GLOBAL: Global bar plot: mean absolute SHAP values and cohort
            # summaries
            'no_false_negatives': 3,
            # Rating 2/5; original=None; v3.3.11=2. retained after comparative review.
            # Reason: Summary statistics omit individual configurations and interactions.
            # Comparison: Global SHAP summaries (2/5) scores below PDP (3/5): the former summary
            # statistics discard instance configurations and interactions; the latter
            # low-dimensional mean curves omit other interactions.
            # Comparison: Global SHAP summaries (2/5) scores below ICE (3/5): the former summary
            # statistics discard instance configurations and interactions; the latter individual
            # curves retain the information used to form matched PDPs.
            # Calibration: A below-neutral limitation. The integer is an ordinal coding decision;
            # neither the unit gap nor universal superiority/inferiority is measured.
            # Evidence: qualitative comparative inference; see study cards for direct endpoints and
            # counterevidence. Confidence: moderate.
            # Sources: GLOBAL, ICE. Comparative studies: E04. See documentation §6 for endpoints and
            # limits.
            # Primary locations: GLOBAL: Global bar plot: mean absolute SHAP values and cohort
            # summaries
            'completeness': 2,
            # Rating 3/5; original=None; v3.3.11=3. retained after comparative review.
            # Reason: Averaging may reduce variability, but cohort shifts remain; no universal
            # stability guarantee.
            # Comparison: Global SHAP summaries (3/5) scores below PDP (4/5): the former aggregation
            # may damp noise but depends on cohort composition; the latter population averaging may
            # damp individual variation.
            # Comparison: Global SHAP summaries (3/5) ties ICE (3/5): the former aggregation may
            # damp noise but depends on cohort composition; the latter curves retain the underlying
            # model’s input sensitivity.
            # Calibration: Neutral bin: the evidence does not warrant a general stronger or weaker
            # claim on this exact property. A tie is not demonstrated empirical equivalence.
            # Evidence: qualitative comparative inference; see study cards for direct endpoints and
            # counterevidence. Confidence: low.
            # Sources: GLOBAL, ICE. Comparative studies: E02. See documentation §6 for endpoints and
            # limits.
            # Primary locations: GLOBAL: Global bar plot: mean absolute SHAP values and cohort
            # summaries
            'stability': 3,
            # Rating 3/5; original=None; v3.3.11=3. retained after comparative review.
            # Reason: Neither inherited vulnerability nor attack protection is automatic; use
            # neutral pending a global threat-model evaluation.
            # Comparison: Global SHAP summaries (3/5) ties PDP (3/5): the former aggregation of
            # manipulable local values is not a defense; the latter averaging is not a privacy or
            # adversarial defense.
            # Comparison: Global SHAP summaries (3/5) ties ICE (3/5): the former aggregation of
            # manipulable local values is not a defense; the latter direct querying is not an
            # adversarial defense.
            # Calibration: Neutral bin: the evidence does not warrant a general stronger or weaker
            # claim on this exact property. A tie is not demonstrated empirical equivalence.
            # Evidence: qualitative comparative inference; see study cards for direct endpoints and
            # counterevidence. Confidence: low.
            # Sources: GLOBAL, ICE. Comparative studies: E11. See documentation §6 for endpoints and
            # limits.
            # Primary locations: GLOBAL: Global bar plot: mean absolute SHAP values and cohort
            # summaries
            'adversarial_robustness': 3,
            # Rating 3/5; original=None; v3.3.11=3. retained after comparative review.
            # Reason: Changing the cohort can alter importance rankings even with reproducible local
            # values.
            # Comparison: Global SHAP summaries (3/5) scores below PDP (4/5): the former
            # repeatability depends on the local estimator and reference cohort; the latter a fixed
            # model, cohort and grid give repeatable means.
            # Comparison: Global SHAP summaries (3/5) scores below ICE (4/5): the former
            # repeatability depends on the local estimator and reference cohort; the latter fixed
            # inputs and grids are repeatable without explainer sampling.
            # Calibration: Neutral bin: the evidence does not warrant a general stronger or weaker
            # claim on this exact property. A tie is not demonstrated empirical equivalence.
            # Evidence: qualitative comparative inference; see study cards for direct endpoints and
            # counterevidence. Confidence: low.
            # Sources: GLOBAL, ICE. Comparative studies: E02. See documentation §6 for endpoints and
            # limits.
            # Primary locations: GLOBAL: Global bar plot: mean absolute SHAP values and cohort
            # summaries
            'consistency': 3,
            # Rating 2/5; original=None; v3.3.11=2. retained after comparative review.
            # Reason: Cohort, background, estimator and aggregation choices all affect results.
            # Comparison: Global SHAP summaries (2/5) scores below PDP (4/5): the former background,
            # local estimator and aggregation rule all matter; the latter few explainer settings
            # remain once cohort and grid are fixed.
            # Comparison: Global SHAP summaries (2/5) scores below ICE (4/5): the former background,
            # local estimator and aggregation rule all matter; the latter grid choice remains,
            # without local surrogate tuning.
            # Calibration: A below-neutral limitation. The integer is an ordinal coding decision;
            # neither the unit gap nor universal superiority/inferiority is measured.
            # Evidence: qualitative comparative inference; see study cards for direct endpoints and
            # counterevidence. Confidence: low.
            # Sources: GLOBAL, ICE. Comparative studies: no matched direct study located;
            # mechanism/threat-model inference. See documentation §6 for endpoints and limits.
            # Primary locations: GLOBAL: Global bar plot: mean absolute SHAP values and cohort
            # summaries
            'hyperparameters_perturbation_robustness': 2,
            # Rating 2/5; original=None; v3.3.11=2. retained after comparative review.
            # Reason: Many-feature, many-observation displays are dense under this scenario.
            # Comparison: Global SHAP summaries (2/5) ties PDP (2/5): the former a population-wide
            # feature display is not a minimal local explanation; the latter a full collection of
            # curves is not feature selection.
            # Comparison: Global SHAP summaries (2/5) ties ICE (2/5): the former a population-wide
            # feature display is not a minimal local explanation; the latter many individual curves
            # can produce a large explanation.
            # Calibration: A below-neutral limitation. The integer is an ordinal coding decision;
            # neither the unit gap nor universal superiority/inferiority is measured.
            # Evidence: qualitative comparative inference; see study cards for direct endpoints and
            # counterevidence. Confidence: moderate.
            # Sources: GLOBAL, ICE. Comparative studies: E04. See documentation §6 for endpoints and
            # limits.
            # Primary locations: GLOBAL: Global bar plot: mean absolute SHAP values and cohort
            # summaries
            'sparsity': 2,
            # Rating 3/5; original=None; v3.3.11=3. retained after comparative review.
            # Reason: Averaging attributions retains feature-level importance but loses
            # instance-level configurations; adding observations does not itself increase the
            # retained rubric granularity. Distribution plots retain more variation, without
            # becoming explicit decision rules.
            # Comparison: Global SHAP summaries (3/5) scores below PDP (4/5): the former summary
            # statistics are coarser than explicit decision rules; the latter response curves expose
            # direction, shape and thresholds.
            # Comparison: Global SHAP summaries (3/5) scores below ICE (4/5): the former summary
            # statistics are coarser than explicit decision rules; the latter curves expose
            # feature-response shape for individual contexts.
            # Calibration: Neutral bin: the evidence does not warrant a general stronger or weaker
            # claim on this exact property. A tie is not demonstrated empirical equivalence.
            # Evidence: qualitative comparative inference; see study cards for direct endpoints and
            # counterevidence. Confidence: moderate.
            # Sources: GLOBAL, ICE. Comparative studies: E04. See documentation §6 for endpoints and
            # limits.
            # Primary locations: GLOBAL: Global bar plot: mean absolute SHAP values and cohort
            # summaries
            'level_of_detail': 3,
            # Rating 3/5; original=None; v3.3.11=3. retained after comparative review.
            # Reason: Aggregation alone is not a privacy guarantee.
            # Comparison: Global SHAP summaries (3/5) ties PDP (3/5): the former aggregation still
            # exposes population behavior without a privacy proof; the latter aggregate responses
            # conceal individual records but reveal behavior.
            # Comparison: Global SHAP summaries (3/5) scores above ICE (2/5): the former aggregation
            # still exposes population behavior without a privacy proof; the latter individual
            # response profiles expose more record-specific information.
            # Calibration: Neutral bin: the evidence does not warrant a general stronger or weaker
            # claim on this exact property. A tie is not demonstrated empirical equivalence.
            # Evidence: qualitative comparative inference; see study cards for direct endpoints and
            # counterevidence. Confidence: low.
            # Sources: GLOBAL, PRIVACY, ICE. Comparative studies: no matched direct study located;
            # mechanism/threat-model inference. See documentation §6 for endpoints and limits.
            # Primary locations: GLOBAL: Global bar plot: mean absolute SHAP values and cohort
            # summaries; PRIVACY: §§3–5; direct evidence for tested gradient/IG/LRP/LIME
            # configurations; threat-model context only for other methods
            'confidentiality': 3,
            # Rating 4/5; original=None; v3.3.11=4. retained after comparative review.
            # Reason: Archive cohort, local values and summary operation to reconstruct the output.
            # Comparison: Global SHAP summaries (4/5) ties PDP (4/5): the former the cohort, local
            # values and aggregation function can be saved; the latter query grids and averages can
            # be directly reproduced.
            # Comparison: Global SHAP summaries (4/5) ties ICE (4/5): the former the cohort, local
            # values and aggregation function can be saved; the latter saved queries reconstruct
            # every curve.
            # Calibration: A qualified comparative strength. The integer is an ordinal coding
            # decision; neither the unit gap nor universal superiority/inferiority is measured.
            # Evidence: qualitative comparative inference; see study cards for direct endpoints and
            # counterevidence. Confidence: moderate.
            # Sources: GLOBAL, ICE. Comparative studies: no matched direct study located;
            # mechanism/threat-model inference. See documentation §6 for endpoints and limits.
            # Primary locations: GLOBAL: Global bar plot: mean absolute SHAP values and cohort
            # summaries
            'traceability': 4,
            # Rating 1/5; original=None; v3.3.11=1. retained after comparative review.
            # Reason: Repeated local estimation across many records has high assumed cost;
            # exact-input or optimized summaries require separate profiles.
            # Comparison: Global SHAP summaries (1/5) scores below PDP (4/5): the former many local
            # explanation costs accumulate across the cohort; the latter fixed small grids require
            # batches of prediction calls.
            # Comparison: Global SHAP summaries (1/5) scores below ICE (4/5): the former many local
            # explanation costs accumulate across the cohort; the latter cost follows instances
            # times grid points, without optimization.
            # Calibration: An inherited endpoint under the stated output/configuration, not a
            # universal guarantee or universal failure. The exact endpoint is low-confidence outside
            # that setting.
            # Evidence: qualitative comparative inference; see study cards for direct endpoints and
            # counterevidence. Confidence: low.
            # Sources: GLOBAL, ICE. Comparative studies: no matched direct study located;
            # mechanism/threat-model inference. See documentation §6 for endpoints and limits.
            # Primary locations: GLOBAL: Global bar plot: mean absolute SHAP values and cohort
            # summaries
            'runtime_performance_and_implementation_constraints': 1,
        },
        'scope_stage': 'global-exante',
        'explanation_target': 'model output',
        "question_types": {'what_feature'},
    },
    # MechaRule §4.2 only: an LLM proposes deterministic predicates, scored on behavior records;
    # RuleSHAP extracts a behavioral surrogate. No internal ablation evidence. Full MechaRule is a
    # separate profile. Task metrics and output-derived features require leakage checks.
    'LLM-assisted behavioral RuleSHAP (MechaRule stage 1)': {
        "subprops": {
            # Rating 3/5; original=None; v3.3.11=3. retained after comparative review.
            # Reason: Hypothesis scoring supports association, not causal necessity.
            # Comparison: LLM-assisted behavioral RuleSHAP (MechaRule stage 1) (3/5) scores below
            # MechaRule (4/5): the former behavioral association does not establish internal
            # necessity; the latter neuron interventions add conditional influence evidence.
            # Comparison: LLM-assisted behavioral RuleSHAP (MechaRule stage 1) (3/5) scores above
            # LLM neuron explanations (Bills et al.) (2/5): the former behavioral association does
            # not establish internal necessity; the latter a fluent description can predict
            # activations incorrectly.
            # Calibration: Neutral bin: the evidence does not warrant a general stronger or weaker
            # claim on this exact property. A tie is not demonstrated empirical equivalence.
            # Evidence: qualitative comparative inference; see study cards for direct endpoints and
            # counterevidence. Confidence: low.
            # Sources: MECHARULE, LLM_NEURON. Comparative studies: E15. See documentation §6 for
            # endpoints and limits.
            # Primary locations: MECHARULE: §4 pipeline; §4.2 behavioral predicates; §8 limitations
            'no_false_positives': 3,
            # Rating 3/5; original=None; v3.3.11=3. retained after comparative review.
            # Reason: Proposed predicates can miss unrepresented behavioral triggers.
            # Comparison: LLM-assisted behavioral RuleSHAP (MechaRule stage 1) (3/5) scores above
            # LLM neuron explanations (Bills et al.) (2/5): the former unproposed predicates leave
            # behavior unrepresented; the latter polysemantic activation patterns can escape one
            # description.
            # Comparison: LLM-assisted behavioral RuleSHAP (MechaRule stage 1) (3/5) ties MechaRule
            # (3/5): the former unproposed predicates leave behavior unrepresented; the latter
            # candidate reduction and weak-effect omissions limit recovery.
            # Calibration: Neutral bin: the evidence does not warrant a general stronger or weaker
            # claim on this exact property. A tie is not demonstrated empirical equivalence.
            # Evidence: qualitative comparative inference; see study cards for direct endpoints and
            # counterevidence. Confidence: low.
            # Sources: MECHARULE, LLM_NEURON. Comparative studies: E15. See documentation §6 for
            # endpoints and limits.
            # Primary locations: MECHARULE: §4 pipeline; §4.2 behavioral predicates; §8 limitations
            'no_false_negatives': 3,
            # Rating 3/5; original=None; v3.3.11=3. retained after comparative review.
            # Reason: Selected rules cover task behavior, not all model logic.
            # Comparison: LLM-assisted behavioral RuleSHAP (MechaRule stage 1) (3/5) scores above
            # LLM neuron explanations (Bills et al.) (2/5): the former selected task rules only
            # partly cover the model; the latter descriptions only partly cover the declared
            # activation target.
            # Comparison: LLM-assisted behavioral RuleSHAP (MechaRule stage 1) (3/5) ties MechaRule
            # (3/5): the former selected task rules only partly cover the model; the latter
            # task-conditioned rules do not cover the full model.
            # Calibration: Neutral bin: the evidence does not warrant a general stronger or weaker
            # claim on this exact property. A tie is not demonstrated empirical equivalence.
            # Evidence: qualitative comparative inference; see study cards for direct endpoints and
            # counterevidence. Confidence: low.
            # Sources: MECHARULE, LLM_NEURON. Comparative studies: E15. See documentation §6 for
            # endpoints and limits.
            # Primary locations: MECHARULE: §4 pipeline; §4.2 behavioral predicates; §8 limitations
            'completeness': 3,
            # Rating 2/5; original=None; v3.3.11=2. retained after comparative review.
            # Reason: Feature proposals and fitted rules may vary.
            # Comparison: LLM-assisted behavioral RuleSHAP (MechaRule stage 1) (2/5) scores below
            # LLM neuron explanations (Bills et al.) (3/5): the former generated features and fitted
            # rules can vary; the latter activation prediction error alone is not a local-stability
            # test.
            # Comparison: LLM-assisted behavioral RuleSHAP (MechaRule stage 1) (2/5) scores below
            # MechaRule (3/5): the former generated features and fitted rules can vary; the latter
            # results depend on task and intervention regime.
            # Calibration: A below-neutral limitation. The integer is an ordinal coding decision;
            # neither the unit gap nor universal superiority/inferiority is measured.
            # Evidence: qualitative comparative inference; see study cards for direct endpoints and
            # counterevidence. Confidence: low.
            # Sources: MECHARULE, LLM_NEURON_OVERVIEW. Comparative studies: no matched direct study
            # located; mechanism/threat-model inference. See documentation §6 for endpoints and
            # limits.
            # Primary locations: MECHARULE: §4 pipeline; §4.2 behavioral predicates; §8 limitations
            'stability': 2,
            # Rating 3/5; original=None; v3.3.11=3. retained after comparative review.
            # Reason: No explanation attack-resistance guarantee is established.
            # Comparison: LLM-assisted behavioral RuleSHAP (MechaRule stage 1) (3/5) ties LLM neuron
            # explanations (Bills et al.) (3/5): the former there is no published generic
            # explainer-attack defense; the latter a scored description has no established attack
            # defense.
            # Comparison: LLM-assisted behavioral RuleSHAP (MechaRule stage 1) (3/5) ties MechaRule
            # (3/5): the former there is no published generic explainer-attack defense; the latter
            # jailbreak experiments are not attacks against the explainer.
            # Calibration: Neutral bin: the evidence does not warrant a general stronger or weaker
            # claim on this exact property. A tie is not demonstrated empirical equivalence.
            # Evidence: qualitative comparative inference; see study cards for direct endpoints and
            # counterevidence. Confidence: low.
            # Sources: MECHARULE, LLM_NEURON. Comparative studies: no matched direct study located;
            # mechanism/threat-model inference. See documentation §6 for endpoints and limits.
            # Primary locations: MECHARULE: §4 pipeline; §4.2 behavioral predicates; §8 limitations
            'adversarial_robustness': 3,
            # Rating 2/5; original=None; v3.3.11=2. retained after comparative review.
            # Reason: LLM proposals can change between runs.
            # Comparison: LLM-assisted behavioral RuleSHAP (MechaRule stage 1) (2/5) ties LLM neuron
            # explanations (Bills et al.) (2/5): the former LLM predicate proposals add run
            # variability; the latter generative descriptions can vary across runs.
            # Comparison: LLM-assisted behavioral RuleSHAP (MechaRule stage 1) (2/5) scores below
            # MechaRule (3/5): the former LLM predicate proposals add run variability; the latter
            # fixed artifacts support replay, with regime dependence.
            # Calibration: A below-neutral limitation. The integer is an ordinal coding decision;
            # neither the unit gap nor universal superiority/inferiority is measured.
            # Evidence: qualitative comparative inference; see study cards for direct endpoints and
            # counterevidence. Confidence: low.
            # Sources: MECHARULE, LLM_NEURON. Comparative studies: no matched direct study located;
            # mechanism/threat-model inference. See documentation §6 for endpoints and limits.
            # Primary locations: MECHARULE: §4 pipeline; §4.2 behavioral predicates; §8 limitations
            'consistency': 2,
            # Rating 2/5; original=None; v3.3.11=2. retained after comparative review.
            # Reason: Prompt, filtering and rule-selection settings matter.
            # Comparison: LLM-assisted behavioral RuleSHAP (MechaRule stage 1) (2/5) ties LLM neuron
            # explanations (Bills et al.) (2/5): the former prompt, candidate budget and rule
            # settings affect output; the latter examples, prompt and simulator choices affect the
            # result.
            # Comparison: LLM-assisted behavioral RuleSHAP (MechaRule stage 1) (2/5) ties MechaRule
            # (2/5): the former prompt, candidate budget and rule settings affect output; the latter
            # effect threshold and candidate budget change localized neurons.
            # Calibration: A below-neutral limitation. The integer is an ordinal coding decision;
            # neither the unit gap nor universal superiority/inferiority is measured.
            # Evidence: qualitative comparative inference; see study cards for direct endpoints and
            # counterevidence. Confidence: low.
            # Sources: MECHARULE, LLM_NEURON. Comparative studies: E15. See documentation §6 for
            # endpoints and limits.
            # Primary locations: MECHARULE: §4 pipeline; §4.2 behavioral predicates; §8 limitations
            'hyperparameters_perturbation_robustness': 2,
            # Rating 3/5; original=None; v3.3.11=3. retained after comparative review.
            # Reason: Greedy selection promotes compactness without minimality guarantees.
            # Comparison: LLM-assisted behavioral RuleSHAP (MechaRule stage 1) (3/5) ties LLM neuron
            # explanations (Bills et al.) (3/5): the former the behavioral high-recall stage is not
            # the sparse final neuron-linked output; the latter a short description may be compact
            # without semantic minimality.
            # Comparison: LLM-assisted behavioral RuleSHAP (MechaRule stage 1) (3/5) scores below
            # MechaRule (4/5): the former the behavioral high-recall stage is not the sparse final
            # neuron-linked output; the latter compressed neuron-linked rules can summarize many
            # observations.
            # Calibration: Neutral bin: the evidence does not warrant a general stronger or weaker
            # claim on this exact property. A tie is not demonstrated empirical equivalence.
            # Evidence: qualitative comparative inference; see study cards for direct endpoints and
            # counterevidence. Confidence: low.
            # Sources: MECHARULE, LLM_NEURON. Comparative studies: E15. See documentation §6 for
            # endpoints and limits.
            # Primary locations: MECHARULE: §4 pipeline; §4.2 behavioral predicates; §8 limitations
            'sparsity': 3,
            # Rating 4/5; original=None; v3.3.11=4. retained after comparative review.
            # Reason: Executable predicates expose detailed behavioral conditions.
            # Comparison: LLM-assisted behavioral RuleSHAP (MechaRule stage 1) (4/5) scores above
            # LLM neuron explanations (Bills et al.) (3/5): the former explicit behavioral
            # predicates give more structure than a weight vector; the latter language descriptions
            # abstract over activation observations.
            # Comparison: LLM-assisted behavioral RuleSHAP (MechaRule stage 1) (4/5) ties MechaRule
            # (4/5): the former explicit behavioral predicates give more structure than a weight
            # vector; the latter predicates plus neuron interventions expose conditional mechanism
            # evidence.
            # Calibration: A qualified comparative strength. The integer is an ordinal coding
            # decision; neither the unit gap nor universal superiority/inferiority is measured.
            # Evidence: qualitative comparative inference; see study cards for direct endpoints and
            # counterevidence. Confidence: low.
            # Sources: MECHARULE, LLM_NEURON. Comparative studies: no matched direct study located;
            # mechanism/threat-model inference. See documentation §6 for endpoints and limits.
            # Primary locations: MECHARULE: §4 pipeline; §4.2 behavioral predicates; §8 limitations
            'level_of_detail': 4,
            # Rating 2/5; original=None; v3.3.11=2. retained after comparative review.
            # Reason: Prompts, outputs and extracted rules may be sensitive.
            # Comparison: LLM-assisted behavioral RuleSHAP (MechaRule stage 1) (2/5) scores below
            # LLM neuron explanations (Bills et al.) (3/5): the former behavior records and reusable
            # rules can disclose sensitive logic; the latter activation exemplars and prompts may
            # disclose sensitive text.
            # Comparison: LLM-assisted behavioral RuleSHAP (MechaRule stage 1) (2/5) ties MechaRule
            # (2/5): the former behavior records and reusable rules can disclose sensitive logic;
            # the latter behavioral rules and internals disclose reusable model information.
            # Calibration: A below-neutral limitation. The integer is an ordinal coding decision;
            # neither the unit gap nor universal superiority/inferiority is measured.
            # Evidence: qualitative comparative inference; see study cards for direct endpoints and
            # counterevidence. Confidence: low.
            # Sources: MECHARULE, PRIVACY, LLM_NEURON. Comparative studies: no matched direct study
            # located; mechanism/threat-model inference. See documentation §6 for endpoints and
            # limits.
            # Primary locations: MECHARULE: §4 pipeline; §4.2 behavioral predicates; §8 limitations;
            # PRIVACY: §§3–5; direct evidence for tested gradient/IG/LRP/LIME configurations;
            # threat-model context only for other methods
            'confidentiality': 2,
            # Rating 3/5; original=None; v3.3.11=3. retained after comparative review.
            # Reason: Record proposals, predicate code and evaluation data.
            # Comparison: LLM-assisted behavioral RuleSHAP (MechaRule stage 1) (3/5) scores below
            # LLM neuron explanations (Bills et al.) (4/5): the former predicate proposals and
            # fitting records are needed, without ablation traces; the latter stored exemplars,
            # prompts and simulation scores support inspection.
            # Comparison: LLM-assisted behavioral RuleSHAP (MechaRule stage 1) (3/5) scores below
            # MechaRule (4/5): the former predicate proposals and fitting records are needed,
            # without ablation traces; the latter ablation records connect rules to tested internal
            # changes.
            # Calibration: Neutral bin: the evidence does not warrant a general stronger or weaker
            # claim on this exact property. A tie is not demonstrated empirical equivalence.
            # Evidence: qualitative comparative inference; see study cards for direct endpoints and
            # counterevidence. Confidence: moderate.
            # Sources: MECHARULE, LLM_NEURON. Comparative studies: no matched direct study located;
            # mechanism/threat-model inference. See documentation §6 for endpoints and limits.
            # Primary locations: MECHARULE: §4 pipeline; §4.2 behavioral predicates; §8 limitations
            'traceability': 3,
            # Rating 2/5; original=None; v3.3.11=2. retained after comparative review.
            # Reason: LLM calls and rule fitting add computation.
            # Comparison: LLM-assisted behavioral RuleSHAP (MechaRule stage 1) (2/5) ties LLM neuron
            # explanations (Bills et al.) (2/5): the former LLM proposals and behavioral scoring
            # precede rule fitting; the latter both explanation generation and held-out simulation
            # require LLM work.
            # Comparison: LLM-assisted behavioral RuleSHAP (MechaRule stage 1) (2/5) ties MechaRule
            # (2/5): the former LLM proposals and behavioral scoring precede rule fitting; the
            # latter candidate search and interventions require substantial model access and work.
            # Calibration: A below-neutral limitation. The integer is an ordinal coding decision;
            # neither the unit gap nor universal superiority/inferiority is measured.
            # Evidence: qualitative comparative inference; see study cards for direct endpoints and
            # counterevidence. Confidence: low.
            # Sources: MECHARULE, LLM_NEURON. Comparative studies: E15. See documentation §6 for
            # endpoints and limits.
            # Primary locations: MECHARULE: §4 pipeline; §4.2 behavioral predicates; §8 limitations
            'runtime_performance_and_implementation_constraints': 2,
        },
        'scope_stage': 'global-exante',
        'models': ['task-labeled predictor outputs; evaluated on language-model tasks'],
        'required_access': 'behavioral_records',
        'requires_model_replacement': False,
        'component_only': False,
        'explanation_target': 'task success/failure patterns of the unchanged predictor',
        "question_types": {'how_computed', 'what_feature', 'what_rule'},
    },
}

algorithms_model_specific = {
    # CAV directional sensitivity / TCAV on an already trained network.
    'CAVs': {
        "subprops": {
            # Rating 3/5; original=3; v3.3.11=3. retained after comparative review.
            # Reason: A concept direction is fitted from labeled concept examples. Directional
            # sensitivity can identify an association with model behavior, but a confounded
            # direction need not isolate the named concept. Retain neutral 3 for this
            # semantic-relevance uncertainty; real-world causality is not required.
            # Comparison: CAVs (3/5) ties Supervised CBM (3/5): the former a learned direction may
            # mix the named concept with confounders; the latter named concept coordinates may
            # contain unintended information.
            # Comparison: CAVs (3/5) ties Post-hoc CBM (concept-only) (3/5): the former a learned
            # direction may mix the named concept with confounders; the latter explicit head weights
            # do not ensure concept purity.
            # Calibration: Neutral bin: the evidence does not warrant a general stronger or weaker
            # claim on this exact property. A tie is not demonstrated empirical equivalence.
            # Evidence: qualitative comparative inference; see study cards for direct endpoints and
            # counterevidence. Confidence: moderate.
            # Sources: TCAV, CBM, CBM_LIMIT, PCBM. Comparative studies: E13, E18. See documentation
            # §6 for endpoints and limits.
            # Primary locations: TCAV: CAV construction, directional derivatives and significance
            # testing
            'no_false_positives': 3,
            # Rating 2/5; original=2; v3.3.11=2. retained after comparative review.
            # Reason: Only supplied concepts are tested; unspecified concepts can be missed.
            # Comparison: CAVs (2/5) scores below Supervised CBM (3/5): the former only the supplied
            # concept vocabulary is examined; the latter semantic labels may fail to name all
            # encoded influences.
            # Comparison: CAVs (2/5) scores below Post-hoc CBM (concept-only) (3/5): the former only
            # the supplied concept vocabulary is examined; the latter semantic ambiguity can persist
            # despite exposed head inputs.
            # Calibration: A below-neutral limitation. The integer is an ordinal coding decision;
            # neither the unit gap nor universal superiority/inferiority is measured.
            # Evidence: qualitative comparative inference; see study cards for direct endpoints and
            # counterevidence. Confidence: moderate.
            # Sources: TCAV, CBM, CBM_LIMIT, PCBM. Comparative studies: E13, E18. See documentation
            # §6 for endpoints and limits.
            # Primary locations: TCAV: CAV construction, directional derivatives and significance
            # testing
            'no_false_negatives': 2,
            # Rating 2/5; original=2; v3.3.11=2. retained after comparative review.
            # Reason: Concept directions do not recover the whole model rationale.
            # Comparison: CAVs (2/5) scores below Supervised CBM (4/5): the former concept
            # sensitivities are partial probes of a larger network; the latter the no-bypass head
            # uses only exposed concepts.
            # Comparison: CAVs (2/5) scores below Post-hoc CBM (concept-only) (4/5): the former
            # concept sensitivities are partial probes of a larger network; the latter the
            # replacement head uses only exposed concept coordinates.
            # Calibration: A below-neutral limitation. The integer is an ordinal coding decision;
            # neither the unit gap nor universal superiority/inferiority is measured.
            # Evidence: qualitative comparative inference; see study cards for direct endpoints and
            # counterevidence. Confidence: moderate.
            # Sources: TCAV, CBM, CBM_LIMIT, PCBM. Comparative studies: E13, E18. See documentation
            # §6 for endpoints and limits.
            # Primary locations: TCAV: CAV construction, directional derivatives and significance
            # testing
            'completeness': 2,
            # Rating 2/5; original=1; v3.3.11=2. retained after comparative review.
            # Reason: Concept examples and learned directions can change measured sensitivity.
            # Comparison: CAVs (2/5) scores below Supervised CBM (3/5): the former concept examples
            # and representation choices affect measured sensitivity; the latter concept encoders
            # can remain input-sensitive.
            # Comparison: CAVs (2/5) scores below Post-hoc CBM (concept-only) (3/5): the former
            # concept examples and representation choices affect measured sensitivity; the latter a
            # frozen backbone aids replay without guaranteeing input continuity.
            # Calibration: A below-neutral limitation. The integer is an ordinal coding decision;
            # neither the unit gap nor universal superiority/inferiority is measured.
            # Evidence: qualitative comparative inference; see study cards for direct endpoints and
            # counterevidence. Confidence: low.
            # Sources: TCAV, CBM, CBM_LIMIT, PCBM. Comparative studies: no matched direct study
            # located; mechanism/threat-model inference. See documentation §6 for endpoints and
            # limits.
            # Primary locations: TCAV: CAV construction, directional derivatives and significance
            # testing
            'stability': 2,
            # Rating 2/5; original=2; v3.3.11=2. retained after comparative review.
            # Reason: Concept sensitivity can be changed by attacks on concept-based explanations.
            # Retain a below-neutral prior for ordinary TCAV; demonstrated attacks are not proof of
            # failure for every concept bank.
            # Comparison: CAVs (2/5) scores below Supervised CBM (3/5): the former concept-example
            # attacks can redirect TCAV results; the latter a concept bottleneck is not an
            # explanation-attack defense.
            # Comparison: CAVs (2/5) scores below Post-hoc CBM (concept-only) (3/5): the former
            # concept-example attacks can redirect TCAV results; the latter concept projection is
            # not an adversarial defense.
            # Calibration: A below-neutral limitation. The integer is an ordinal coding decision;
            # neither the unit gap nor universal superiority/inferiority is measured.
            # Evidence: qualitative comparative inference; see study cards for direct endpoints and
            # counterevidence. Confidence: low.
            # Sources: TCAV, TCAV_ATTACK, CBM, CBM_LIMIT, PCBM. Comparative studies: E18. See
            # documentation §6 for endpoints and limits.
            # Primary locations: TCAV: CAV construction, directional derivatives and significance
            # testing; TCAV_ATTACK: Attacks on concept exemplars used by TCAV
            'adversarial_robustness': 2,
            # Rating 3/5; original=3; v3.3.11=3. retained after comparative review.
            # Reason: Repeated concept-set trials and significance checks help, but do not guarantee
            # cross-dataset consistency.
            # Comparison: CAVs (3/5) ties Supervised CBM (3/5): the former random concept controls
            # reduce but do not eliminate run variation; the latter trained encoders and heads can
            # differ between runs.
            # Comparison: CAVs (3/5) ties Post-hoc CBM (concept-only) (3/5): the former random
            # concept controls reduce but do not eliminate run variation; the latter a frozen
            # representation reduces retraining variation.
            # Calibration: Neutral bin: the evidence does not warrant a general stronger or weaker
            # claim on this exact property. A tie is not demonstrated empirical equivalence.
            # Evidence: qualitative comparative inference; see study cards for direct endpoints and
            # counterevidence. Confidence: low.
            # Sources: TCAV, CBM, CBM_LIMIT, PCBM. Comparative studies: no matched direct study
            # located; mechanism/threat-model inference. See documentation §6 for endpoints and
            # limits.
            # Primary locations: TCAV: CAV construction, directional derivatives and significance
            # testing
            'consistency': 3,
            # Rating 1/5; original=1; v3.3.11=1. retained after comparative review.
            # Reason: Concept examples and layer choice define what is measured; retain the original
            # weakest comparative prior for an unconstrained concept bank.
            # Comparison: CAVs (1/5) scores below Supervised CBM (2/5): the former layer and concept
            # exemplar choices can strongly alter directions; the latter concept supervision and
            # bottleneck design affect explanations.
            # Comparison: CAVs (1/5) scores below Post-hoc CBM (concept-only) (2/5): the former
            # layer and concept exemplar choices can strongly alter directions; the latter concept
            # bank and sparse-head regularization affect outputs.
            # Calibration: An inherited endpoint under the stated output/configuration, not a
            # universal guarantee or universal failure. The exact endpoint is low-confidence outside
            # that setting.
            # Evidence: qualitative comparative inference; see study cards for direct endpoints and
            # counterevidence. Confidence: low.
            # Sources: TCAV, CBM, CBM_LIMIT, PCBM. Comparative studies: E18. See documentation §6
            # for endpoints and limits.
            # Primary locations: TCAV: CAV construction, directional derivatives and significance
            # testing
            'hyperparameters_perturbation_robustness': 1,
            # Rating 3/5; original=5; v3.3.11=3. retained after comparative review.
            # Reason: Few concepts can be concise, but CAVs do not enforce a minimal concept set.
            # Comparison: CAVs (3/5) ties Supervised CBM (3/5): the former the number of tested
            # concepts is user-selected; the latter a concept layer need not use few nonzero
            # concepts.
            # Comparison: CAVs (3/5) scores below Post-hoc CBM (concept-only) (4/5): the former the
            # number of tested concepts is user-selected; the latter a sparse linear head explicitly
            # selects active concept terms.
            # Calibration: Neutral bin: the evidence does not warrant a general stronger or weaker
            # claim on this exact property. A tie is not demonstrated empirical equivalence.
            # Evidence: qualitative comparative inference; see study cards for direct endpoints and
            # counterevidence. Confidence: moderate.
            # Sources: TCAV, CBM, CBM_LIMIT, PCBM. Comparative studies: E13. See documentation §6
            # for endpoints and limits.
            # Primary locations: TCAV: CAV construction, directional derivatives and significance
            # testing
            'sparsity': 3,
            # Rating 2/5; original=1; v3.3.11=2. retained after comparative review.
            # Reason: Concept-level abstraction is coarser than feature predicates; low detail is
            # not a claim of low usefulness.
            # Comparison: CAVs (2/5) scores below Supervised CBM (3/5): the former concept-direction
            # scores abstract away input-level computation; the latter concept-level prediction
            # exposes less input detail than explicit rules.
            # Comparison: CAVs (2/5) scores below Post-hoc CBM (concept-only) (3/5): the former
            # concept-direction scores abstract away input-level computation; the latter concept
            # contributions abstract away the encoder’s details.
            # Calibration: A below-neutral limitation. The integer is an ordinal coding decision;
            # neither the unit gap nor universal superiority/inferiority is measured.
            # Evidence: qualitative comparative inference; see study cards for direct endpoints and
            # counterevidence. Confidence: moderate.
            # Sources: TCAV, CBM, CBM_LIMIT, PCBM. Comparative studies: no matched direct study
            # located; mechanism/threat-model inference. See documentation §6 for endpoints and
            # limits.
            # Primary locations: TCAV: CAV construction, directional derivatives and significance
            # testing
            'level_of_detail': 2,
            # Rating 3/5; original=3; v3.3.11=3. retained after comparative review.
            # Reason: Concept examples and scores require contextual disclosure controls.
            # Comparison: CAVs (3/5) ties Supervised CBM (3/5): the former concept scores do not
            # provide a confidentiality mechanism; the latter concept scores do not ensure
            # confidentiality.
            # Comparison: CAVs (3/5) ties Post-hoc CBM (concept-only) (3/5): the former concept
            # scores do not provide a confidentiality mechanism; the latter the concept output has
            # no formal privacy mechanism.
            # Calibration: Neutral bin: the evidence does not warrant a general stronger or weaker
            # claim on this exact property. A tie is not demonstrated empirical equivalence.
            # Evidence: qualitative comparative inference; see study cards for direct endpoints and
            # counterevidence. Confidence: low.
            # Sources: TCAV, PRIVACY, CBM, CBM_LIMIT, PCBM. Comparative studies: no matched direct
            # study located; mechanism/threat-model inference. See documentation §6 for endpoints
            # and limits.
            # Primary locations: TCAV: CAV construction, directional derivatives and significance
            # testing; PRIVACY: §§3–5; direct evidence for tested gradient/IG/LRP/LIME
            # configurations; threat-model context only for other methods
            'confidentiality': 3,
            # Rating 3/5; original=1; v3.3.11=3. retained after comparative review.
            # Reason: Recording the model, input, random state and settings makes reconstruction
            # possible; use 3 rather than assuming either complete or inherently poor auditability.
            # Comparison: CAVs (3/5) scores below Supervised CBM (4/5): the former concept examples,
            # learned vectors and tests can be retained; the latter concept values and the
            # prediction head can be inspected.
            # Comparison: CAVs (3/5) scores below Post-hoc CBM (concept-only) (4/5): the former
            # concept examples, learned vectors and tests can be retained; the latter stored
            # projections and sparse head permit inspection.
            # Calibration: Neutral bin: the evidence does not warrant a general stronger or weaker
            # claim on this exact property. A tie is not demonstrated empirical equivalence.
            # Evidence: qualitative comparative inference; see study cards for direct endpoints and
            # counterevidence. Confidence: moderate.
            # Sources: TCAV, CBM, CBM_LIMIT, PCBM. Comparative studies: no matched direct study
            # located; mechanism/threat-model inference. See documentation §6 for endpoints and
            # limits.
            # Primary locations: TCAV: CAV construction, directional derivatives and significance
            # testing
            'traceability': 3,
            # Rating 3/5; original=1; v3.3.11=3. retained after comparative review.
            # Reason: Fits concept classifiers on frozen activations; it does not require training
            # the underlying neural network.
            # Comparison: CAVs (3/5) scores above Supervised CBM (2/5): the former post-hoc linear
            # probes use an existing network rather than retraining it; the latter concept
            # annotations and predictor training are required.
            # Comparison: CAVs (3/5) ties Post-hoc CBM (concept-only) (3/5): the former post-hoc
            # linear probes use an existing network rather than retraining it; the latter a frozen
            # backbone reduces training and annotation burden.
            # Calibration: Neutral bin: the evidence does not warrant a general stronger or weaker
            # claim on this exact property. A tie is not demonstrated empirical equivalence.
            # Evidence: qualitative comparative inference; see study cards for direct endpoints and
            # counterevidence. Confidence: moderate.
            # Sources: TCAV, CBM, CBM_LIMIT, PCBM. Comparative studies: E13. See documentation §6
            # for endpoints and limits.
            # Primary locations: TCAV: CAV construction, directional derivatives and significance
            # testing
            'runtime_performance_and_implementation_constraints': 3,
        },
        'scope_stage': 'local-expost',
        'models': ['deep-neural-networks (CNNs, RNNs, Transformers)'],
        'explanation_target': 'model output',
        "question_types": {'how_computed', 'what_feature'},
    },
    # DeepLIFT with fixed reference and propagation rules.
    'DeepLift': {
        "subprops": {
            # Rating 3/5; original=3; v3.3.11=3. retained after comparative review.
            # Reason: Reference-based contributions are useful but do not establish absence of
            # irrelevant features.
            # Comparison: DeepLift (3/5) ties DeepSHAP (3/5): the former reference contributions are
            # not per-feature necessity certificates; the latter approximate background-based
            # allocation retains relevance limitations.
            # Comparison: DeepLift (3/5) ties LRP (3/5): the former reference contributions are not
            # per-feature necessity certificates; the latter conservation does not establish
            # decision relevance.
            # Calibration: Neutral bin: the evidence does not warrant a general stronger or weaker
            # claim on this exact property. A tie is not demonstrated empirical equivalence.
            # Evidence: qualitative comparative inference; see study cards for direct endpoints and
            # counterevidence. Confidence: moderate.
            # Sources: DEEPLIFT, SIXT, DEEPSHAP, RELEVANCE, LRP, IG. Comparative studies: E01, E09,
            # E10, E17. See documentation §6 for endpoints and limits.
            # Primary locations: DEEPLIFT: Reference-based differences and contribution propagation
            # rules; SIXT: §§2–4; positive-relevance LRP variants, DeepLIFT, VGG-16/ResNet-50;
            # variant-specific findings
            'no_false_positives': 3,
            # Rating 3/5; original=3; v3.3.11=3. retained after comparative review.
            # Reason: Summation-to-delta does not prove every relevant factor is recovered.
            # Comparison: DeepLift (3/5) ties DeepSHAP (3/5): the former summation-to-delta does not
            # certify contributor recall; the latter propagation and references can miss relevant
            # effects.
            # Comparison: DeepLift (3/5) ties LRP (3/5): the former summation-to-delta does not
            # certify contributor recall; the latter some positive-only variants lose later-layer
            # information.
            # Calibration: Neutral bin: the evidence does not warrant a general stronger or weaker
            # claim on this exact property. A tie is not demonstrated empirical equivalence.
            # Evidence: qualitative comparative inference; see study cards for direct endpoints and
            # counterevidence. Confidence: moderate.
            # Sources: DEEPLIFT, SIXT, DEEPSHAP, LRP, IG. Comparative studies: E01, E09, E10, E17.
            # See documentation §6 for endpoints and limits.
            # Primary locations: DEEPLIFT: Reference-based differences and contribution propagation
            # rules; SIXT: §§2–4; positive-relevance LRP variants, DeepLIFT, VGG-16/ResNet-50;
            # variant-specific findings
            'no_false_negatives': 3,
            # Rating 3/5; original=3; v3.3.11=3. retained after comparative review.
            # Reason: An additive decomposition relative to a reference is not the complete decision
            # rationale.
            # Comparison: DeepLift (3/5) ties DeepSHAP (3/5): the former a reference-relative
            # allocation is not the full decision rationale; the latter background-relative
            # reconstruction is not a full rationale.
            # Comparison: DeepLift (3/5) ties LRP (3/5): the former a reference-relative allocation
            # is not the full decision rationale; the latter redistribution omits the full
            # computation’s explanatory structure.
            # Calibration: Neutral bin: the evidence does not warrant a general stronger or weaker
            # claim on this exact property. A tie is not demonstrated empirical equivalence.
            # Evidence: qualitative comparative inference; see study cards for direct endpoints and
            # counterevidence. Confidence: moderate.
            # Sources: DEEPLIFT, SIXT, DEEPSHAP, LRP. Comparative studies: E01, E09, E10, E17. See
            # documentation §6 for endpoints and limits.
            # Primary locations: DEEPLIFT: Reference-based differences and contribution propagation
            # rules; SIXT: §§2–4; positive-relevance LRP variants, DeepLIFT, VGG-16/ResNet-50;
            # variant-specific findings
            'completeness': 3,
            # Rating 3/5; original=3; v3.3.11=3. retained after comparative review.
            # Reason: Fixed references remove sampling variation; sensitivity to input and
            # representation remains.
            # Comparison: DeepLift (3/5) ties DeepSHAP (3/5): the former fixed-reference propagation
            # avoids local surrogate resampling; the latter fixed background avoids resampling but
            # retains input dependence.
            # Comparison: DeepLift (3/5) scores above LRP (1/5): the former fixed-reference
            # propagation avoids local surrogate resampling; the latter unprotected relevance maps
            # can change sharply under perturbations.
            # Calibration: Neutral bin: the evidence does not warrant a general stronger or weaker
            # claim on this exact property. A tie is not demonstrated empirical equivalence.
            # Evidence: qualitative comparative inference; see study cards for direct endpoints and
            # counterevidence. Confidence: low.
            # Sources: DEEPLIFT, SALIENCY, ROBUST, DEEPSHAP, LRP. Comparative studies: no matched
            # direct study located; mechanism/threat-model inference. See documentation §6 for
            # endpoints and limits.
            # Primary locations: DEEPLIFT: Reference-based differences and contribution propagation
            # rules; SALIENCY: Input invariance, reference dependence and saliency counterexamples;
            # ROBUST: §§2–3 neighborhood sensitivity and worst-case perturbations; §4 interpretation
            'stability': 3,
            # Rating 2/5; original=2; v3.3.11=2. retained after comparative review.
            # Reason: Reference/representation sensitivity motivates a cautious below-neutral prior,
            # not a universal attack result.
            # Comparison: DeepLift (2/5) scores below DeepSHAP (3/5): the former reference-based
            # propagation has no general attack protection; the latter approximate Shapley structure
            # is not an attack defense.
            # Comparison: DeepLift (2/5) scores above LRP (1/5): the former reference-based
            # propagation has no general attack protection; the latter manipulation and invariance
            # failures limit confidence.
            # Calibration: A below-neutral limitation. The integer is an ordinal coding decision;
            # neither the unit gap nor universal superiority/inferiority is measured.
            # Evidence: qualitative comparative inference; see study cards for direct endpoints and
            # counterevidence. Confidence: low.
            # Sources: DEEPLIFT, SALIENCY, ROBUST, DEEPSHAP, LRP. Comparative studies: E17. See
            # documentation §6 for endpoints and limits.
            # Primary locations: DEEPLIFT: Reference-based differences and contribution propagation
            # rules; SALIENCY: Input invariance, reference dependence and saliency counterexamples;
            # ROBUST: §§2–3 neighborhood sensitivity and worst-case perturbations; §4 interpretation
            'adversarial_robustness': 2,
            # Rating 3/5; original=3; v3.3.11=3. retained after comparative review.
            # Reason: Fixed execution can repeat; cross-model consistency is not guaranteed by the
            # attribution definition.
            # Comparison: DeepLift (3/5) ties DeepSHAP (3/5): the former fixed rules and reference
            # help replay, without temporal guarantees; the latter fixed backgrounds help replay but
            # not cross-model agreement.
            # Comparison: DeepLift (3/5) ties LRP (3/5): the former fixed rules and reference help
            # replay, without temporal guarantees; the latter fixed propagation rules support
            # replay, not invariance across models.
            # Calibration: Neutral bin: the evidence does not warrant a general stronger or weaker
            # claim on this exact property. A tie is not demonstrated empirical equivalence.
            # Evidence: qualitative comparative inference; see study cards for direct endpoints and
            # counterevidence. Confidence: low.
            # Sources: DEEPLIFT, DEEPSHAP, LRP. Comparative studies: E09, E10, E17. See
            # documentation §6 for endpoints and limits.
            # Primary locations: DEEPLIFT: Reference-based differences and contribution propagation
            # rules
            'consistency': 3,
            # Rating 1/5; original=1; v3.3.11=1. retained after comparative review.
            # Reason: Reference choice can materially change contributions; the original low
            # comparative rating is defensible without treating dependence as inevitable failure.
            # Comparison: DeepLift (1/5) scores below DeepSHAP (2/5): the former changing the
            # reference or propagation rule can change the result; the latter background choice and
            # propagation approximations alter values.
            # Comparison: DeepLift (1/5) ties LRP (1/5): the former changing the reference or
            # propagation rule can change the result; the latter epsilon and positive/negative
            # propagation rules materially affect output.
            # Calibration: An inherited endpoint under the stated output/configuration, not a
            # universal guarantee or universal failure. The exact endpoint is low-confidence outside
            # that setting.
            # Evidence: qualitative comparative inference; see study cards for direct endpoints and
            # counterevidence. Confidence: low.
            # Sources: DEEPLIFT, DEEPSHAP, LRP. Comparative studies: E09. See documentation §6 for
            # endpoints and limits.
            # Primary locations: DEEPLIFT: Reference-based differences and contribution propagation
            # rules
            'hyperparameters_perturbation_robustness': 1,
            # Rating 3/5; original=3; v3.3.11=3. retained after comparative review.
            # Reason: Feature attributions can be dense or truncated for presentation. Retain the
            # original neutral rating; selection does not establish minimality.
            # Comparison: DeepLift (3/5) ties DeepSHAP (3/5): the former an attribution vector is
            # not intrinsically a minimal feature set; the latter the full attribution vector need
            # not be sparse.
            # Comparison: DeepLift (3/5) scores above LRP (2/5): the former an attribution vector is
            # not intrinsically a minimal feature set; the latter dense pixel maps can involve many
            # features.
            # Calibration: Neutral bin: the evidence does not warrant a general stronger or weaker
            # claim on this exact property. A tie is not demonstrated empirical equivalence.
            # Evidence: qualitative comparative inference; see study cards for direct endpoints and
            # counterevidence. Confidence: moderate.
            # Sources: DEEPLIFT, DEEPSHAP, LRP. Comparative studies: no matched direct study
            # located; mechanism/threat-model inference. See documentation §6 for endpoints and
            # limits.
            # Primary locations: DEEPLIFT: Reference-based differences and contribution propagation
            # rules
            'sparsity': 3,
            # Rating 3/5; original=3; v3.3.11=3. retained after comparative review.
            # Reason: Feature contributions provide intermediate detail.
            # Comparison: DeepLift (3/5) ties DeepSHAP (3/5): the former signed feature
            # contributions expose allocation but not full rules; the latter feature allocations are
            # more specific than raw attention weights.
            # Comparison: DeepLift (3/5) ties LRP (3/5): the former signed feature contributions
            # expose allocation but not full rules; the latter pixel relevance gives a finer
            # allocation than a concept score.
            # Calibration: Neutral bin: the evidence does not warrant a general stronger or weaker
            # claim on this exact property. A tie is not demonstrated empirical equivalence.
            # Evidence: qualitative comparative inference; see study cards for direct endpoints and
            # counterevidence. Confidence: moderate.
            # Sources: DEEPLIFT, DEEPSHAP, LRP. Comparative studies: no matched direct study
            # located; mechanism/threat-model inference. See documentation §6 for endpoints and
            # limits.
            # Primary locations: DEEPLIFT: Reference-based differences and contribution propagation
            # rules
            'level_of_detail': 3,
            # Rating 3/5; original=3; v3.3.11=3. retained after comparative review.
            # Reason: Feature maps have no inherent privacy guarantee.
            # Comparison: DeepLift (3/5) ties DeepSHAP (3/5): the former a feature vector may leak
            # information despite being local; the latter local attributions carry no formal privacy
            # protection.
            # Comparison: DeepLift (3/5) ties LRP (3/5): the former a feature vector may leak
            # information despite being local; the latter local relevance vectors may disclose
            # training membership.
            # Calibration: Neutral bin: the evidence does not warrant a general stronger or weaker
            # claim on this exact property. A tie is not demonstrated empirical equivalence.
            # Evidence: qualitative comparative inference; see study cards for direct endpoints and
            # counterevidence. Confidence: low.
            # Sources: DEEPLIFT, PRIVACY, DEEPSHAP, LRP. Comparative studies: no matched direct
            # study located; mechanism/threat-model inference. See documentation §6 for endpoints
            # and limits.
            # Primary locations: DEEPLIFT: Reference-based differences and contribution propagation
            # rules; PRIVACY: §§3–5; direct evidence for tested gradient/IG/LRP/LIME configurations;
            # threat-model context only for other methods
            'confidentiality': 3,
            # Rating 4/5; original=3; v3.3.11=4. retained after comparative review.
            # Reason: Fixed-reference contribution propagation is inspectable and reconstructable
            # with the same retained artifacts as other deterministic attribution methods. Use the
            # same conditional 4 as LRP, IG and DeepSHAP; neither inherent randomness nor an
            # automatic audit trail is assumed.
            # Comparison: DeepLift (4/5) ties DeepSHAP (4/5): the former stored reference and
            # propagation rules support reconstruction; the latter backgrounds and propagation
            # records can be versioned.
            # Comparison: DeepLift (4/5) ties LRP (4/5): the former stored reference and propagation
            # rules support reconstruction; the latter the computational graph and propagation rule
            # can be recorded.
            # Calibration: A qualified comparative strength. The integer is an ordinal coding
            # decision; neither the unit gap nor universal superiority/inferiority is measured.
            # Evidence: qualitative comparative inference; see study cards for direct endpoints and
            # counterevidence. Confidence: moderate.
            # Sources: DEEPLIFT, DEEPSHAP, LRP. Comparative studies: no matched direct study
            # located; mechanism/threat-model inference. See documentation §6 for endpoints and
            # limits.
            # Primary locations: DEEPLIFT: Reference-based differences and contribution propagation
            # rules
            'traceability': 4,
            # Rating 4/5; original=4; v3.3.11=4. retained after comparative review.
            # Reason: A contribution backpropagation pass is cheaper than multi-baseline or
            # multi-step integration approaches.
            # Comparison: DeepLift (4/5) scores above DeepSHAP (3/5): the former modified
            # backpropagation avoids a many-point path integral; the latter cost grows with the
            # background set, exceeding one-reference propagation.
            # Comparison: DeepLift (4/5) ties LRP (4/5): the former modified backpropagation avoids
            # a many-point path integral; the latter a propagation pass avoids sampling many
            # coalitions.
            # Calibration: A qualified comparative strength. The integer is an ordinal coding
            # decision; neither the unit gap nor universal superiority/inferiority is measured.
            # Evidence: qualitative comparative inference; see study cards for direct endpoints and
            # counterevidence. Confidence: moderate.
            # Sources: DEEPLIFT, DEEPSHAP, LRP. Comparative studies: E01, E10. See documentation §6
            # for endpoints and limits.
            # Primary locations: DEEPLIFT: Reference-based differences and contribution propagation
            # rules
            'runtime_performance_and_implementation_constraints': 4,
        },
        'scope_stage': 'local-expost',
        'models': ['deep-neural-networks (feed-forward, CNNs, RNN/LSTM, Transformers)'],
        'explanation_target': 'model output',
        "question_types": {'how_computed', 'what_feature', 'what_if'},
    },
    # DeepExplainer approximation with a fixed background set.
    'DeepSHAP': {
        "subprops": {
            # Rating 3/5; original=4; v3.3.11=3. retained after comparative review.
            # Reason: Approximate propagation has no blanket guarantee of identifying only directly
            # influential features. Exact Shapley computation also lacks a universal
            # logical-relevance guarantee; neutral 3 does not imply that approximation alone causes
            # every relevance error.
            # Comparison: DeepSHAP (3/5) ties DeepLift (3/5): the former approximate
            # background-based allocation retains relevance limitations; the latter reference
            # contributions are not per-feature necessity certificates.
            # Comparison: DeepSHAP (3/5) ties LRP (3/5): the former approximate background-based
            # allocation retains relevance limitations; the latter conservation does not establish
            # decision relevance.
            # Calibration: Neutral bin: the evidence does not warrant a general stronger or weaker
            # claim on this exact property. A tie is not demonstrated empirical equivalence.
            # Evidence: qualitative comparative inference; see study cards for direct endpoints and
            # counterevidence. Confidence: moderate.
            # Sources: DEEPSHAP, RELEVANCE, DEEPLIFT, SIXT, LRP, IG. Comparative studies: E01, E20.
            # See documentation §6 for endpoints and limits.
            # Primary locations: DEEPSHAP: DeepExplainer: approximate SHAP values using background
            # samples and modified DeepLIFT rules; RELEVANCE: Sections 6–7: counterexamples under
            # abductive feature relevance
            'no_false_positives': 3,
            # Rating 3/5; original=4; v3.3.11=3. retained after comparative review.
            # Reason: Approximation and reference choice can miss effects; no universal advantage
            # over DeepLIFT is established.
            # Comparison: DeepSHAP (3/5) ties DeepLift (3/5): the former propagation and references
            # can miss relevant effects; the latter summation-to-delta does not certify contributor
            # recall.
            # Comparison: DeepSHAP (3/5) ties LRP (3/5): the former propagation and references can
            # miss relevant effects; the latter some positive-only variants lose later-layer
            # information.
            # Calibration: Neutral bin: the evidence does not warrant a general stronger or weaker
            # claim on this exact property. A tie is not demonstrated empirical equivalence.
            # Evidence: qualitative comparative inference; see study cards for direct endpoints and
            # counterevidence. Confidence: moderate.
            # Sources: DEEPSHAP, DEEPLIFT, SIXT, LRP, IG. Comparative studies: E01, E20. See
            # documentation §6 for endpoints and limits.
            # Primary locations: DEEPSHAP: DeepExplainer description, background sample dependence
            # and supported inputs
            'no_false_negatives': 3,
            # Rating 3/5; original=3; v3.3.11=3. retained after comparative review.
            # Reason: Expected-output reconstruction is distinct from complete explanatory coverage.
            # Comparison: DeepSHAP (3/5) ties DeepLift (3/5): the former background-relative
            # reconstruction is not a full rationale; the latter a reference-relative allocation is
            # not the full decision rationale.
            # Comparison: DeepSHAP (3/5) ties LRP (3/5): the former background-relative
            # reconstruction is not a full rationale; the latter redistribution omits the full
            # computation’s explanatory structure.
            # Calibration: Neutral bin: the evidence does not warrant a general stronger or weaker
            # claim on this exact property. A tie is not demonstrated empirical equivalence.
            # Evidence: qualitative comparative inference; see study cards for direct endpoints and
            # counterevidence. Confidence: moderate.
            # Sources: DEEPSHAP, DEEPLIFT, SIXT, LRP. Comparative studies: E01, E20. See
            # documentation §6 for endpoints and limits.
            # Primary locations: DEEPSHAP: DeepExplainer description, background sample dependence
            # and supported inputs
            'completeness': 3,
            # Rating 3/5; original=2; v3.3.11=3. retained after comparative review.
            # Reason: Fixed background execution need not be stochastic; background and input
            # sensitivity remain.
            # Comparison: DeepSHAP (3/5) ties DeepLift (3/5): the former fixed background avoids
            # resampling but retains input dependence; the latter fixed-reference propagation avoids
            # local surrogate resampling.
            # Comparison: DeepSHAP (3/5) scores above LRP (1/5): the former fixed background avoids
            # resampling but retains input dependence; the latter unprotected relevance maps can
            # change sharply under perturbations.
            # Calibration: Neutral bin: the evidence does not warrant a general stronger or weaker
            # claim on this exact property. A tie is not demonstrated empirical equivalence.
            # Evidence: qualitative comparative inference; see study cards for direct endpoints and
            # counterevidence. Confidence: low.
            # Sources: DEEPSHAP, SALIENCY, ROBUST, DEEPLIFT, LRP. Comparative studies: no matched
            # direct study located; mechanism/threat-model inference. See documentation §6 for
            # endpoints and limits.
            # Primary locations: DEEPSHAP: DeepExplainer description, background sample dependence
            # and supported inputs; SALIENCY: Input invariance, reference dependence and saliency
            # counterexamples; ROBUST: §§2–3 neighborhood sensitivity and worst-case perturbations;
            # §4 interpretation
            'stability': 3,
            # Rating 3/5; original=3; v3.3.11=3. retained after comparative review.
            # Reason: No broadly established attack-resistance ordering follows from approximation;
            # retain the original neutral 3 instead of an unsupported new penalty.
            # Comparison: DeepSHAP (3/5) scores above DeepLift (2/5): the former approximate Shapley
            # structure is not an attack defense; the latter reference-based propagation has no
            # general attack protection.
            # Comparison: DeepSHAP (3/5) scores above LRP (1/5): the former approximate Shapley
            # structure is not an attack defense; the latter manipulation and invariance failures
            # limit confidence.
            # Calibration: Neutral bin: the evidence does not warrant a general stronger or weaker
            # claim on this exact property. A tie is not demonstrated empirical equivalence.
            # Evidence: qualitative comparative inference; see study cards for direct endpoints and
            # counterevidence. Confidence: low.
            # Sources: DEEPSHAP, SALIENCY, ROBUST, DEEPLIFT, LRP. Comparative studies: no matched
            # direct study located; mechanism/threat-model inference. See documentation §6 for
            # endpoints and limits.
            # Primary locations: DEEPSHAP: DeepExplainer description, background sample dependence
            # and supported inputs; SALIENCY: Input invariance, reference dependence and saliency
            # counterexamples; ROBUST: §§2–3 neighborhood sensitivity and worst-case perturbations;
            # §4 interpretation
            'adversarial_robustness': 3,
            # Rating 3/5; original=4; v3.3.11=3. retained after comparative review.
            # Reason: Approximation does not establish the retained across-instance and across-time
            # consistency.
            # Comparison: DeepSHAP (3/5) ties DeepLift (3/5): the former fixed backgrounds help
            # replay but not cross-model agreement; the latter fixed rules and reference help
            # replay, without temporal guarantees.
            # Comparison: DeepSHAP (3/5) ties LRP (3/5): the former fixed backgrounds help replay
            # but not cross-model agreement; the latter fixed propagation rules support replay, not
            # invariance across models.
            # Calibration: Neutral bin: the evidence does not warrant a general stronger or weaker
            # claim on this exact property. A tie is not demonstrated empirical equivalence.
            # Evidence: qualitative comparative inference; see study cards for direct endpoints and
            # counterevidence. Confidence: low.
            # Sources: DEEPSHAP, DEEPLIFT, LRP. Comparative studies: no matched direct study
            # located; mechanism/threat-model inference. See documentation §6 for endpoints and
            # limits.
            # Primary locations: DEEPSHAP: DeepExplainer description, background sample dependence
            # and supported inputs
            'consistency': 3,
            # Rating 2/5; original=2; v3.3.11=2. retained after comparative review.
            # Reason: Background set and supported propagation operations affect results.
            # Comparison: DeepSHAP (2/5) scores above DeepLift (1/5): the former background choice
            # and propagation approximations alter values; the latter changing the reference or
            # propagation rule can change the result.
            # Comparison: DeepSHAP (2/5) scores above LRP (1/5): the former background choice and
            # propagation approximations alter values; the latter epsilon and positive/negative
            # propagation rules materially affect output.
            # Calibration: A below-neutral limitation. The integer is an ordinal coding decision;
            # neither the unit gap nor universal superiority/inferiority is measured.
            # Evidence: qualitative comparative inference; see study cards for direct endpoints and
            # counterevidence. Confidence: low.
            # Sources: DEEPSHAP, DEEPLIFT, LRP. Comparative studies: E20. See documentation §6 for
            # endpoints and limits.
            # Primary locations: DEEPSHAP: DeepExplainer description, background sample dependence
            # and supported inputs
            'hyperparameters_perturbation_robustness': 2,
            # Rating 3/5; original=3; v3.3.11=3. retained after comparative review.
            # Reason: Feature attributions can be dense or truncated for presentation. Retain the
            # original neutral rating; selection does not establish minimality.
            # Comparison: DeepSHAP (3/5) ties DeepLift (3/5): the former the full attribution vector
            # need not be sparse; the latter an attribution vector is not intrinsically a minimal
            # feature set.
            # Comparison: DeepSHAP (3/5) scores above LRP (2/5): the former the full attribution
            # vector need not be sparse; the latter dense pixel maps can involve many features.
            # Calibration: Neutral bin: the evidence does not warrant a general stronger or weaker
            # claim on this exact property. A tie is not demonstrated empirical equivalence.
            # Evidence: qualitative comparative inference; see study cards for direct endpoints and
            # counterevidence. Confidence: moderate.
            # Sources: DEEPSHAP, DEEPLIFT, LRP. Comparative studies: no matched direct study
            # located; mechanism/threat-model inference. See documentation §6 for endpoints and
            # limits.
            # Primary locations: DEEPSHAP: DeepExplainer description, background sample dependence
            # and supported inputs
            'sparsity': 3,
            # Rating 3/5; original=3; v3.3.11=3. retained after comparative review.
            # Reason: Per-feature contributions have comparable detail to DeepLIFT.
            # Comparison: DeepSHAP (3/5) ties DeepLift (3/5): the former feature allocations are
            # more specific than raw attention weights; the latter signed feature contributions
            # expose allocation but not full rules.
            # Comparison: DeepSHAP (3/5) ties LRP (3/5): the former feature allocations are more
            # specific than raw attention weights; the latter pixel relevance gives a finer
            # allocation than a concept score.
            # Calibration: Neutral bin: the evidence does not warrant a general stronger or weaker
            # claim on this exact property. A tie is not demonstrated empirical equivalence.
            # Evidence: qualitative comparative inference; see study cards for direct endpoints and
            # counterevidence. Confidence: moderate.
            # Sources: DEEPSHAP, DEEPLIFT, LRP. Comparative studies: no matched direct study
            # located; mechanism/threat-model inference. See documentation §6 for endpoints and
            # limits.
            # Primary locations: DEEPSHAP: DeepExplainer description, background sample dependence
            # and supported inputs
            'level_of_detail': 3,
            # Rating 3/5; original=3; v3.3.11=3. retained after comparative review.
            # Reason: No inherent privacy guarantee follows from background averaging.
            # Comparison: DeepSHAP (3/5) ties DeepLift (3/5): the former local attributions carry no
            # formal privacy protection; the latter a feature vector may leak information despite
            # being local.
            # Comparison: DeepSHAP (3/5) ties LRP (3/5): the former local attributions carry no
            # formal privacy protection; the latter local relevance vectors may disclose training
            # membership.
            # Calibration: Neutral bin: the evidence does not warrant a general stronger or weaker
            # claim on this exact property. A tie is not demonstrated empirical equivalence.
            # Evidence: qualitative comparative inference; see study cards for direct endpoints and
            # counterevidence. Confidence: low.
            # Sources: DEEPSHAP, PRIVACY, DEEPLIFT, LRP. Comparative studies: no matched direct
            # study located; mechanism/threat-model inference. See documentation §6 for endpoints
            # and limits.
            # Primary locations: DEEPSHAP: DeepExplainer description, background sample dependence
            # and supported inputs; PRIVACY: §§3–5; direct evidence for tested gradient/IG/LRP/LIME
            # configurations; threat-model context only for other methods
            'confidentiality': 3,
            # Rating 4/5; original=4; v3.3.11=4. retained after comparative review.
            # Reason: Archive background, model and operator implementations for reproducible
            # attribution.
            # Comparison: DeepSHAP (4/5) ties DeepLift (4/5): the former backgrounds and propagation
            # records can be versioned; the latter stored reference and propagation rules support
            # reconstruction.
            # Comparison: DeepSHAP (4/5) ties LRP (4/5): the former backgrounds and propagation
            # records can be versioned; the latter the computational graph and propagation rule can
            # be recorded.
            # Calibration: A qualified comparative strength. The integer is an ordinal coding
            # decision; neither the unit gap nor universal superiority/inferiority is measured.
            # Evidence: qualitative comparative inference; see study cards for direct endpoints and
            # counterevidence. Confidence: moderate.
            # Sources: DEEPSHAP, DEEPLIFT, LRP. Comparative studies: no matched direct study
            # located; mechanism/threat-model inference. See documentation §6 for endpoints and
            # limits.
            # Primary locations: DEEPSHAP: DeepExplainer description, background sample dependence
            # and supported inputs
            'traceability': 4,
            # Rating 3/5; original=3; v3.3.11=3. retained after comparative review.
            # Reason: Work scales with background examples; typically more than single-reference
            # DeepLIFT.
            # Comparison: DeepSHAP (3/5) scores below DeepLift (4/5): the former cost grows with the
            # background set, exceeding one-reference propagation; the latter modified
            # backpropagation avoids a many-point path integral.
            # Comparison: DeepSHAP (3/5) scores below LRP (4/5): the former cost grows with the
            # background set, exceeding one-reference propagation; the latter a propagation pass
            # avoids sampling many coalitions.
            # Calibration: Neutral bin: the evidence does not warrant a general stronger or weaker
            # claim on this exact property. A tie is not demonstrated empirical equivalence.
            # Evidence: qualitative comparative inference; see study cards for direct endpoints and
            # counterevidence. Confidence: moderate.
            # Sources: DEEPSHAP, DEEPLIFT, LRP. Comparative studies: E01. See documentation §6 for
            # endpoints and limits.
            # Primary locations: DEEPSHAP: DeepExplainer description, background sample dependence
            # and supported inputs
            'runtime_performance_and_implementation_constraints': 3,
        },
        'scope_stage': 'local-expost',
        'models': ['deep-neural-networks (feed-forward, CNNs, RNN/LSTM, Transformers)'],
        'explanation_target': 'model output',
        "question_types": {'how_computed', 'what_feature', 'what_if'},
    },
    # Layer-wise relevance propagation; rule variant explicitly retained.
    'LRP': {
        "subprops": {
            # Rating 3/5; original=4; v3.3.11=3. retained after comparative review.
            # Reason: Conservation does not certify that highlighted features influence the final
            # decision. Retain an evidence-limited 3 for the broad LRP family; Sixt et al. show that
            # positive-relevance variants can ignore later-layer parameters. Those variants require
            # a lower context-specific rating than this pooled family prior.
            # Comparison: LRP (3/5) ties DeepLift (3/5): the former conservation does not establish
            # decision relevance; the latter reference contributions are not per-feature necessity
            # certificates.
            # Comparison: LRP (3/5) ties DeepSHAP (3/5): the former conservation does not establish
            # decision relevance; the latter approximate background-based allocation retains
            # relevance limitations.
            # Calibration: Neutral bin: the evidence does not warrant a general stronger or weaker
            # claim on this exact property. A tie is not demonstrated empirical equivalence.
            # Evidence: qualitative comparative inference; see study cards for direct endpoints and
            # counterevidence. Confidence: moderate.
            # Sources: LRP, IG, SIXT, DEEPLIFT, DEEPSHAP, RELEVANCE. Comparative studies: E07, E09,
            # E10, E20. See documentation §6 for endpoints and limits.
            # Primary locations: LRP: Methods: relevance decomposition and propagation rules;
            # experimental evaluations; IG: Sensitivity, implementation invariance and numerical
            # path integration; SIXT: §§2–4; positive-relevance LRP variants, DeepLIFT,
            # VGG-16/ResNet-50; variant-specific findings
            'no_false_positives': 3,
            # Rating 3/5; original=4; v3.3.11=3. retained after comparative review.
            # Reason: A conserved score need not identify every influential factor. Retain the
            # broad-family neutral 3; the documented failures of positive-relevance LRP variants
            # versus DeepLIFT prevent claiming that this tie proves equal fidelity.
            # Comparison: LRP (3/5) ties DeepLift (3/5): the former some positive-only variants lose
            # later-layer information; the latter summation-to-delta does not certify contributor
            # recall.
            # Comparison: LRP (3/5) ties DeepSHAP (3/5): the former some positive-only variants lose
            # later-layer information; the latter propagation and references can miss relevant
            # effects.
            # Calibration: Neutral bin: the evidence does not warrant a general stronger or weaker
            # claim on this exact property. A tie is not demonstrated empirical equivalence.
            # Evidence: qualitative comparative inference; see study cards for direct endpoints and
            # counterevidence. Confidence: moderate.
            # Sources: LRP, IG, SIXT, DEEPLIFT, DEEPSHAP. Comparative studies: E07, E09, E10, E20.
            # See documentation §6 for endpoints and limits.
            # Primary locations: LRP: Methods: relevance decomposition and propagation rules;
            # experimental evaluations; IG: Sensitivity, implementation invariance and numerical
            # path integration; SIXT: §§2–4; positive-relevance LRP variants, DeepLIFT,
            # VGG-16/ResNet-50; variant-specific findings
            'no_false_negatives': 3,
            # Rating 3/5; original=4; v3.3.11=3. retained after comparative review.
            # Reason: Redistributing an output quantity does not supply a complete rationale;
            # conservation depends on propagation rule.
            # Comparison: LRP (3/5) ties DeepLift (3/5): the former redistribution omits the full
            # computation’s explanatory structure; the latter a reference-relative allocation is not
            # the full decision rationale.
            # Comparison: LRP (3/5) ties DeepSHAP (3/5): the former redistribution omits the full
            # computation’s explanatory structure; the latter background-relative reconstruction is
            # not a full rationale.
            # Calibration: Neutral bin: the evidence does not warrant a general stronger or weaker
            # claim on this exact property. A tie is not demonstrated empirical equivalence.
            # Evidence: qualitative comparative inference; see study cards for direct endpoints and
            # counterevidence. Confidence: moderate.
            # Sources: LRP, SIXT, DEEPLIFT, DEEPSHAP. Comparative studies: E07, E09, E10, E20. See
            # documentation §6 for endpoints and limits.
            # Primary locations: LRP: Methods: relevance decomposition and propagation rules;
            # experimental evaluations; SIXT: §§2–4; positive-relevance LRP variants, DeepLIFT,
            # VGG-16/ResNet-50; variant-specific findings
            'completeness': 3,
            # Rating 1/5; original=1; v3.3.11=1. retained after comparative review.
            # Reason: The original low prior represents sensitivity of unstabilized relevance maps;
            # fixed-input deterministic replay is a different property.
            # Comparison: LRP (1/5) scores below Integrated Gradients (3/5): the former unprotected
            # relevance maps can change sharply under perturbations; the latter path integration
            # does not ensure local input continuity.
            # Comparison: LRP (1/5) ties LIME (1/5): the former unprotected relevance maps can
            # change sharply under perturbations; the latter local sampling and neighborhood fitting
            # can be highly sensitive.
            # Calibration: An inherited endpoint under the stated output/configuration, not a
            # universal guarantee or universal failure. The exact endpoint is low-confidence outside
            # that setting.
            # Evidence: qualitative comparative inference; see study cards for direct endpoints and
            # counterevidence. Confidence: low.
            # Sources: LRP, SALIENCY, ROBUST, IG, LIME, MAN_CHAN. Comparative studies: E03. See
            # documentation §6 for endpoints and limits.
            # Primary locations: LRP: Methods: relevance decomposition and propagation rules;
            # experimental evaluations; SALIENCY: Input invariance, reference dependence and
            # saliency counterexamples; ROBUST: §§2–3 neighborhood sensitivity and worst-case
            # perturbations; §4 interpretation
            'stability': 1,
            # Rating 1/5; original=1; v3.3.11=1. retained after comparative review.
            # Reason: Saliency manipulation motivates the original low comparative prior; it is not
            # a theorem that every propagation rule fails.
            # Comparison: LRP (1/5) scores below DeepLift (2/5): the former manipulation and
            # invariance failures limit confidence; the latter reference-based propagation has no
            # general attack protection.
            # Comparison: LRP (1/5) scores below DeepSHAP (3/5): the former manipulation and
            # invariance failures limit confidence; the latter approximate Shapley structure is not
            # an attack defense.
            # Calibration: An inherited endpoint under the stated output/configuration, not a
            # universal guarantee or universal failure. The exact endpoint is low-confidence outside
            # that setting.
            # Evidence: qualitative comparative inference; see study cards for direct endpoints and
            # counterevidence. Confidence: low.
            # Sources: LRP, SALIENCY, ROBUST, DEEPLIFT, DEEPSHAP. Comparative studies: E03. See
            # documentation §6 for endpoints and limits.
            # Primary locations: LRP: Methods: relevance decomposition and propagation rules;
            # experimental evaluations; SALIENCY: Input invariance, reference dependence and
            # saliency counterexamples; ROBUST: §§2–3 neighborhood sensitivity and worst-case
            # perturbations; §4 interpretation
            'adversarial_robustness': 1,
            # Rating 3/5; original=3; v3.3.11=3. retained after comparative review.
            # Reason: Fixed rules can repeat, but rule and model changes can alter the explanation.
            # Comparison: LRP (3/5) ties DeepLift (3/5): the former fixed propagation rules support
            # replay, not invariance across models; the latter fixed rules and reference help
            # replay, without temporal guarantees.
            # Comparison: LRP (3/5) ties DeepSHAP (3/5): the former fixed propagation rules support
            # replay, not invariance across models; the latter fixed backgrounds help replay but not
            # cross-model agreement.
            # Calibration: Neutral bin: the evidence does not warrant a general stronger or weaker
            # claim on this exact property. A tie is not demonstrated empirical equivalence.
            # Evidence: qualitative comparative inference; see study cards for direct endpoints and
            # counterevidence. Confidence: low.
            # Sources: LRP, DEEPLIFT, DEEPSHAP. Comparative studies: E09, E10. See documentation §6
            # for endpoints and limits.
            # Primary locations: LRP: Methods: relevance decomposition and propagation rules;
            # experimental evaluations
            'consistency': 3,
            # Rating 1/5; original=1; v3.3.11=1. retained after comparative review.
            # Reason: Propagation rules and stabilizers materially affect maps; the original weak
            # anchor is retained as a comparative judgment.
            # Comparison: LRP (1/5) ties DeepLift (1/5): the former epsilon and positive/negative
            # propagation rules materially affect output; the latter changing the reference or
            # propagation rule can change the result.
            # Comparison: LRP (1/5) scores below DeepSHAP (2/5): the former epsilon and
            # positive/negative propagation rules materially affect output; the latter background
            # choice and propagation approximations alter values.
            # Calibration: An inherited endpoint under the stated output/configuration, not a
            # universal guarantee or universal failure. The exact endpoint is low-confidence outside
            # that setting.
            # Evidence: qualitative comparative inference; see study cards for direct endpoints and
            # counterevidence. Confidence: low.
            # Sources: LRP, DEEPLIFT, DEEPSHAP. Comparative studies: E09, E20. See documentation §6
            # for endpoints and limits.
            # Primary locations: LRP: Methods: relevance decomposition and propagation rules;
            # experimental evaluations
            'hyperparameters_perturbation_robustness': 1,
            # Rating 2/5; original=2; v3.3.11=2. retained after comparative review.
            # Reason: Pixel or feature relevance is usually dense.
            # Comparison: LRP (2/5) scores below DeepLift (3/5): the former dense pixel maps can
            # involve many features; the latter an attribution vector is not intrinsically a minimal
            # feature set.
            # Comparison: LRP (2/5) scores below DeepSHAP (3/5): the former dense pixel maps can
            # involve many features; the latter the full attribution vector need not be sparse.
            # Calibration: A below-neutral limitation. The integer is an ordinal coding decision;
            # neither the unit gap nor universal superiority/inferiority is measured.
            # Evidence: qualitative comparative inference; see study cards for direct endpoints and
            # counterevidence. Confidence: moderate.
            # Sources: LRP, DEEPLIFT, DEEPSHAP. Comparative studies: E07. See documentation §6 for
            # endpoints and limits.
            # Primary locations: LRP: Methods: relevance decomposition and propagation rules;
            # experimental evaluations
            'sparsity': 2,
            # Rating 3/5; original=3; v3.3.11=3. retained after comparative review.
            # Reason: Feature-resolution relevance is intermediate detail, not full logic.
            # Comparison: LRP (3/5) ties DeepLift (3/5): the former pixel relevance gives a finer
            # allocation than a concept score; the latter signed feature contributions expose
            # allocation but not full rules.
            # Comparison: LRP (3/5) ties DeepSHAP (3/5): the former pixel relevance gives a finer
            # allocation than a concept score; the latter feature allocations are more specific than
            # raw attention weights.
            # Calibration: Neutral bin: the evidence does not warrant a general stronger or weaker
            # claim on this exact property. A tie is not demonstrated empirical equivalence.
            # Evidence: qualitative comparative inference; see study cards for direct endpoints and
            # counterevidence. Confidence: moderate.
            # Sources: LRP, DEEPLIFT, DEEPSHAP. Comparative studies: E07. See documentation §6 for
            # endpoints and limits.
            # Primary locations: LRP: Methods: relevance decomposition and propagation rules;
            # experimental evaluations
            'level_of_detail': 3,
            # Rating 3/5; original=3; v3.3.11=3. retained after comparative review.
            # Reason: No inherent privacy protection is supplied by relevance conservation.
            # Comparison: LRP (3/5) ties DeepLift (3/5): the former local relevance vectors may
            # disclose training membership; the latter a feature vector may leak information despite
            # being local.
            # Comparison: LRP (3/5) ties DeepSHAP (3/5): the former local relevance vectors may
            # disclose training membership; the latter local attributions carry no formal privacy
            # protection.
            # Calibration: Neutral bin: the evidence does not warrant a general stronger or weaker
            # claim on this exact property. A tie is not demonstrated empirical equivalence.
            # Evidence: qualitative comparative inference; see study cards for direct endpoints and
            # counterevidence. Confidence: low.
            # Sources: LRP, PRIVACY, DEEPLIFT, DEEPSHAP. Comparative studies: E12. See documentation
            # §6 for endpoints and limits.
            # Primary locations: LRP: Methods: relevance decomposition and propagation rules;
            # experimental evaluations; PRIVACY: §§3–5; direct evidence for tested
            # gradient/IG/LRP/LIME configurations; threat-model context only for other methods
            'confidentiality': 3,
            # Rating 4/5; original=5; v3.3.11=4. retained after comparative review.
            # Reason: A specified computation can be reconstructed if model, input, reference or
            # propagation settings and software versions are retained. This supports strong
            # traceability, but the method supplies no complete audit trail or accountability
            # process; the retained rubric does not justify 5 from determinism alone.
            # Comparison: LRP (4/5) ties DeepLift (4/5): the former the computational graph and
            # propagation rule can be recorded; the latter stored reference and propagation rules
            # support reconstruction.
            # Comparison: LRP (4/5) ties DeepSHAP (4/5): the former the computational graph and
            # propagation rule can be recorded; the latter backgrounds and propagation records can
            # be versioned.
            # Calibration: A qualified comparative strength. The integer is an ordinal coding
            # decision; neither the unit gap nor universal superiority/inferiority is measured.
            # Evidence: qualitative comparative inference; see study cards for direct endpoints and
            # counterevidence. Confidence: moderate.
            # Sources: LRP, DEEPLIFT, DEEPSHAP. Comparative studies: no matched direct study
            # located; mechanism/threat-model inference. See documentation §6 for endpoints and
            # limits.
            # Primary locations: LRP: Methods: relevance decomposition and propagation rules;
            # experimental evaluations
            'traceability': 4,
            # Rating 4/5; original=4; v3.3.11=4. retained after comparative review.
            # Reason: Layerwise backpropagation is comparatively efficient.
            # Comparison: LRP (4/5) ties DeepLift (4/5): the former a propagation pass avoids
            # sampling many coalitions; the latter modified backpropagation avoids a many-point path
            # integral.
            # Comparison: LRP (4/5) scores above DeepSHAP (3/5): the former a propagation pass
            # avoids sampling many coalitions; the latter cost grows with the background set,
            # exceeding one-reference propagation.
            # Calibration: A qualified comparative strength. The integer is an ordinal coding
            # decision; neither the unit gap nor universal superiority/inferiority is measured.
            # Evidence: qualitative comparative inference; see study cards for direct endpoints and
            # counterevidence. Confidence: moderate.
            # Sources: LRP, DEEPLIFT, DEEPSHAP. Comparative studies: E10. See documentation §6 for
            # endpoints and limits.
            # Primary locations: LRP: Methods: relevance decomposition and propagation rules;
            # experimental evaluations
            'runtime_performance_and_implementation_constraints': 4,
        },
        'scope_stage': 'local-expost',
        'models': ['deep-neural-networks (especially CNNs, RNNs, Transformers)'],
        'explanation_target': 'model output',
        "question_types": {'how_computed', 'what_feature'},
    },
    # Standard positive-evidence Grad-CAM at a convolutional layer.
    'Grad-CAM': {
        "subprops": {
            # Rating 3/5; original=3; v3.3.11=3. retained after comparative review.
            # Reason: Coarse localization can identify useful regions, without establishing
            # pixel-level necessity.
            # Comparison: Grad-CAM (3/5) ties DeepLift (3/5): the former coarse positive
            # localization does not prove pixel necessity; the latter reference contributions are
            # not per-feature necessity certificates.
            # Comparison: Grad-CAM (3/5) ties DeepSHAP (3/5): the former coarse positive
            # localization does not prove pixel necessity; the latter approximate background-based
            # allocation retains relevance limitations.
            # Calibration: Neutral bin: the evidence does not warrant a general stronger or weaker
            # claim on this exact property. A tie is not demonstrated empirical equivalence.
            # Evidence: qualitative comparative inference; see study cards for direct endpoints and
            # counterevidence. Confidence: moderate.
            # Sources: GRADCAM, DEEPLIFT, SIXT, DEEPSHAP, RELEVANCE. Comparative studies: E18, E21.
            # See documentation §6 for endpoints and limits.
            # Primary locations: GRADCAM: Gradient pooling and positive class-localization
            # construction
            'no_false_positives': 3,
            # Rating 2/5; original=3; v3.3.11=2. retained after comparative review.
            # Reason: Positive-only localization omits negative evidence and finer feature
            # contributions.
            # Comparison: Grad-CAM (2/5) scores below DeepLift (3/5): the former positive-only maps
            # omit negative evidence and fine effects; the latter summation-to-delta does not
            # certify contributor recall.
            # Comparison: Grad-CAM (2/5) scores below DeepSHAP (3/5): the former positive-only maps
            # omit negative evidence and fine effects; the latter propagation and references can
            # miss relevant effects.
            # Calibration: A below-neutral limitation. The integer is an ordinal coding decision;
            # neither the unit gap nor universal superiority/inferiority is measured.
            # Evidence: qualitative comparative inference; see study cards for direct endpoints and
            # counterevidence. Confidence: moderate.
            # Sources: GRADCAM, DEEPLIFT, SIXT, DEEPSHAP. Comparative studies: E18, E21. See
            # documentation §6 for endpoints and limits.
            # Primary locations: GRADCAM: Gradient pooling and positive class-localization
            # construction
            'no_false_negatives': 2,
            # Rating 2/5; original=2; v3.3.11=2. retained after comparative review.
            # Reason: A coarse region map does not conserve all evidence or explain the full
            # decision.
            # Comparison: Grad-CAM (2/5) scores below DeepLift (3/5): the former one layer’s
            # localization is partial decision coverage; the latter a reference-relative allocation
            # is not the full decision rationale.
            # Comparison: Grad-CAM (2/5) scores below DeepSHAP (3/5): the former one layer’s
            # localization is partial decision coverage; the latter background-relative
            # reconstruction is not a full rationale.
            # Calibration: A below-neutral limitation. The integer is an ordinal coding decision;
            # neither the unit gap nor universal superiority/inferiority is measured.
            # Evidence: qualitative comparative inference; see study cards for direct endpoints and
            # counterevidence. Confidence: moderate.
            # Sources: GRADCAM, DEEPLIFT, SIXT, DEEPSHAP. Comparative studies: E18, E21. See
            # documentation §6 for endpoints and limits.
            # Primary locations: GRADCAM: Gradient pooling and positive class-localization
            # construction
            'completeness': 2,
            # Rating 2/5; original=2; v3.3.11=2. retained after comparative review.
            # Reason: Layer and gradient changes can alter localization.
            # Comparison: Grad-CAM (2/5) scores below DeepLift (3/5): the former gradient and
            # target-layer changes can shift highlighted regions; the latter fixed-reference
            # propagation avoids local surrogate resampling.
            # Comparison: Grad-CAM (2/5) scores below DeepSHAP (3/5): the former gradient and
            # target-layer changes can shift highlighted regions; the latter fixed background avoids
            # resampling but retains input dependence.
            # Calibration: A below-neutral limitation. The integer is an ordinal coding decision;
            # neither the unit gap nor universal superiority/inferiority is measured.
            # Evidence: qualitative comparative inference; see study cards for direct endpoints and
            # counterevidence. Confidence: low.
            # Sources: GRADCAM, SALIENCY, ROBUST, DEEPLIFT, DEEPSHAP. Comparative studies: no
            # matched direct study located; mechanism/threat-model inference. See documentation §6
            # for endpoints and limits.
            # Primary locations: GRADCAM: Gradient pooling and positive class-localization
            # construction; SALIENCY: Input invariance, reference dependence and saliency
            # counterexamples; ROBUST: §§2–3 neighborhood sensitivity and worst-case perturbations;
            # §4 interpretation
            'stability': 2,
            # Rating 2/5; original=4; v3.3.11=2. retained after comparative review.
            # Reason: Published model and input manipulation can produce misleading Grad-CAM maps
            # while preserving prediction accuracy. Retain the below-neutral 2; gradient pooling
            # does not confer attack resistance.
            # Comparison: Grad-CAM (2/5) ties DeepLift (2/5): the former targeted localization
            # manipulation has been demonstrated; the latter reference-based propagation has no
            # general attack protection.
            # Comparison: Grad-CAM (2/5) scores below DeepSHAP (3/5): the former targeted
            # localization manipulation has been demonstrated; the latter approximate Shapley
            # structure is not an attack defense.
            # Calibration: A below-neutral limitation. The integer is an ordinal coding decision;
            # neither the unit gap nor universal superiority/inferiority is measured.
            # Evidence: qualitative comparative inference; see study cards for direct endpoints and
            # counterevidence. Confidence: low.
            # Sources: GRADCAM, GRADCAM_ATTACK, DEEPLIFT, SALIENCY, ROBUST, DEEPSHAP. Comparative
            # studies: E18. See documentation §6 for endpoints and limits.
            # Primary locations: GRADCAM: Gradient pooling and positive class-localization
            # construction; GRADCAM_ATTACK: Model manipulation and trigger-based input attacks on
            # Grad-CAM
            'adversarial_robustness': 2,
            # Rating 3/5; original=3; v3.3.11=3. retained after comparative review.
            # Reason: Fixed inference repeats, but model and sample changes can alter maps.
            # Comparison: Grad-CAM (3/5) ties DeepLift (3/5): the former fixed layer and model give
            # repeatable maps; the latter fixed rules and reference help replay, without temporal
            # guarantees.
            # Comparison: Grad-CAM (3/5) ties DeepSHAP (3/5): the former fixed layer and model give
            # repeatable maps; the latter fixed backgrounds help replay but not cross-model
            # agreement.
            # Calibration: Neutral bin: the evidence does not warrant a general stronger or weaker
            # claim on this exact property. A tie is not demonstrated empirical equivalence.
            # Evidence: qualitative comparative inference; see study cards for direct endpoints and
            # counterevidence. Confidence: low.
            # Sources: GRADCAM, DEEPLIFT, DEEPSHAP. Comparative studies: no matched direct study
            # located; mechanism/threat-model inference. See documentation §6 for endpoints and
            # limits.
            # Primary locations: GRADCAM: Gradient pooling and positive class-localization
            # construction
            'consistency': 3,
            # Rating 2/5; original=2; v3.3.11=2. retained after comparative review.
            # Reason: Chosen layer and aggregation conventions materially affect localization.
            # Comparison: Grad-CAM (2/5) scores above DeepLift (1/5): the former layer selection and
            # post-processing determine localization; the latter changing the reference or
            # propagation rule can change the result.
            # Comparison: Grad-CAM (2/5) ties DeepSHAP (2/5): the former layer selection and
            # post-processing determine localization; the latter background choice and propagation
            # approximations alter values.
            # Calibration: A below-neutral limitation. The integer is an ordinal coding decision;
            # neither the unit gap nor universal superiority/inferiority is measured.
            # Evidence: qualitative comparative inference; see study cards for direct endpoints and
            # counterevidence. Confidence: low.
            # Sources: GRADCAM, DEEPLIFT, DEEPSHAP. Comparative studies: E18. See documentation §6
            # for endpoints and limits.
            # Primary locations: GRADCAM: Gradient pooling and positive class-localization
            # construction
            'hyperparameters_perturbation_robustness': 2,
            # Rating 3/5; original=3; v3.3.11=3. retained after comparative review.
            # Reason: Localized regions can be compact but do not enforce a minimal feature set.
            # Comparison: Grad-CAM (3/5) ties DeepLift (3/5): the former a coarse region map may be
            # compact but is not minimal; the latter an attribution vector is not intrinsically a
            # minimal feature set.
            # Comparison: Grad-CAM (3/5) ties DeepSHAP (3/5): the former a coarse region map may be
            # compact but is not minimal; the latter the full attribution vector need not be sparse.
            # Calibration: Neutral bin: the evidence does not warrant a general stronger or weaker
            # claim on this exact property. A tie is not demonstrated empirical equivalence.
            # Evidence: qualitative comparative inference; see study cards for direct endpoints and
            # counterevidence. Confidence: moderate.
            # Sources: GRADCAM, DEEPLIFT, DEEPSHAP. Comparative studies: no matched direct study
            # located; mechanism/threat-model inference. See documentation §6 for endpoints and
            # limits.
            # Primary locations: GRADCAM: Gradient pooling and positive class-localization
            # construction
            'sparsity': 3,
            # Rating 3/5; original=3; v3.3.11=3. retained after comparative review.
            # Reason: Coarse class-localization maps offer feature-region detail; retain neutral 3,
            # with resolution limitations explicit.
            # Comparison: Grad-CAM (3/5) ties DeepLift (3/5): the former coarse feature maps give
            # less mechanism detail than explicit rules; the latter signed feature contributions
            # expose allocation but not full rules.
            # Comparison: Grad-CAM (3/5) ties DeepSHAP (3/5): the former coarse feature maps give
            # less mechanism detail than explicit rules; the latter feature allocations are more
            # specific than raw attention weights.
            # Calibration: Neutral bin: the evidence does not warrant a general stronger or weaker
            # claim on this exact property. A tie is not demonstrated empirical equivalence.
            # Evidence: qualitative comparative inference; see study cards for direct endpoints and
            # counterevidence. Confidence: moderate.
            # Sources: GRADCAM, DEEPLIFT, DEEPSHAP. Comparative studies: E21. See documentation §6
            # for endpoints and limits.
            # Primary locations: GRADCAM: Gradient pooling and positive class-localization
            # construction
            'level_of_detail': 3,
            # Rating 3/5; original=3; v3.3.11=3. retained after comparative review.
            # Reason: Heatmaps do not inherently protect information about inputs or models.
            # Comparison: Grad-CAM (3/5) ties DeepLift (3/5): the former local maps lack formal
            # confidentiality protection; the latter a feature vector may leak information despite
            # being local.
            # Comparison: Grad-CAM (3/5) ties DeepSHAP (3/5): the former local maps lack formal
            # confidentiality protection; the latter local attributions carry no formal privacy
            # protection.
            # Calibration: Neutral bin: the evidence does not warrant a general stronger or weaker
            # claim on this exact property. A tie is not demonstrated empirical equivalence.
            # Evidence: qualitative comparative inference; see study cards for direct endpoints and
            # counterevidence. Confidence: low.
            # Sources: GRADCAM, PRIVACY, DEEPLIFT, DEEPSHAP. Comparative studies: no matched direct
            # study located; mechanism/threat-model inference. See documentation §6 for endpoints
            # and limits.
            # Primary locations: GRADCAM: Gradient pooling and positive class-localization
            # construction; PRIVACY: §§3–5; direct evidence for tested gradient/IG/LRP/LIME
            # configurations; threat-model context only for other methods
            'confidentiality': 3,
            # Rating 4/5; original=5; v3.3.11=4. retained after comparative review.
            # Reason: A specified computation can be reconstructed if model, input, reference or
            # propagation settings and software versions are retained. This supports strong
            # traceability, but the method supplies no complete audit trail or accountability
            # process; the retained rubric does not justify 5 from determinism alone.
            # Comparison: Grad-CAM (4/5) ties DeepLift (4/5): the former layer, class target and
            # gradients identify the computation; the latter stored reference and propagation rules
            # support reconstruction.
            # Comparison: Grad-CAM (4/5) ties DeepSHAP (4/5): the former layer, class target and
            # gradients identify the computation; the latter backgrounds and propagation records can
            # be versioned.
            # Calibration: A qualified comparative strength. The integer is an ordinal coding
            # decision; neither the unit gap nor universal superiority/inferiority is measured.
            # Evidence: qualitative comparative inference; see study cards for direct endpoints and
            # counterevidence. Confidence: moderate.
            # Sources: GRADCAM, DEEPLIFT, DEEPSHAP. Comparative studies: no matched direct study
            # located; mechanism/threat-model inference. See documentation §6 for endpoints and
            # limits.
            # Primary locations: GRADCAM: Gradient pooling and positive class-localization
            # construction
            'traceability': 4,
            # Rating 5/5; original=5; v3.3.11=5. retained after comparative review.
            # Reason: For a fixed network, one gradient pass and pooling give a top relative runtime
            # rating; memory remains architecture-dependent.
            # Comparison: Grad-CAM (5/5) scores above DeepLift (4/5): the former one
            # forward/backward calculation is comparatively inexpensive; the latter modified
            # backpropagation avoids a many-point path integral.
            # Comparison: Grad-CAM (5/5) scores above Integrated Gradients (2/5): the former one
            # forward/backward calculation is comparatively inexpensive; the latter many gradient
            # evaluations cost more than one backward pass.
            # Calibration: An inherited endpoint under the stated output/configuration, not a
            # universal guarantee or universal failure. The exact endpoint is low-confidence outside
            # that setting.
            # Evidence: qualitative comparative inference; see study cards for direct endpoints and
            # counterevidence. Confidence: low.
            # Sources: GRADCAM, DEEPLIFT, IG. Comparative studies: E21. See documentation §6 for
            # endpoints and limits.
            # Primary locations: GRADCAM: Gradient pooling and positive class-localization
            # construction
            'runtime_performance_and_implementation_constraints': 5,
        },
        'scope_stage': 'local-expost',
        'models': ['convolutional neural networks (2-D/3-D, vision, video)'],
        'explanation_target': 'model output',
        "question_types": {'how_computed', 'what_feature'},
    },
    # Integrated Gradients with numerical quadrature and a fixed baseline.
    'Integrated Gradients': {
        "subprops": {
            # Rating 4/5; original=4; v3.3.11=4. retained after comparative review.
            # Reason: Sensitivity(b), or the dummy axiom, assigns zero to variables on which the
            # model function does not depend. This directly supports a qualified 4 for avoiding
            # globally unused features. It does not prove necessity for one decision, causal
            # relevance, or baseline invariance.
            # Comparison: Integrated Gradients (4/5) scores above DeepLift (3/5): the former the
            # dummy axiom excludes globally unused function variables; the latter reference
            # contributions are not per-feature necessity certificates.
            # Comparison: Integrated Gradients (4/5) scores above Exact local SHAP (3/5): the former
            # the dummy axiom excludes globally unused function variables; the latter exact game
            # allocation is not generic decision-feature necessity.
            # Calibration: A qualified comparative strength. The integer is an ordinal coding
            # decision; neither the unit gap nor universal superiority/inferiority is measured.
            # Evidence: qualitative comparative inference; see study cards for direct endpoints and
            # counterevidence. Confidence: moderate.
            # Sources: IG, DEEPLIFT, SIXT, SHAP, RELEVANCE, MANY_SHAP. Comparative studies: E09,
            # E10, E17, E20. See documentation §6 for endpoints and limits.
            # Primary locations: IG: Section 4.1: Sensitivity(b) / dummy and Proposition 2; Section
            # 2.2 implementation invariance
            'no_false_positives': 4,
            # Rating 3/5; original=4; v3.3.11=4. corrected in this review.
            # Reason: Corrected 4 to 3: Sensitivity(a) addresses a single changed feature between
            # baseline and input. It does not imply recovery of every influence in general
            # multifeature cases; a coordinate equal to its baseline receives zero even when the
            # function depends on it. Tie DeepLIFT at 3: both address saturation, and no general
            # recall advantage over DeepLIFT is established.
            # Comparison: Integrated Gradients (3/5) ties DeepLift (3/5): the former one-feature
            # Sensitivity(a) is not universal contributor recall; the latter summation-to-delta does
            # not certify contributor recall.
            # Comparison: Integrated Gradients (3/5) scores above Grad-CAM (2/5): the former
            # one-feature Sensitivity(a) is not universal contributor recall; the latter
            # positive-only maps omit negative evidence and fine effects.
            # Calibration: Neutral bin: the evidence does not warrant a general stronger or weaker
            # claim on this exact property. A tie is not demonstrated empirical equivalence.
            # Evidence: qualitative comparative inference; see study cards for direct endpoints and
            # counterevidence. Confidence: low.
            # Sources: IG, DEEPLIFT, SIXT, GRADCAM. Comparative studies: E09, E10, E17, E20. See
            # documentation §6 for endpoints and limits.
            # Primary locations: IG: IG §2.1 and path formula; DeepLIFT saturation examples;
            # DEEPLIFT: IG §2.1 and path formula; DeepLIFT saturation examples
            'no_false_negatives': 3,
            # Rating 3/5; original=3; v3.3.11=3. retained after comparative review.
            # Reason: Path completeness is a mathematical allocation identity, not complete decision
            # rationale.
            # Comparison: Integrated Gradients (3/5) ties DeepLift (3/5): the former path
            # completeness accounts for a difference, not the full rationale; the latter a
            # reference-relative allocation is not the full decision rationale.
            # Comparison: Integrated Gradients (3/5) ties DeepSHAP (3/5): the former path
            # completeness accounts for a difference, not the full rationale; the latter
            # background-relative reconstruction is not a full rationale.
            # Calibration: Neutral bin: the evidence does not warrant a general stronger or weaker
            # claim on this exact property. A tie is not demonstrated empirical equivalence.
            # Evidence: qualitative comparative inference; see study cards for direct endpoints and
            # counterevidence. Confidence: moderate.
            # Sources: IG, DEEPLIFT, SIXT, DEEPSHAP. Comparative studies: E09, E10, E17, E20. See
            # documentation §6 for endpoints and limits.
            # Primary locations: IG: Sensitivity, implementation invariance and numerical path
            # integration
            'completeness': 3,
            # Rating 3/5; original=3; v3.3.11=3. retained after comparative review.
            # Reason: Integration does not guarantee input or baseline stability; neutral remains
            # appropriate.
            # Comparison: Integrated Gradients (3/5) ties DeepLift (3/5): the former path
            # integration does not ensure local input continuity; the latter fixed-reference
            # propagation avoids local surrogate resampling.
            # Comparison: Integrated Gradients (3/5) ties DeepSHAP (3/5): the former path
            # integration does not ensure local input continuity; the latter fixed background avoids
            # resampling but retains input dependence.
            # Calibration: Neutral bin: the evidence does not warrant a general stronger or weaker
            # claim on this exact property. A tie is not demonstrated empirical equivalence.
            # Evidence: qualitative comparative inference; see study cards for direct endpoints and
            # counterevidence. Confidence: low.
            # Sources: IG, SALIENCY, ROBUST, DEEPLIFT, DEEPSHAP. Comparative studies: E03. See
            # documentation §6 for endpoints and limits.
            # Primary locations: IG: Sensitivity, implementation invariance and numerical path
            # integration; SALIENCY: Input invariance, reference dependence and saliency
            # counterexamples; ROBUST: §§2–3 neighborhood sensitivity and worst-case perturbations;
            # §4 interpretation
            'stability': 3,
            # Rating 3/5; original=3; v3.3.11=3. retained after comparative review.
            # Reason: The comparative robustness study evaluates IG among gradient methods and finds
            # sensitivity under small, worst-case perturbations, while gradient methods are
            # generally less unstable than sampled approaches. Retain the original neutral
            # comparative 3 under a fixed baseline; this is not an attack-resistance guarantee.
            # Comparison: Integrated Gradients (3/5) scores above DeepLift (2/5): the former
            # integration does not certify resistance to malicious perturbations; the latter
            # reference-based propagation has no general attack protection.
            # Comparison: Integrated Gradients (3/5) ties DeepSHAP (3/5): the former integration
            # does not certify resistance to malicious perturbations; the latter approximate Shapley
            # structure is not an attack defense.
            # Calibration: Neutral bin: the evidence does not warrant a general stronger or weaker
            # claim on this exact property. A tie is not demonstrated empirical equivalence.
            # Evidence: qualitative comparative inference; see study cards for direct endpoints and
            # counterevidence. Confidence: low.
            # Sources: IG, ROBUST, DEEPLIFT, SALIENCY, DEEPSHAP. Comparative studies: E03, E17. See
            # documentation §6 for endpoints and limits.
            # Primary locations: IG: Sensitivity, implementation invariance and numerical path
            # integration; ROBUST: §§2–3 neighborhood sensitivity and worst-case perturbations; §4
            # interpretation
            'adversarial_robustness': 3,
            # Rating 3/5; original=4; v3.3.11=3. retained after comparative review.
            # Reason: Implementation invariance concerns functionally equivalent networks at the
            # same input. the retained rubric instead concerns data samples, runs or time; the axiom
            # does not justify an above-neutral rating on that broader property.
            # Comparison: Integrated Gradients (3/5) ties DeepLift (3/5): the former implementation
            # invariance is narrower than cross-run consistency; the latter fixed rules and
            # reference help replay, without temporal guarantees.
            # Comparison: Integrated Gradients (3/5) ties DeepSHAP (3/5): the former implementation
            # invariance is narrower than cross-run consistency; the latter fixed backgrounds help
            # replay but not cross-model agreement.
            # Calibration: Neutral bin: the evidence does not warrant a general stronger or weaker
            # claim on this exact property. A tie is not demonstrated empirical equivalence.
            # Evidence: qualitative comparative inference; see study cards for direct endpoints and
            # counterevidence. Confidence: low.
            # Sources: IG, DEEPLIFT, DEEPSHAP. Comparative studies: E09, E10, E17. See documentation
            # §6 for endpoints and limits.
            # Primary locations: IG: Sensitivity, implementation invariance and numerical path
            # integration
            'consistency': 3,
            # Rating 3/5; original=3; v3.3.11=3. retained after comparative review.
            # Reason: Baseline and quadrature settings matter; original neutral 3 is retained
            # because there is no calibrated general penalty.
            # Comparison: Integrated Gradients (3/5) scores above DeepLift (1/5): the former
            # baseline and quadrature choices remain consequential; the latter changing the
            # reference or propagation rule can change the result.
            # Comparison: Integrated Gradients (3/5) scores above DeepSHAP (2/5): the former
            # baseline and quadrature choices remain consequential; the latter background choice and
            # propagation approximations alter values.
            # Calibration: Neutral bin: the evidence does not warrant a general stronger or weaker
            # claim on this exact property. A tie is not demonstrated empirical equivalence.
            # Evidence: qualitative comparative inference; see study cards for direct endpoints and
            # counterevidence. Confidence: low.
            # Sources: IG, DEEPLIFT, DEEPSHAP. Comparative studies: E09, E20. See documentation §6
            # for endpoints and limits.
            # Primary locations: IG: Sensitivity, implementation invariance and numerical path
            # integration
            'hyperparameters_perturbation_robustness': 3,
            # Rating 3/5; original=3; v3.3.11=3. retained after comparative review.
            # Reason: Feature attributions can be dense or truncated for presentation. Retain the
            # original neutral rating; selection does not establish minimality.
            # Comparison: Integrated Gradients (3/5) ties DeepLift (3/5): the former the complete
            # feature vector need not be sparse; the latter an attribution vector is not
            # intrinsically a minimal feature set.
            # Comparison: Integrated Gradients (3/5) ties DeepSHAP (3/5): the former the complete
            # feature vector need not be sparse; the latter the full attribution vector need not be
            # sparse.
            # Calibration: Neutral bin: the evidence does not warrant a general stronger or weaker
            # claim on this exact property. A tie is not demonstrated empirical equivalence.
            # Evidence: qualitative comparative inference; see study cards for direct endpoints and
            # counterevidence. Confidence: moderate.
            # Sources: IG, DEEPLIFT, DEEPSHAP. Comparative studies: no matched direct study located;
            # mechanism/threat-model inference. See documentation §6 for endpoints and limits.
            # Primary locations: IG: Sensitivity, implementation invariance and numerical path
            # integration
            'sparsity': 3,
            # Rating 3/5; original=3; v3.3.11=3. retained after comparative review.
            # Reason: Feature-level contributions have intermediate detail.
            # Comparison: Integrated Gradients (3/5) ties DeepLift (3/5): the former signed path
            # contributions expose more than raw attention weights; the latter signed feature
            # contributions expose allocation but not full rules.
            # Comparison: Integrated Gradients (3/5) ties DeepSHAP (3/5): the former signed path
            # contributions expose more than raw attention weights; the latter feature allocations
            # are more specific than raw attention weights.
            # Calibration: Neutral bin: the evidence does not warrant a general stronger or weaker
            # claim on this exact property. A tie is not demonstrated empirical equivalence.
            # Evidence: qualitative comparative inference; see study cards for direct endpoints and
            # counterevidence. Confidence: moderate.
            # Sources: IG, DEEPLIFT, DEEPSHAP. Comparative studies: no matched direct study located;
            # mechanism/threat-model inference. See documentation §6 for endpoints and limits.
            # Primary locations: IG: Sensitivity, implementation invariance and numerical path
            # integration
            'level_of_detail': 3,
            # Rating 3/5; original=3; v3.3.11=3. retained after comparative review.
            # Reason: No inherent confidentiality guarantee is supplied.
            # Comparison: Integrated Gradients (3/5) ties DeepLift (3/5): the former path
            # attributions may expose membership information; the latter a feature vector may leak
            # information despite being local.
            # Comparison: Integrated Gradients (3/5) ties DeepSHAP (3/5): the former path
            # attributions may expose membership information; the latter local attributions carry no
            # formal privacy protection.
            # Calibration: Neutral bin: the evidence does not warrant a general stronger or weaker
            # claim on this exact property. A tie is not demonstrated empirical equivalence.
            # Evidence: qualitative comparative inference; see study cards for direct endpoints and
            # counterevidence. Confidence: low.
            # Sources: IG, PRIVACY, DEEPLIFT, DEEPSHAP. Comparative studies: E12. See documentation
            # §6 for endpoints and limits.
            # Primary locations: IG: Sensitivity, implementation invariance and numerical path
            # integration; PRIVACY: §§3–5; direct evidence for tested gradient/IG/LRP/LIME
            # configurations; threat-model context only for other methods
            'confidentiality': 3,
            # Rating 4/5; original=5; v3.3.11=4. retained after comparative review.
            # Reason: A specified computation can be reconstructed if model, input, reference or
            # propagation settings and software versions are retained. This supports strong
            # traceability, but the method supplies no complete audit trail or accountability
            # process; the retained rubric does not justify 5 from determinism alone.
            # Comparison: Integrated Gradients (4/5) ties DeepLift (4/5): the former baseline, path
            # and quadrature are recordable; the latter stored reference and propagation rules
            # support reconstruction.
            # Comparison: Integrated Gradients (4/5) ties DeepSHAP (4/5): the former baseline, path
            # and quadrature are recordable; the latter backgrounds and propagation records can be
            # versioned.
            # Calibration: A qualified comparative strength. The integer is an ordinal coding
            # decision; neither the unit gap nor universal superiority/inferiority is measured.
            # Evidence: qualitative comparative inference; see study cards for direct endpoints and
            # counterevidence. Confidence: moderate.
            # Sources: IG, DEEPLIFT, DEEPSHAP. Comparative studies: no matched direct study located;
            # mechanism/threat-model inference. See documentation §6 for endpoints and limits.
            # Primary locations: IG: Sensitivity, implementation invariance and numerical path
            # integration
            'traceability': 4,
            # Rating 2/5; original=2; v3.3.11=2. retained after comparative review.
            # Reason: Multiple gradient evaluations cost more than single-pass methods. Original 2
            # remains a plausible comparative prior for standard integration workloads.
            # Comparison: Integrated Gradients (2/5) scores below DeepLift (4/5): the former many
            # gradient evaluations cost more than one backward pass; the latter modified
            # backpropagation avoids a many-point path integral.
            # Comparison: Integrated Gradients (2/5) scores below DeepSHAP (3/5): the former many
            # gradient evaluations cost more than one backward pass; the latter cost grows with the
            # background set, exceeding one-reference propagation.
            # Calibration: A below-neutral limitation. The integer is an ordinal coding decision;
            # neither the unit gap nor universal superiority/inferiority is measured.
            # Evidence: qualitative comparative inference; see study cards for direct endpoints and
            # counterevidence. Confidence: low.
            # Sources: IG, DEEPLIFT, DEEPSHAP. Comparative studies: E10. See documentation §6 for
            # endpoints and limits.
            # Primary locations: IG: Sensitivity, implementation invariance and numerical path
            # integration
            'runtime_performance_and_implementation_constraints': 2,
        },
        'scope_stage': 'local-expost',
        'models': ['any differentiable model (deep neural networks)'],
        'explanation_target': 'model output',
        "question_types": {'how_computed', 'what_feature'},
    },
    # Raw attention weights interpreted as explanations, not specialized attention attribution.
    'Attention': {
        "subprops": {
            # Rating 2/5; original=2; v3.3.11=2. retained after comparative review.
            # Reason: Attention weights alone can disagree with output influence; contextual
            # explanatory value remains debated.
            # Comparison: Attention (2/5) scores below DeepLift (3/5): the former raw attention can
            # diverge from output influence; the latter reference contributions are not per-feature
            # necessity certificates.
            # Comparison: Attention (2/5) scores below DeepSHAP (3/5): the former raw attention can
            # diverge from output influence; the latter approximate background-based allocation
            # retains relevance limitations.
            # Calibration: A below-neutral limitation. The integer is an ordinal coding decision;
            # neither the unit gap nor universal superiority/inferiority is measured.
            # Evidence: qualitative comparative inference; see study cards for direct endpoints and
            # counterevidence. Confidence: moderate.
            # Sources: ATTENTION, ATTENTION_DEBATE, DEEPLIFT, SIXT, DEEPSHAP, RELEVANCE. Comparative
            # studies: E17. See documentation §6 for endpoints and limits.
            # Primary locations: ATTENTION: Attention correlation and counterfactual attention
            # experiments; ATTENTION_DEBATE: Tests and qualifications for interpreting attention
            'no_false_positives': 2,
            # Rating 2/5; original=2; v3.3.11=2. retained after comparative review.
            # Reason: Relevant factors outside displayed attention can be missed.
            # Comparison: Attention (2/5) scores below DeepLift (3/5): the former displayed weights
            # omit influences outside the attention matrix; the latter summation-to-delta does not
            # certify contributor recall.
            # Comparison: Attention (2/5) scores below DeepSHAP (3/5): the former displayed weights
            # omit influences outside the attention matrix; the latter propagation and references
            # can miss relevant effects.
            # Calibration: A below-neutral limitation. The integer is an ordinal coding decision;
            # neither the unit gap nor universal superiority/inferiority is measured.
            # Evidence: qualitative comparative inference; see study cards for direct endpoints and
            # counterevidence. Confidence: moderate.
            # Sources: ATTENTION, ATTENTION_DEBATE, DEEPLIFT, SIXT, DEEPSHAP. Comparative studies:
            # E17. See documentation §6 for endpoints and limits.
            # Primary locations: ATTENTION: Attention correlation and counterfactual attention
            # experiments; ATTENTION_DEBATE: Tests and qualifications for interpreting attention
            'no_false_negatives': 2,
            # Rating 1/5; original=1; v3.3.11=1. retained after comparative review.
            # Reason: Raw weights omit the downstream computation needed to explain a decision.
            # Retain the lowest original coverage anchor; useful correlations may still exist.
            # Comparison: Attention (1/5) scores below DeepLift (3/5): the former weights alone omit
            # the downstream decision computation; the latter a reference-relative allocation is not
            # the full decision rationale.
            # Comparison: Attention (1/5) scores below Grad-CAM (2/5): the former weights alone omit
            # the downstream decision computation; the latter one layer’s localization is partial
            # decision coverage.
            # Calibration: An inherited endpoint under the stated output/configuration, not a
            # universal guarantee or universal failure. The exact endpoint is low-confidence outside
            # that setting.
            # Evidence: qualitative comparative inference; see study cards for direct endpoints and
            # counterevidence. Confidence: low.
            # Sources: ATTENTION, ATTENTION_DEBATE, DEEPLIFT, SIXT, GRADCAM. Comparative studies:
            # E17. See documentation §6 for endpoints and limits.
            # Primary locations: ATTENTION: Attention correlation and counterfactual attention
            # experiments; ATTENTION_DEBATE: Tests and qualifications for interpreting attention
            'completeness': 1,
            # Rating 3/5; original=3; v3.3.11=3. retained after comparative review.
            # Reason: A general stability ranking is not established; retain neutral.
            # Comparison: Attention (3/5) ties DeepLift (3/5): the former no general small-input
            # continuity ranking is established; the latter fixed-reference propagation avoids local
            # surrogate resampling.
            # Comparison: Attention (3/5) ties DeepSHAP (3/5): the former no general small-input
            # continuity ranking is established; the latter fixed background avoids resampling but
            # retains input dependence.
            # Calibration: Neutral bin: the evidence does not warrant a general stronger or weaker
            # claim on this exact property. A tie is not demonstrated empirical equivalence.
            # Evidence: qualitative comparative inference; see study cards for direct endpoints and
            # counterevidence. Confidence: low.
            # Sources: ATTENTION, ATTENTION_DEBATE, DEEPLIFT, SALIENCY, ROBUST, DEEPSHAP.
            # Comparative studies: no matched direct study located; mechanism/threat-model
            # inference. See documentation §6 for endpoints and limits.
            # Primary locations: ATTENTION: Attention correlation and counterfactual attention
            # experiments; ATTENTION_DEBATE: Tests and qualifications for interpreting attention
            'stability': 3,
            # Rating 3/5; original=3; v3.3.11=3. retained after comparative review.
            # Reason: No universal attack-resistance ranking for all attention architectures is
            # established.
            # Comparison: Attention (3/5) scores above DeepLift (2/5): the former no general
            # attack-resistance ranking is established; the latter reference-based propagation has
            # no general attack protection.
            # Comparison: Attention (3/5) ties DeepSHAP (3/5): the former no general
            # attack-resistance ranking is established; the latter approximate Shapley structure is
            # not an attack defense.
            # Calibration: Neutral bin: the evidence does not warrant a general stronger or weaker
            # claim on this exact property. A tie is not demonstrated empirical equivalence.
            # Evidence: qualitative comparative inference; see study cards for direct endpoints and
            # counterevidence. Confidence: low.
            # Sources: ATTENTION, ATTENTION_DEBATE, DEEPLIFT, SALIENCY, ROBUST, DEEPSHAP.
            # Comparative studies: E17. See documentation §6 for endpoints and limits.
            # Primary locations: ATTENTION: Attention correlation and counterfactual attention
            # experiments; ATTENTION_DEBATE: Tests and qualifications for interpreting attention
            'adversarial_robustness': 3,
            # Rating 3/5; original=3; v3.3.11=3. retained after comparative review.
            # Reason: Repeatable weights in evaluation mode do not guarantee consistency across
            # models or time.
            # Comparison: Attention (3/5) ties DeepLift (3/5): the former fixed-model replay does
            # not establish explanatory agreement over time; the latter fixed rules and reference
            # help replay, without temporal guarantees.
            # Comparison: Attention (3/5) ties DeepSHAP (3/5): the former fixed-model replay does
            # not establish explanatory agreement over time; the latter fixed backgrounds help
            # replay but not cross-model agreement.
            # Calibration: Neutral bin: the evidence does not warrant a general stronger or weaker
            # claim on this exact property. A tie is not demonstrated empirical equivalence.
            # Evidence: qualitative comparative inference; see study cards for direct endpoints and
            # counterevidence. Confidence: low.
            # Sources: ATTENTION, ATTENTION_DEBATE, DEEPLIFT, DEEPSHAP. Comparative studies: E17.
            # See documentation §6 for endpoints and limits.
            # Primary locations: ATTENTION: Attention correlation and counterfactual attention
            # experiments; ATTENTION_DEBATE: Tests and qualifications for interpreting attention
            'consistency': 3,
            # Rating 2/5; original=2; v3.3.11=2. retained after comparative review.
            # Reason: Layer, head and aggregation choices change the displayed explanation.
            # Comparison: Attention (2/5) scores above DeepLift (1/5): the former layer/head choices
            # alter the displayed map; the latter changing the reference or propagation rule can
            # change the result.
            # Comparison: Attention (2/5) ties DeepSHAP (2/5): the former layer/head choices alter
            # the displayed map; the latter background choice and propagation approximations alter
            # values.
            # Calibration: A below-neutral limitation. The integer is an ordinal coding decision;
            # neither the unit gap nor universal superiority/inferiority is measured.
            # Evidence: qualitative comparative inference; see study cards for direct endpoints and
            # counterevidence. Confidence: low.
            # Sources: ATTENTION, ATTENTION_DEBATE, DEEPLIFT, DEEPSHAP. Comparative studies: no
            # matched direct study located; mechanism/threat-model inference. See documentation §6
            # for endpoints and limits.
            # Primary locations: ATTENTION: Attention correlation and counterfactual attention
            # experiments; ATTENTION_DEBATE: Tests and qualifications for interpreting attention
            'hyperparameters_perturbation_robustness': 2,
            # Rating 3/5; original=3; v3.3.11=3. retained after comparative review.
            # Reason: A selected attention view may be compact or dense depending on aggregation;
            # original neutral 3 remains defensible.
            # Comparison: Attention (3/5) ties DeepLift (3/5): the former raw attention is often
            # dense and compactness needs selection; the latter an attribution vector is not
            # intrinsically a minimal feature set.
            # Comparison: Attention (3/5) ties DeepSHAP (3/5): the former raw attention is often
            # dense and compactness needs selection; the latter the full attribution vector need not
            # be sparse.
            # Calibration: Neutral bin: the evidence does not warrant a general stronger or weaker
            # claim on this exact property. A tie is not demonstrated empirical equivalence.
            # Evidence: qualitative comparative inference; see study cards for direct endpoints and
            # counterevidence. Confidence: moderate.
            # Sources: ATTENTION, ATTENTION_DEBATE, DEEPLIFT, DEEPSHAP. Comparative studies: no
            # matched direct study located; mechanism/threat-model inference. See documentation §6
            # for endpoints and limits.
            # Primary locations: ATTENTION: Attention correlation and counterfactual attention
            # experiments; ATTENTION_DEBATE: Tests and qualifications for interpreting attention
            'sparsity': 3,
            # Rating 2/5; original=4; v3.3.11=2. retained after comparative review.
            # Reason: Head-level associations are coarser than a complete feature or rule-level
            # rationale.
            # Comparison: Attention (2/5) scores below DeepLift (3/5): the former attention weights
            # expose routing associations rather than contribution rules; the latter signed feature
            # contributions expose allocation but not full rules.
            # Comparison: Attention (2/5) scores below DeepSHAP (3/5): the former attention weights
            # expose routing associations rather than contribution rules; the latter feature
            # allocations are more specific than raw attention weights.
            # Calibration: A below-neutral limitation. The integer is an ordinal coding decision;
            # neither the unit gap nor universal superiority/inferiority is measured.
            # Evidence: qualitative comparative inference; see study cards for direct endpoints and
            # counterevidence. Confidence: moderate.
            # Sources: ATTENTION, ATTENTION_DEBATE, DEEPLIFT, DEEPSHAP. Comparative studies: no
            # matched direct study located; mechanism/threat-model inference. See documentation §6
            # for endpoints and limits.
            # Primary locations: ATTENTION: Attention correlation and counterfactual attention
            # experiments; ATTENTION_DEBATE: Tests and qualifications for interpreting attention
            'level_of_detail': 2,
            # Rating 3/5; original=3; v3.3.11=3. retained after comparative review.
            # Reason: Attention displays are not privacy mechanisms.
            # Comparison: Attention (3/5) ties DeepLift (3/5): the former raw attention carries no
            # privacy guarantee; the latter a feature vector may leak information despite being
            # local.
            # Comparison: Attention (3/5) ties DeepSHAP (3/5): the former raw attention carries no
            # privacy guarantee; the latter local attributions carry no formal privacy protection.
            # Calibration: Neutral bin: the evidence does not warrant a general stronger or weaker
            # claim on this exact property. A tie is not demonstrated empirical equivalence.
            # Evidence: qualitative comparative inference; see study cards for direct endpoints and
            # counterevidence. Confidence: low.
            # Sources: ATTENTION, ATTENTION_DEBATE, PRIVACY, DEEPLIFT, DEEPSHAP. Comparative
            # studies: no matched direct study located; mechanism/threat-model inference. See
            # documentation §6 for endpoints and limits.
            # Primary locations: ATTENTION: Attention correlation and counterfactual attention
            # experiments; ATTENTION_DEBATE: Tests and qualifications for interpreting attention;
            # PRIVACY: §§3–5; direct evidence for tested gradient/IG/LRP/LIME configurations;
            # threat-model context only for other methods
            'confidentiality': 3,
            # Rating 3/5; original=3; v3.3.11=3. retained after comparative review.
            # Reason: Recording the model, input, random state and settings makes reconstruction
            # possible; use 3 rather than assuming either complete or inherently poor auditability.
            # Comparison: Attention (3/5) scores below DeepLift (4/5): the former the weights are
            # available but explanatory processing must be logged; the latter stored reference and
            # propagation rules support reconstruction.
            # Comparison: Attention (3/5) scores below DeepSHAP (4/5): the former the weights are
            # available but explanatory processing must be logged; the latter backgrounds and
            # propagation records can be versioned.
            # Calibration: Neutral bin: the evidence does not warrant a general stronger or weaker
            # claim on this exact property. A tie is not demonstrated empirical equivalence.
            # Evidence: qualitative comparative inference; see study cards for direct endpoints and
            # counterevidence. Confidence: moderate.
            # Sources: ATTENTION, ATTENTION_DEBATE, DEEPLIFT, DEEPSHAP. Comparative studies: no
            # matched direct study located; mechanism/threat-model inference. See documentation §6
            # for endpoints and limits.
            # Primary locations: ATTENTION: Attention correlation and counterfactual attention
            # experiments; ATTENTION_DEBATE: Tests and qualifications for interpreting attention
            'traceability': 3,
            # Rating 5/5; original=5; v3.3.11=5. retained after comparative review.
            # Reason: Extraction from an existing forward pass is inexpensive; this excludes
            # training and additional attention-attribution algorithms.
            # Comparison: Attention (5/5) scores above DeepLift (4/5): the former weights already
            # computed during inference have little extraction overhead; the latter modified
            # backpropagation avoids a many-point path integral.
            # Comparison: Attention (5/5) scores above DeepSHAP (3/5): the former weights already
            # computed during inference have little extraction overhead; the latter cost grows with
            # the background set, exceeding one-reference propagation.
            # Calibration: An inherited endpoint under the stated output/configuration, not a
            # universal guarantee or universal failure. The exact endpoint is low-confidence outside
            # that setting.
            # Evidence: qualitative comparative inference; see study cards for direct endpoints and
            # counterevidence. Confidence: low.
            # Sources: ATTENTION, ATTENTION_DEBATE, DEEPLIFT, DEEPSHAP. Comparative studies: no
            # matched direct study located; mechanism/threat-model inference. See documentation §6
            # for endpoints and limits.
            # Primary locations: ATTENTION: Attention correlation and counterfactual attention
            # experiments; ATTENTION_DEBATE: Tests and qualifications for interpreting attention
            'runtime_performance_and_implementation_constraints': 5,
        },
        'scope_stage': 'local-expost',
        'models': ['transformers and any architecture with attention mechanisms'],
        'explanation_target': 'model output',
        "question_types": {'how_computed', 'what_feature'},
    },
    # Training/replacing the predictor is required; strict concept-only bottleneck, no bypass.
    # Concept semantics need validation.
    'Supervised CBM': {
        "subprops": {
            # Rating 3/5; original=None; v3.3.11=3. retained after comparative review.
            # Reason: Concept labels need not match encoded information; no automatic necessity
            # guarantee.
            # Comparison: Supervised CBM (3/5) ties CAVs (3/5): the former named concept coordinates
            # may contain unintended information; the latter a learned direction may mix the named
            # concept with confounders.
            # Comparison: Supervised CBM (3/5) ties Post-hoc CBM (concept-only) (3/5): the former
            # named concept coordinates may contain unintended information; the latter explicit head
            # weights do not ensure concept purity.
            # Calibration: Neutral bin: the evidence does not warrant a general stronger or weaker
            # claim on this exact property. A tie is not demonstrated empirical equivalence.
            # Evidence: qualitative comparative inference; see study cards for direct endpoints and
            # counterevidence. Confidence: moderate.
            # Sources: CBM, CBM_LIMIT, TCAV, PCBM. Comparative studies: E13, E14, E18. See
            # documentation §6 for endpoints and limits.
            # Primary locations: CBM: Concept-to-label architecture and intervention experiments;
            # CBM_LIMIT: Concept representation/semantic-alignment analysis
            'no_false_positives': 3,
            # Rating 3/5; original=None; v3.3.11=3. retained after comparative review.
            # Reason: The target is the constructed concept head. Its concept coordinates may expose
            # the numerical inputs while imperfect concept semantics leave encoded influences
            # unnamed or misleadingly described. Retain neutral 3; omission of a useful domain
            # concept alone is a predictive-model limitation, not proof that this explanation
            # omitted a feature the model actually used.
            # Comparison: Supervised CBM (3/5) scores above CAVs (2/5): the former semantic labels
            # may fail to name all encoded influences; the latter only the supplied concept
            # vocabulary is examined.
            # Comparison: Supervised CBM (3/5) ties Post-hoc CBM (concept-only) (3/5): the former
            # semantic labels may fail to name all encoded influences; the latter semantic ambiguity
            # can persist despite exposed head inputs.
            # Calibration: Neutral bin: the evidence does not warrant a general stronger or weaker
            # claim on this exact property. A tie is not demonstrated empirical equivalence.
            # Evidence: qualitative comparative inference; see study cards for direct endpoints and
            # counterevidence. Confidence: low.
            # Sources: CBM, CBM_LIMIT, TCAV, PCBM. Comparative studies: E13, E14, E18. See
            # documentation §6 for endpoints and limits.
            # Primary locations: CBM: Concept-to-label architecture and intervention experiments;
            # CBM_LIMIT: Concept representation/semantic-alignment analysis
            'no_false_negatives': 3,
            # Rating 4/5; original=None; v3.3.11=4. retained after comparative review.
            # Reason: Concept-only routing exposes all inputs to the constructed prediction head.
            # The comparative 4 is conditional on inspecting that head; it does not establish
            # semantic purity of concepts or explain all encoder computations.
            # Comparison: Supervised CBM (4/5) scores above CAVs (2/5): the former the no-bypass
            # head uses only exposed concepts; the latter concept sensitivities are partial probes
            # of a larger network.
            # Comparison: Supervised CBM (4/5) scores above DeepLift (3/5): the former the no-bypass
            # head uses only exposed concepts; the latter a reference-relative allocation is not the
            # full decision rationale.
            # Calibration: A qualified comparative strength. The integer is an ordinal coding
            # decision; neither the unit gap nor universal superiority/inferiority is measured.
            # Evidence: qualitative comparative inference; see study cards for direct endpoints and
            # counterevidence. Confidence: moderate.
            # Sources: CBM, CBM_LIMIT, TCAV, DEEPLIFT, SIXT. Comparative studies: E13, E14, E18. See
            # documentation §6 for endpoints and limits.
            # Primary locations: CBM: Concept-to-label architecture and intervention experiments;
            # CBM_LIMIT: Concept representation/semantic-alignment analysis
            'completeness': 4,
            # Rating 3/5; original=None; v3.3.11=3. retained after comparative review.
            # Reason: Concept predictions remain sensitive to model and data.
            # Comparison: Supervised CBM (3/5) scores above CAVs (2/5): the former concept encoders
            # can remain input-sensitive; the latter concept examples and representation choices
            # affect measured sensitivity.
            # Comparison: Supervised CBM (3/5) ties Post-hoc CBM (concept-only) (3/5): the former
            # concept encoders can remain input-sensitive; the latter a frozen backbone aids replay
            # without guaranteeing input continuity.
            # Calibration: Neutral bin: the evidence does not warrant a general stronger or weaker
            # claim on this exact property. A tie is not demonstrated empirical equivalence.
            # Evidence: qualitative comparative inference; see study cards for direct endpoints and
            # counterevidence. Confidence: low.
            # Sources: CBM, CBM_LIMIT, TCAV, PCBM. Comparative studies: no matched direct study
            # located; mechanism/threat-model inference. See documentation §6 for endpoints and
            # limits.
            # Primary locations: CBM: Concept-to-label architecture and intervention experiments;
            # CBM_LIMIT: Concept representation/semantic-alignment analysis
            'stability': 3,
            # Rating 3/5; original=None; v3.3.11=3. retained after comparative review.
            # Reason: Concept intervention is not a general attack defense.
            # Comparison: Supervised CBM (3/5) scores above CAVs (2/5): the former a concept
            # bottleneck is not an explanation-attack defense; the latter concept-example attacks
            # can redirect TCAV results.
            # Comparison: Supervised CBM (3/5) ties Post-hoc CBM (concept-only) (3/5): the former a
            # concept bottleneck is not an explanation-attack defense; the latter concept projection
            # is not an adversarial defense.
            # Calibration: Neutral bin: the evidence does not warrant a general stronger or weaker
            # claim on this exact property. A tie is not demonstrated empirical equivalence.
            # Evidence: qualitative comparative inference; see study cards for direct endpoints and
            # counterevidence. Confidence: low.
            # Sources: CBM, CBM_LIMIT, TCAV, TCAV_ATTACK, PCBM. Comparative studies: E18. See
            # documentation §6 for endpoints and limits.
            # Primary locations: CBM: Concept-to-label architecture and intervention experiments;
            # CBM_LIMIT: Concept representation/semantic-alignment analysis
            'adversarial_robustness': 3,
            # Rating 3/5; original=None; v3.3.11=3. retained after comparative review.
            # Reason: Fixed concepts aid comparison; learned encoders can vary.
            # Comparison: Supervised CBM (3/5) ties CAVs (3/5): the former trained encoders and
            # heads can differ between runs; the latter random concept controls reduce but do not
            # eliminate run variation.
            # Comparison: Supervised CBM (3/5) ties Post-hoc CBM (concept-only) (3/5): the former
            # trained encoders and heads can differ between runs; the latter a frozen representation
            # reduces retraining variation.
            # Calibration: Neutral bin: the evidence does not warrant a general stronger or weaker
            # claim on this exact property. A tie is not demonstrated empirical equivalence.
            # Evidence: qualitative comparative inference; see study cards for direct endpoints and
            # counterevidence. Confidence: low.
            # Sources: CBM, CBM_LIMIT, TCAV, PCBM. Comparative studies: no matched direct study
            # located; mechanism/threat-model inference. See documentation §6 for endpoints and
            # limits.
            # Primary locations: CBM: Concept-to-label architecture and intervention experiments;
            # CBM_LIMIT: Concept representation/semantic-alignment analysis
            'consistency': 3,
            # Rating 2/5; original=None; v3.3.11=2. retained after comparative review.
            # Reason: Concept bank and training scheme influence representations.
            # Comparison: Supervised CBM (2/5) scores above CAVs (1/5): the former concept
            # supervision and bottleneck design affect explanations; the latter layer and concept
            # exemplar choices can strongly alter directions.
            # Comparison: Supervised CBM (2/5) ties Post-hoc CBM (concept-only) (2/5): the former
            # concept supervision and bottleneck design affect explanations; the latter concept bank
            # and sparse-head regularization affect outputs.
            # Calibration: A below-neutral limitation. The integer is an ordinal coding decision;
            # neither the unit gap nor universal superiority/inferiority is measured.
            # Evidence: qualitative comparative inference; see study cards for direct endpoints and
            # counterevidence. Confidence: low.
            # Sources: CBM, CBM_LIMIT, TCAV, PCBM. Comparative studies: E14, E18. See documentation
            # §6 for endpoints and limits.
            # Primary locations: CBM: Concept-to-label architecture and intervention experiments;
            # CBM_LIMIT: Concept representation/semantic-alignment analysis
            'hyperparameters_perturbation_robustness': 2,
            # Rating 3/5; original=None; v3.3.11=3. retained after comparative review.
            # Reason: Few concepts help, but no minimal set is enforced.
            # Comparison: Supervised CBM (3/5) ties CAVs (3/5): the former a concept layer need not
            # use few nonzero concepts; the latter the number of tested concepts is user-selected.
            # Comparison: Supervised CBM (3/5) scores below Post-hoc CBM (concept-only) (4/5): the
            # former a concept layer need not use few nonzero concepts; the latter a sparse linear
            # head explicitly selects active concept terms.
            # Calibration: Neutral bin: the evidence does not warrant a general stronger or weaker
            # claim on this exact property. A tie is not demonstrated empirical equivalence.
            # Evidence: qualitative comparative inference; see study cards for direct endpoints and
            # counterevidence. Confidence: moderate.
            # Sources: CBM, CBM_LIMIT, TCAV, PCBM. Comparative studies: E13, E14. See documentation
            # §6 for endpoints and limits.
            # Primary locations: CBM: Concept-to-label architecture and intervention experiments;
            # CBM_LIMIT: Concept representation/semantic-alignment analysis
            'sparsity': 3,
            # Rating 3/5; original=None; v3.3.11=3. retained after comparative review.
            # Reason: Concept values and head behavior expose intermediate computation.
            # Comparison: Supervised CBM (3/5) scores above CAVs (2/5): the former concept-level
            # prediction exposes less input detail than explicit rules; the latter concept-direction
            # scores abstract away input-level computation.
            # Comparison: Supervised CBM (3/5) ties Post-hoc CBM (concept-only) (3/5): the former
            # concept-level prediction exposes less input detail than explicit rules; the latter
            # concept contributions abstract away the encoder’s details.
            # Calibration: Neutral bin: the evidence does not warrant a general stronger or weaker
            # claim on this exact property. A tie is not demonstrated empirical equivalence.
            # Evidence: qualitative comparative inference; see study cards for direct endpoints and
            # counterevidence. Confidence: moderate.
            # Sources: CBM, CBM_LIMIT, TCAV, PCBM. Comparative studies: no matched direct study
            # located; mechanism/threat-model inference. See documentation §6 for endpoints and
            # limits.
            # Primary locations: CBM: Concept-to-label architecture and intervention experiments;
            # CBM_LIMIT: Concept representation/semantic-alignment analysis
            'level_of_detail': 3,
            # Rating 3/5; original=None; v3.3.11=3. retained after comparative review.
            # Reason: Concept annotations can be sensitive; no privacy mechanism.
            # Comparison: Supervised CBM (3/5) ties CAVs (3/5): the former concept scores do not
            # ensure confidentiality; the latter concept scores do not provide a confidentiality
            # mechanism.
            # Comparison: Supervised CBM (3/5) ties Post-hoc CBM (concept-only) (3/5): the former
            # concept scores do not ensure confidentiality; the latter the concept output has no
            # formal privacy mechanism.
            # Calibration: Neutral bin: the evidence does not warrant a general stronger or weaker
            # claim on this exact property. A tie is not demonstrated empirical equivalence.
            # Evidence: qualitative comparative inference; see study cards for direct endpoints and
            # counterevidence. Confidence: low.
            # Sources: CBM, CBM_LIMIT, PRIVACY, TCAV, PCBM. Comparative studies: no matched direct
            # study located; mechanism/threat-model inference. See documentation §6 for endpoints
            # and limits.
            # Primary locations: CBM: Concept-to-label architecture and intervention experiments;
            # CBM_LIMIT: Concept representation/semantic-alignment analysis; PRIVACY: §§3–5; direct
            # evidence for tested gradient/IG/LRP/LIME configurations; threat-model context only for
            # other methods
            'confidentiality': 3,
            # Rating 4/5; original=None; v3.3.11=4. retained after comparative review.
            # Reason: Archive encoder, concept labels and head for reconstruction.
            # Comparison: Supervised CBM (4/5) scores above CAVs (3/5): the former concept values
            # and the prediction head can be inspected; the latter concept examples, learned vectors
            # and tests can be retained.
            # Comparison: Supervised CBM (4/5) ties Post-hoc CBM (concept-only) (4/5): the former
            # concept values and the prediction head can be inspected; the latter stored projections
            # and sparse head permit inspection.
            # Calibration: A qualified comparative strength. The integer is an ordinal coding
            # decision; neither the unit gap nor universal superiority/inferiority is measured.
            # Evidence: qualitative comparative inference; see study cards for direct endpoints and
            # counterevidence. Confidence: moderate.
            # Sources: CBM, CBM_LIMIT, TCAV, PCBM. Comparative studies: no matched direct study
            # located; mechanism/threat-model inference. See documentation §6 for endpoints and
            # limits.
            # Primary locations: CBM: Concept-to-label architecture and intervention experiments;
            # CBM_LIMIT: Concept representation/semantic-alignment analysis
            'traceability': 4,
            # Rating 2/5; original=None; v3.3.11=2. retained after comparative review.
            # Reason: Concept supervision and training add substantial implementation cost.
            # Comparison: Supervised CBM (2/5) scores below CAVs (3/5): the former concept
            # annotations and predictor training are required; the latter post-hoc linear probes use
            # an existing network rather than retraining it.
            # Comparison: Supervised CBM (2/5) scores below Post-hoc CBM (concept-only) (3/5): the
            # former concept annotations and predictor training are required; the latter a frozen
            # backbone reduces training and annotation burden.
            # Calibration: A below-neutral limitation. The integer is an ordinal coding decision;
            # neither the unit gap nor universal superiority/inferiority is measured.
            # Evidence: qualitative comparative inference; see study cards for direct endpoints and
            # counterevidence. Confidence: moderate.
            # Sources: CBM, CBM_LIMIT, TCAV, PCBM. Comparative studies: E13, E14. See documentation
            # §6 for endpoints and limits.
            # Primary locations: CBM: Concept-to-label architecture and intervention experiments;
            # CBM_LIMIT: Concept representation/semantic-alignment analysis
            'runtime_performance_and_implementation_constraints': 2,
        },
        'scope_stage': 'both',
        'models': ['concept-bottleneck classifier'],
        'required_access': 'model_replacement',
        'requires_model_replacement': True,
        'component_only': False,
        'explanation_target': 'concept-head output of the CBM itself',
        "question_types": {'how_computed', 'what_feature', 'what_if'},
    },
    # Frozen backbone, concept projection and sparse head; excludes residual PCBM-h. It replaces the
    # head, not an exact explanation of the original predictor.
    'Post-hoc CBM (concept-only)': {
        "subprops": {
            # Rating 3/5; original=None; v3.3.11=3. retained after comparative review.
            # Reason: Head contributions are explicit; concept semantics may remain imperfect.
            # Comparison: Post-hoc CBM (concept-only) (3/5) ties CAVs (3/5): the former explicit
            # head weights do not ensure concept purity; the latter a learned direction may mix the
            # named concept with confounders.
            # Comparison: Post-hoc CBM (concept-only) (3/5) ties Supervised CBM (3/5): the former
            # explicit head weights do not ensure concept purity; the latter named concept
            # coordinates may contain unintended information.
            # Calibration: Neutral bin: the evidence does not warrant a general stronger or weaker
            # claim on this exact property. A tie is not demonstrated empirical equivalence.
            # Evidence: qualitative comparative inference; see study cards for direct endpoints and
            # counterevidence. Confidence: moderate.
            # Sources: PCBM, CBM_LIMIT, TCAV, CBM. Comparative studies: E13, E14. See documentation
            # §6 for endpoints and limits.
            # Primary locations: PCBM: §2 pure concept head versus residual extension; §6
            # limitations; CBM_LIMIT: Concept representation/semantic-alignment analysis
            'no_false_positives': 3,
            # Rating 3/5; original=None; v3.3.11=3. retained after comparative review.
            # Reason: The target is the constructed concept head. Its concept coordinates may expose
            # the numerical inputs while imperfect concept semantics leave encoded influences
            # unnamed or misleadingly described. Retain neutral 3; omission of a useful domain
            # concept alone is a predictive-model limitation, not proof that this explanation
            # omitted a feature the model actually used.
            # Comparison: Post-hoc CBM (concept-only) (3/5) scores above CAVs (2/5): the former
            # semantic ambiguity can persist despite exposed head inputs; the latter only the
            # supplied concept vocabulary is examined.
            # Comparison: Post-hoc CBM (concept-only) (3/5) ties Supervised CBM (3/5): the former
            # semantic ambiguity can persist despite exposed head inputs; the latter semantic labels
            # may fail to name all encoded influences.
            # Calibration: Neutral bin: the evidence does not warrant a general stronger or weaker
            # claim on this exact property. A tie is not demonstrated empirical equivalence.
            # Evidence: qualitative comparative inference; see study cards for direct endpoints and
            # counterevidence. Confidence: low.
            # Sources: PCBM, CBM_LIMIT, TCAV, CBM. Comparative studies: E13, E14. See documentation
            # §6 for endpoints and limits.
            # Primary locations: PCBM: §2 pure concept head versus residual extension; §6
            # limitations; CBM_LIMIT: Concept representation/semantic-alignment analysis
            'no_false_negatives': 3,
            # Rating 4/5; original=None; v3.3.11=4. retained after comparative review.
            # Reason: Concept-only routing exposes all inputs to the constructed prediction head.
            # The comparative 4 is conditional on inspecting that head; it does not establish
            # semantic purity of concepts or explain all encoder computations.
            # Comparison: Post-hoc CBM (concept-only) (4/5) scores above CAVs (2/5): the former the
            # replacement head uses only exposed concept coordinates; the latter concept
            # sensitivities are partial probes of a larger network.
            # Comparison: Post-hoc CBM (concept-only) (4/5) scores above DeepLift (3/5): the former
            # the replacement head uses only exposed concept coordinates; the latter a
            # reference-relative allocation is not the full decision rationale.
            # Calibration: A qualified comparative strength. The integer is an ordinal coding
            # decision; neither the unit gap nor universal superiority/inferiority is measured.
            # Evidence: qualitative comparative inference; see study cards for direct endpoints and
            # counterevidence. Confidence: moderate.
            # Sources: PCBM, CBM_LIMIT, TCAV, DEEPLIFT, SIXT. Comparative studies: E13, E14. See
            # documentation §6 for endpoints and limits.
            # Primary locations: PCBM: §2 pure concept head versus residual extension; §6
            # limitations; CBM_LIMIT: Concept representation/semantic-alignment analysis
            'completeness': 4,
            # Rating 3/5; original=None; v3.3.11=3. retained after comparative review.
            # Reason: Frozen embeddings help repeatability but do not guarantee stability.
            # Comparison: Post-hoc CBM (concept-only) (3/5) scores above CAVs (2/5): the former a
            # frozen backbone aids replay without guaranteeing input continuity; the latter concept
            # examples and representation choices affect measured sensitivity.
            # Comparison: Post-hoc CBM (concept-only) (3/5) ties Supervised CBM (3/5): the former a
            # frozen backbone aids replay without guaranteeing input continuity; the latter concept
            # encoders can remain input-sensitive.
            # Calibration: Neutral bin: the evidence does not warrant a general stronger or weaker
            # claim on this exact property. A tie is not demonstrated empirical equivalence.
            # Evidence: qualitative comparative inference; see study cards for direct endpoints and
            # counterevidence. Confidence: low.
            # Sources: PCBM, CBM_LIMIT, TCAV, CBM. Comparative studies: no matched direct study
            # located; mechanism/threat-model inference. See documentation §6 for endpoints and
            # limits.
            # Primary locations: PCBM: §2 pure concept head versus residual extension; §6
            # limitations; CBM_LIMIT: Concept representation/semantic-alignment analysis
            'stability': 3,
            # Rating 3/5; original=None; v3.3.11=3. retained after comparative review.
            # Reason: No general adversarial resistance follows from concept projection.
            # Comparison: Post-hoc CBM (concept-only) (3/5) scores above CAVs (2/5): the former
            # concept projection is not an adversarial defense; the latter concept-example attacks
            # can redirect TCAV results.
            # Comparison: Post-hoc CBM (concept-only) (3/5) ties Supervised CBM (3/5): the former
            # concept projection is not an adversarial defense; the latter a concept bottleneck is
            # not an explanation-attack defense.
            # Calibration: Neutral bin: the evidence does not warrant a general stronger or weaker
            # claim on this exact property. A tie is not demonstrated empirical equivalence.
            # Evidence: qualitative comparative inference; see study cards for direct endpoints and
            # counterevidence. Confidence: low.
            # Sources: PCBM, CBM_LIMIT, TCAV, TCAV_ATTACK, CBM. Comparative studies: no matched
            # direct study located; mechanism/threat-model inference. See documentation §6 for
            # endpoints and limits.
            # Primary locations: PCBM: §2 pure concept head versus residual extension; §6
            # limitations; CBM_LIMIT: Concept representation/semantic-alignment analysis
            'adversarial_robustness': 3,
            # Rating 3/5; original=None; v3.3.11=3. retained after comparative review.
            # Reason: Stored concepts aid repeatability; refitted heads may differ.
            # Comparison: Post-hoc CBM (concept-only) (3/5) ties CAVs (3/5): the former a frozen
            # representation reduces retraining variation; the latter random concept controls reduce
            # but do not eliminate run variation.
            # Comparison: Post-hoc CBM (concept-only) (3/5) ties Supervised CBM (3/5): the former a
            # frozen representation reduces retraining variation; the latter trained encoders and
            # heads can differ between runs.
            # Calibration: Neutral bin: the evidence does not warrant a general stronger or weaker
            # claim on this exact property. A tie is not demonstrated empirical equivalence.
            # Evidence: qualitative comparative inference; see study cards for direct endpoints and
            # counterevidence. Confidence: low.
            # Sources: PCBM, CBM_LIMIT, TCAV, CBM. Comparative studies: no matched direct study
            # located; mechanism/threat-model inference. See documentation §6 for endpoints and
            # limits.
            # Primary locations: PCBM: §2 pure concept head versus residual extension; §6
            # limitations; CBM_LIMIT: Concept representation/semantic-alignment analysis
            'consistency': 3,
            # Rating 2/5; original=None; v3.3.11=2. retained after comparative review.
            # Reason: Concept bank and sparsity penalty influence the predictor.
            # Comparison: Post-hoc CBM (concept-only) (2/5) scores above CAVs (1/5): the former
            # concept bank and sparse-head regularization affect outputs; the latter layer and
            # concept exemplar choices can strongly alter directions.
            # Comparison: Post-hoc CBM (concept-only) (2/5) ties Supervised CBM (2/5): the former
            # concept bank and sparse-head regularization affect outputs; the latter concept
            # supervision and bottleneck design affect explanations.
            # Calibration: A below-neutral limitation. The integer is an ordinal coding decision;
            # neither the unit gap nor universal superiority/inferiority is measured.
            # Evidence: qualitative comparative inference; see study cards for direct endpoints and
            # counterevidence. Confidence: low.
            # Sources: PCBM, CBM_LIMIT, TCAV, CBM. Comparative studies: E14. See documentation §6
            # for endpoints and limits.
            # Primary locations: PCBM: §2 pure concept head versus residual extension; §6
            # limitations; CBM_LIMIT: Concept representation/semantic-alignment analysis
            'hyperparameters_perturbation_robustness': 2,
            # Rating 4/5; original=None; v3.3.11=4. retained after comparative review.
            # Reason: Sparse linear head promotes compact concept contributions.
            # Comparison: Post-hoc CBM (concept-only) (4/5) scores above LaBo (LLM-guided CBM)
            # (3/5): the former a sparse linear head explicitly selects active concept terms; the
            # latter a selected vocabulary with a dense head is not sparse PCBM output.
            # Comparison: Post-hoc CBM (concept-only) (4/5) scores above Supervised CBM (3/5): the
            # former a sparse linear head explicitly selects active concept terms; the latter a
            # concept layer need not use few nonzero concepts.
            # Calibration: A qualified comparative strength. The integer is an ordinal coding
            # decision; neither the unit gap nor universal superiority/inferiority is measured.
            # Evidence: qualitative comparative inference; see study cards for direct endpoints and
            # counterevidence. Confidence: moderate.
            # Sources: PCBM, CBM_LIMIT, LABO, CBM. Comparative studies: E13, E14. See documentation
            # §6 for endpoints and limits.
            # Primary locations: PCBM: §2 pure concept head versus residual extension; §6
            # limitations; CBM_LIMIT: Concept representation/semantic-alignment analysis
            'sparsity': 4,
            # Rating 3/5; original=None; v3.3.11=3. retained after comparative review.
            # Reason: Coefficients and concept scores expose head-level computation.
            # Comparison: Post-hoc CBM (concept-only) (3/5) scores above CAVs (2/5): the former
            # concept contributions abstract away the encoder’s details; the latter
            # concept-direction scores abstract away input-level computation.
            # Comparison: Post-hoc CBM (concept-only) (3/5) ties Supervised CBM (3/5): the former
            # concept contributions abstract away the encoder’s details; the latter concept-level
            # prediction exposes less input detail than explicit rules.
            # Calibration: Neutral bin: the evidence does not warrant a general stronger or weaker
            # claim on this exact property. A tie is not demonstrated empirical equivalence.
            # Evidence: qualitative comparative inference; see study cards for direct endpoints and
            # counterevidence. Confidence: moderate.
            # Sources: PCBM, CBM_LIMIT, TCAV, CBM. Comparative studies: no matched direct study
            # located; mechanism/threat-model inference. See documentation §6 for endpoints and
            # limits.
            # Primary locations: PCBM: §2 pure concept head versus residual extension; §6
            # limitations; CBM_LIMIT: Concept representation/semantic-alignment analysis
            'level_of_detail': 3,
            # Rating 3/5; original=None; v3.3.11=3. retained after comparative review.
            # Reason: Published concepts and weights may reveal sensitive behavior.
            # Comparison: Post-hoc CBM (concept-only) (3/5) ties CAVs (3/5): the former the concept
            # output has no formal privacy mechanism; the latter concept scores do not provide a
            # confidentiality mechanism.
            # Comparison: Post-hoc CBM (concept-only) (3/5) ties Supervised CBM (3/5): the former
            # the concept output has no formal privacy mechanism; the latter concept scores do not
            # ensure confidentiality.
            # Calibration: Neutral bin: the evidence does not warrant a general stronger or weaker
            # claim on this exact property. A tie is not demonstrated empirical equivalence.
            # Evidence: qualitative comparative inference; see study cards for direct endpoints and
            # counterevidence. Confidence: low.
            # Sources: PCBM, CBM_LIMIT, PRIVACY, TCAV, CBM. Comparative studies: no matched direct
            # study located; mechanism/threat-model inference. See documentation §6 for endpoints
            # and limits.
            # Primary locations: PCBM: §2 pure concept head versus residual extension; §6
            # limitations; CBM_LIMIT: Concept representation/semantic-alignment analysis; PRIVACY:
            # §§3–5; direct evidence for tested gradient/IG/LRP/LIME configurations; threat-model
            # context only for other methods
            'confidentiality': 3,
            # Rating 4/5; original=None; v3.3.11=4. retained after comparative review.
            # Reason: Retain backbone, projection, concepts and head weights.
            # Comparison: Post-hoc CBM (concept-only) (4/5) scores above CAVs (3/5): the former
            # stored projections and sparse head permit inspection; the latter concept examples,
            # learned vectors and tests can be retained.
            # Comparison: Post-hoc CBM (concept-only) (4/5) ties Supervised CBM (4/5): the former
            # stored projections and sparse head permit inspection; the latter concept values and
            # the prediction head can be inspected.
            # Calibration: A qualified comparative strength. The integer is an ordinal coding
            # decision; neither the unit gap nor universal superiority/inferiority is measured.
            # Evidence: qualitative comparative inference; see study cards for direct endpoints and
            # counterevidence. Confidence: moderate.
            # Sources: PCBM, CBM_LIMIT, TCAV, CBM. Comparative studies: no matched direct study
            # located; mechanism/threat-model inference. See documentation §6 for endpoints and
            # limits.
            # Primary locations: PCBM: §2 pure concept head versus residual extension; §6
            # limitations; CBM_LIMIT: Concept representation/semantic-alignment analysis
            'traceability': 4,
            # Rating 3/5; original=None; v3.3.11=3. retained after comparative review.
            # Reason: Reuse of a frozen backbone reduces training overhead.
            # Comparison: Post-hoc CBM (concept-only) (3/5) scores above Supervised CBM (2/5): the
            # former a frozen backbone reduces training and annotation burden; the latter concept
            # annotations and predictor training are required.
            # Comparison: Post-hoc CBM (concept-only) (3/5) ties CAVs (3/5): the former a frozen
            # backbone reduces training and annotation burden; the latter post-hoc linear probes use
            # an existing network rather than retraining it.
            # Calibration: Neutral bin: the evidence does not warrant a general stronger or weaker
            # claim on this exact property. A tie is not demonstrated empirical equivalence.
            # Evidence: qualitative comparative inference; see study cards for direct endpoints and
            # counterevidence. Confidence: moderate.
            # Sources: PCBM, CBM_LIMIT, CBM, TCAV. Comparative studies: E13, E14. See documentation
            # §6 for endpoints and limits.
            # Primary locations: PCBM: §2 pure concept head versus residual extension; §6
            # limitations; CBM_LIMIT: Concept representation/semantic-alignment analysis
            'runtime_performance_and_implementation_constraints': 3,
        },
        'scope_stage': 'both',
        'models': ['concept-bottleneck classifier'],
        'required_access': 'model_replacement',
        'requires_model_replacement': True,
        'component_only': False,
        'explanation_target': 'output of the fitted post-hoc concept head',
        "question_types": {'how_computed', 'what_feature', 'what_if'},
    },
    # GPT-3 generates candidate concepts; selection and CLIP alignment form a predictive bottleneck.
    # Intrinsic explanation of the constructed classifier, not an arbitrary unchanged black box.
    'LaBo (LLM-guided CBM)': {
        "subprops": {
            # Rating 3/5; original=None; v3.3.11=3. retained after comparative review.
            # Reason: Generated concepts and visual grounding need validation.
            # Comparison: LaBo (LLM-guided CBM) (3/5) ties CAVs (3/5): the former generated language
            # can be weakly grounded in image evidence; the latter a learned direction may mix the
            # named concept with confounders.
            # Comparison: LaBo (LLM-guided CBM) (3/5) ties Supervised CBM (3/5): the former
            # generated language can be weakly grounded in image evidence; the latter named concept
            # coordinates may contain unintended information.
            # Calibration: Neutral bin: the evidence does not warrant a general stronger or weaker
            # claim on this exact property. A tie is not demonstrated empirical equivalence.
            # Evidence: qualitative comparative inference; see study cards for direct endpoints and
            # counterevidence. Confidence: moderate.
            # Sources: LABO, CBM_LIMIT, TCAV, CBM. Comparative studies: E14. See documentation §6
            # for endpoints and limits.
            # Primary locations: LABO: Concept generation, concept selection and concept-based
            # prediction; CBM_LIMIT: Concept representation/semantic-alignment analysis
            'no_false_positives': 3,
            # Rating 3/5; original=None; v3.3.11=3. retained after comparative review.
            # Reason: The target is the constructed concept head. Its concept coordinates may expose
            # the numerical inputs while imperfect concept semantics leave encoded influences
            # unnamed or misleadingly described. Retain neutral 3; omission of a useful domain
            # concept alone is a predictive-model limitation, not proof that this explanation
            # omitted a feature the model actually used.
            # Comparison: LaBo (LLM-guided CBM) (3/5) scores above CAVs (2/5): the former a
            # generated vocabulary need not name all encoded influences; the latter only the
            # supplied concept vocabulary is examined.
            # Comparison: LaBo (LLM-guided CBM) (3/5) ties Supervised CBM (3/5): the former a
            # generated vocabulary need not name all encoded influences; the latter semantic labels
            # may fail to name all encoded influences.
            # Calibration: Neutral bin: the evidence does not warrant a general stronger or weaker
            # claim on this exact property. A tie is not demonstrated empirical equivalence.
            # Evidence: qualitative comparative inference; see study cards for direct endpoints and
            # counterevidence. Confidence: low.
            # Sources: LABO, CBM_LIMIT, TCAV, CBM. Comparative studies: E14. See documentation §6
            # for endpoints and limits.
            # Primary locations: LABO: Concept generation, concept selection and concept-based
            # prediction; CBM_LIMIT: Concept representation/semantic-alignment analysis
            'no_false_negatives': 3,
            # Rating 4/5; original=None; v3.3.11=4. retained after comparative review.
            # Reason: Concept-only routing exposes all inputs to the constructed prediction head.
            # The comparative 4 is conditional on inspecting that head; it does not establish
            # semantic purity of concepts or explain all encoder computations.
            # Comparison: LaBo (LLM-guided CBM) (4/5) scores above CAVs (2/5): the former the
            # constructed no-bypass head routes through concepts; the latter concept sensitivities
            # are partial probes of a larger network.
            # Comparison: LaBo (LLM-guided CBM) (4/5) scores above DeepLift (3/5): the former the
            # constructed no-bypass head routes through concepts; the latter a reference-relative
            # allocation is not the full decision rationale.
            # Calibration: A qualified comparative strength. The integer is an ordinal coding
            # decision; neither the unit gap nor universal superiority/inferiority is measured.
            # Evidence: qualitative comparative inference; see study cards for direct endpoints and
            # counterevidence. Confidence: moderate.
            # Sources: LABO, CBM_LIMIT, TCAV, DEEPLIFT, SIXT. Comparative studies: E14. See
            # documentation §6 for endpoints and limits.
            # Primary locations: LABO: Concept generation, concept selection and concept-based
            # prediction; CBM_LIMIT: Concept representation/semantic-alignment analysis
            'completeness': 4,
            # Rating 3/5; original=None; v3.3.11=3. retained after comparative review.
            # Reason: Fixed selected concepts help; input sensitivity remains.
            # Comparison: LaBo (LLM-guided CBM) (3/5) scores above CAVs (2/5): the former fixed
            # concepts do not eliminate image-encoder sensitivity; the latter concept examples and
            # representation choices affect measured sensitivity.
            # Comparison: LaBo (LLM-guided CBM) (3/5) ties Supervised CBM (3/5): the former fixed
            # concepts do not eliminate image-encoder sensitivity; the latter concept encoders can
            # remain input-sensitive.
            # Calibration: Neutral bin: the evidence does not warrant a general stronger or weaker
            # claim on this exact property. A tie is not demonstrated empirical equivalence.
            # Evidence: qualitative comparative inference; see study cards for direct endpoints and
            # counterevidence. Confidence: low.
            # Sources: LABO, CBM_LIMIT, TCAV, CBM. Comparative studies: no matched direct study
            # located; mechanism/threat-model inference. See documentation §6 for endpoints and
            # limits.
            # Primary locations: LABO: Concept generation, concept selection and concept-based
            # prediction; CBM_LIMIT: Concept representation/semantic-alignment analysis
            'stability': 3,
            # Rating 3/5; original=None; v3.3.11=3. retained after comparative review.
            # Reason: Language-generated concepts do not establish attack resistance.
            # Comparison: LaBo (LLM-guided CBM) (3/5) scores above CAVs (2/5): the former LLM-guided
            # concepts do not certify attack resistance; the latter concept-example attacks can
            # redirect TCAV results.
            # Comparison: LaBo (LLM-guided CBM) (3/5) ties Supervised CBM (3/5): the former
            # LLM-guided concepts do not certify attack resistance; the latter a concept bottleneck
            # is not an explanation-attack defense.
            # Calibration: Neutral bin: the evidence does not warrant a general stronger or weaker
            # claim on this exact property. A tie is not demonstrated empirical equivalence.
            # Evidence: qualitative comparative inference; see study cards for direct endpoints and
            # counterevidence. Confidence: low.
            # Sources: LABO, CBM_LIMIT, TCAV, TCAV_ATTACK, CBM. Comparative studies: no matched
            # direct study located; mechanism/threat-model inference. See documentation §6 for
            # endpoints and limits.
            # Primary locations: LABO: Concept generation, concept selection and concept-based
            # prediction; CBM_LIMIT: Concept representation/semantic-alignment analysis
            'adversarial_robustness': 3,
            # Rating 2/5; original=None; v3.3.11=2. retained after comparative review.
            # Reason: LLM sampling and concept selection can change representations.
            # Comparison: LaBo (LLM-guided CBM) (2/5) scores below CAVs (3/5): the former LLM
            # generation adds vocabulary variability to training; the latter random concept controls
            # reduce but do not eliminate run variation.
            # Comparison: LaBo (LLM-guided CBM) (2/5) scores below Supervised CBM (3/5): the former
            # LLM generation adds vocabulary variability to training; the latter trained encoders
            # and heads can differ between runs.
            # Calibration: A below-neutral limitation. The integer is an ordinal coding decision;
            # neither the unit gap nor universal superiority/inferiority is measured.
            # Evidence: qualitative comparative inference; see study cards for direct endpoints and
            # counterevidence. Confidence: low.
            # Sources: LABO, CBM_LIMIT, TCAV, CBM. Comparative studies: no matched direct study
            # located; mechanism/threat-model inference. See documentation §6 for endpoints and
            # limits.
            # Primary locations: LABO: Concept generation, concept selection and concept-based
            # prediction; CBM_LIMIT: Concept representation/semantic-alignment analysis
            'consistency': 2,
            # Rating 2/5; original=None; v3.3.11=2. retained after comparative review.
            # Reason: Prompts, bottleneck size and selection weights affect output.
            # Comparison: LaBo (LLM-guided CBM) (2/5) scores above CAVs (1/5): the former prompt,
            # concept count and selection weights influence output; the latter layer and concept
            # exemplar choices can strongly alter directions.
            # Comparison: LaBo (LLM-guided CBM) (2/5) ties Supervised CBM (2/5): the former prompt,
            # concept count and selection weights influence output; the latter concept supervision
            # and bottleneck design affect explanations.
            # Calibration: A below-neutral limitation. The integer is an ordinal coding decision;
            # neither the unit gap nor universal superiority/inferiority is measured.
            # Evidence: qualitative comparative inference; see study cards for direct endpoints and
            # counterevidence. Confidence: low.
            # Sources: LABO, CBM_LIMIT, TCAV, CBM. Comparative studies: E14. See documentation §6
            # for endpoints and limits.
            # Primary locations: LABO: Concept generation, concept selection and concept-based
            # prediction; CBM_LIMIT: Concept representation/semantic-alignment analysis
            'hyperparameters_perturbation_robustness': 2,
            # Rating 3/5; original=None; v3.3.11=3. retained after comparative review.
            # Reason: Selecting a vocabulary does not make the prediction head sparse. The published
            # default selects 50 concepts per class and uses a dense softmax-normalized concept
            # weight matrix; retain neutral compactness unless a smaller deployed bottleneck is
            # specified.
            # Comparison: LaBo (LLM-guided CBM) (3/5) scores below Post-hoc CBM (concept-only)
            # (4/5): the former a selected vocabulary with a dense head is not sparse PCBM output;
            # the latter a sparse linear head explicitly selects active concept terms.
            # Comparison: LaBo (LLM-guided CBM) (3/5) ties Supervised CBM (3/5): the former a
            # selected vocabulary with a dense head is not sparse PCBM output; the latter a concept
            # layer need not use few nonzero concepts.
            # Calibration: Neutral bin: the evidence does not warrant a general stronger or weaker
            # claim on this exact property. A tie is not demonstrated empirical equivalence.
            # Evidence: qualitative comparative inference; see study cards for direct endpoints and
            # counterevidence. Confidence: moderate.
            # Sources: LABO, PCBM, CBM_LIMIT, CBM. Comparative studies: E14. See documentation §6
            # for endpoints and limits.
            # Primary locations: LABO: Sections 3.2–3.3 and 4.3: class-count times concept budget;
            # dense weight matrix; 50 concepts/class
            'sparsity': 3,
            # Rating 3/5; original=None; v3.3.11=3. retained after comparative review.
            # Reason: Concept scores and head weights expose intermediate detail.
            # Comparison: LaBo (LLM-guided CBM) (3/5) scores above CAVs (2/5): the former concept
            # descriptions convey semantics without full encoder detail; the latter
            # concept-direction scores abstract away input-level computation.
            # Comparison: LaBo (LLM-guided CBM) (3/5) ties Supervised CBM (3/5): the former concept
            # descriptions convey semantics without full encoder detail; the latter concept-level
            # prediction exposes less input detail than explicit rules.
            # Calibration: Neutral bin: the evidence does not warrant a general stronger or weaker
            # claim on this exact property. A tie is not demonstrated empirical equivalence.
            # Evidence: qualitative comparative inference; see study cards for direct endpoints and
            # counterevidence. Confidence: moderate.
            # Sources: LABO, CBM_LIMIT, TCAV, CBM. Comparative studies: no matched direct study
            # located; mechanism/threat-model inference. See documentation §6 for endpoints and
            # limits.
            # Primary locations: LABO: Concept generation, concept selection and concept-based
            # prediction; CBM_LIMIT: Concept representation/semantic-alignment analysis
            'level_of_detail': 3,
            # Rating 3/5; original=None; v3.3.11=3. retained after comparative review.
            # Reason: Prompts and data require contextual confidentiality controls.
            # Comparison: LaBo (LLM-guided CBM) (3/5) ties CAVs (3/5): the former prompts and
            # concept outputs need their own disclosure assessment; the latter concept scores do not
            # provide a confidentiality mechanism.
            # Comparison: LaBo (LLM-guided CBM) (3/5) ties Supervised CBM (3/5): the former prompts
            # and concept outputs need their own disclosure assessment; the latter concept scores do
            # not ensure confidentiality.
            # Calibration: Neutral bin: the evidence does not warrant a general stronger or weaker
            # claim on this exact property. A tie is not demonstrated empirical equivalence.
            # Evidence: qualitative comparative inference; see study cards for direct endpoints and
            # counterevidence. Confidence: low.
            # Sources: LABO, CBM_LIMIT, PRIVACY, TCAV, CBM. Comparative studies: no matched direct
            # study located; mechanism/threat-model inference. See documentation §6 for endpoints
            # and limits.
            # Primary locations: LABO: Concept generation, concept selection and concept-based
            # prediction; CBM_LIMIT: Concept representation/semantic-alignment analysis; PRIVACY:
            # §§3–5; direct evidence for tested gradient/IG/LRP/LIME configurations; threat-model
            # context only for other methods
            'confidentiality': 3,
            # Rating 4/5; original=None; v3.3.11=4. retained after comparative review.
            # Reason: Retain generated candidates, selected concepts and model versions.
            # Comparison: LaBo (LLM-guided CBM) (4/5) scores above CAVs (3/5): the former saved
            # prompts, concepts, embeddings and head enable reconstruction; the latter concept
            # examples, learned vectors and tests can be retained.
            # Comparison: LaBo (LLM-guided CBM) (4/5) ties Supervised CBM (4/5): the former saved
            # prompts, concepts, embeddings and head enable reconstruction; the latter concept
            # values and the prediction head can be inspected.
            # Calibration: A qualified comparative strength. The integer is an ordinal coding
            # decision; neither the unit gap nor universal superiority/inferiority is measured.
            # Evidence: qualitative comparative inference; see study cards for direct endpoints and
            # counterevidence. Confidence: moderate.
            # Sources: LABO, CBM_LIMIT, TCAV, CBM. Comparative studies: no matched direct study
            # located; mechanism/threat-model inference. See documentation §6 for endpoints and
            # limits.
            # Primary locations: LABO: Concept generation, concept selection and concept-based
            # prediction; CBM_LIMIT: Concept representation/semantic-alignment analysis
            'traceability': 4,
            # Rating 3/5; original=None; v3.3.11=3. retained after comparative review.
            # Reason: Concept generation and alignment add cost; encoders are reused.
            # Comparison: LaBo (LLM-guided CBM) (3/5) scores above Supervised CBM (2/5): the former
            # pretrained language/vision models reduce retraining but add setup work; the latter
            # concept annotations and predictor training are required.
            # Comparison: LaBo (LLM-guided CBM) (3/5) ties Post-hoc CBM (concept-only) (3/5): the
            # former pretrained language/vision models reduce retraining but add setup work; the
            # latter a frozen backbone reduces training and annotation burden.
            # Calibration: Neutral bin: the evidence does not warrant a general stronger or weaker
            # claim on this exact property. A tie is not demonstrated empirical equivalence.
            # Evidence: qualitative comparative inference; see study cards for direct endpoints and
            # counterevidence. Confidence: moderate.
            # Sources: LABO, CBM_LIMIT, CBM, PCBM. Comparative studies: E14. See documentation §6
            # for endpoints and limits.
            # Primary locations: LABO: Concept generation, concept selection and concept-based
            # prediction; CBM_LIMIT: Concept representation/semantic-alignment analysis
            'runtime_performance_and_implementation_constraints': 3,
        },
        'scope_stage': 'both',
        'models': ['concept-bottleneck classifier'],
        'required_access': 'model_replacement',
        'requires_model_replacement': True,
        'component_only': False,
        'explanation_target': 'output of the LaBo concept classifier',
        "question_types": {'how_computed', 'what_feature', 'what_if'},
    },
    # An explainer LLM proposes descriptions, then simulation scores them against held-out
    # activations. Requires activation access; model-output legal explanations need additional
    # evidence.
    'LLM neuron explanations (Bills et al.)': {
        "subprops": {
            # Rating 2/5; original=None; v3.3.11=2. retained after comparative review.
            # Reason: Descriptions are imperfect correlations with activation patterns.
            # Comparison: LLM neuron explanations (Bills et al.) (2/5) scores below LLM-assisted
            # behavioral RuleSHAP (MechaRule stage 1) (3/5): the former a fluent description can
            # predict activations incorrectly; the latter behavioral association does not establish
            # internal necessity.
            # Comparison: LLM neuron explanations (Bills et al.) (2/5) scores below MechaRule (4/5):
            # the former a fluent description can predict activations incorrectly; the latter neuron
            # interventions add conditional influence evidence.
            # Calibration: A below-neutral limitation. The integer is an ordinal coding decision;
            # neither the unit gap nor universal superiority/inferiority is measured.
            # Evidence: qualitative comparative inference; see study cards for direct endpoints and
            # counterevidence. Confidence: moderate.
            # Sources: LLM_NEURON, MECHARULE. Comparative studies: E19. See documentation §6 for
            # endpoints and limits.
            # Primary locations: LLM_NEURON: Explanation/simulation pipeline; Results and
            # Limitations
            'no_false_positives': 2,
            # Rating 2/5; original=None; v3.3.11=2. retained after comparative review.
            # Reason: Polysemantic behavior can escape concise descriptions.
            # Comparison: LLM neuron explanations (Bills et al.) (2/5) scores below LLM-assisted
            # behavioral RuleSHAP (MechaRule stage 1) (3/5): the former polysemantic activation
            # patterns can escape one description; the latter unproposed predicates leave behavior
            # unrepresented.
            # Comparison: LLM neuron explanations (Bills et al.) (2/5) scores below MechaRule (3/5):
            # the former polysemantic activation patterns can escape one description; the latter
            # candidate reduction and weak-effect omissions limit recovery.
            # Calibration: A below-neutral limitation. The integer is an ordinal coding decision;
            # neither the unit gap nor universal superiority/inferiority is measured.
            # Evidence: qualitative comparative inference; see study cards for direct endpoints and
            # counterevidence. Confidence: moderate.
            # Sources: LLM_NEURON, MECHARULE. Comparative studies: E19. See documentation §6 for
            # endpoints and limits.
            # Primary locations: LLM_NEURON: Explanation/simulation pipeline; Results and
            # Limitations
            'no_false_negatives': 2,
            # Rating 2/5; original=None; v3.3.11=2. retained after comparative review.
            # Reason: The declared target is neuron activation behavior. The reported descriptions
            # often explain that behavior only partially; score low coverage of this target. Missing
            # downstream decision mechanisms is a separate scope exclusion, not a reason to assign
            # the lowest within-target score.
            # Comparison: LLM neuron explanations (Bills et al.) (2/5) scores below LLM-assisted
            # behavioral RuleSHAP (MechaRule stage 1) (3/5): the former descriptions only partly
            # cover the declared activation target; the latter selected task rules only partly cover
            # the model.
            # Comparison: LLM neuron explanations (Bills et al.) (2/5) scores below MechaRule (3/5):
            # the former descriptions only partly cover the declared activation target; the latter
            # task-conditioned rules do not cover the full model.
            # Calibration: A below-neutral limitation. The integer is an ordinal coding decision;
            # neither the unit gap nor universal superiority/inferiority is measured.
            # Evidence: qualitative comparative inference; see study cards for direct endpoints and
            # counterevidence. Confidence: moderate.
            # Sources: LLM_NEURON, MECHARULE. Comparative studies: E19. See documentation §6 for
            # endpoints and limits.
            # Primary locations: LLM_NEURON: Explanation/simulation pipeline; Results and
            # Limitations
            'completeness': 2,
            # Rating 3/5; original=None; v3.3.11=3. retained after comparative review.
            # Reason: Poor activation prediction or out-of-distribution generalization does not
            # establish instability under small, behavior-preserving input changes. No direct
            # local-stability evaluation supports the previous 2; use the neutral evidence-limited
            # prior. Generation variability is assessed separately under consistency.
            # Comparison: LLM neuron explanations (Bills et al.) (3/5) scores above LLM-assisted
            # behavioral RuleSHAP (MechaRule stage 1) (2/5): the former activation prediction error
            # alone is not a local-stability test; the latter generated features and fitted rules
            # can vary.
            # Comparison: LLM neuron explanations (Bills et al.) (3/5) ties MechaRule (3/5): the
            # former activation prediction error alone is not a local-stability test; the latter
            # results depend on task and intervention regime.
            # Calibration: Neutral bin: the evidence does not warrant a general stronger or weaker
            # claim on this exact property. A tie is not demonstrated empirical equivalence.
            # Evidence: qualitative comparative inference; see study cards for direct endpoints and
            # counterevidence. Confidence: low.
            # Sources: LLM_NEURON_OVERVIEW, MECHARULE. Comparative studies: no matched direct study
            # located; mechanism/threat-model inference. See documentation §6 for endpoints and
            # limits.
            # Primary locations: LLM_NEURON_OVERVIEW: What we found; Outlook: imperfect
            # correlations, out-of-distribution limitations, and distinction from downstream effects
            'stability': 3,
            # Rating 3/5; original=None; v3.3.11=3. retained after comparative review.
            # Reason: No general adversarial-resistance evaluation establishes a strength.
            # Comparison: LLM neuron explanations (Bills et al.) (3/5) ties LLM-assisted behavioral
            # RuleSHAP (MechaRule stage 1) (3/5): the former a scored description has no established
            # attack defense; the latter there is no published generic explainer-attack defense.
            # Comparison: LLM neuron explanations (Bills et al.) (3/5) ties MechaRule (3/5): the
            # former a scored description has no established attack defense; the latter jailbreak
            # experiments are not attacks against the explainer.
            # Calibration: Neutral bin: the evidence does not warrant a general stronger or weaker
            # claim on this exact property. A tie is not demonstrated empirical equivalence.
            # Evidence: qualitative comparative inference; see study cards for direct endpoints and
            # counterevidence. Confidence: low.
            # Sources: LLM_NEURON, MECHARULE. Comparative studies: no matched direct study located;
            # mechanism/threat-model inference. See documentation §6 for endpoints and limits.
            # Primary locations: LLM_NEURON: Explanation/simulation pipeline; Results and
            # Limitations
            'adversarial_robustness': 3,
            # Rating 2/5; original=None; v3.3.11=2. retained after comparative review.
            # Reason: Generated descriptions can vary across models or runs.
            # Comparison: LLM neuron explanations (Bills et al.) (2/5) ties LLM-assisted behavioral
            # RuleSHAP (MechaRule stage 1) (2/5): the former generative descriptions can vary across
            # runs; the latter LLM predicate proposals add run variability.
            # Comparison: LLM neuron explanations (Bills et al.) (2/5) scores below MechaRule (3/5):
            # the former generative descriptions can vary across runs; the latter fixed artifacts
            # support replay, with regime dependence.
            # Calibration: A below-neutral limitation. The integer is an ordinal coding decision;
            # neither the unit gap nor universal superiority/inferiority is measured.
            # Evidence: qualitative comparative inference; see study cards for direct endpoints and
            # counterevidence. Confidence: low.
            # Sources: LLM_NEURON, MECHARULE. Comparative studies: E19. See documentation §6 for
            # endpoints and limits.
            # Primary locations: LLM_NEURON: Explanation/simulation pipeline; Results and
            # Limitations
            'consistency': 2,
            # Rating 2/5; original=None; v3.3.11=2. retained after comparative review.
            # Reason: Prompts, examples and simulator choices affect explanations.
            # Comparison: LLM neuron explanations (Bills et al.) (2/5) ties LLM-assisted behavioral
            # RuleSHAP (MechaRule stage 1) (2/5): the former examples, prompt and simulator choices
            # affect the result; the latter prompt, candidate budget and rule settings affect
            # output.
            # Comparison: LLM neuron explanations (Bills et al.) (2/5) ties MechaRule (2/5): the
            # former examples, prompt and simulator choices affect the result; the latter effect
            # threshold and candidate budget change localized neurons.
            # Calibration: A below-neutral limitation. The integer is an ordinal coding decision;
            # neither the unit gap nor universal superiority/inferiority is measured.
            # Evidence: qualitative comparative inference; see study cards for direct endpoints and
            # counterevidence. Confidence: low.
            # Sources: LLM_NEURON, MECHARULE. Comparative studies: no matched direct study located;
            # mechanism/threat-model inference. See documentation §6 for endpoints and limits.
            # Primary locations: LLM_NEURON: Explanation/simulation pipeline; Results and
            # Limitations
            'hyperparameters_perturbation_robustness': 2,
            # Rating 3/5; original=None; v3.3.11=3. retained after comparative review.
            # Reason: Short descriptions compress behavior without proving minimality.
            # Comparison: LLM neuron explanations (Bills et al.) (3/5) ties LLM-assisted behavioral
            # RuleSHAP (MechaRule stage 1) (3/5): the former a short description may be compact
            # without semantic minimality; the latter the behavioral high-recall stage is not the
            # sparse final neuron-linked output.
            # Comparison: LLM neuron explanations (Bills et al.) (3/5) scores below MechaRule (4/5):
            # the former a short description may be compact without semantic minimality; the latter
            # compressed neuron-linked rules can summarize many observations.
            # Calibration: Neutral bin: the evidence does not warrant a general stronger or weaker
            # claim on this exact property. A tie is not demonstrated empirical equivalence.
            # Evidence: qualitative comparative inference; see study cards for direct endpoints and
            # counterevidence. Confidence: moderate.
            # Sources: LLM_NEURON, MECHARULE. Comparative studies: no matched direct study located;
            # mechanism/threat-model inference. See documentation §6 for endpoints and limits.
            # Primary locations: LLM_NEURON: Explanation/simulation pipeline; Results and
            # Limitations
            'sparsity': 3,
            # Rating 3/5; original=None; v3.3.11=3. retained after comparative review.
            # Reason: Neuron-level linguistic patterns offer intermediate descriptive detail.
            # Comparison: LLM neuron explanations (Bills et al.) (3/5) scores below LLM-assisted
            # behavioral RuleSHAP (MechaRule stage 1) (4/5): the former language descriptions
            # abstract over activation observations; the latter explicit behavioral predicates give
            # more structure than a weight vector.
            # Comparison: LLM neuron explanations (Bills et al.) (3/5) scores below MechaRule (4/5):
            # the former language descriptions abstract over activation observations; the latter
            # predicates plus neuron interventions expose conditional mechanism evidence.
            # Calibration: Neutral bin: the evidence does not warrant a general stronger or weaker
            # claim on this exact property. A tie is not demonstrated empirical equivalence.
            # Evidence: qualitative comparative inference; see study cards for direct endpoints and
            # counterevidence. Confidence: moderate.
            # Sources: LLM_NEURON, MECHARULE. Comparative studies: no matched direct study located;
            # mechanism/threat-model inference. See documentation §6 for endpoints and limits.
            # Primary locations: LLM_NEURON: Explanation/simulation pipeline; Results and
            # Limitations
            'level_of_detail': 3,
            # Rating 3/5; original=None; v3.3.11=3. retained after comparative review.
            # Reason: Activation examples may contain sensitive text.
            # Comparison: LLM neuron explanations (Bills et al.) (3/5) scores above LLM-assisted
            # behavioral RuleSHAP (MechaRule stage 1) (2/5): the former activation exemplars and
            # prompts may disclose sensitive text; the latter behavior records and reusable rules
            # can disclose sensitive logic.
            # Comparison: LLM neuron explanations (Bills et al.) (3/5) scores above MechaRule (2/5):
            # the former activation exemplars and prompts may disclose sensitive text; the latter
            # behavioral rules and internals disclose reusable model information.
            # Calibration: Neutral bin: the evidence does not warrant a general stronger or weaker
            # claim on this exact property. A tie is not demonstrated empirical equivalence.
            # Evidence: qualitative comparative inference; see study cards for direct endpoints and
            # counterevidence. Confidence: low.
            # Sources: LLM_NEURON, PRIVACY, MECHARULE. Comparative studies: no matched direct study
            # located; mechanism/threat-model inference. See documentation §6 for endpoints and
            # limits.
            # Primary locations: LLM_NEURON: Explanation/simulation pipeline; Results and
            # Limitations; PRIVACY: §§3–5; direct evidence for tested gradient/IG/LRP/LIME
            # configurations; threat-model context only for other methods
            'confidentiality': 3,
            # Rating 4/5; original=None; v3.3.11=4. retained after comparative review.
            # Reason: Archive examples, prompts, activations and generated descriptions.
            # Comparison: LLM neuron explanations (Bills et al.) (4/5) scores above LLM-assisted
            # behavioral RuleSHAP (MechaRule stage 1) (3/5): the former stored exemplars, prompts
            # and simulation scores support inspection; the latter predicate proposals and fitting
            # records are needed, without ablation traces.
            # Comparison: LLM neuron explanations (Bills et al.) (4/5) ties MechaRule (4/5): the
            # former stored exemplars, prompts and simulation scores support inspection; the latter
            # ablation records connect rules to tested internal changes.
            # Calibration: A qualified comparative strength. The integer is an ordinal coding
            # decision; neither the unit gap nor universal superiority/inferiority is measured.
            # Evidence: qualitative comparative inference; see study cards for direct endpoints and
            # counterevidence. Confidence: moderate.
            # Sources: LLM_NEURON, MECHARULE. Comparative studies: no matched direct study located;
            # mechanism/threat-model inference. See documentation §6 for endpoints and limits.
            # Primary locations: LLM_NEURON: Explanation/simulation pipeline; Results and
            # Limitations
            'traceability': 4,
            # Rating 2/5; original=None; v3.3.11=2. retained after comparative review.
            # Reason: Repeated generation and simulation are compute-intensive.
            # Comparison: LLM neuron explanations (Bills et al.) (2/5) ties LLM-assisted behavioral
            # RuleSHAP (MechaRule stage 1) (2/5): the former both explanation generation and
            # held-out simulation require LLM work; the latter LLM proposals and behavioral scoring
            # precede rule fitting.
            # Comparison: LLM neuron explanations (Bills et al.) (2/5) ties MechaRule (2/5): the
            # former both explanation generation and held-out simulation require LLM work; the
            # latter candidate search and interventions require substantial model access and work.
            # Calibration: A below-neutral limitation. The integer is an ordinal coding decision;
            # neither the unit gap nor universal superiority/inferiority is measured.
            # Evidence: qualitative comparative inference; see study cards for direct endpoints and
            # counterevidence. Confidence: moderate.
            # Sources: LLM_NEURON, MECHARULE. Comparative studies: E19. See documentation §6 for
            # endpoints and limits.
            # Primary locations: LLM_NEURON: Explanation/simulation pipeline; Results and
            # Limitations
            'runtime_performance_and_implementation_constraints': 2,
        },
        'scope_stage': 'global-exante',
        'models': ['transformer language model with required internal access'],
        'required_access': 'component_analysis',
        'requires_model_replacement': False,
        'component_only': True,
        'explanation_target': 'neuron activation patterns, not downstream model decisions',
        "question_types": {'what_feature'},
    },
    # Open-weight LLM with internal intervention access. Task-local rules summarize a task cohort,
    # not a full model or individual legal decision. Preprint v1; experimental pruning is empirical,
    # not globally certified.
    'MechaRule': {
        "subprops": {
            # Rating 4/5; original=None; v3.3.11=4. retained after comparative review.
            # Reason: Ablation provides conditional necessity evidence, not uniquely symbolic
            # mechanisms.
            # Comparison: MechaRule (4/5) scores above LLM-assisted behavioral RuleSHAP (MechaRule
            # stage 1) (3/5): the former neuron interventions add conditional influence evidence;
            # the latter behavioral association does not establish internal necessity.
            # Comparison: MechaRule (4/5) scores above LLM neuron explanations (Bills et al.) (2/5):
            # the former neuron interventions add conditional influence evidence; the latter a
            # fluent description can predict activations incorrectly.
            # Calibration: A qualified comparative strength. The integer is an ordinal coding
            # decision; neither the unit gap nor universal superiority/inferiority is measured.
            # Evidence: qualitative comparative inference; see study cards for direct endpoints and
            # counterevidence. Confidence: moderate.
            # Sources: MECHARULE, LLM_NEURON. Comparative studies: E15. See documentation §6 for
            # endpoints and limits.
            # Primary locations: MECHARULE: §4 pipeline; §4.2 behavioral predicates; §8 limitations
            'no_false_positives': 4,
            # Rating 3/5; original=None; v3.3.11=3. retained after comparative review.
            # Reason: Candidate reduction and weak-effect search can miss neurons.
            # Comparison: MechaRule (3/5) scores above LLM neuron explanations (Bills et al.) (2/5):
            # the former candidate reduction and weak-effect omissions limit recovery; the latter
            # polysemantic activation patterns can escape one description.
            # Comparison: MechaRule (3/5) ties LLM-assisted behavioral RuleSHAP (MechaRule stage 1)
            # (3/5): the former candidate reduction and weak-effect omissions limit recovery; the
            # latter unproposed predicates leave behavior unrepresented.
            # Calibration: Neutral bin: the evidence does not warrant a general stronger or weaker
            # claim on this exact property. A tie is not demonstrated empirical equivalence.
            # Evidence: qualitative comparative inference; see study cards for direct endpoints and
            # counterevidence. Confidence: moderate.
            # Sources: MECHARULE, LLM_NEURON. Comparative studies: E15. See documentation §6 for
            # endpoints and limits.
            # Primary locations: MECHARULE: §4 pipeline; §4.2 behavioral predicates; §8 limitations
            'no_false_negatives': 3,
            # Rating 3/5; original=None; v3.3.11=3. retained after comparative review.
            # Reason: Coverage is restricted to task, candidates and intervention basis.
            # Comparison: MechaRule (3/5) scores above LLM neuron explanations (Bills et al.) (2/5):
            # the former task-conditioned rules do not cover the full model; the latter descriptions
            # only partly cover the declared activation target.
            # Comparison: MechaRule (3/5) ties LLM-assisted behavioral RuleSHAP (MechaRule stage 1)
            # (3/5): the former task-conditioned rules do not cover the full model; the latter
            # selected task rules only partly cover the model.
            # Calibration: Neutral bin: the evidence does not warrant a general stronger or weaker
            # claim on this exact property. A tie is not demonstrated empirical equivalence.
            # Evidence: qualitative comparative inference; see study cards for direct endpoints and
            # counterevidence. Confidence: moderate.
            # Sources: MECHARULE, LLM_NEURON. Comparative studies: E15. See documentation §6 for
            # endpoints and limits.
            # Primary locations: MECHARULE: §4 pipeline; §4.2 behavioral predicates; §8 limitations
            'completeness': 3,
            # Rating 3/5; original=None; v3.3.11=3. retained after comparative review.
            # Reason: Baseline and task regime affect localized explanations.
            # Comparison: MechaRule (3/5) ties LLM neuron explanations (Bills et al.) (3/5): the
            # former results depend on task and intervention regime; the latter activation
            # prediction error alone is not a local-stability test.
            # Comparison: MechaRule (3/5) scores above LLM-assisted behavioral RuleSHAP (MechaRule
            # stage 1) (2/5): the former results depend on task and intervention regime; the latter
            # generated features and fitted rules can vary.
            # Calibration: Neutral bin: the evidence does not warrant a general stronger or weaker
            # claim on this exact property. A tie is not demonstrated empirical equivalence.
            # Evidence: qualitative comparative inference; see study cards for direct endpoints and
            # counterevidence. Confidence: low.
            # Sources: MECHARULE, LLM_NEURON_OVERVIEW. Comparative studies: no matched direct study
            # located; mechanism/threat-model inference. See documentation §6 for endpoints and
            # limits.
            # Primary locations: MECHARULE: §4 pipeline; §4.2 behavioral predicates; §8 limitations
            'stability': 3,
            # Rating 3/5; original=None; v3.3.11=3. retained after comparative review.
            # Reason: Jailbreak suppression is not robustness of the explanation itself.
            # Comparison: MechaRule (3/5) ties LLM neuron explanations (Bills et al.) (3/5): the
            # former jailbreak experiments are not attacks against the explainer; the latter a
            # scored description has no established attack defense.
            # Comparison: MechaRule (3/5) ties LLM-assisted behavioral RuleSHAP (MechaRule stage 1)
            # (3/5): the former jailbreak experiments are not attacks against the explainer; the
            # latter there is no published generic explainer-attack defense.
            # Calibration: Neutral bin: the evidence does not warrant a general stronger or weaker
            # claim on this exact property. A tie is not demonstrated empirical equivalence.
            # Evidence: qualitative comparative inference; see study cards for direct endpoints and
            # counterevidence. Confidence: low.
            # Sources: MECHARULE, LLM_NEURON. Comparative studies: no matched direct study located;
            # mechanism/threat-model inference. See documentation §6 for endpoints and limits.
            # Primary locations: MECHARULE: §4 pipeline; §4.2 behavioral predicates; §8 limitations
            'adversarial_robustness': 3,
            # Rating 3/5; original=None; v3.3.11=3. retained after comparative review.
            # Reason: Cross-model and temporal consistency remain unestablished.
            # Comparison: MechaRule (3/5) scores above LLM neuron explanations (Bills et al.) (2/5):
            # the former fixed artifacts support replay, with regime dependence; the latter
            # generative descriptions can vary across runs.
            # Comparison: MechaRule (3/5) scores above LLM-assisted behavioral RuleSHAP (MechaRule
            # stage 1) (2/5): the former fixed artifacts support replay, with regime dependence; the
            # latter LLM predicate proposals add run variability.
            # Calibration: Neutral bin: the evidence does not warrant a general stronger or weaker
            # claim on this exact property. A tie is not demonstrated empirical equivalence.
            # Evidence: qualitative comparative inference; see study cards for direct endpoints and
            # counterevidence. Confidence: low.
            # Sources: MECHARULE, LLM_NEURON. Comparative studies: no matched direct study located;
            # mechanism/threat-model inference. See documentation §6 for endpoints and limits.
            # Primary locations: MECHARULE: §4 pipeline; §4.2 behavioral predicates; §8 limitations
            'consistency': 3,
            # Rating 2/5; original=None; v3.3.11=2. retained after comparative review.
            # Reason: Candidate budget, thresholds and baselines affect localization.
            # Comparison: MechaRule (2/5) ties LLM neuron explanations (Bills et al.) (2/5): the
            # former effect threshold and candidate budget change localized neurons; the latter
            # examples, prompt and simulator choices affect the result.
            # Comparison: MechaRule (2/5) ties LLM-assisted behavioral RuleSHAP (MechaRule stage 1)
            # (2/5): the former effect threshold and candidate budget change localized neurons; the
            # latter prompt, candidate budget and rule settings affect output.
            # Calibration: A below-neutral limitation. The integer is an ordinal coding decision;
            # neither the unit gap nor universal superiority/inferiority is measured.
            # Evidence: qualitative comparative inference; see study cards for direct endpoints and
            # counterevidence. Confidence: low.
            # Sources: MECHARULE, LLM_NEURON. Comparative studies: E15. See documentation §6 for
            # endpoints and limits.
            # Primary locations: MECHARULE: §4 pipeline; §4.2 behavioral predicates; §8 limitations
            'hyperparameters_perturbation_robustness': 2,
            # Rating 4/5; original=None; v3.3.11=4. retained after comparative review.
            # Reason: Sparse neurons and compact rules are explicit objectives.
            # Comparison: MechaRule (4/5) scores above LLM neuron explanations (Bills et al.) (3/5):
            # the former compressed neuron-linked rules can summarize many observations; the latter
            # a short description may be compact without semantic minimality.
            # Comparison: MechaRule (4/5) scores above LLM-assisted behavioral RuleSHAP (MechaRule
            # stage 1) (3/5): the former compressed neuron-linked rules can summarize many
            # observations; the latter the behavioral high-recall stage is not the sparse final
            # neuron-linked output.
            # Calibration: A qualified comparative strength. The integer is an ordinal coding
            # decision; neither the unit gap nor universal superiority/inferiority is measured.
            # Evidence: qualitative comparative inference; see study cards for direct endpoints and
            # counterevidence. Confidence: moderate.
            # Sources: MECHARULE, LLM_NEURON. Comparative studies: E15. See documentation §6 for
            # endpoints and limits.
            # Primary locations: MECHARULE: §4 pipeline; §4.2 behavioral predicates; §8 limitations
            'sparsity': 4,
            # Rating 4/5; original=None; v3.3.11=4. retained after comparative review.
            # Reason: Rules linked to neuron coordinates add mechanistic detail.
            # Comparison: MechaRule (4/5) scores above LLM neuron explanations (Bills et al.) (3/5):
            # the former predicates plus neuron interventions expose conditional mechanism evidence;
            # the latter language descriptions abstract over activation observations.
            # Comparison: MechaRule (4/5) ties LLM-assisted behavioral RuleSHAP (MechaRule stage 1)
            # (4/5): the former predicates plus neuron interventions expose conditional mechanism
            # evidence; the latter explicit behavioral predicates give more structure than a weight
            # vector.
            # Calibration: A qualified comparative strength. The integer is an ordinal coding
            # decision; neither the unit gap nor universal superiority/inferiority is measured.
            # Evidence: qualitative comparative inference; see study cards for direct endpoints and
            # counterevidence. Confidence: moderate.
            # Sources: MECHARULE, LLM_NEURON. Comparative studies: no matched direct study located;
            # mechanism/threat-model inference. See documentation §6 for endpoints and limits.
            # Primary locations: MECHARULE: §4 pipeline; §4.2 behavioral predicates; §8 limitations
            'level_of_detail': 4,
            # Rating 2/5; original=None; v3.3.11=2. retained after comparative review.
            # Reason: Internal coordinates and rules can expose proprietary mechanisms.
            # Comparison: MechaRule (2/5) scores below LLM neuron explanations (Bills et al.) (3/5):
            # the former behavioral rules and internals disclose reusable model information; the
            # latter activation exemplars and prompts may disclose sensitive text.
            # Comparison: MechaRule (2/5) ties LLM-assisted behavioral RuleSHAP (MechaRule stage 1)
            # (2/5): the former behavioral rules and internals disclose reusable model information;
            # the latter behavior records and reusable rules can disclose sensitive logic.
            # Calibration: A below-neutral limitation. The integer is an ordinal coding decision;
            # neither the unit gap nor universal superiority/inferiority is measured.
            # Evidence: qualitative comparative inference; see study cards for direct endpoints and
            # counterevidence. Confidence: low.
            # Sources: MECHARULE, PRIVACY, LLM_NEURON. Comparative studies: no matched direct study
            # located; mechanism/threat-model inference. See documentation §6 for endpoints and
            # limits.
            # Primary locations: MECHARULE: §4 pipeline; §4.2 behavioral predicates; §8 limitations;
            # PRIVACY: §§3–5; direct evidence for tested gradient/IG/LRP/LIME configurations;
            # threat-model context only for other methods
            'confidentiality': 2,
            # Rating 4/5; original=None; v3.3.11=4. retained after comparative review.
            # Reason: Record rules, intervention traces, candidates and baseline choices.
            # Comparison: MechaRule (4/5) ties LLM neuron explanations (Bills et al.) (4/5): the
            # former ablation records connect rules to tested internal changes; the latter stored
            # exemplars, prompts and simulation scores support inspection.
            # Comparison: MechaRule (4/5) scores above LLM-assisted behavioral RuleSHAP (MechaRule
            # stage 1) (3/5): the former ablation records connect rules to tested internal changes;
            # the latter predicate proposals and fitting records are needed, without ablation
            # traces.
            # Calibration: A qualified comparative strength. The integer is an ordinal coding
            # decision; neither the unit gap nor universal superiority/inferiority is measured.
            # Evidence: qualitative comparative inference; see study cards for direct endpoints and
            # counterevidence. Confidence: moderate.
            # Sources: MECHARULE, LLM_NEURON. Comparative studies: no matched direct study located;
            # mechanism/threat-model inference. See documentation §6 for endpoints and limits.
            # Primary locations: MECHARULE: §4 pipeline; §4.2 behavioral predicates; §8 limitations
            'traceability': 4,
            # Rating 2/5; original=None; v3.3.11=2. retained after comparative review.
            # Reason: Hierarchical search saves interventions but requires costly internal access.
            # Comparison: MechaRule (2/5) ties LLM neuron explanations (Bills et al.) (2/5): the
            # former candidate search and interventions require substantial model access and work;
            # the latter both explanation generation and held-out simulation require LLM work.
            # Comparison: MechaRule (2/5) ties LLM-assisted behavioral RuleSHAP (MechaRule stage 1)
            # (2/5): the former candidate search and interventions require substantial model access
            # and work; the latter LLM proposals and behavioral scoring precede rule fitting.
            # Calibration: A below-neutral limitation. The integer is an ordinal coding decision;
            # neither the unit gap nor universal superiority/inferiority is measured.
            # Evidence: qualitative comparative inference; see study cards for direct endpoints and
            # counterevidence. Confidence: moderate.
            # Sources: MECHARULE, LLM_NEURON. Comparative studies: E15. See documentation §6 for
            # endpoints and limits.
            # Primary locations: MECHARULE: §4 pipeline; §4.2 behavioral predicates; §8 limitations
            'runtime_performance_and_implementation_constraints': 2,
        },
        'scope_stage': 'global-exante',
        'models': ['transformer language model with required internal access'],
        'required_access': 'internal_interventions',
        'requires_model_replacement': False,
        'component_only': False,
        'explanation_target': 'task-conditioned behavior under internal neuron ablation',
        "question_types": {'how_computed', 'what_feature', 'what_rule'},
    },
}

# add model families each XAI method was built for / excels on
algorithms_model_specific['CAVs'                ]['models'] = [
	'deep-neural-networks (CNNs, RNNs, Transformers)'
]  

# algorithms_model_specific['TreeSHAP'            ]['models'] = [
# 	'decision-trees',
# 	'random-forests',
# 	'gradient-boosted trees (XGBoost, LightGBM, CatBoost)'
# ]  

algorithms_model_specific['DeepLift'            ]['models'] = [
	'deep-neural-networks (feed-forward, CNNs, RNN/LSTM, Transformers)'
]  

algorithms_model_specific['DeepSHAP'            ]['models'] = [
	'deep-neural-networks (feed-forward, CNNs, RNN/LSTM, Transformers)'
]  

# algorithms_model_specific['Shapley Flow'        ]['models'] = [
# 	'model-agnostic (any ML pipeline given a causal DAG)'
# ]  

algorithms_model_specific['LRP'                 ]['models'] = [
	'deep-neural-networks (especially CNNs, RNNs, Transformers)'
]  

# algorithms_model_specific['Activation Maximization']['models'] = [
# 	'convolutional neural networks (vision)',
# 	'other deep-neural-networks amenable to gradient ascent'
# ]  

algorithms_model_specific['Grad-CAM'            ]['models'] = [
	'convolutional neural networks (2-D/3-D, vision, video)'
]  

algorithms_model_specific['Integrated Gradients']['models'] = [
	'any differentiable model (deep neural networks)'
]  

algorithms_model_specific['Attention'           ]['models'] = [
	'transformers and any architecture with attention mechanisms'
] 

# -------------------------------------------------------------------
# Helper functions
# -------------------------------------------------------------------
def procedure_fit(algo_mode, reg_mode, runtime_performance_and_implementation_constraints):
	# D3 requires an actual intersection. Global summaries do not automatically
	# answer a local/ex-post request. Explicit both-scope metadata is supported.
	modes = {'local-expost', 'global-exante'}
	if algo_mode not in modes | {'both'} or reg_mode not in modes | {'both'}:
		raise ValueError("Unknown scope/stage")
	cost = float(runtime_performance_and_implementation_constraints)
	if not math.isfinite(cost) or not 0 <= cost <= 5:
		raise ValueError("Efficiency must be finite and in [0, 5]")
	return cost > 0 and (reg_mode == 'both' or algo_mode == 'both' or algo_mode == reg_mode)

def question_fit(algo_q, reg_q):
	"""Return the shared supported/requested question kinds (empty means no fit)."""
	return algo_q & reg_q

def compute_w_pi(algo_subprops, reg_required):
	"""
	Return dict category -> coverage score in [0,1].
	Uses weighted average of (λ_s * score/5).
	"""
	# group regulation subprops by category
	assert all(s in SUBPROP_TO_CAT for s in algo_subprops.keys()), f"There's an invalid algo_subprops: {algo_subprops}"
	cat_weights = {}
	for sub, lam in reg_required.items():
		if not math.isfinite(float(lam)) or not 0 <= lam <= 1:
			raise ValueError("Legal weights must be finite and in [0, 1]")
		if sub not in SUBPROP_TO_CAT:
			raise KeyError(sub)
		# Only required categories enter the denominator of Eq. (2).
		if lam == 0:
			continue
		if not math.isfinite(float(algo_subprops.get(sub, 0))) or not 0 <= algo_subprops.get(sub, 0) <= 5:
			raise ValueError("Property scores must be finite and in [0, 5]")
		cat = SUBPROP_TO_CAT[sub]
		if cat not in cat_weights:
			cat_weights[cat] = {'num':0.0,'den':0.0}
		score_norm = (algo_subprops.get(sub,0))/5.0
		cat_weights[cat]['num'] += lam * score_norm
		cat_weights[cat]['den'] += lam

	w = {cat:(v['num']/v['den'] if v['den']>0 else 0.0)*CAT_WEIGHTS[cat]
		 for cat,v in cat_weights.items()}
	return w

def assess_xai_algorithms(algorithms, *, allow_model_replacement=False, include_component_explanations=False, available_access=None):
	"""Return a pandas table of best eligible candidates per regulation/question.

	Replacement predictors and component-only explanations are excluded by
	default. None for available_access assumes required access is available;
	an explicit set checks only profiles declaring a required_access field.
	The descriptive models metadata is not an automatic compatibility check.
	"""
	# D3 feasibility must not silently substitute a different predictor or a
	# component-level target for the requested explanation of a model output.
	algorithms = {name: profile for name, profile in algorithms.items()
		if (allow_model_replacement or not profile.get('requires_model_replacement'))
		and (include_component_explanations or not profile.get('component_only'))
		and (available_access is None or not profile.get('required_access')
		     or profile['required_access'] in available_access)}
	# -------------------------------------------------------------------
	#  Compute overall scores
	# -------------------------------------------------------------------
	rows = []
	for reg_name, reg in regulations.items():
		req = reg['required']
		assert all(q in TEXT_TO_QUESTION_KIND for q in reg['question_types']), f"There's an invalid question in {reg_name}"
		for algo_name, algo in algorithms.items():
			assert all(q in QUESTION_KINDS for q in algo['question_types']), f"There's an invalid question in {algo_name}"
			w_pi = compute_w_pi(algo['subprops'], req)
			avg_cov = sum(req[k]*algo['subprops'][k]/5 for k in req)/sum(req.values())
			fit_proc = procedure_fit(algo['scope_stage'], reg['scope_stage'], algo['subprops']['runtime_performance_and_implementation_constraints'])
			fit_q    = question_fit(algo['question_types'], set(map(lambda x: TEXT_TO_QUESTION_KIND[x], reg['question_types'])))
			# Keep precision through ranking; rounding first creates false ties.
			S = avg_cov * (1 if (fit_proc and fit_q) else 0)
			rows.append({
				"Regulation": reg_name,
				"Algorithm": algo_name,
				"Score": S,
			})

	scores_df = pd.DataFrame(rows, columns=["Regulation", "Algorithm", "Score"])

	# -------------------------------------------------------------------
	# Pick the best-fit XAI algorithm *for each question* in every regulation
	# -------------------------------------------------------------------
	best_rows = []
	for reg_name, reg in regulations.items():
		for q in set(map(lambda x: TEXT_TO_QUESTION_KIND[x], reg['question_types'])):
			# print(q)
			# for a in algorithms:
			#   print(q in algorithms[a]['question_types'], a)
			# candidates: rows for this regulation whose algorithm supports q
			cand = scores_df[
				(scores_df['Regulation'] == reg_name) &
				scores_df['Algorithm'].apply(lambda a: q in algorithms[a]['question_types'])
			]
			# find the max score in this candidate set
			max_score = cand['Score'].max()

			# select all rows that have that score
			best_candidates = cand[cand['Score'] == max_score]

			# now append one entry per best row
			best_algorithms = ', '.join(best['Algorithm'] for _, best in best_candidates.iterrows())
			best_rows.append({
				'Regulation'     : reg_name,
				'Question'       : q,
				'Best Algorithm' : best_algorithms if max_score > 0 else None,
				'Fit-score'      : max_score     if max_score > 0 else None,
			})

	best_df = (
		pd.DataFrame(best_rows)
		  .sort_values(['Regulation', 'Question'])
		  .reset_index(drop=True)
	)
	return best_df

# -------------------------------------------------------------------
# 4.  Show the results
# -------------------------------------------------------------------
if __name__ == '__main__':
	print("1️⃣ Best model agnostic XAI algorithm per regulation-question:\n")
	print(assess_xai_algorithms(algorithms_model_agnostic).to_string(index=False))
	
	print("2️⃣ Best eligible model-specific candidates (required access assumed; replacement models and component-only explanations excluded):\n")
	algorithms_all = {}
	algorithms_all.update(algorithms_model_agnostic)
	algorithms_all.update(algorithms_model_specific)
	print(assess_xai_algorithms(algorithms_all).to_string(index=False))
