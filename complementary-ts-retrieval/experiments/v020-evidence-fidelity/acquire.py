"""Pinned, selected real recordings and official QA metadata; never downloads models."""
import os
import concurrent.futures,hashlib,json,pathlib,subprocess
ROOT=pathlib.Path(__file__).resolve().parents[2];OUT=pathlib.Path(os.environ.get('V020_OUT',str(ROOT/'results/v020-evidence-fidelity')));DATA=ROOT/'data/v020-evidence-fidelity';DATA.mkdir(parents=True,exist_ok=True)
def fetch(repo,rev,name,dest,expected=None):
 if dest.exists():raw=dest.read_bytes()
 else:
  dest.parent.mkdir(parents=True,exist_ok=True);part=dest.with_suffix(dest.suffix+'.partial')
  url=f'https://hf-mirror.com/datasets/{repo}/resolve/{rev}/{name}'
  subprocess.run(['curl','-4','--noproxy','*','-L','--fail','--silent','--show-error','--connect-timeout','10','--max-time','300','--retry','2','--retry-all-errors','--continue-at','-','-o',str(part),url],check=True)
  raw=part.read_bytes()
  if expected:
   assert len(raw)==expected['size']
   if expected.get('lfs'):assert hashlib.sha256(raw).hexdigest()==expected['lfs']['sha256']
  # Retain partial file; do not delete existing artifacts.
  import os;os.link(part,dest)
 if expected:
  assert len(raw)==expected['size']
  if expected.get('lfs'):assert hashlib.sha256(raw).hexdigest()==expected['lfs']['sha256']
 return {'repo':repo,'revision':rev,'file':name,'path':str(dest.relative_to(ROOT)),'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest(),'expected':expected}
def main():
 meta=json.load(open(OUT/'sources/ltaf-raw-hf.json'));split=json.load(open(OUT/'sources/ltaf-split.json'))
 records=sorted(split['test'])[:8]
 protocol={'records':records,'selection':'First eight lexicographic official test records; no outcome-based replacement. Separate train record 00 used only for calibration if needed.','lengths':[16384,131072,1048576],'sample_rate':128,'channels':['ECG1','ECG2'],'signal_revision':meta['sha'],'qa_revision':'595630367eefc6da5211dc512efe0ee3491bc197','primary':'Numeric rule QA on unmodified real ECG; not the official rhythm QA labels; no clinical interpretation. Official task metadata audited separately.'}
 p=OUT/'data-selection.json'
 if p.exists():assert json.load(open(p))==protocol
 else:p.write_text(json.dumps(protocol,indent=2)+'\n')
 lookup={r['rfilename']:r for r in meta['siblings']}
 def one(rid):
  name=f'{rid}/{rid}.npy';r=fetch('nz00shuuuu/ltaf-raw',meta['sha'],name,DATA/'raw'/name,lookup[name]);print('real ECG verified',rid,r['bytes'],flush=True);return r
 with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:rows=list(pool.map(one,records))
 for name in ['conversion_manifest.json']:
  if name in lookup:rows.append(fetch('nz00shuuuu/ltaf-raw',meta['sha'],name,DATA/name,lookup[name]))
 # Official annotation metadata only. Not supplied to numeric selection policies.
 for name in ['rhythms/tasks/100_0s/existence/test/data.parquet','rhythms/tasks/7200_0s/ordering/test/data.parquet','rhythms/tasks/3600_0s/counting/test/data.parquet']:
  rows.append(fetch('nz00shuuuu/ltaf-haystack-fixed',protocol['qa_revision'],name,DATA/'official-qa'/name))
 (OUT/'acquisition.json').write_text(json.dumps(rows,indent=2)+'\n')
if __name__=='__main__':main()
