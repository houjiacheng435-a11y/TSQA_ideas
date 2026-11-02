import concurrent.futures,json,pathlib,subprocess
OUT=pathlib.Path(__file__).resolve().parents[2]/'results/v020-evidence-fidelity/sources'
OUT.mkdir(parents=True,exist_ok=True)
urls={
'sleep-hf':'https://huggingface.co/api/datasets/nz00shuuuu/sleep_psg_ts_haystack',
'ltaf-hf':'https://huggingface.co/api/datasets/nz00shuuuu/ltaf-haystack-fixed',
'haystack-tree':'https://api.github.com/repos/AI-X-Labs/TS-Haystack/git/trees/main?recursive=1',
'timerlm-tree':'https://api.github.com/repos/OpenTSLM/TimeRLM/git/trees/main?recursive=1',
'artist-tree':'https://api.github.com/repos/mims-harvard/ARTIST/git/trees/main?recursive=1',
'timer-tree':'https://api.github.com/repos/hyuna0926/TiMER_paper/git/trees/main?recursive=1',
 'ttsax-tree':'https://api.github.com/repos/Atlamtiz/tt-sax/git/trees/main?recursive=1'}
def get(item):
 key,url=item
 p=subprocess.run(['curl','-4','--noproxy','*','-L','--fail','--silent','--show-error','--connect-timeout','8','--max-time','30',url],capture_output=True)
 if p.returncode:return key,p.stderr.decode()[-200:]
 try:data=json.loads(p.stdout)
 except Exception:return key,p.stdout[:200].decode()
 (OUT/(key+'.json')).write_bytes(p.stdout)
 if 'siblings' in data:return key,{'sha':data.get('sha'),'gated':data.get('gated'),'size':data.get('usedStorage'),'files':[x['rfilename'] for x in data['siblings']][:35]}
 return key,{'sha':data.get('sha'),'files':[x['path'] for x in data.get('tree',[]) if x.get('type')=='blob'][:50]}
with concurrent.futures.ThreadPoolExecutor(max_workers=5) as pool:
 for r in pool.map(get,urls.items()):print(json.dumps(r),flush=True)
