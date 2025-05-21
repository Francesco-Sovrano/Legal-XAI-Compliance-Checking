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

SUBPROP_TO_CAT = {
	# Faithfulness
	'no_fp': 'Faithfulness',
	'no_fn': 'Faithfulness',
	'completeness': 'Faithfulness',
	# Robustness
	'stability': 'Robustness',
	'adversarial': 'Robustness',
	'consistency': 'Robustness',
	'sensitivity': 'Robustness',
	# Complexity
	'sparsity': 'Complexity',
	'granularity': 'Complexity',
	# Responsibility
	'fairness': 'Responsibility',
	'privacy': 'Responsibility',
	'traceability': 'Responsibility',
	# Efficiency
	'runtime': 'Efficiency',
}

CAT_WEIGHTS = {
	'Faithfulness': 1,
	'Robustness': 1,
	'Complexity': 1,
	'Responsibility': 1,
	'Efficiency': 1,
}

# -------------------------------------------------------------------
# 1.  Regulation‑level metadata
# -------------------------------------------------------------------
regulations = {
	'GDPR+AIA86+MiFID25': {
		# ---------- legal property requirements (sub‑property granularity) ----------
		'required': {
			'no_fp':1, 'no_fn':1,
			'stability':1,'adversarial':0.5,'consistency':1,
			'sparsity':1,
			'fairness':1,'privacy':0.5,'traceability':1,
			# 'runtime':0.5,
		},
		# ---------- procedure ----------
		'scope_stage': 'local-expost',
		# ---------- questions ----------
		'question_types': {'what_rule', 'how_differs', 'what_feature', 'what_if', 'how_modify_input'},
	},

	'DSA17': {
		'required': {
			'no_fp':1,'no_fn':1,'completeness':1,
			'stability':1,'adversarial':0.5,'consistency':1,
			'fairness':1,'privacy':0.5,'traceability':1,
			# 'runtime':0.5,
		},
		'scope_stage': 'local-expost',
		'question_types': {'what_rule', 'how_differs', 'what_feature', 'what_if', 'how_modify_input'},
	},

	'DSA27+P2B5': {
		'required': {
			'no_fp':1,
			'stability':1,'adversarial':0.5,'consistency':1,'sensitivity':1,
			'sparsity':1,'granularity':0.75,
			'fairness':1,'privacy':1,
			'runtime':0,
		},
		'scope_stage': 'global-exante',
		'question_types': {'what_rule', 'what_if'},
	},

	'AIA13-14': {
		'required': {
			'no_fp':0.75,'no_fn':1,'completeness':0.75,
			'stability':1,'adversarial':1,'consistency':1,'sensitivity':1,
			'fairness':1,'traceability':1,
			'runtime':0.5,
		},
		'scope_stage': 'both',  # accepts both local/ex‑post and global/ex‑ante
		'question_types': {'what_rule'},
	},

	'MDR': {
		'required': {
			'no_fp':1,'no_fn':1,'completeness':1,
			'stability':1,'adversarial':1,'consistency':1,'sensitivity':1,
			'sparsity':0.5,
			'fairness':1,'privacy':0.5,'traceability':1,
			'runtime':1,
		},
		'scope_stage': 'both',
		'question_types': {'what_rule', 'what_feature', 'what_if'},
	},

	'MiFID17': {
		'required': {
			'no_fp':1,'no_fn':1,'completeness':1,
			'stability':1,'adversarial':1,'consistency':1,'sensitivity':1,
			'fairness':1,'traceability':1,
			'runtime':0.5,
		},
		'scope_stage': 'both',
		'question_types': {'what_rule', 'what_feature', 'what_if'},
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
			'runtime':5,'no_fp':3,'no_fp':3,'consistency':3,
			'stability':2,'completeness':2, 'sparsity':1
		},
		'scope_stage': 'global-exante',
		'question_types': {'what_rule', 'how_differs', 'what_feature', 'what_if', 'how_modify_input'},
	},
	'RuleFit': {
		'subprops': {
			'no_fp':4,'no_fp':3,'consistency':4,'completeness':4,
			'stability':2,'sparsity':3,'runtime':4
		},
		'scope_stage': 'global-exante',
		'question_types': {'what_rule', 'how_differs', 'what_feature', 'what_if', 'how_modify_input'},
	},
	'Anchors': {
		'subprops': {
			'no_fp':5,'sparsity':4,'completeness':3,
			'adversarial':2,'sensitivity':2
		},
		'scope_stage': 'local-expost',
		'question_types': {'what_rule', 'what_feature', 'what_if'},
	},
	'LIME': {
		'subprops': {
			'runtime':4,'no_fp':3,
			'stability':2,'sensitivity':2,'completeness':2
		},
		'scope_stage': 'local-expost',
		'question_types': {'what_feature', 'what_if'},
	},
	'SHAP': {
		'subprops': {
			'no_fp':5,'no_fn':5,'consistency':5,
			'adversarial':3,'runtime':2,'sensitivity':2
		},
		'scope_stage': 'local-expost',
		'question_types': {'what_feature', 'what_if'},
	},
	'DiCE': {
		'subprops': {
			'no_fp':4,'runtime':4,
			'completeness':2,'stability':2,'sensitivity':2
		},
		'scope_stage': 'local-expost',
		'question_types': {'what_rule', 'what_feature', 'what_if', 'how_modify_input'},
	},
	'PDP': {
		'subprops': {
			'no_fp':4,'runtime':4,
			'completeness':2,'stability':2
		},
		'scope_stage': 'global-exante',
		'question_types': {'what_rule', 'what_feature', 'how_modify_input'},
	},
	'ICE': {
		'subprops': {
			'no_fp':4,'runtime':4,
			'completeness':1,'stability':2
		},
		'scope_stage': 'local-expost',
		'question_types': {'what_feature', 'how_modify_input'},
	},
	'CEM': {
		'subprops': {
			'no_fp':4,'no_fn':4,'completeness':4,
			'stability':2,'consistency':2
		},
		'scope_stage': 'local-expost',
		'question_types': {'what_rule', 'what_feature', 'what_if', 'how_modify_input'},
	},
	'ProtoDash': {
		'subprops': {
			'runtime':5,'sparsity':4,'no_fp':4,'no_fn':4,
			'completeness':2,'stability':2
		},
		'scope_stage': 'local-expost',
		'question_types': {'how_differs'},
	},
	
}

# --------------------------- MODEL‑SPECIFIC ---------------------------
algorithms_model_specific = {
	'CAVs': {
		'subprops': {
			'granularity':4,'no_fp':4,
			'stability':2,'completeness':2,'adversarial':2
		},
		'scope_stage': 'local-expost',
		'question_types': {'how_computed', 'what_feature'},
	},
	'TreeSHAP': {
		'subprops': {
			'no_fp':5,'no_fn':5,'completeness':5,
			'runtime':4,'adversarial':2,'stability':2
		},
		'scope_stage': 'global-exante',
		'question_types': {'what_feature', 'what_if'},
	},
	'DeepLift': {
		'subprops': {
			'no_fp':4,'runtime':4,
			'stability':2,'sensitivity':2,'completeness':2
		},
		'scope_stage': 'local-expost',
		'question_types': {'what_feature', 'what_if'},
	},
	'DeepSHAP': {
		'subprops': {
			'no_fp':4,'no_fn':4,'completeness':2,
			'consistency':4,'runtime':4,'adversarial':2
		},
		'scope_stage': 'local-expost',
		'question_types': {'what_feature', 'what_if'},
	},
	'Boolean Rules': {
		'subprops': {
			'sparsity':4,'granularity':4,'no_fp':4,'no_fn':4,
			'runtime':2,'stability':2,'completeness':2
		},
		'scope_stage': 'global-exante',
		'question_types': {'what_rule', 'how_differs', 'what_feature', 'what_if', 'how_modify_input'},
	},
	'Shapley Flow': {
		'subprops': {
			'no_fp':4,'no_fn':4,'granularity':4,'completeness':4,
			'runtime':2,'stability':2
		},
		'scope_stage': 'local-expost',
		'question_types': {'what_feature', 'what_if'},
	},
	'LRP': {
		'subprops': {
			'runtime':4,'granularity':4,
			'stability':2,'sensitivity':2,'completeness':2
		},
		'scope_stage': 'local-expost',
		'question_types': {'what_feature', 'what_if'},
	},
	'Activation Maximization': {
		'subprops': {
			'consistency':4,'granularity':4,'runtime':2,
			'stability':2,'adversarial':2
		},
		'scope_stage': 'local-expost',
		'question_types': {'how_computed'},
	},
	'Grad-CAM': {
		'subprops': {
			'runtime':5,'no_fn':3,
			'completeness':2,'adversarial':2,'stability':2
		},
		'scope_stage': 'local-expost',
		'question_types': {'what_feature', 'what_if'},
	},
	'Integrated Gradients': {
		'subprops': {
			'no_fp':4,'runtime':4,'stability':4,
			'completeness':3,'adversarial':2,'sensitivity':2
		},
		'scope_stage': 'local-expost',
		'question_types': {'what_feature', 'what_if'},
	},
	'Attention': {
		'subprops': {
			'runtime':4,'granularity':4,
			'stability':2,'no_fp':2,'no_fn':2,'completeness':1
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
		assert all(q in QUESTION_KINDS for q in reg['question_types']), f"There's an invalid question in {reg_name}"
		for algo_name, algo in algorithms.items():
			assert all(q in QUESTION_KINDS for q in algo['question_types']), f"There's an invalid question in {algo_name}"
			w_pi = compute_w_pi(algo['subprops'], req)
			avg_cov = sum(w_pi.values())/len(w_pi) if w_pi else 0.0
			fit_proc = procedure_fit(algo['scope_stage'], reg['scope_stage'])
			fit_q    = question_fit(algo['question_types'], reg['question_types'])
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
		for q in reg['question_types']:
			# candidates: rows for this regulation whose algorithm supports q
			cand = scores_df[
				(scores_df['Regulation'] == reg_name) &
				scores_df['Algorithm'].apply(lambda a: q in algorithms[a]['question_types'])
			]
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