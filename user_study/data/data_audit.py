"""Audit the fixed analytic cohort and descriptive feedback coding."""
from pathlib import Path
import sqlite3,json,hashlib,sys
import pandas as pd

def analyse(root,out):
    root=Path(root);out=Path(out);out.mkdir(parents=True,exist_ok=True)
    c=sqlite3.connect('file:'+str((root/'user_study/data/public-review.sqlite3').resolve())+'?mode=ro',uri=True)
    sessions=pd.read_sql_query('SELECT * FROM sessions',c);sessions.to_csv(out/'sessions.csv',index=False)
    metadata=dict(c.execute('SELECT key,value FROM metadata').fetchall())
    slots=['E08','E11','E13','E18'];marks=','.join('?' for _ in slots)
    counts={t:c.execute('SELECT COUNT(*) FROM '+t+' r JOIN sessions s ON s.id=r.session_id WHERE s.panel_slot IN ('+marks+')',slots).fetchone()[0] for t in ['trial_responses','ranking_responses','checklist_responses','poststudy_responses']}
    observed=pd.read_sql_query('SELECT s.panel_slot,r.* FROM trial_responses r JOIN sessions s ON s.id=r.session_id WHERE s.panel_slot IN ('+marks+') ORDER BY s.panel_slot,r.module_id,r.trial_index',c,params=slots)
    confidence=observed.groupby('module_id')['confidence'].median().to_dict()
    checks={'primary_count':counts['trial_responses'],'comparison_count':counts['ranking_responses'],'confidence_medians':confidence,'content_only_confirmations':int((observed['visual_appearance_influenced']=='no').sum())}
    schema={name:[{'name':r[1],'type':r[2],'required':bool(r[3]),'primary_key_order':r[5]} for r in c.execute('PRAGMA table_info('+name+')').fetchall()] for name, in c.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
    (out/'database_schema.json').write_text(json.dumps(schema,indent=2));c.close()
    a=json.loads((root/'methods_scoring/inputs/qualitative_annotations.json').read_text());slots=['E08','E11','E13','E18']
    annotations=pd.DataFrame(a);annotations.to_csv(out/'qualitative_annotations.csv',index=False)
    sys.path.insert(0,str(root/'user_study/ui'))
    from study_core import load_config,config_hash
    observed=metadata.get('config_hash');canonical=config_hash(load_config(root/'user_study/ui/config/study.json'))
    report={'included_slots':slots,'primary_observations':counts['trial_responses'],'primary_observations_per_expert':counts['trial_responses']//len(slots),'descriptive_checks':checks,'technical_property_language_count':sum(v['technical_property_language'] for v in a),'qualitative_coders':1,'database_metadata':metadata,'packaged_ui_canonical_sha256':canonical,'instrument_hash_match':observed==canonical,'instrument_verification':'Retrieve the study instrument with the database config_hash to verify exact collection text.'}
    (out/'data_audit.json').write_text(json.dumps(report,indent=2));return report
