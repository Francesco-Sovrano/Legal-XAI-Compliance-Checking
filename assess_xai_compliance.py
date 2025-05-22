import pandas as pd
from itertools import combinations
import math

# -------------------------------------------------------------------
# 0. Helper: define canonical question categories
# -------------------------------------------------------------------
# Canonical question kinds that we will track. A regulation "requires"
# a subset; an algorithm "supports" a subset.  A match occurs iff
# every required question category is contained in the supported set.
QUESTION_KINDS = {
	'what_feature',  # "What specific features…"
	'what_rule',     # "What rule / threshold…"
	'how_computed',     # "What rule / threshold…"
	'how_differs',   # "How does this decision differ from…"
	'what_if',       # "What if parameter X changed…"
	'how_modify_input',  # "What input values should I adjust…"
}

# map from the exact phrase (or a close synonym) to our canonical question key
TEXT_TO_QUESTION_KIND = {
	# rule-related
	'what rule':           'what_rule',
	'what general logic':  'what_rule',
	'how model decides':   'how_computed',

	# feature-related
	'what features':         'what_feature',
	'what are top features': 'what_feature',
	'what reasons':          'what_feature',
	'what feature importance': 'what_feature',

	'why those top features': 'how_computed', # think about it

	# comparison
	'how output differs from others': 'how_differs',

	# counterfactual / sensitivity
	'what if':                    'what_if',
	'how sensitive to outliers': 'what_if',

	# input modification
	'how to change':                'how_modify_input',
	'what inputs have wrong outcomes': 'how_modify_input',
	'what best input format and ranges': 'how_modify_input', # not sure about format

	# computation transparency
	'how output is computed':      'how_computed',
	'is input problematic':        'what_rule',
	'what input quality':          'how_modify_input',
	'how reliable is output':      'how_differs', # think about it, maybe not about XAI but rather confidence scoring
	'how robust':      'how_differs', # think about it, maybe not about XAI but rather confidence scoring
}

SUBPROP_TO_CAT = {
	# Faithfulness
	'no_false_positives': 'Faithfulness',
	'no_false_negatives': 'Faithfulness',
	'completeness': 'Faithfulness',
	# Robustness
	'stability': 'Robustness',
	'adversarial_robustness': 'Robustness',
	'consistency': 'Robustness',
	'hyperparameters_perturbation_robustness': 'Robustness',
	# Complexity
	'sparsity_and_size': 'Complexity',
	'level_of_detail': 'Complexity',
	# Responsibility
	'fairness': 'Responsibility',
	'confidentiality': 'Responsibility',
	'traceability': 'Responsibility',
	# Efficiency
	'runtime_performance_and_implementation_constraints': 'Efficiency',
}

CAT_WEIGHTS = {
	'Faithfulness': 1, # these seems to be the most represented category in the legislations analysed, so maybe it has higher priority than efficiency and complexity
	'Robustness': 1, # these seems to be the (second) most represented category in the legislations analysed, so maybe it has higher priority than efficiency and complexity
	'Complexity': 1, # 4th most represented
	'Responsibility': 1, # 3rd most represented
	'Efficiency': 1, # 5th most represented
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
			'sparsity_and_size': 0, 'level_of_detail': 0,
			'fairness':1, 'confidentiality':0.5, 'traceability':1,
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
			'sparsity_and_size': 0, 'level_of_detail': 0,
			'fairness':1, 'confidentiality':0.5, 'traceability':1,
			'runtime_performance_and_implementation_constraints':0,
		},
		'scope_stage': 'local-expost',
		'question_types': ['what rule', 'how output differs from others', 'what features', 'what reasons', 'is input problematic', 'how to change'],
	},

	'DSA27+P2B5': {
		'required': {
			'no_false_positives':1, 'no_false_negatives':0, 'completeness':0,
			'stability':0, 'adversarial_robustness':0.5, 'consistency':0, 'hyperparameters_perturbation_robustness': 1, 
			'sparsity_and_size': 0, 'level_of_detail': 1,
			'fairness':1, 'confidentiality':1, 'traceability':0,
			'runtime_performance_and_implementation_constraints':0,
		},
		'scope_stage': 'global-exante',
		'question_types': ['what are top features', 'why those top features', 'what general logic', 'what if'],
	},

	'AIA13-14': {
		'required': {
			'no_false_positives':0.75, 'no_false_negatives':1, 'completeness':0.75,
			'stability':1, 'adversarial_robustness':1, 'consistency':1, 'hyperparameters_perturbation_robustness': 1, 
			'sparsity_and_size': 0, 'level_of_detail': 0,
			'fairness':1, 'confidentiality':0, 'traceability':1,
			'runtime_performance_and_implementation_constraints':1, # we assume the worst-case scenario
		},
		'scope_stage': 'both',  # accepts both local/ex‑post and global/ex‑ante
		'question_types': ['what input quality', 'how output is computed', 'how sensitive to outliers', 'what rule', 'how reliable is output'],
	},

	'MDR': {
		'required': {
			'no_false_positives':1, 'no_false_negatives':1, 'completeness':1,
			'stability':1, 'adversarial_robustness':1, 'consistency':1, 'hyperparameters_perturbation_robustness': 1, 
			'sparsity_and_size': 0.5, 'level_of_detail': 0,
			'fairness':1, 'confidentiality':1, 'traceability':1, # we assume the worst-case scenario for confidentiality
			'runtime_performance_and_implementation_constraints':1, # we assume the worst-case scenario
		},
		'scope_stage': 'both',
		'question_types': ['what rule', 'what general logic', 'is input problematic', 'what inputs have wrong outcomes', 'what best input format and ranges', 'how reliable is output'],
	},

	'MiFID17': {
		'required': {
			'no_false_positives':1, 'no_false_negatives':1, 'completeness':1,
			'stability':1, 'adversarial_robustness':1, 'consistency':1, 'hyperparameters_perturbation_robustness': 1, 
			'sparsity_and_size': 0, 'level_of_detail': 0,
			'fairness':1, 'confidentiality':0, 'traceability':1, 
			'runtime_performance_and_implementation_constraints':1, # we assume the worst-case scenario
		},
		'scope_stage': 'both',
		'question_types': [
			'how model decides', 'what feature importance', 
			# 'how regulatory compliance implemented', # not about XAI
			'how robust', 'what inputs have wrong outcomes'],
	},

	'AIA11': {
		'required': {
			'no_false_positives':1, 'no_false_negatives':1, 'completeness':1,
			'stability':0, 'adversarial_robustness':1, 'consistency':0, 'hyperparameters_perturbation_robustness': 1, 
			'sparsity_and_size': 1, 'level_of_detail': 1,
			'fairness':1, 'confidentiality':0, 'traceability':1, 
			'runtime_performance_and_implementation_constraints':0,
		},
		'scope_stage': 'global-exante',
		'question_types': [
			'how model decides', 'what feature importance', 
			# 'how regulatory compliance implemented', # not about XAI
			'how robust', 'what inputs have wrong outcomes'],
	},
}

# -------------------------------------------------------------------
# 2.  Algorithm‑level metadata
#     For brevity we include all algorithms in Tables 2 & 3.
# -------------------------------------------------------------------
algorithms_model_agnostic = {
	# --------------------------- MODEL‑AGNOSTIC ---------------------------
	'Decision Trees': {
		'subprops': {
			'no_false_positives': 2, 'no_false_negatives': 4, 'completeness': 5, # 'no_false_positives' is 2 due to well-known overfitting issues # 'completeness' is 5 because it's a global XAI method
			'stability': 5, 'adversarial_robustness': 2, 'consistency': 5, 'hyperparameters_perturbation_robustness': 0, # global methods are stable and consistent # adversarial robustness depends on false positives and false negatives, we pick the min score of the two
			'sparsity_and_size':  2, 'level_of_detail':  5, # sparsity_and_size is 2 because rules are very long
			'fairness': 4, 'confidentiality': 3, 'traceability': 5, # 'confidentiality': it's a global explanation learned over lots of possibly confidential data # 'traceability' is 5 because it's a white-box surrogate model with an explainable learning procedure
			'runtime_performance_and_implementation_constraints': 4,
		},
		'scope_stage': 'global-exante',
		'question_types': {'what_rule', 'how_differs', 'what_feature', 'what_if', 'how_modify_input', 'how_computed'},
	},
	'RuleFit': {
		'subprops': {
			'no_false_positives': 3, 'no_false_negatives': 4, 'completeness': 5, # 'no_false_positives' is 3 since RuleFit overfits less # 'completeness' is 5 because it's a global XAI method
			'stability': 5, 'adversarial_robustness': 3, 'consistency': 5, 'hyperparameters_perturbation_robustness': 3, # global methods are stable and consistent # adversarial robustness depends on false positives and false negatives, we pick the min score of the two
			'sparsity_and_size':  2, 'level_of_detail':  5, # sparsity_and_size is 2 because rules are long
			'fairness': 4, 'confidentiality': 3, 'traceability': 5, # 'confidentiality': it's a global explanation learned over lots of possibly confidential data # 'traceability' is 5 because it's a white-box surrogate model with an explainable learning procedure
			'runtime_performance_and_implementation_constraints': 3,
		},
		'scope_stage': 'global-exante',
		'question_types': {'what_rule', 'how_differs', 'what_feature', 'what_if', 'how_modify_input', 'how_computed'},
	},
	'Anchors': {
		'subprops': {
			'no_false_positives': 4,   # high-precision “anchors” ⇒ far fewer FP than LIME (2) or ICE (3)
			'no_false_negatives': 2,   # but guarantees precision at the cost of recall, missing many true features
			'completeness': 2,         # covers only the portion of the rule captured by the anchor
			'stability': 3,            # sampling variance > SHAP(4) but better than LIME(2)
			'adversarial_robustness': 2, # limited by the weaker of FP/FN
			'consistency': 3,          # anchors is non-deterministic; random search yields moderate run-to-run variability
			'hyperparameters_perturbation_robustness': 2,  # anchor threshold changes can alter rules
			'sparsity_and_size': 4,    # anchors are short, so more compact than DT(2)
			'level_of_detail': 4,      # specific feature-level rules for individual predictions, but not showin all conditions as it's what-if
			'fairness': 3,             # neutral; unlike DiCE(4) it has no explicit fairness constraints
			'confidentiality': 4,      # local sampling only; leaks less data than global DT(3)
			'traceability': 2,         # anchors is non-deterministic; search procedure reproducible
			'runtime_performance_and_implementation_constraints': 2, # combinatorial rule search can be slow
		},
		'scope_stage': 'local-expost',
		'question_types': {'what_rule', 'what_feature', 'what_if'},
	},

	'LIME': {
		'subprops': {
			# -- Faithfulness
			'no_false_positives': 2,  # linear surrogate often attributes non-causal features (worse than ICE (3) and ANC (4))
			'no_false_negatives' : 3,  # captures most influential features but can still miss some; better recall than ANC (2)
			'completeness'      : 3,  # local fidelity only; less complete than global DT/RF (5)
			# -- Robustness
			'stability'                         : 2,  # heavy sampling variance; far less stable than SHAP (4)
			'adversarial_robustness'            : 2,  # min(FP=2,FN=3); can be gamed by small perturbations
			'consistency'                       : 2,  # reruns with a new seed give noticeably different weights
			'hyperparameters_perturbation_robustness': 2,  # kernel-width or feature-count tweaks change explanations
			# -- Complexity
			'sparsity_and_size' : 3,  # configurable K-feature sparsity—denser than ANC (4) but leaner than SHAP (2)
			'level_of_detail'   : 4,  # per-feature weights → richer than PDP/ICE curves (3) but not concept-level
			# -- Responsibility
			'fairness'        : 3,  # no explicit bias control, neutral like PDP
			'confidentiality' : 4,  # only local synthetic perturbations → leaks less training data than global DT/RF (3)
			'traceability'    : 3,  # linear regression is transparent, but randomness hurts full reproducibility
			# -- Efficiency
			'runtime_performance_and_implementation_constraints': 3,  # moderate; O(K·M) model calls—not as cheap as PDP (3) but far cheaper than KernelSHAP (2)
		},
		'scope_stage': 'local-expost',
		'question_types': {'what_feature', 'what_if', 'how_computed'},
	},

	'SHAP': {
		'subprops': {
			# -- Faithfulness
			'no_false_positives': 4,  # Shapley axiom ⇒ irrelevant features get ≈ 0 (better than LIME (2))
			'no_false_negatives': 4,  # captures all influential features with non-zero value (≈ PPV=recall)
			'completeness'     : 5,  # “additive completeness” axiom: Σφ = f(x)−E[f(X)]
			# -- Robustness
			'stability'                         : 4,  # TreeSHAP deterministic; KernelSHAP converges with enough samples
			'adversarial_robustness'            : 4,  # min(FP,FN)=4; still manipulable but far tougher than LIME (2)
			'consistency'                       : 5,  # built-in monotonicity axiom; identical model change ⇒ no rank-flips
			'hyperparameters_perturbation_robustness': 3,  # KernelSHAP sample size & background distribution matter
			# -- Complexity
			'sparsity_and_size' : 2,  # every feature gets a value; long tails hurt compactness (worse than LIME (3))
			'level_of_detail'   : 5,  # exact per-feature contributions
			# -- Responsibility
			'fairness'        : 3,  # neutral; fairness constraints must be added externally
			'confidentiality' : 4,  # uses only model queries; no raw training records surfaced
			'traceability'    : 4,  # open algorithm + theoretical guarantees, but KernelSHAP sampling adds some noise
			# -- Efficiency
			'runtime_performance_and_implementation_constraints': 2,  # TreeSHAP is fast, but model-agnostic KernelSHAP is expensive (≈ O(2^d))
		},
		'scope_stage': 'local-expost',
		'question_types': {'what_feature', 'what_if', 'how_computed'},
	},

	'DiCE': {
		'subprops': {
			# -- Faithfulness
			'no_false_positives': 3,  # returned CF features do flip the label, but extra changes are common
			'no_false_negatives': 2,  # may omit other minimal changes; lower recall than LIME (3)
			'completeness'     : 2,  # shows *a* path, not the whole rationale
			# -- Robustness
			'stability'                         : 2,  # gradient-based search sensitive to init/random seed
			'adversarial_robustness'            : 2,  # min(FP=3,FN=2); can be steered by small gradient hacks
			'consistency'                       : 2,  # different runs often yield diverse CF sets
			'hyperparameters_perturbation_robustness': 1,  # λ weights for sparsity/diversity drastically change CFs
			# -- Complexity
			'sparsity_and_size' : 4,  # optimises for minimal feature tweaks (better than LIME (3))
			'level_of_detail'   : 4,  # explicit “change age from 35→52” style prescriptions
			# -- Responsibility
			'fairness'        : 4,  # built-in constrained-optimisation to enforce equal-opportunity if desired
			'confidentiality' : 4,  # only accesses black-box model, not training data
			'traceability'    : 3,  # optimisation objective visible, but non-convex search less reproducible
			# -- Efficiency
			'runtime_performance_and_implementation_constraints': 2,  # iterative search (esp. for deep nets) is slow
		},
		'scope_stage': 'local-expost',
		'question_types': {'what_rule', 'what_feature', 'what_if', 'how_modify_input'},
	},

	'PDP': {
		'subprops': {
			# -- Faithfulness
			'no_false_positives': 3,  # averages can mask interactions (better than DT (2) FP though)
			'no_false_negatives': 3,  # likewise misses some truly important features
			'completeness'     : 3,  # covers selected features globally but omits interactions/higher-order terms
			# -- Robustness
			'stability'                         : 4,  # deterministic given enough grid points; less noisy than LIME (2)
			'adversarial_robustness'            : 3,  # min(FP,FN)=3
			'consistency'                       : 4,  # same model + data ⇒ identical curves
			'hyperparameters_perturbation_robustness': 4,  # grid resolution has mild effect only
			# -- Complexity
			'sparsity_and_size' : 3,  # one curve per feature; moderate cognitive load
			'level_of_detail'   : 3,  # shows monotonic/non-linear trend but not fine-grained interactions
			# -- Responsibility
			'fairness'        : 3,
			'confidentiality' : 3,  # aggregated plot, but curves derived from full data distribution
			'traceability'    : 4,  # straightforward averaging formula
			# -- Efficiency
			'runtime_performance_and_implementation_constraints': 3,  # O(N·G) model calls (G=grid points)
		},
		'scope_stage': 'global-exante',
		'question_types': {'what_rule', 'what_feature', 'how_modify_input'},
	},

	'ICE': {
		'subprops': {
			# -- Faithfulness
			'no_false_positives': 3,  # individual curve reflects model response; still ignores other vars
			'no_false_negatives': 3,
			'completeness'     : 2,  # local to one feature & one instance
			# -- Robustness
			'stability'                         : 3,  # deterministic but jagged if model is non-smooth
			'adversarial_robustness'            : 3,
			'consistency'                       : 4,  # rerunning on same x gives identical curve
			'hyperparameters_perturbation_robustness': 4,  # grid density hardly changes qualitative shape
			# -- Complexity
			'sparsity_and_size' : 2,  # a whole curve per feature→user must parse many points
			'level_of_detail'   : 5,  # full functional relationship for *that* instance
			# -- Responsibility
			'fairness'        : 3,
			'confidentiality' : 3,  # reveals path of synthetic points close to real data
			'traceability'    : 4,  # computation is transparent
			# -- Efficiency
			'runtime_performance_and_implementation_constraints': 3,
		},
		'scope_stage': 'local-expost',
		'question_types': {'what_feature', 'how_modify_input'},
	},

	'CEM': {
		'subprops': {
			# -- Faithfulness
			'no_false_positives': 4,  # optimisation yields *pertinent* positives/negatives ⇒ high precision
			'no_false_negatives': 3,  # may still omit some causal features when searching minima
			'completeness'     : 3,
			# -- Robustness
			'stability'                         : 2,  # non-convex optimisation → multiple local optima
			'adversarial_robustness'            : 3,  # min(4,3)
			'consistency'                       : 3,
			'hyperparameters_perturbation_robustness': 2,  # β balancing PP/P N affects the sets a lot
			# -- Complexity
			'sparsity_and_size' : 5,  # explicitly minimises cardinality of PP / PN sets
			'level_of_detail'   : 4,  # tells which features must stay & which must flip
			# -- Responsibility
			'fairness'        : 3,
			'confidentiality' : 4,
			'traceability'    : 3,
			# -- Efficiency
			'runtime_performance_and_implementation_constraints': 2,  # iterative gradient + proxim. ops is costly
		},
		'scope_stage': 'local-expost',
		'question_types': {'what_rule', 'what_feature', 'what_if', 'how_modify_input'},
	},

	'ProtoDash': {
		'subprops': {
			# -- Faithfulness
			'no_false_positives': 3,  # prototypes are real points ⇒ at least valid examples, but not always causal
			'no_false_negatives': 2,  # a small prototype set can miss some behaviours
			'completeness'     : 2,  # covers data manifold ≈, but not decision logic
			# -- Robustness
			'stability'                         : 3,  # greedy selection order-dependent; still reproducible given seed
			'adversarial_robustness'            : 2,  # min(3,2)
			'consistency'                       : 4,  # same K & seed → identical protos
			'hyperparameters_perturbation_robustness': 3,  # K (number of protos) changes coverage gradually
			# -- Complexity
			'sparsity_and_size' : 4,  # user sets small K; compact representative set
			'level_of_detail'   : 3,  # shows *examples* but not feature contributions
			# -- Responsibility
			'fairness'        : 3,  # can inherit dataset bias; no explicit mitigation
			'confidentiality' : 2,  # exposes real data points ⇒ higher leakage risk than LIME (4)
			'traceability'    : 4,  # kernel-distance objective + greedy selection is transparent
			# -- Efficiency
			'runtime_performance_and_implementation_constraints': 3,  # O(N·K) kernel evals
		},
		'scope_stage': 'local-expost',
		'question_types': {'how_differs'},
	},
	
}

# --------------------------- MODEL‑SPECIFIC ---------------------------
algorithms_model_specific = {
	'CAVs': {
		'subprops': {
			'level_of_detail':4,'no_false_positives':4,
			'stability':2,'completeness':2,'adversarial_robustness':2
		},
		'scope_stage': 'local-expost',
		'question_types': {'how_computed', 'what_feature'},
	},
	'TreeSHAP': {
		'subprops': {
			'no_false_positives':5,'no_false_negatives':5,'completeness':5,
			'runtime_performance_and_implementation_constraints':4,'adversarial_robustness':2,'stability':2
		},
		'scope_stage': 'global-exante',
		'question_types': {'what_feature', 'what_if', 'how_computed'},
	},
	'DeepLift': {
		'subprops': {
			'no_false_positives':4,'runtime_performance_and_implementation_constraints':4,
			'stability':2,'hyperparameters_perturbation_robustness':2,'completeness':2
		},
		'scope_stage': 'local-expost',
		'question_types': {'what_feature', 'what_if', 'how_computed'},
	},
	'DeepSHAP': {
		'subprops': {
			'no_false_positives':4,'no_false_negatives':4,'completeness':2,
			'consistency':4,'runtime_performance_and_implementation_constraints':4,'adversarial_robustness':2
		},
		'scope_stage': 'local-expost',
		'question_types': {'what_feature', 'what_if', 'how_computed'},
	},
	'Boolean Rules': {
		'subprops': {
			'sparsity_and_size':4,'level_of_detail':4,'no_false_positives':4,'no_false_negatives':4,
			'runtime_performance_and_implementation_constraints':2,'stability':2,'completeness':2
		},
		'scope_stage': 'global-exante',
		'question_types': {'what_rule', 'how_differs', 'what_feature', 'what_if', 'how_modify_input'},
	},
	'Shapley Flow': {
		'subprops': {
			'no_false_positives':4,'no_false_negatives':4,'level_of_detail':4,'completeness':4,
			'runtime_performance_and_implementation_constraints':2,'stability':2
		},
		'scope_stage': 'local-expost',
		'question_types': {'what_feature', 'what_if', 'how_computed'},
	},
	'LRP': {
		'subprops': {
			'runtime_performance_and_implementation_constraints':4,'level_of_detail':4,
			'stability':2,'hyperparameters_perturbation_robustness':2,'completeness':2
		},
		'scope_stage': 'local-expost',
		'question_types': {'what_feature', 'what_if'},
	},
	'Activation Maximization': {
		'subprops': {
			'consistency':4,'level_of_detail':4,'runtime_performance_and_implementation_constraints':2,
			'stability':2,'adversarial_robustness':2
		},
		'scope_stage': 'local-expost',
		'question_types': {'how_computed'},
	},
	'Grad-CAM': {
		'subprops': {
			'runtime_performance_and_implementation_constraints':5,'no_false_negatives':3,
			'completeness':2,'adversarial_robustness':2,'stability':2
		},
		'scope_stage': 'local-expost',
		'question_types': {'what_feature', 'what_if', 'how_computed'},
	},
	'Integrated Gradients': {
		'subprops': {
			'no_false_positives':4,'runtime_performance_and_implementation_constraints':4,'stability':4,
			'completeness':3,'adversarial_robustness':2,'hyperparameters_perturbation_robustness':2
		},
		'scope_stage': 'local-expost',
		'question_types': {'what_feature', 'what_if', 'how_computed'},
	},
	'Attention': {
		'subprops': {
			'runtime_performance_and_implementation_constraints':4,'level_of_detail':4,
			'stability':2,'no_false_positives':2,'no_false_negatives':2,'completeness':1
		},
		'scope_stage': 'local-expost',
		'question_types': {'how_computed', 'what_feature'},
	},
}

# add model families each XAI method was built for / excels on
algorithms_model_specific['CAVs'                ]['models'] = [
	'deep-neural-networks (CNNs, RNNs, Transformers)'
]  

algorithms_model_specific['TreeSHAP'            ]['models'] = [
	'decision-trees',
	'random-forests',
	'gradient-boosted trees (XGBoost, LightGBM, CatBoost)'
]  

algorithms_model_specific['DeepLift'            ]['models'] = [
	'deep-neural-networks (feed-forward, CNNs, RNN/LSTM, Transformers)'
]  

algorithms_model_specific['DeepSHAP'            ]['models'] = [
	'deep-neural-networks (feed-forward, CNNs, RNN/LSTM, Transformers)'
]  

algorithms_model_specific['Boolean Rules'       ]['models'] = [
	'rule-based classifiers / Boolean rule learners',
	'interpretable tree or list models'
]  

algorithms_model_specific['Shapley Flow'        ]['models'] = [
	'model-agnostic (any ML pipeline given a causal DAG)'
]  

algorithms_model_specific['LRP'                 ]['models'] = [
	'deep-neural-networks (especially CNNs, RNNs, Transformers)'
]  

algorithms_model_specific['Activation Maximization']['models'] = [
	'convolutional neural networks (vision)',
	'other deep-neural-networks amenable to gradient ascent'
]  

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
def procedure_fit(algo_mode, reg_mode):
	return reg_mode == 'both' or algo_mode == reg_mode or (algo_mode == 'global-exante' and reg_mode == 'local-expost')

def question_fit(algo_q, reg_q):
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
		cat = SUBPROP_TO_CAT[sub]
		if cat not in cat_weights:
			cat_weights[cat] = {'num':0.0,'den':0.0}
		score_norm = (algo_subprops.get(sub,0))/5.0
		cat_weights[cat]['num'] += lam * score_norm
		cat_weights[cat]['den'] += lam

	w = {cat:(v['num']/v['den'] if v['den']>0 else 0.0)*CAT_WEIGHTS[cat]
		 for cat,v in cat_weights.items()}
	return w

def assess_xai_algorithms(algorithms):
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
			avg_cov = sum(w_pi.values())/len(w_pi) if w_pi else 0.0
			fit_proc = procedure_fit(algo['scope_stage'], reg['scope_stage'])
			fit_q    = question_fit(algo['question_types'], set(map(lambda x: TEXT_TO_QUESTION_KIND[x], reg['question_types'])))
			S = round(avg_cov * (1 if (fit_proc and fit_q) else 0), 2)
			rows.append({
				"Regulation": reg_name,
				"Algorithm": algo_name,
				"Score": S,
				"Scope‑fit": fit_proc,
				"Questions‑fit": fit_q
			})

	scores_df = pd.DataFrame(rows)

	# -------------------------------------------------------------------
	# Pick the best-fit XAI algorithm *for each question* in every regulation
	# -------------------------------------------------------------------
	best_rows = []
	for reg_name, reg in regulations.items():
		for q in map(lambda x: TEXT_TO_QUESTION_KIND[x], reg['question_types']):
			# print(q)
			# for a in algorithms:
			#   print(q in algorithms[a]['question_types'], a)
			# candidates: rows for this regulation whose algorithm supports q
			cand = scores_df[
				(scores_df['Regulation'] == reg_name) &
				scores_df['Algorithm'].apply(lambda a: q in algorithms[a]['question_types'])
			]
			# print(cand)
			best = cand.loc[cand['Score'].idxmax()]
			best_rows.append({
				'Regulation'     : reg_name,
				'Question'       : q,
				'Best Algorithm' : best['Algorithm'] if not cand.empty else None,
				'Fit-score'      : best['Score'] if not cand.empty else None,
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
print("1️⃣ Best model agnostic XAI algorithm per regulation-question:\n")
print(assess_xai_algorithms(algorithms_model_agnostic).to_string(index=False))

print("2️⃣ Best model specific XAI algorithm per regulation-question:\n")
algorithms_all = {}
algorithms_all.update(algorithms_model_agnostic)
algorithms_all.update(algorithms_model_specific)
print(assess_xai_algorithms(algorithms_all).to_string(index=False))