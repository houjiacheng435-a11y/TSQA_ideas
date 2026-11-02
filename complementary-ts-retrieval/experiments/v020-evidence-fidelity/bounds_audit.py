"""Check measured PLA bounds and conservative sufficient-answer certificates."""
import os
import json,pathlib,numpy as np,pandas as pd
from core import compress,answer
ROOT=pathlib.Path(__file__).resolve().parents[2];OUT=pathlib.Path(os.environ.get('V020_OUT',str(ROOT/'results/v020-evidence-fidelity')));DATA=ROOT/'data/v020-evidence-fidelity';rows=[]
for c in json.load(open(OUT/'contexts.json')):
 x=np.array(np.load(DATA/f'raw/{c["record"]}/{c["record"]}.npy',mmap_mode='r')[c['start_sample']:c['start_sample']+c['n']])
 for r in [4,16,64,256]:
  y,m,_,_=compress(x,r,'pla_bound');assert np.all(x>=m['lo']) and np.all(x<=m['hi'])
  for kind,t in [('exists05',.5),('exists10',1.)]:
   lo,hi=m['lo'][:,0],m['hi'][:,0];cert=True if (lo>=t).any() else False if (hi<t).all() else None
   if cert is not None:assert cert==answer(x,kind)
   rows.append({'context':c['id'],'ratio_target':r,'kind':kind,'interval_certificate':cert,'truth':answer(x,kind),'decoder_answer':answer(y,kind),'scope':'A sufficient interval certificate; inconclusive does not prove ambiguity.'})
pd.DataFrame(rows).to_csv(OUT/'pla-bound-certificates.csv',index=False);(OUT/'pla-bound-audit.json').write_text(json.dumps({'contexts':24,'ratios':4,'all_96_context_ratio_bounds_contain_every_original_sample':True,'existence_queries':len(rows),'certified':sum(r['interval_certificate'] is not None for r in rows),'wrong_certificates':0,'note':'The other PLA rows use the interpolant as a point estimate. Neither point-estimate error nor a wide bound alone proves intrinsic information loss.'},indent=2)+'\n')
