"""Keep full traces locally; publish reproducible SQL/hash manifests without raw signals."""
import gzip,hashlib,json,os,pathlib
ROOT=pathlib.Path(__file__).resolve().parents[2];OUT=pathlib.Path(os.environ.get('V020_OUT',str(ROOT/'results/v020-evidence-fidelity')));rows=[]
def summary(v):
 blob=json.dumps(v,separators=(',',':'),sort_keys=True,default=str).encode()
 return {'type':type(v).__name__,'length':len(v) if hasattr(v,'__len__') else None,'canonical_json_sha256':hashlib.sha256(blob).hexdigest(),'payload_omitted':'Full values remain in the local original trace; recover from pinned data and recorded SQL/code.'}
for p in sorted((OUT/'sonar/traces').glob('*/sql-*.jsonl.gz')):
 dest=OUT/'sonar/public-sql'/p.parent.name/p.name;dest.parent.mkdir(parents=True,exist_ok=True)
 with gzip.open(p,'rt') as source,gzip.open(dest,'wt',compresslevel=9) as target:
  for line in source:
   event=json.loads(line)
   for k in ['rows','row']:
    if k in event:event[k+'_audit']=summary(event.pop(k))
   if 'values' in event:
    event['values']={k:(v if v is None or isinstance(v,(int,float,bool)) or isinstance(v,str) and len(v)<200 else summary(v)) for k,v in event['values'].items()}
   target.write(json.dumps(event,separators=(',',':'),default=str)+'\n')
 rows.append({'local_original':str(p.relative_to(OUT)),'local_sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'local_bytes':p.stat().st_size,'published':str(dest.relative_to(OUT)),'published_sha256':hashlib.sha256(dest.read_bytes()).hexdigest()})
(OUT/'sonar/sql-trace-manifest.json').write_text(json.dumps({'purpose':'Raw signal payload is kept locally, excluded from GitHub; SQL, row counts, errors, final scalar outputs and payload checksums retained.','files':rows},indent=2)+'\n');print('Published audit versions of',len(rows),'SQL traces; original full traces retained.')
