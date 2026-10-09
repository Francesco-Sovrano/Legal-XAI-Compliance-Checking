"""Recompute deterministic legal-task comparisons from the supplied weight cases."""
from pathlib import Path
import argparse,json
import numpy as np
import pandas as pd
from scoring import INPUTS, PROPERTIES, ratings, weights, questions, eligible, score_views, winners

def analyse(out):
    out=Path(out);out.mkdir(parents=True,exist_ok=True)
    cases=json.loads((Path(__file__).resolve().parent/'inputs/legal_task_cases.json').read_text())
    names=[n for n,m in INPUTS['methods'].items() if not m.get('requires_model_replacement') and not m.get('component_only')]
    x=ratings(names);rows=[]
    for case in cases:
        for reg,w in case['weights'].items():
            base=score_views(x,weights([reg])[0])
            changed=score_views(x,[w[p] for p in PROPERTIES])
            for group in ['all','agnostic']:
                for q in questions(reg):
                    ids=[i for i,n in enumerate(names) if eligible(n,reg,q) and (group=='all' or INPUTS['methods'][n].get('type')=='model-agnostic' or i<14)]
                    if not ids:continue
                    for view in ['soft','threshold','geometric']:
                        default=sorted(names[ids[i]] for i in np.flatnonzero(winners(base[view][ids])))
                        variant=sorted(names[ids[i]] for i in np.flatnonzero(winners(changed[view][ids])))
                        rows.append(dict(case=case['case'],catalogue=group,bundle=reg,question=q,view=view,
                                         default_winners='; '.join(default),variant_winners='; '.join(variant),
                                         score=float(changed[view][ids].max()),same_winners=int(default==variant),
                                         retains_default_winner=int(bool(set(default)&set(variant)))))
    df=pd.DataFrame(rows);df.to_csv(out/'legal_task_sensitivity.csv',index=False)
    endpoint=df[df['case'].str.startswith('endpoints_')]
    summary=[]
    for (bundle,catalogue,view),g in endpoint.groupby(['bundle','catalogue','view'],sort=False):
        summary.append(dict(bundle=bundle,catalogue=catalogue,view=view,
                            same_winner_fraction=float(g['same_winners'].mean()),
                            retention_fraction=float(g['retains_default_winner'].mean())))
    result=dict(endpoint_cases=sum(c['case'].startswith('endpoints_') for c in cases),
                task_cases=sum(not c['case'].startswith('endpoints_') for c in cases),summary=summary)
    (out/'legal_task_sensitivity_summary.json').write_text(json.dumps(result,indent=2)+'\n')
    return result

if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--outdir',type=Path,default=Path(__file__).resolve().parent/'analysis')
    args=parser.parse_args();analyse(args.outdir)

