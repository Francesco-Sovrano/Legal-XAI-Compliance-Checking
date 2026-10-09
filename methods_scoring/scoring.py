"""Property-weighted scores, procedural eligibility and joint perturbations."""
from pathlib import Path
import json
import numpy as np

ROOT=Path(__file__).resolve().parent
INPUTS=json.loads((ROOT/'inputs/paper_inputs.json').read_text())
PROPERTIES=INPUTS['properties']
QUESTION_MAP={'what rule':'what_rule','what general logic':'what_rule','how model decides':'how_computed','what features':'what_feature','what are top features':'what_feature','what reasons':'why_instead_of','what feature importance':'what_feature','why those top features':'how_computed','how output differs from others':'how_differs','what if':'what_if','how sensitive to outliers':'what_if','how to change':'how_modify_input','what inputs have wrong outcomes':'what_feature','what best input format and ranges':'what_rule','how output is computed':'how_computed','is input problematic':'what_rule','what input quality':'how_modify_input','how robust is output':'how_differs'}

def score_views(x,w,threshold=3,omega=None):
    x=np.asarray(x,dtype=float);w=np.asarray(w,dtype=float)
    if not np.all(np.isfinite(x)) or np.any((x<1)|(x>5)):raise ValueError('Ratings must be finite and between 1 and 5')
    if not np.all(np.isfinite(w)) or np.any((w<0)|(w>1)) or np.any(w.sum(axis=-1)<=0):raise ValueError('Legal weights must be in [0,1] with positive total')
    om=np.ones_like(w) if omega is None else np.asarray(omega,dtype=float)
    if not np.all(np.isfinite(om)) or np.any(om<=0):raise ValueError('Priority weights must be finite and positive')
    den=w.sum(axis=-1);weighted=w*om;z=x/5
    return {'soft':np.round((z*w).sum(axis=-1)/den,12),'threshold':np.round(((x>=threshold)*w).sum(axis=-1)/den,12),'geometric':np.round(np.exp((np.log(z)*weighted).sum(axis=-1)/weighted.sum(axis=-1)),12)}

def eligible(method,regulation,question,available_access=None):
    m=INPUTS['methods'][method];r=INPUTS['regulations'][regulation]
    if m.get('requires_model_replacement') or m.get('component_only'):return False
    if available_access is not None and m.get('required_access') and m['required_access'] not in available_access:return False
    return question in m['question_types'] and (r['scope_stage']=='both' or m['scope_stage']=='both' or r['scope_stage']==m['scope_stage']) and m['subprops'][PROPERTIES[-1]]>0

def questions(regulation):return sorted({QUESTION_MAP[q] for q in INPUTS['regulations'][regulation]['question_types']})
def ratings(names):return np.array([[INPUTS['methods'][n]['subprops'][p] for p in PROPERTIES] for n in names],dtype=float)
def weights(regulations):return np.array([[INPUTS['regulations'][n]['required'][p] for p in PROPERTIES] for n in regulations],dtype=float)
def winners(v):return np.isclose(v,np.max(v,axis=-1,keepdims=True),atol=1e-10,rtol=0)

def joint_draws(names,regulations,draws=10000,seed=20261005):
    """One shared method-rating draw and independent legal-input draws per context."""
    if draws<1:raise ValueError('draws must be positive')
    rng=np.random.default_rng(seed);x=ratings(names);w=weights(regulations)
    xd=np.clip(x[None]+rng.integers(-2,3,(draws,len(names),len(PROPERTIES))),1,5)
    wd=np.clip(w[None]*rng.uniform(.75,1.25,(draws,len(regulations),len(PROPERTIES))),0,1)
    om=np.exp(rng.uniform(np.log(.5),np.log(2),(draws,len(regulations),len(PROPERTIES))))
    td=rng.integers(2,5,(draws,len(regulations),len(PROPERTIES)))
    result={}
    for j,r in enumerate(regulations):
        v=score_views(xd,wd[:,j,None],td[:,j,None],om[:,j,None])
        result[r]=(v['soft']+v['threshold']+v['geometric'])/3
    return result

def hard_gate(values,evidence):
    """Return zero when any mandatory criterion is unmet or unestablished."""
    return np.asarray(values)*int(all(v is True for v in evidence.values()))

def tau_batch(scores,expert):
    """Tie-aware Kendall tau-b for four alternatives, one result per draw."""
    scores=np.asarray(scores);expert=np.asarray(expert)
    pairs=[(i,j) for i in range(scores.shape[-1]) for j in range(i+1,scores.shape[-1])]
    d=np.stack([scores[...,i]-scores[...,j] for i,j in pairs],axis=-1)
    d=np.where(np.abs(d)<1e-10,0,np.sign(d));e=np.array([np.sign(expert[i]-expert[j]) for i,j in pairs])
    den=np.sqrt((d!=0).sum(axis=-1)*(e!=0).sum())
    return np.divide((d*e).sum(axis=-1),den,out=np.full(den.shape,np.nan),where=den!=0)
