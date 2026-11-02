"""Aggregate paired numeric audit, cluster uncertainty, cost accounting and figures."""
import os
import gzip,hashlib,json,pathlib,platform,subprocess,importlib.metadata
import numpy as np,pandas as pd
import matplotlib;matplotlib.use('Agg')
import matplotlib.pyplot as plt
ROOT=pathlib.Path(__file__).resolve().parents[2];OUT=pathlib.Path(os.environ.get('V020_OUT',str(ROOT/'results/v020-evidence-fidelity')));FIG=OUT/'figures';FIG.mkdir(exist_ok=True)
def dump(name,x):(OUT/name).write_text(json.dumps(x,indent=2,default=str,allow_nan=False)+'\n')
def plotend(name):plt.tight_layout();plt.savefig(FIG/name,dpi=170);plt.close()
d=pd.read_csv(OUT/'raw-results.csv');e=pd.read_csv(OUT/'evidence-metrics.csv');b=pd.read_csv(OUT/'index-build.csv');d['full_relevant_bytes']=d.n*4*d.kind.map(lambda k:2 if k in ['ordering','cooccur'] else 1);d['raw_fraction']=d.raw_bytes/d.full_relevant_bytes;d['online_fraction']=(d.raw_bytes+d.summary_bytes_read)/d.full_relevant_bytes
# Bootstrap recording clusters, preserving all lengths/tasks/conditions inside a cluster.
rng=np.random.default_rng(20261102);stats=[]
for (m,r),g in d.groupby(['method','ratio_target']):
 clusters=g.groupby('record').correct.mean().values;means=clusters[rng.integers(0,len(clusters),(4000,len(clusters)))].mean(1)
 stats.append({'method':m,'ratio_target':int(r),'queries':len(g),'correct':int(g.correct.sum()),'accuracy':float(g.correct.mean()),'record_cluster_bootstrap_ci95':np.quantile(means,[.025,.975]).tolist(),'mean_online_ms':float(g.online_seconds.mean()*1000),'mean_raw_fraction':float(g.raw_fraction.mean()),'mean_online_bytes_fraction':float(g.online_fraction.mean()),'mean_index_bytes':float(g.index_bytes.mean()),'certified_fraction':float(g.certified.mean())})
dump('aggregate.json',stats);pd.DataFrame(stats).drop(columns='record_cluster_bootstrap_ci95').to_csv(OUT/'aggregate.csv',index=False)
d.groupby(['method','ratio_target','kind']).correct.agg(['sum','count','mean']).to_csv(OUT/'by-query-type.csv');d.groupby(['method','ratio_target','n']).correct.mean().to_csv(OUT/'by-length.csv')
d[d.method.isin(['query_aware_rule','hierarchical_minmax_sum','event_index','full_resolution'])].groupby(['method','ratio_target','kind'])[['raw_fraction','online_fraction','online_seconds']].mean().to_csv(OUT/'cost-by-query.csv')
# Evidence plots omit MinMax midpoint and TT-SAX level-only decoders from method ranking.
fixed=['uniform','paa','pla_bound','sax'];labels={'uniform':'Uniform hold','paa':'PAA hold','pla_bound':'PLA interpolant','sax':'SAX level decode'}
plt.figure(figsize=(7,4))
for m in fixed:
 g=e[e.method==m].groupby('ratio_target').agg(actual_ratio=('actual_ratio','mean'),recall=('event_recall50','mean'));plt.plot(g.actual_ratio,g.recall,'o-',label=labels[m])
plt.xscale('log',base=4);plt.xlabel('Actual raw float32 bytes / stored representation bytes');plt.ylabel('Event recall at IoU >= 0.5 (macro contexts)');plt.ylim(-.02,1.02);plt.legend();plotend('01-compression-event-recall.png')
plt.figure(figsize=(7,4))
for m in fixed+['query_aware_rule']:
 g=d[d.method==m].groupby('ratio_target').correct.mean();plt.plot(g.index,g,'o-',label=labels.get(m,'MinMax+Sum + query rules'))
plt.xscale('log',base=4);plt.xlabel('Nominal compression target (tree stores extra levels)');plt.ylabel('Answer equality to exact full signal');plt.ylim(0,1.04);plt.legend();plotend('02-answer-preservation.png')
plt.figure(figsize=(7,4))
for m in fixed:
 g=e[(e.method==m)&(e.ratio_target==64)].groupby('n').mean_nearest_onset_error_s.mean();plt.plot(g.index,g,'o-',label=labels[m])
plt.xscale('log');plt.yscale('log');plt.xlabel('Context length (real samples)');plt.ylabel('Mean nearest predicted onset error (s)');plt.title('Nominal 64x; missing predictions excluded, see missingness CSV');plt.legend();plotend('03-length-onset-error.png')
e.groupby(['method','ratio_target','n']).agg(contexts=('context','count'),finite_timing=('mean_nearest_onset_error_s','count'),recall=('event_recall50','mean')).to_csv(OUT/'evidence-missingness.csv')
h=d[(d.ratio_target==64)&(d.method.isin(fixed+['query_aware_rule']))].pivot_table(index='method',columns='kind',values='correct');plt.figure(figsize=(10,3.5));plt.imshow(h.values,vmin=0,vmax=1,cmap='RdYlGn');plt.xticks(range(len(h.columns)),h.columns,rotation=35,ha='right');plt.yticks(range(len(h.index)),h.index);plt.colorbar(label='Answer preservation');plotend('04-query-heatmap.png')
plt.figure(figsize=(7.4,4.5))
for m in ['full_resolution','event_index','query_aware_rule','hierarchical_minmax_sum']+fixed:
 g=d[d.method==m].groupby('ratio_target').agg(x=('online_fraction','mean'),y=('correct','mean'))
 plt.plot(g.x,g.y,'o-',label=m)
plt.xscale('log');plt.ylim(0,1.05);plt.xlabel('Logical online raw + summary bytes / full relevant raw bytes');plt.ylabel('Answer equality');plt.title('Read-cost frontier only; excludes offline builds and latency');plt.legend(fontsize=7);plotend('05-read-cost-frontier.png')
# An explicit point on a real ECG; fixed before checking model results.
x=np.array(np.load(ROOT/'data/v020-evidence-fidelity/raw/104/104.npy',mmap_mode='r')[:16384]);from core import compress,answer
lo,hi=12128,12384;ts=np.arange(lo,hi)/128;plt.figure(figsize=(9,4));plt.plot(ts,x[lo:hi,0],label='Raw ECG1',lw=1)
for m in ['paa','uniform']:
 y,_,_,_=compress(x,64,m);plt.plot(ts,y[lo:hi,0],label=m+' 64x')
plt.axhline(.5,color='black',ls='--',label='Query threshold 0.5');plt.xlabel('Relative time (seconds)');plt.ylabel('Released numeric signal value');plt.legend();plotend('06-real-event-example.png')
# Save an unambiguous numerical worked example.
ex=[]
for m in ['paa','uniform']:
 y,_,_,_=compress(x,64,m);ex.append({'method':m,'first':answer(y,'first'),'count':answer(y,'count'),'maximum':answer(y,'maximum')})
dump('worked-example.json',{'context':'104-s0-n16384','full':{k:answer(x,k) for k in ['first','count','maximum']},'decoded':ex,'figure_samples':[lo,hi]})
# Compact every raw-access trace losslessly; source files remain in place.
with gzip.open(OUT/'refinement-traces.jsonl.gz','wt',compresslevel=9) as f:
 for p in sorted((OUT/'refinement-traces').glob('*.json')):f.write(json.dumps(dict(file=p.name,**json.load(open(p))),separators=(',',':'))+'\n')
manifest={'traces':len(list((OUT/'refinement-traces').glob('*.json'))),'sha256':hashlib.sha256((OUT/'refinement-traces.jsonl.gz').read_bytes()).hexdigest(),'note':'All per-query Broker fetches, losslessly consolidated; originals retained locally. Raw costs are distinct scalar values fetched; not measured disk I/O.'};dump('trace-manifest.json',manifest)
# Build cost amortization includes a complete offline scan for indexes, plus query reads.
rows=[]
for s in stats:
 if s['method'] not in ['event_index','query_aware_rule','hierarchical_minmax_sum','full_resolution']:continue
 match=b[(b.method==('minmax_sum_tree' if s['method'] in ['query_aware_rule','hierarchical_minmax_sum'] else s['method']))&(b.ratio_target==s['ratio_target'])]
 for qcount in [1,10,100]:
  rows.append({'method':s['method'],'ratio_target':s['ratio_target'],'queries_per_context':qcount,'mean_build_seconds':float(match.seconds.mean()) if len(match) else 0,'mean_total_seconds':float(match.seconds.mean())+qcount*s['mean_online_ms']/1000 if len(match) else qcount*s['mean_online_ms']/1000,'mean_full_source_input_bytes_offline':float(match.input_bytes.mean()) if len(match) else 0,'mean_index_bytes':s['mean_index_bytes'],'note':'Wall times on already memory-resident data; not cold-disk end-to-end. Index construction contains multiple passes.'})
pd.DataFrame(rows).to_csv(OUT/'amortized-cost.csv',index=False)
print('Aggregates, six figures and',manifest['traces'],'trace records written.')
