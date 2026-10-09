"""Question-specific sensitivity figure from the shared joint draws."""
from pathlib import Path
import argparse,json
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle
from scoring import INPUTS,ratings,weights,eligible,score_views,winners
from sensitivity_analysis import ALIASES,DISPLAY

QUESTION_LABELS={'what_rule':'what rule','how_computed':'how computed','what_feature':'what feature',
                 'how_differs':'how differs','why_instead_of':'why instead of','what_if':'what if',
                 'how_modify_input':'edit input'}
QUESTION_ORDER={
 'AIA11':['what_feature','how_computed','how_differs'],
 'AIA13-14':['what_rule','how_computed','how_differs','what_if','how_modify_input'],
 'DSA17':['what_rule','what_feature','how_differs','how_modify_input','why_instead_of'],
 'DSA27+P2B5':['what_rule','what_feature','how_computed','what_if'],
 'GDPR+AIA86+MiFID25':['what_rule','what_feature','how_differs','how_modify_input','why_instead_of'],
 'MDR':['what_rule','what_feature','how_differs'],
 'MiFID17':['what_feature','how_computed','how_differs']}
TITLES={'AIA11':'AIA Art. 11 + Annex IV','AIA13-14':'AIA Arts. 13-14','DSA17':'DSA Art. 17',
        'DSA27+P2B5':'DSA Art. 27 + P2B Art. 5','GDPR+AIA86+MiFID25':'GDPR + AIA Art. 86 + MiFID II Art. 25',
        'MDR':'MDR','MiFID17':'MiFID II Art. 17'}

def analyse(out):
    out=Path(out);meta=json.loads((out/'sensitivity_summary.json').read_text())
    draws=np.load(out/'joint_draw_scores.npz');names=meta['methods'];x=ratings(names)
    panels={};entries=[]
    for reg in DISPLAY:
        qs=QUESTION_ORDER[reg];p=np.full((len(names),len(qs)),np.nan);base=np.zeros_like(p,dtype=bool)
        v=score_views(x,weights([reg])[0])
        for j,q in enumerate(qs):
            ix=[i for i,n in enumerate(names) if eligible(n,reg,q)]
            if not ix:continue
            prob=winners(draws[reg][:,ix]).mean(axis=0)
            p[ix,j]=prob;base[ix,j]=winners(v['soft'][ix])
            for k,i in enumerate(ix):
                entries.append(dict(regulation=reg,question=q,method=names[i],probability=float(prob[k]),
                                    baseline_soft_winner=int(base[i,j])))
        ids=[i for i in range(len(names)) if np.isfinite(p[i]).any()]
        ids.sort(key=lambda i:-float(np.nanmax(p[i])))
        ids=ids[:10]
        panels[reg]=(qs,ids,p,base)
    pd.DataFrame(entries).to_csv(out/'question_winning_probabilities.csv',index=False)
    plt.rcParams.update({'font.family':'DejaVu Sans','pdf.fonttype':42,'font.size':8})
    fig,axes=plt.subplots(4,2,figsize=(10.8,14.2))
    fig.subplots_adjust(left=.18,right=.88,top=.96,bottom=.075,hspace=.65,wspace=.55)
    cmap=plt.colormaps['Blues'].copy();cmap.set_bad('white')
    for ax,reg in zip(axes.flat,DISPLAY):
        qs,ids,p,base=panels[reg];data=p[ids]
        im=ax.imshow(np.ma.masked_invalid(data),vmin=0,vmax=1,cmap=cmap,aspect='auto')
        ax.set_xticks(range(len(qs)),[QUESTION_LABELS[q] for q in qs],rotation=28,ha='right',fontsize=7.5)
        ax.set_yticks(range(len(ids)),[ALIASES.get(names[i],names[i]) for i in ids],fontsize=7.5)
        ax.set_title(TITLES[reg],fontsize=10.5,pad=8)
        ax.set_xticks(np.arange(-.5,len(qs),1),minor=True)
        ax.set_yticks(np.arange(-.5,len(ids),1),minor=True)
        ax.grid(which='minor',color='white',linewidth=.6);ax.tick_params(which='minor',length=0)
        for y,i in enumerate(ids):
            for j,q in enumerate(qs):
                if not np.isfinite(p[i,j]):continue
                ax.text(j,y,f'{p[i,j]:.2f}',ha='center',va='center',fontsize=7,
                        color='white' if p[i,j]>.6 else 'black')
                if base[i,j]:ax.add_patch(Rectangle((j-.49,y-.49),.98,.98,fill=False,edgecolor='black',linewidth=.6))
    axes.flat[-1].axis('off')
    cax=fig.add_axes([.925,.32,.014,.38]);cb=fig.colorbar(im,cax=cax)
    cb.set_label('Probability of top rank under perturbation',fontsize=9)
    fig.suptitle('Question-level ranking sensitivity by article bundle',fontsize=12,y=.995)
    fig.text(.53,.028,'Black outline marks the baseline soft-score winner. Blank cells are not procedurally eligible.',
             ha='center',fontsize=8)
    fig.text(.53,.012,'Panels show up to 10 methods; complete probabilities are in question_winning_probabilities.csv.',
             ha='center',fontsize=8)
    fig.savefig(out/'sensitivity_stability_questions.pdf',bbox_inches='tight');plt.close(fig)
    return entries

if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--outdir',type=Path,default=Path(__file__).resolve().parent/'analysis')
    args=parser.parse_args();analyse(args.outdir)

