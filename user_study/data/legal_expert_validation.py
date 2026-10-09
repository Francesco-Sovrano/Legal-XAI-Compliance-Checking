#!/usr/bin/env python3
"""Reproduce the legal-expert validation figures from public-review.sqlite3.

The expert observations are read from the SQLite database. Legal weights,
XAI-property ratings, scoring rules, the strict scope gate, and sensitivity
ranges are the fixed inputs reported in manuscript.tex.

Usage:
    python legal_expert_validation.py public-review.sqlite3 --outdir figures

Outputs (vector PDF):
    expert_alignment_gdpr.pdf
    expert_alignment_mdr.pdf
    expert_alignment_across_regulations.pdf
    expert_alignment_metrics.csv
    expert_alignment_per_expert.csv
"""
from __future__ import annotations

import argparse
import itertools
import math
import sqlite3
from pathlib import Path
import sys,json
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'methods_scoring'))
from scoring import INPUTS, ratings as canonical_ratings, weights as canonical_weights, tau_batch

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.stats import kendalltau, rankdata

plt.rcParams.update({
    "pdf.fonttype": 42,
    "ps.fonttype": 42,
    "font.size": 10,
    "axes.titlesize": 14,
    "axes.labelsize": 11,
    "xtick.labelsize": 10,
    "ytick.labelsize": 10,
})

VALID_SLOTS = ("E08", "E11", "E13", "E18")

CONDITION_TO_METHOD = {
    "credit-authority-a": "Approx. local SHAP",
    "credit-authority-b": "PDP",
    "credit-authority-c": "CEM",
    "credit-authority-d": "DiCE",
    "clinical-shap": "Global SHAP",
    "clinical-pdp": "PDP",
    "clinical-tree": "Decision Trees",
    "clinical-ruleshap": "RuleSHAP",
}

CANONICAL_METHODS = {"Approx. local SHAP":"Approximate local SHAP", "PDP":"PDP", "CEM":"CEM", "DiCE":"DiCE", "Global SHAP":"Global SHAP summaries", "Decision Trees":"Decision Trees", "RuleSHAP":"RuleSHAP"}
PROPERTY_SCORES = {alias:canonical_ratings([name])[0] for alias,name in CANONICAL_METHODS.items()}
GDPR_WEIGHTS = canonical_weights(['GDPR+AIA86+MiFID25'])[0]
MDR_WEIGHTS = canonical_weights(['MDR'])[0]
CONTEXTS = {"GDPR":{"module":"credit_authority", "methods":("Approx. local SHAP","PDP","CEM","DiCE"), "weights":GDPR_WEIGHTS, "eligibility":np.array([1,0,1,1],dtype=float)}, "MDR":{"module":"clinical_empirical", "methods":("Global SHAP","PDP","Decision Trees","RuleSHAP"), "weights":MDR_WEIGHTS, "eligibility":np.ones(4)}}

FORMULA_COLUMNS = ("Soft", "Geometric", "T=2", "T=3", "T=4")

# Method-specific line colours, symbols and dash patterns.
METHOD_STYLE = {
    "Approx. local SHAP": dict(color="tab:blue", marker="o", linestyle="-"),
    "Global SHAP": dict(color="tab:blue", marker="o", linestyle="-"),
    "PDP": dict(color="tab:orange", marker="s", linestyle="--"),
    "CEM": dict(color="tab:green", marker="^", linestyle="-."),
    "Decision Trees": dict(color="tab:green", marker="^", linestyle="-."),
    "DiCE": dict(color="tab:red", marker="D", linestyle=":"),
    "RuleSHAP": dict(color="tab:red", marker="D", linestyle=":"),
}


def load_locked_ratings(db_path: Path) -> dict[str, pd.DataFrame]:
    """Return the locked 1-7 legal-objective ratings, one record per expert."""
    con = sqlite3.connect("file:"+str(Path(db_path).resolve())+"?mode=ro",uri=True)
    placeholders = ",".join("?" for _ in VALID_SLOTS)
    results: dict[str, pd.DataFrame] = {}
    try:
        for context, spec in CONTEXTS.items():
            query = f"""
                SELECT s.panel_slot, s.stage, a.condition_id,
                       tr.enables_legal_objective
                FROM sessions s
                JOIN assignments a ON a.session_id = s.id
                JOIN trial_responses tr
                  ON tr.session_id = s.id
                 AND tr.module_id = a.module_id
                 AND tr.trial_index = a.trial_index
                WHERE s.panel_slot IN ({placeholders})
                  AND a.module_id = ?
            """
            frame = pd.read_sql_query(query, con, params=[*VALID_SLOTS, spec["module"]])
            if set(frame["panel_slot"]) != set(VALID_SLOTS):
                missing = sorted(set(VALID_SLOTS) - set(frame["panel_slot"]))
                raise RuntimeError(f"Missing valid participant slots in {context}: {missing}")
            if not (frame["stage"] == "complete").all():
                raise RuntimeError(f"A valid participant is not complete in {context}")
            frame["method"] = frame["condition_id"].map(CONDITION_TO_METHOD)
            if frame["method"].isna().any():
                bad = frame.loc[frame["method"].isna(), "condition_id"].unique().tolist()
                raise RuntimeError(f"Unknown condition IDs: {bad}")
            wide = frame.pivot(index="panel_slot", columns="method", values="enables_legal_objective")
            results[context] = wide.reindex(index=VALID_SLOTS, columns=spec["methods"])
            if results[context].isna().any().any():raise RuntimeError("Incomplete primary judgments")
    finally:
        con.close()
    return results


def score_views(methods: tuple[str, ...], weights: np.ndarray, eligibility: np.ndarray) -> pd.DataFrame:
    active = weights > 0
    den = weights[active].sum()
    observations = []
    for method, gate in zip(methods, eligibility):
        x = PROPERTY_SCORES[method][active]
        w = weights[active]
        soft = float(np.sum(w * (x / 5.0)) / den)
        geo = float(math.exp(np.sum(w * np.log(x / 5.0)) / den))
        t2 = float(np.sum(w * (x >= 2)) / den)
        t3 = float(np.sum(w * (x >= 3)) / den)
        t4 = float(np.sum(w * (x >= 4)) / den)
        observations.append(np.array([soft, geo, t2, t3, t4]) * gate)
    return pd.DataFrame(observations, index=methods, columns=FORMULA_COLUMNS)


def rank_frame(scores: pd.DataFrame, locked: pd.DataFrame) -> pd.DataFrame:
    """Formula ranks plus the rank induced by median locked expert ratings."""
    medians = locked.median(axis=0).reindex(scores.index)
    out = pd.DataFrame(index=scores.index)
    for column in FORMULA_COLUMNS:
        out[column] = rankdata(-scores[column].to_numpy(), method="average")
    out["EXPERTS"] = rankdata(-medians.to_numpy(), method="average")
    return out


def per_expert_taus(scores: pd.DataFrame, locked: pd.DataFrame) -> pd.DataFrame:
    observations = []
    for slot in VALID_SLOTS:
        ratings = locked.loc[slot].reindex(scores.index).to_numpy()
        row = {"participant": slot}
        for formula in FORMULA_COLUMNS:
            row[formula] = float(kendalltau(scores[formula].to_numpy(), ratings).statistic)
        observations.append(row)
    return pd.DataFrame(observations).set_index("participant")


def null_taus(formula,locked):
    perms=list(itertools.permutations(range(4)))
    return [np.array([kendalltau(formula, locked.loc[slot].to_numpy()[list(p)]).statistic for p in perms]) for slot in VALID_SLOTS]

def exact_tail(distributions,observed):
    # Count repeated tied outcomes through their probability masses.
    distributions=[np.unique(np.round(x,12),return_counts=True) for x in distributions]
    total=0.0
    third,fourth=np.meshgrid(distributions[2][0],distributions[3][0],indexing='ij')
    tail_weights=distributions[2][1][:,None]*distributions[3][1][None,:]
    denominator=np.prod([counts.sum() for _,counts in distributions],dtype=float)
    for a,ca in zip(*distributions[0]):
        for b,cb in zip(*distributions[1]):
            values=np.stack([np.full_like(third,a),np.full_like(third,b),third,fourth],axis=-1)
            total+=float(ca)*float(cb)*np.sum(tail_weights*(np.median(values,axis=-1)>=observed-1e-10))
    return float(total/denominator)

def exact_context_permutation_p(formula,locked):
    observed=np.median([kendalltau(formula,locked.loc[slot].to_numpy()).statistic for slot in VALID_SLOTS])
    return exact_tail(null_taus(formula,locked),observed)

def exact_pooled_permutation_p(formula_gdpr,locked_gdpr,formula_mdr,locked_mdr):
    # Method sets differ between contexts: shuffle their labels independently.
    left=null_taus(formula_gdpr,locked_gdpr);right=null_taus(formula_mdr,locked_mdr)
    joint=[((a[:,None]+b[None,:])/2).ravel() for a,b in zip(left,right)]
    observed=np.median([(kendalltau(formula_gdpr,locked_gdpr.loc[slot]).statistic+kendalltau(formula_mdr,locked_mdr.loc[slot]).statistic)/2 for slot in VALID_SLOTS])
    return exact_tail(joint,observed)

def bh_fdr(pvalues: list[float]) -> np.ndarray:
    """Benjamini-Hochberg adjusted p-values."""
    p = np.asarray(pvalues, dtype=float)
    order = np.argsort(p)
    ranked = p[order]
    n = len(p)
    q_ranked = ranked * n / np.arange(1, n + 1)
    q_ranked = np.minimum.accumulate(q_ranked[::-1])[::-1]
    q_ranked = np.clip(q_ranked, 0, 1)
    q = np.empty_like(q_ranked)
    q[order] = q_ranked
    return q


def plot_rank_trajectory(ranks: pd.DataFrame, title: str, path: Path) -> None:
    labels = list(FORMULA_COLUMNS) + ["EXPERTS"]
    x = np.arange(len(labels))
    fig, ax = plt.subplots(figsize=(9.2, 4.7))

    for method, row in ranks.iterrows():
        style = METHOD_STYLE[method]
        ax.plot(
            x, row[labels].to_numpy(),
            linewidth=1.8, markersize=5.5,
            color=style["color"], marker=style["marker"], linestyle=style["linestyle"],
        )

    # Direct labels at the expert end; offset tied labels slightly for readability.
    tied = ranks["EXPERTS"].duplicated(keep=False)
    seen: dict[float, int] = {}
    for method, row in ranks.iterrows():
        y = float(row["EXPERTS"])
        offset = 0.0
        if tied.loc[method]:
            k = seen.get(y, 0)
            offset = (-0.10 if k == 0 else 0.10)
            seen[y] = k + 1
        ax.text(
            x[-1] + 0.20, y + offset, method,
            color=METHOD_STYLE[method]["color"], fontsize=9, va="center", ha="left",
        )

    divider = len(labels) - 1.5
    ax.axvline(divider, linestyle="--", linewidth=1, color="tab:blue", alpha=0.8)
    ax.text(
        0.99, 0.02, "Dashed line separates formulas from expert ranking",
        transform=ax.transAxes, ha="right", va="bottom", fontsize=7.5,
    )
    ax.set_xticks(x, labels)
    ax.set_yticks([1, 2, 3, 4])
    ax.set_ylim(4.35, 0.65)
    ax.set_xlim(-0.1, x[-1] + 0.85)
    ax.set_ylabel("Rank (1 = best)")
    ax.set_title(title)
    ax.grid(axis="y", alpha=0.22)
    fig.tight_layout()
    fig.savefig(path, bbox_inches="tight")
    plt.close(fig)


def plot_aggregate(
    fixed_individual: dict[str, pd.DataFrame],
    sensitivity: dict[str, np.ndarray],
    pvals_t4: dict[str, float],
    qvals_t4: dict[str, float],
    path: Path,
) -> pd.DataFrame:
    labels = list(FORMULA_COLUMNS) + ["Sensitivity median"]
    x = np.arange(len(labels))
    width = 0.24
    contexts = ("GDPR", "MDR", "Across both")
    colors = {"GDPR": "tab:blue", "MDR": "tab:orange", "Across both": "tab:green"}
    offsets = {"GDPR": -width, "MDR": 0.0, "Across both": width}

    # Per-expert values for fixed formula views.
    pooled = (fixed_individual["GDPR"] + fixed_individual["MDR"]) / 2.0
    per_expert = {"GDPR": fixed_individual["GDPR"], "MDR": fixed_individual["MDR"], "Across both": pooled}

    # For each expert, take the median concordance across draws; then take
    # the median across experts. Paired concordance averages the two contexts
    # within each expert and draw before these medians.
    sens_values = {
        "GDPR": float(np.median(np.nanmedian(sensitivity["GDPR"],axis=0))),
        "MDR": float(np.median(np.nanmedian(sensitivity["MDR"],axis=0))),
        "Across both": float(np.median(np.nanmedian((sensitivity["GDPR"] + sensitivity["MDR"]) / 2.0,axis=0))),
    }

    observations = []
    for context in contexts:
        vals = [float(np.nanmedian(per_expert[context][f])) for f in FORMULA_COLUMNS]
        vals.append(sens_values[context])
        observations.append([context, *vals])
    summary = pd.DataFrame(observations, columns=["Context", *labels]).set_index("Context")

    fig, ax = plt.subplots(figsize=(10.3, 5.15))
    for context in contexts:
        vals = summary.loc[context, labels].to_numpy(dtype=float)
        xpos = x + offsets[context]
        bars = ax.bar(xpos, vals, width=width, label=context, color=colors[context], alpha=0.88)

        # Expert-level concordances on fixed and sensitivity views.
        for j, formula in enumerate(FORMULA_COLUMNS):
            dots = per_expert[context][formula].to_numpy(dtype=float)
            ax.scatter(
                np.full(len(dots), xpos[j]), dots,
                s=18, color=colors[context], edgecolor="black", linewidth=0.35, zorder=4,
            )

        if context == "Across both":
            sens_dots=np.nanmedian((sensitivity["GDPR"]+sensitivity["MDR"])/2,axis=0)
        else:
            sens_dots=np.nanmedian(sensitivity[context],axis=0)
        ax.scatter(np.full(4,xpos[-1]),sens_dots,s=18,color=colors[context],edgecolor="black",linewidth=.35,zorder=4)
        # Numeric bar labels.
        for bar, val in zip(bars, vals):
            ax.text(
                bar.get_x() + bar.get_width() / 2,
                val + (0.035 if val >= 0 else -0.06),
                f"{val:.2f}", ha="center",
                va="bottom" if val >= 0 else "top", fontsize=8,
            )

    # Formal T=4 test annotations only.
    t4_idx = labels.index("T=4")
    # Fixed annotation heights keep the p/q labels clear of the four expert dots.
    annotation_y = {"GDPR": 0.57, "MDR": 0.99, "Across both": 0.60}
    for context in contexts:
        xpos = x[t4_idx] + offsets[context]
        y = annotation_y[context]
        ax.text(
            xpos, y,
            f"p={pvals_t4[context]:.3f}\nq={qvals_t4[context]:.3f}",
            ha="center", va="bottom", fontsize=7.5,
        )

    ax.axhline(0, color="black", linewidth=0.8)
    ax.set_xticks(x, labels)
    ax.set_ylim(-0.80, 1.15)
    ax.set_ylabel(r"Median per-expert Kendall $\tau_b$")
    ax.set_title("Formula-expert rank alignment across the two validation contexts")
    ax.grid(axis="y", alpha=0.22)
    ax.legend(ncol=3, loc="upper left", frameon=True)
    ax.text(
        0.995, 0.025,
        "T=4 labels: exploratory exact permutation tests; q = BH-FDR across 15 comparisons\n"
        "Dots = 4 experts; sensitivity uses per-expert median concordance",
        transform=ax.transAxes, ha="right", va="bottom", fontsize=7.3,
    )
    fig.tight_layout()
    fig.savefig(path, bbox_inches="tight")
    plt.close(fig)
    return summary


def analyse(database,outdir,drawdir):
    plt.rcParams.update({
        "pdf.fonttype": 42,
        "ps.fonttype": 42,
        "font.size": 10,
        "axes.titlesize": 14,
        "axes.labelsize": 11,
        "xtick.labelsize": 10,
        "ytick.labelsize": 10,
    })
    outdir=Path(outdir);outdir.mkdir(parents=True,exist_ok=True)
    locked=load_locked_ratings(Path(database));scores={};ranks={};per_expert={};sensitivity={}
    d=np.load(Path(drawdir)/'joint_draw_scores.npz');meta=json.loads((Path(drawdir)/'sensitivity_summary.json').read_text())
    for context,spec in CONTEXTS.items():
        scores[context]=score_views(spec['methods'],spec['weights'],spec['eligibility']).round(12)
        ranks[context]=rank_frame(scores[context],locked[context]);per_expert[context]=per_expert_taus(scores[context],locked[context])
        case=INPUTS['study']['contexts'][context];indices=[meta['methods'].index(CANONICAL_METHODS[m]) for m in spec['methods']]
        perturbed=d[case['regulation']][:,indices]*spec['eligibility']
        sensitivity[context]=np.stack([tau_batch(perturbed,locked[context].loc[slot].to_numpy()) for slot in VALID_SLOTS],axis=1)
        pd.DataFrame(sensitivity[context],columns=VALID_SLOTS).to_csv(outdir/('sensitivity_concordance_'+context.lower()+'.csv'),index=False)
        scores[context].to_csv(outdir/('formula_scores_'+context.lower()+'.csv'));locked[context].to_csv(outdir/('locked_ratings_'+context.lower()+'.csv'))
    tests=[]
    for f in FORMULA_COLUMNS:
        for context in ['GDPR','MDR']:
            tests.append(dict(context=context,formula=f,p=exact_context_permutation_p(scores[context][f].to_numpy(),locked[context])))
        tests.append(dict(context='Across both',formula=f,p=exact_pooled_permutation_p(scores['GDPR'][f].to_numpy(),locked['GDPR'],scores['MDR'][f].to_numpy(),locked['MDR'])))
    for item,q in zip(tests,bh_fdr([v['p'] for v in tests])):item['q']=float(q)
    pd.DataFrame(tests).to_csv(outdir/'exploratory_permutation_tests.csv',index=False)
    pvals={v['context']:v['p'] for v in tests if v['formula']=='T=4'};qvals={v['context']:v['q'] for v in tests if v['formula']=='T=4'}
    for context in ['GDPR','MDR']:plot_rank_trajectory(ranks[context],context+': formula rankings and expert ranking',outdir/('expert_alignment_'+context.lower()+'.pdf'))
    summary=plot_aggregate(per_expert,sensitivity,pvals,qvals,outdir/'expert_alignment_across_regulations.pdf')
    pooled=(per_expert['GDPR']+per_expert['MDR'])/2
    detail=[]
    for context,frame in [('GDPR',per_expert['GDPR']),('MDR',per_expert['MDR']),('Across both',pooled)]:
        sens=np.nanmedian((sensitivity['GDPR']+sensitivity['MDR'])/2,axis=0) if context=='Across both' else np.nanmedian(sensitivity[context],axis=0)
        for j,slot in enumerate(VALID_SLOTS):detail.append(dict(context=context,participant=slot,**frame.loc[slot].to_dict(),sensitivity=float(sens[j])))
    pd.DataFrame(detail).to_csv(outdir/'expert_alignment_per_expert.csv',index=False)
    metrics=[]
    for context in ['GDPR','MDR','Across both']:
        metrics.append(dict(context=context,**{'median_tau_'+f:float(summary.loc[context,f]) for f in FORMULA_COLUMNS},sensitivity_median_tau=float(summary.loc[context,'Sensitivity median']),T4_exact_one_sided_p=pvals[context],T4_BH_FDR_q=qvals[context]))
    pd.DataFrame(metrics).to_csv(outdir/'expert_alignment_metrics.csv',index=False)
    comparison=[];con=sqlite3.connect("file:"+str(Path(database).resolve())+"?mode=ro",uri=True)
    for context,spec in CONTEXTS.items():
        for slot in VALID_SLOTS:
            entries=pd.read_sql_query('SELECT r.condition_id,r.rank_group,r.revised_enables_legal_objective FROM ranking_responses r JOIN sessions s ON s.id=r.session_id WHERE s.panel_slot=? AND r.module_id=?',con,params=[slot,spec['module']]);entries['method']=entries['condition_id'].map(CONDITION_TO_METHOD);entries=entries.set_index('method').reindex(spec['methods'])
            if entries.isna().any().any():raise ValueError('Incomplete comparison records')
            comparison.append(dict(context=context,participant=slot,**{f:float(kendalltau(scores[context][f],-entries['rank_group']).statistic) for f in FORMULA_COLUMNS},changed_legal_goal_ratings=int(np.sum(entries['revised_enables_legal_objective'].to_numpy()!=locked[context].loc[slot].to_numpy()))))
    con.close();pd.DataFrame(comparison).to_csv(outdir/'comparison_stage_concordance.csv',index=False)
    (outdir/'expert_summary.json').write_text(json.dumps(dict(metrics=metrics,comparison=comparison),indent=2));return metrics

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('database',type=Path,nargs='?',default=Path(__file__).resolve().parent/'public-review.sqlite3');parser.add_argument('--outdir',type=Path,default=Path(__file__).resolve().parent/'analysis');parser.add_argument('--drawdir',type=Path,default=Path(__file__).resolve().parents[2]/'methods_scoring/analysis');args=parser.parse_args();analyse(args.database,args.outdir,args.drawdir)
