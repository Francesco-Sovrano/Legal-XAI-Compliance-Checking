"""Reproduce question-specific scores, winning probabilities and retention."""
from pathlib import Path
import sys,json,argparse
sys.path.insert(0,str(Path(__file__).resolve().parent))
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from scoring import INPUTS,ratings,weights,questions,eligible,score_views,winners,joint_draws

ALIASES={'Decision Trees':'Decision Trees','LLM-assisted behavioral RuleSHAP (MechaRule stage 1)':'MechaRule stage 1','Global SHAP summaries':'Global SHAP','Approximate local SHAP':'Approximate local SHAP','Exact local SHAP':'Exact local SHAP','DeepLift':'DeepLIFT'}
DISPLAY=['AIA11','AIA13-14','DSA17','DSA27+P2B5','GDPR+AIA86+MiFID25','MDR','MiFID17']
LABELS=['AIA 11\n+ Annex IV','AIA\n13-14','DSA 17','DSA 27\n+ P2B 5','GDPR + AIA 86\n+ MiFID 25','MDR','MiFID 17']

def analyse(out,draws=10000,seed=20261005):
    out=Path(out);out.mkdir(parents=True,exist_ok=True)
    names=[n for n,p in INPUTS['methods'].items() if not p.get('requires_model_replacement') and not p.get('component_only')]
    regs=list(INPUTS['regulations']);x=ratings(names);w=weights(regs);scores=joint_draws(names,regs,draws,seed)
    probability=np.full((len(names),len(regs)),np.nan);count=np.zeros_like(probability,dtype=int);stars=np.zeros_like(probability,dtype=bool)
    entries=[];retention=[];fixed=[]
    for j,r in enumerate(regs):
        v=score_views(x,w[j]);prob=[[] for n in names];rets={'all':[],'agnostic':[]}
        for q in questions(r):
            full=np.array([i for i,n in enumerate(names) if eligible(n,r,q)])
            if not len(full):continue
            win=winners(scores[r][:,full]);base=winners(v['soft'][full]);stars[full[base],j]=True
            for k,i in enumerate(full):prob[i].append(float(win[:,k].mean()));count[i,j]+=1
            for group in ['all','agnostic']:
                ix=full if group=='all' else np.array([i for i in full if INPUTS['methods'][names[i]].get('type')=='model-agnostic' or i<14])
                # Catalogue order stores the fourteen model-agnostic profiles first.
                if not len(ix):continue
                sw=winners(v['soft'][ix]);tw=winners(v['threshold'][ix]);dw=winners(scores[r][:,ix])
                keep=float(np.any(dw[:,sw],axis=1).mean());rets[group].append(keep)
                entries.append(dict(catalogue=group,regulation=r,question=q,soft_winners='; '.join(names[i] for i in ix[sw]),soft_score=float(v['soft'][ix][sw][0]),threshold_winners='; '.join(names[i] for i in ix[tw]),threshold_score=float(v['threshold'][ix][tw][0]),retention=keep))
        for i,p in enumerate(prob):
            if p:probability[i,j]=np.mean(p)
        for group,vv in rets.items():retention.append(dict(catalogue=group,regulation=r,mean=float(np.mean(vv)),minimum=float(np.min(vv)),maximum=float(np.max(vv))))
        for i,n in enumerate(names):fixed.append(dict(regulation=r,method=n,**{k:float(vv[i]) for k,vv in v.items()}))
    pd.DataFrame(entries).to_csv(out/'question_scores.csv',index=False);pd.DataFrame(retention).to_csv(out/'winner_retention.csv',index=False);pd.DataFrame(fixed).to_csv(out/'method_scores.csv',index=False)
    pd.DataFrame(probability,index=names,columns=regs).to_csv(out/'winning_probabilities.csv');pd.DataFrame(count,index=names,columns=regs).to_csv(out/'eligibility_counts.csv')
    np.savez_compressed(out/'joint_draw_scores.npz',**scores)
    plot_heatmap(names,regs,probability,count,stars,out/'sensitivity_stability.pdf')
    result=dict(seed=seed,draws=draws,methods=names,regulations=regs,retention=retention)
    (out/'sensitivity_summary.json').write_text(json.dumps(result,indent=2));return result

def plot_heatmap(names,regs,p,count,stars,path):
    plt.rcParams.update({'font.family':'DejaVu Sans','pdf.fonttype':42,'font.size':8})
    global_order=['Decision Trees','RuleFit','RuleSHAP','MechaRule','LLM-assisted behavioral RuleSHAP (MechaRule stage 1)','PDP','ICE','Global SHAP summaries']
    groups=[global_order,[n for n in names if n not in global_order]]
    fig,axes=plt.subplots(2,1,figsize=(8.4,11.1),gridspec_kw={'height_ratios':[len(g) for g in groups]},layout='constrained')
    cmap=plt.colormaps['Blues'].copy();cmap.set_bad('#e8e8e8');cols=[regs.index(r) for r in DISPLAY]
    for ax,group,title in zip(axes,groups,['Global / system-level methods','Local / decision-level methods']):
        ii=[names.index(n) for n in group];data=p[np.ix_(ii,cols)];im=ax.imshow(np.ma.masked_invalid(data),vmin=0,vmax=1,cmap=cmap,aspect='auto')
        ax.set_xticks(range(7),LABELS,fontsize=7);ax.set_yticks(range(len(group)),[ALIASES.get(n,n) for n in group],fontsize=7);ax.set_title(title,loc='left',fontsize=10)
        ax.set_xticks(np.arange(-.5,7,1),minor=True);ax.set_yticks(np.arange(-.5,len(group),1),minor=True);ax.grid(which='minor',color='white',linewidth=.8);ax.tick_params(which='both',length=0)
        for k,i in enumerate(ii):
            for a,j in enumerate(cols):
                if not np.isfinite(p[i,j]):continue
                ax.text(a,k,f'{p[i,j]:.2f}'+('*' if stars[i,j] else '')+f'\n[{count[i,j]}]',ha='center',va='center',fontsize=6.5,color='white' if p[i,j]>.6 else '#17364d')
    cb=fig.colorbar(im,ax=axes,shrink=.48,pad=.015);cb.set_label('Mean probability of top rank under perturbation')
    fig.suptitle('Ranking sensitivity by method and article bundle',fontsize=12)
    fig.supxlabel('* baseline soft-score winner for at least one question; [n] = eligible question cells; grey = ineligible',fontsize=7)
    fig.savefig(path);plt.close(fig)

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--outdir',type=Path,default=Path(__file__).resolve().parent/'analysis');parser.add_argument('--draws',type=int,default=10000);parser.add_argument('--seed',type=int,default=20261005);a=parser.parse_args();analyse(a.outdir,a.draws,a.seed)
