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
	'sparsity': 'Complexity',
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
			'sparsity': 0, 'level_of_detail': 0,
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
			'sparsity': 0, 'level_of_detail': 0,
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
			'sparsity': 0, 'level_of_detail': 1,
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
			'sparsity': 0, 'level_of_detail': 0,
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
			'sparsity': 0.5, 'level_of_detail': 0,
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
			'sparsity': 0, 'level_of_detail': 0,
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
			'sparsity': 1, 'level_of_detail': 1,
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
# We assign scores \emph{by comparison}, i.e., by evaluating whether an algorithm performs better or worse than others, such that the resulting scores align with common knowledge about these algorithms. For instance, it is well-established that SHAP provides strong theoretical guarantees for faithfulness, whereas LIME tends to lag behind. Consequently, LIME's faithfulness scores should be lower than those of SHAP, and so forth. 
# As another example, decision trees are known to overfit and are therefore generally less reliable than gradient-boosting-based methods such as RuleFit, which exhibit higher faithfulness. Furthermore, decision trees struggle to capture linear dependencies, whereas RuleFit is specifically designed to handle such patterns, making it producing more complete explanations.
# We consider a score of 3 to be neutral. Other considerations include the potential for global methods to leak confidential data, and the reduction in traceability and consistency caused by non-deterministic behavior.
# Our scoring methodology begins with the use of ChatGPT o4-mini (OpenAI's most advanced reasoning model), which is provided with the guidelines mentioned above to generate initial scores for all XAI methods together. Subsequently, the authors of the paper manually revised these scores based on their expertise and the relevant literature, correcting inaccuracies and enhancing the overall quality of the scoring. The fundamental principle is that scores are assigned \emph{by comparison}, making them meaningful only within the context of the full set of algorithms. Introducing new XAI methods may necessitate rescaling, potentially including the use of decimal scores (which we avoided).
# It is crucial to note that, due to the methodology used and the inherently qualitative nature of the scoring, the resulting compliance scores should be interpreted with caution. They are not to be regarded as definitive certificates of compliance but rather as helpful indicators for selecting appropriate XAI methods to ensure legally compliant explanations.

# Keep in mind that: 3 is somehow a neutral score; global methods may leak confidential data; non-determinism reduces traceability and consistency; RuleFit is more faithful than Decision Trees; SHAP is the most faithful model in terms of positives and negatives but not in terms of completeness; Anchors is more faithful than LIME; SHAP is better than LIME.
algorithms_model_agnostic = {
	'Decision Trees': {
		'subprops': {
			'no_false_positives': 2,       # DTs can include spurious predicates due to overfitting → more false positives than SHAP (5).
			'no_false_negatives': 3,       # DTs may ignore subtle interactions → more false negatives; same as RuleFit (3) and SHAP (5).
			'completeness': 3,        # neutral global coverage; SHAP/TreeSHAP (4) more complete
			'stability': 1,                # Small data changes can yield very different trees due to overfitting → lowest of all methods.
			'adversarial_robustness': 2,   # Vulnerable to adversarial examples (https://arxiv.org/pdf/1902.10660v2) → lower than global‐smooth methods like PDP (3).
			'consistency': 2,              # Different runs often differ → lower than surrogate linear methods (RuleFit 3).
			'hyperparameters_perturbation_robustness': 2,  # Tree depth/pruning changes shape drastically → lower than PDP/ICE (4).
			'sparsity': 3,        # Typical pruned trees are readable but can still be large.
			'level_of_detail': 5,          # Very fine‐grained (per‐leaf) → highest detail.
			'fairness': 3,                 # Neutral (inherits model biases) → same as most global XAI.
			'confidentiality': 2,          # Full structure leaks splits/data distribution → worse than local methods (3).
			'traceability': 4,             # Deterministic training allows audit → better than non‐deterministic LIME (1).
			'runtime_performance_and_implementation_constraints': 4,  # Fast inference, easy to implement → better than sampling methods like SHAP (1).
		},
		'scope_stage': 'global-exante',
		'question_types': {'what_rule', 'what_feature', 'what_if', 'how_modify_input', 'how_computed'},
	},
	'RuleFit': {
		'subprops': {
			'no_false_positives': 3,       # More faithful than DT (2) but still surrogate → moderate, lower than SHAP (5).
			'no_false_negatives': 3,       # Worse at capturing real influences than SHAP (5). Same as DT (3).
			'completeness': 4,          # blends linear terms and rules to better cover model behavior → better than DT (3).
			'stability': 3,                # LASSO regularization dampens variance → more stable than DT (1); PDP (4) is better though.
			'adversarial_robustness': 3,   # Moderate robustness → above DT (2) due to gradient boosting being less prone to overfitting.
			'consistency': 3,              # LASSO regularization yields some consistency → above DT (2).
			'hyperparameters_perturbation_robustness': 3,  # Regularization helps → above DT (2).
			'sparsity': 2,        # LASSO regularization enforces sparsity but still worse than DT (3) due to gradient boosting generating hundreds of decision trees.
			'level_of_detail': 4,          # Rule+coef detail → less granular than DT (5).
			'fairness': 3,                 # Neutral → same as DT.
			'confidentiality': 2,          # Leaks rule logic → same as DT.
			'traceability': 4,             # Linear+rule pipeline is transparent → close to DT (4).
			'runtime_performance_and_implementation_constraints': 3,  # More expensive to fit than DT but lighter than SHAP.
		},
		'scope_stage': 'global-exante',
		'question_types': {'what_rule', 'what_feature', 'what_if', 'how_modify_input', 'how_computed'},
	},
	'RuleSHAP': {
		'subprops': {
			'no_false_positives': 4,       # More faithful than RuleFit due to SHAP-driven rule generation, lower than SHAP (5).
			'no_false_negatives': 4,       # More faithful than RuleFit due to SHAP-driven rule generation but less than SHAP (5).
			'completeness': 4,          # Same as RuleFit (4)
			'stability': 3,                # Regularization dampens variance → more stable than DT (1), same as RuleFit (3).
			'adversarial_robustness': 3,   # Same as RuleFit (3) although SHAP-driven rule extraction and SHAP-driven LASSO regression might help increasing robustness.
			'consistency': 3,              # L1 smoothing yields consistency → above DT (2).
			'hyperparameters_perturbation_robustness': 3,  # Regularization helps → above DT (2).
			'sparsity': 3,        # L1 penalty enforces sparsity → similar to DT thanks to SHAP-driven LASSO regression (4) and better than RuleFit (3).
			'level_of_detail': 4,          # Rule+coef detail → less granular than DT (5), same as RuleFit (4).
			'fairness': 3,                 # Neutral → same as RuleFit.
			'confidentiality': 2,          # Leaks rule logic → same as RuleFit.
			'traceability': 3,             # Linear+rule pipeline is transparent. However SHAP approximations add some extra non-determinism → less than RuleFit (4).
			'runtime_performance_and_implementation_constraints': 2,  # More expensive to fit than RuleFit but lighter than SHAP since approximations are used.
		},
		'scope_stage': 'global-exante',
		'question_types': {'what_rule', 'what_feature', 'what_if', 'how_modify_input', 'how_computed'},
	},
	'Anchors': {
		'subprops': {
			'no_false_positives': 3,       # Better precision than LIME (2) but not perfect like SHAP (5).
			'no_false_negatives': 3,       # Higher recall than LIME (2), lower than SHAP (5).
			'completeness': 3,          # what-if explanation that doesn't cover full (local) decision region
			'stability': 2,                # Sampling yields moderate stability → better than LIME (1), worse than PDP (4).
			'adversarial_robustness': 2,   # Can still be fooled by adversarial points → same as SHAP (3) which is stronger.
			'consistency': 2,              # Varies per seed → better than LIME (1).
			'hyperparameters_perturbation_robustness': 2,  # Anchor selection can change → slightly above LIME (1).
			'sparsity': 5,        # Very compact anchors → best among all.
			'level_of_detail': 3,          # Rules at feature‐value granularity → neutral detail.
			'fairness': 3,                 # Neutral → same as LIME.
			'confidentiality': 3,          # Local what-if explanations don't leak global logic → better than DT (2).
			'traceability': 3,             # Procedure is clear but non-deterministic sampling adds opacity → above LIME (1).
			'runtime_performance_and_implementation_constraints': 2,  # Sampling is costly → worse than LIME (3).
		},
		'scope_stage': 'local-expost',
		'question_types': {'what_rule', 'what_feature', 'what_if'},
	},
	'LIME': {
		'subprops': {
			'no_false_positives': 2,       # Tends to highlight irrelevant features → lower than Anchors (3).
			'no_false_negatives': 2,       # Omits some real effects → same.
			'completeness': 2,          # local linear fit only partial view
			'stability': 1,                # Extremely sensitive to samples → worst.
			'adversarial_robustness': 1,   # Easily manipulated → worst.
			'consistency': 1,              # Varies run to run → lowest.
			'hyperparameters_perturbation_robustness': 1,  # Kernel width / sample count drastically shift outcome → worst.
			'sparsity': 3,        # User‐set feature count → neutral.
			'level_of_detail': 3,          # Feature‐level weights → neutral.
			'fairness': 3,                 # Neutral → same as other locals.
			'confidentiality': 3,          # Local explanations don't leak global logic → better than DT (2).
			'traceability': 1,             # Random seeds obscure path → worst.
			'runtime_performance_and_implementation_constraints': 3,  # Moderate sampling cost.
		},
		'scope_stage': 'local-expost',
		'question_types': {'what_feature', 'what_if', 'how_computed'},
	},
	'SHAP': {
		'subprops': {
			'no_false_positives': 5,       # Theoretically only truly contributive features → highest.
			'no_false_negatives': 5,       # Captures all positive/negative contributions → highest.
			'completeness': 3,        # positive & negative faithful but not full rationale; moderate
			'stability': 4,                # Exact SHAP values are very stable and deterministic, but approximations are non-deterministic; still sampling noise.
			'adversarial_robustness': 3,   # Some robustness via axioms but can be manipulated in practice → moderate.
			'consistency': 5,              # Satisfies consistency axiom; approximations are non-deterministic → above LIME/Anchors.
			'hyperparameters_perturbation_robustness': 3,  # Background choices matter → better than LIME (1) and Anchors (2).
			'sparsity': 3,        # Same as LIME (3).
			'level_of_detail': 4,          # It can provide interaction effects when exact SHAP values are computed, but not when approximations are used → slightly better than LIME (3)
			'fairness': 3,                 # Neutral → same as other locals.
			'confidentiality': 3,          # Local explanations don't leak global logic → better than DT (2).
			'traceability': 5,             # Well‐defined axioms, deterministic → very high.
			'runtime_performance_and_implementation_constraints': 1,  # Very expensive for many features.
		},
		'scope_stage': 'local-expost',
		'question_types': {'what_feature', 'what_if', 'how_computed'},
	},
	'DiCE': {
		'subprops': {
			'no_false_positives': 3,       # Counterfactuals only include needed changes → neutral.
			'no_false_negatives': 3,       # Might miss some feasible paths → neutral.
			'completeness': 3,          # focuses only on one or few counterfactuals
			'stability': 1,                # Different runs yield different examples → lowest.
			'adversarial_robustness': 1,   # Can be circumvented by adversarial tweaks → lowest.
			'consistency': 1,              # High variance across seeds → lowest.
			'hyperparameters_perturbation_robustness': 1,  # Solver settings sway results → lowest.
			'sparsity': 4,        # Tend to optimize for minimal changes → high sparsity.
			'level_of_detail': 3,          # Shows feature deltas only → medium detail.
			'fairness': 3,                 # Neutral → same as other locals.
			'confidentiality': 3,          # Local only → neutral.
			'traceability': 2,             # Solver complexity obscures path → lower than SHAP (4).
			'runtime_performance_and_implementation_constraints': 3,  # NP‐hard solver with heuristics.
		},
		'scope_stage': 'local-expost',
		'question_types': {'what_rule', 'what_feature', 'what_if', 'how_modify_input'},
	},
	'PDP': {
		'subprops': {
			'no_false_positives': 3,       # Averages out irrelevant effects → neutral.
			'no_false_negatives': 3,       # Some partial effects may be hidden → neutral.
			'completeness': 3,          # shows average effect, misses heterogeneity
			'stability': 4,                # Smooth curves → high stability.
			'adversarial_robustness': 3,   # Aggregation resists single‐point attacks → moderate.
			'consistency': 4,              # Consistent across runs → high.
			'hyperparameters_perturbation_robustness': 4,  # Few hyperparameters → stable.
			'sparsity': 2,        # Presents every feature as curve → low sparsity.
			'level_of_detail': 5,          # Full feature effect curves → high detail.
			'fairness': 3,                 # Neutral → same as other globals.
			'confidentiality': 3,          # Global summary only → neutral.
			'traceability': 4,             # Straightforward averaging → high.
			'runtime_performance_and_implementation_constraints': 3,  # Moderate sampling cost.
		},
		'scope_stage': 'global-exante',
		'question_types': {'what_rule', 'what_feature', 'how_modify_input'},
	},
	'ICE': {
		'subprops': {
			'no_false_positives': 3,       # Same rationale as PDP but per instance → neutral.
			'no_false_negatives': 3,       # Same as PDP → neutral.
			'completeness': 3,          # single‐instance view only
			'stability': 3,                # Some noise from sampling → average.
			'adversarial_robustness': 3,   # As PDP → average.
			'consistency': 3,              # Runs vary slightly → average.
			'hyperparameters_perturbation_robustness': 3,  # Similar to PDP.
			'sparsity': 2,        # Full curve for each feature → low sparsity.
			'level_of_detail': 5,          # Highest granularity per instance.
			'fairness': 3,                 # Neutral → same as PDP.
			'confidentiality': 3,          # Local only → neutral.
			'traceability': 4,             # Simple averaging → high.
			'runtime_performance_and_implementation_constraints': 3,  # As PDP.
		},
		'scope_stage': 'global-exante',
		'question_types': {'what_feature', 'how_modify_input'},
	},
	'CEM': {
		'subprops': {
			'no_false_positives': 3,       # Counterfactual features truly required → neutral.
			'no_false_negatives': 3,       # May miss alternative causal features → neutral.
			'completeness': 2,          # focuses on minimal perturbation, not full rationale
			'stability': 1,                # Highly stochastic solver → worst.
			'adversarial_robustness': 1,   # Can be gamed → worst.
			'consistency': 1,              # Varies per seed → worst.
			'hyperparameters_perturbation_robustness': 1,  # Solver heavily dependent on settings → worst.
			'sparsity': 4,        # Optimizes minimal changes → high.
			'level_of_detail': 3,          # Only changes shown → medium.
			'fairness': 3,                 # Neutral → same.
			'confidentiality': 3,          # Local only → neutral.
			'traceability': 2,             # Complex optimization path → low.
			'runtime_performance_and_implementation_constraints': 2,  # Expensive search.
		},
		'scope_stage': 'local-expost',
		'question_types': {'what_rule', 'what_feature', 'what_if', 'how_modify_input'},
	},
	'ProtoDash': {
		'subprops': {
			'no_false_positives': 3,       # Prototypes representative but not guaranteed → neutral.
			'no_false_negatives': 3,       # May omit some modes → neutral.
			'completeness': 2,          # selects subset only
			'stability': 3,                # Algorithmic convergence ensures moderate stability.
			'adversarial_robustness': 3,   # Prototype set can be attacked → average.
			'consistency': 3,              # Same seeds yield same prototypes → moderate.
			'hyperparameters_perturbation_robustness': 3,  # Kernel parameters matter → average.
			'sparsity': 4,        # Selects few prototypes → high sparsity.
			'level_of_detail': 3,          # Shows representative points only → medium detail.
			'fairness': 3,                 # Neutral → same.
			'confidentiality': 2,          # Exposes actual data points → lower than local proxies.
			'traceability': 4,             # Simple algorithmic steps → high.
			'runtime_performance_and_implementation_constraints': 2,  # Quadratic kernel cost.
		},
		'scope_stage': 'local-expost',
		'question_types': {'how_differs'},
	},
}

# --------------------------- MODEL‑SPECIFIC ---------------------------
algorithms_model_specific = {
	'CAVs': {
		'subprops': {
			'no_false_positives': 3,       # Concept vectors capture some true factors → neutral.
			'no_false_negatives': 3,       # May miss latent factors → neutral.
			'completeness': 2,          # only concept axes, not full model
			'stability': 2,                # Depends on network activations → below average.
			'adversarial_robustness': 2,   # Can be fooled by adversarial examples → low.
			'consistency': 2,              # Concept drift across runs → low.
			'hyperparameters_perturbation_robustness': 2,  # Layer choice matters → low.
			'sparsity': 3,        # One vector per concept → neutral.
			'level_of_detail': 3,          # Concept-level granularity → medium.
			'fairness': 3,                 # Neutral → same.
			'confidentiality': 3,          # Local activations only → neutral.
			'traceability': 3,             # Training of CAVs is clear → medium.
			'runtime_performance_and_implementation_constraints': 3,  # Moderate cost.
		},
		'scope_stage': 'local-expost',
		'question_types': {'how_computed', 'what_feature'},
	},
	'TreeSHAP': {
		'subprops': {
			'no_false_positives': 5,       # Exact Shapley for trees → highest.
			'no_false_negatives': 5,       # Exact coverage → highest.
			'completeness': 4,        # global sum of contributions; near-best
			'stability': 3,                # Deterministic algorithm → average.
			'adversarial_robustness': 3,   # Similar to SHAP → average.
			'consistency': 3,              # Fulfills axioms → average.
			'hyperparameters_perturbation_robustness': 3,  # Few hyperparams → average.
			'sparsity': 2,        # Full set of features → low.
			'level_of_detail': 5,          # Exact feature contributions → highest.
			'fairness': 3,                 # Neutral → same.
			'confidentiality': 3,          # Local only → neutral.
			'traceability': 4,             # Clearly defined algorithm → high.
			'runtime_performance_and_implementation_constraints': 3,  # Faster than kernel SHAP.
		},
		'scope_stage': 'global-exante',
		'question_types': {'what_feature', 'what_if', 'how_computed'},
	},
	'DeepLift': {
		'subprops': {
			'no_false_positives': 3,       # Gradient‐based attribution → neutral.
			'no_false_negatives': 3,       # Similar to IG → neutral.
			'completeness': 3,        # covers paths but not full rationale
			'stability': 2,                # Sensitive to target layer choice → below average.
			'adversarial_robustness': 2,   # Gradients can be fooled → low.
			'consistency': 2,              # Varies by reference input → low.
			'hyperparameters_perturbation_robustness': 2,  # Reference choice matters → low.
			'sparsity': 2,        # Attribution for every input → low sparsity.
			'level_of_detail': 5,          # Fine gradient per feature → high.
			'fairness': 3,                 # Neutral → same.
			'confidentiality': 3,          # Local only → neutral.
			'traceability': 3,             # Clear backprop chain → medium.
			'runtime_performance_and_implementation_constraints': 4,  # One backward pass → efficient.
		},
		'scope_stage': 'local-expost',
		'question_types': {'what_feature', 'what_if', 'how_computed'},
	},
	'DeepSHAP': {
		'subprops': {
			'no_false_positives': 4,       # Combines SHAP axioms + DeepLift → better than DeepLift.
			'no_false_negatives': 4,       # Similar improvement → above neutral.
			'completeness': 3,        # moderated by sampling; neutral
			'stability': 3,                # More stable than pure gradients → average.
			'adversarial_robustness': 3,   # Slight improvement over DeepLift → average.
			'consistency': 3,              # Inherits SHAP axioms → average.
			'hyperparameters_perturbation_robustness': 3,  # Average.
			'sparsity': 2,        # Dense attributions → low.
			'level_of_detail': 5,          # High detail.
			'fairness': 3,                 # Neutral.
			'confidentiality': 3,          # Neutral.
			'traceability': 4,             # Axiomatic + backprop → high.
			'runtime_performance_and_implementation_constraints': 3,  # More passes than DeepLift.
		},
		'scope_stage': 'local-expost',
		'question_types': {'what_feature', 'what_if', 'how_computed'},
	},
	'Shapley Flow': {
		'subprops': {
			'no_false_positives': 5,       # Exact Shapley propagated through graph → highest.
			'no_false_negatives': 5,       # Captures all contributive paths → highest.
			'completeness': 4,        # near TreeSHAP coverage
			'stability': 3,                # Deterministic propagation → average.
			'adversarial_robustness': 3,   # Similar to SHAP → average.
			'consistency': 3,              # Axiomatic → average.
			'hyperparameters_perturbation_robustness': 3,  # Depends on edge weights only → average.
			'sparsity': 2,        # Many edges → low sparsity.
			'level_of_detail': 5,          # Very fine‐grained along network → highest.
			'fairness': 3,                 # Neutral.
			'confidentiality': 3,          # Neutral.
			'traceability': 4,             # Clear flow paths → high.
			'runtime_performance_and_implementation_constraints': 2,  # Heavy graph propagation.
		},
		'scope_stage': 'local-expost',
		'question_types': {'what_feature', 'what_if', 'how_computed'},
	},
	'LRP': {
		'subprops': {
			'no_false_positives': 3,       # Similar to gradient methods → neutral.
			'no_false_negatives': 3,       # Neutral.
			'completeness': 3,        # covers relevance but not full model
			'stability': 2,                # Sensitive to layer selection → low.
			'adversarial_robustness': 1,   # Extremely vulnerable→ lowest.
			'consistency': 2,              # Varies by relevance rule → low.
			'hyperparameters_perturbation_robustness': 2,  # Rule variants shift results → low.
			'sparsity': 2,        # Dense maps → low.
			'level_of_detail': 5,          # Pixel‐level attribution → highest.
			'fairness': 3,                 # Neutral.
			'confidentiality': 3,          # Neutral.
			'traceability': 3,             # Clear backprop path → medium.
			'runtime_performance_and_implementation_constraints': 4,  # One backward pass → efficient.
		},
		'scope_stage': 'local-expost',
		'question_types': {'what_feature', 'what_if'},
	},
	'Activation Maximization': {
		'subprops': {
			'no_false_positives': 3,       # Maximizes particular neurons → neutral.
			'no_false_negatives': 3,       # Neutral.
			'completeness': 1,        # only maximized neuron; minimal
			'stability': 1,                # Highly sensitive to init and optimizer → lowest.
			'adversarial_robustness': 1,   # Easily produces adversarial‐style patterns → lowest.
			'consistency': 2,              # Varies with random seed → low.
			'hyperparameters_perturbation_robustness': 2,  # Regularization critical → low.
			'sparsity': 1,        # Generates dense patterns → lowest.
			'level_of_detail': 5,          # Pixel‐level → highest.
			'fairness': 3,                 # Neutral.
			'confidentiality': 3,          # Neutral.
			'traceability': 2,             # Optimization opaque → low.
			'runtime_performance_and_implementation_constraints': 2,  # Expensive iterative optimization.
		},
		'scope_stage': 'local-expost',
		'question_types': {'how_computed'},
	},
	'Grad-CAM': {
		'subprops': {
			'no_false_positives': 3,       # Highlights regions moderately → neutral.
			'no_false_negatives': 3,       # Neutral.
			'completeness': 3,        # only top activations; low
			'stability': 2,                # Sensitive to layer choice → low.
			'adversarial_robustness': 2,   # Heatmaps can be misled → low.
			'consistency': 2,              # Varies per layer and run → low.
			'hyperparameters_perturbation_robustness': 2,  # Depends on smoothing → low.
			'sparsity': 3,        # Coarse blobs → neutral.
			'level_of_detail': 4,          # Spatial maps → high spatial detail.
			'fairness': 3,                 # Neutral.
			'confidentiality': 3,          # Neutral.
			'traceability': 3,             # Backprop‐based but coarse → medium.
			'runtime_performance_and_implementation_constraints': 4,  # Single forward+backward → efficient.
		},
		'scope_stage': 'local-expost',
		'question_types': {'what_feature', 'what_if', 'how_computed'},
	},
	'Integrated Gradients': {
		'subprops': {
			'no_false_positives': 3,       # Axiomatic but baseline‐dependent → neutral.
			'no_false_negatives': 3,       # Neutral.
			'completeness': 3,        # satisfies completeness axiom but partial rationale
			'stability': 2,                # Sensitive to path/baseline → low.
			'adversarial_robustness': 2,   # Can be manipulated → low.
			'consistency': 2,              # Baseline choice yields variance → low.
			'hyperparameters_perturbation_robustness': 2,  # Step count matters → low.
			'sparsity': 2,        # Attribution for every feature → low.
			'level_of_detail': 5,          # Fine per‐feature detail → highest.
			'fairness': 3,                 # Neutral.
			'confidentiality': 3,          # Neutral.
			'traceability': 3,             # Clear integral path → medium.
			'runtime_performance_and_implementation_constraints': 3,  # Multiple gradients → moderate cost.
		},
		'scope_stage': 'local-expost',
		'question_types': {'what_feature', 'what_if', 'how_computed'},
	},
	'Attention': {
		'subprops': {
			'no_false_positives': 3,       # Debate exists, so neutral.
			'no_false_negatives': 3,       # Neutral.
			'completeness': 2,        # only attended parts; minimal
			'stability': 2,                # Sensitive to training variations → low.
			'adversarial_robustness': 1,   # Easily manipulated → lowest.
			'consistency': 2,              # Layer/head differences → low.
			'hyperparameters_perturbation_robustness': 2,  # Head count matters → low.
			'sparsity': 2,        # Dense weight matrices → low.
			'level_of_detail': 5,          # Token‐level → highest.
			'fairness': 3,                 # Neutral.
			'confidentiality': 3,          # Neutral.
			'traceability': 2,             # Hard to attribute through multiple heads → low.
			'runtime_performance_and_implementation_constraints': 4,  # Already computed in model → efficient.
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