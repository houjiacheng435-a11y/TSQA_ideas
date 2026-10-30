"""Held-out, label-blind Qwen dynamic decisions and separate reader controls.

No generated code is executed. Each FETCH is brokered. Numeric facts are
extracted solely from already-visible source/index/records; no hidden outcome,
posterior answer or unacquired phase is in the action prompt.
"""
import argparse
import concurrent.futures as cf
import hashlib
import json
from pathlib import Path
import threading
import time
import urllib.request
from core import *

HERE=Path(__file__).parent;OUT=HERE.parents[1]/'results/v018-conditional-evidence-value'
LOCK=threading.Lock()
SYSTEM='You control a bounded scientific evidence retrieval system. Use only supplied observations. Return the requested JSON, no prose. Each FETCH reveals one record and costs one unit. Do not invent unobserved measurements. Unknown clock offsets must be calibrated. A coarse proxy has nonzero probability under both answers. An absent index preview is genuinely uninformative about association. You may abstain when the budget cannot establish certainty.'


def parse(raw):
    for i,c in enumerate(raw):
        if c=='{':
            try:return json.JSONDecoder().raw_decode(raw[i:])[0]
            except ValueError:continue
    return None


def action_schema(available,can_fetch=True):
    common={'sufficient':{'type':'boolean'},'answer':{'type':'string','enum':['YES','NO','UNKNOWN']}}
    stop={'type':'object','properties':{'action':{'type':'string','enum':['STOP']},'id':{'type':'string','enum':['NONE']},**common},'required':['action','id','sufficient','answer'],'additionalProperties':False}
    fetch={'type':'object','properties':{'action':{'type':'string','enum':['FETCH']},'id':{'type':'string','enum':available},**common},'required':['action','id','sufficient','answer'],'additionalProperties':False}
    return {'oneOf':[fetch,stop]} if can_fetch else stop


ANSWER_SCHEMA={'type':'object','properties':{'sufficient':{'type':'boolean'},'answer':{'type':'string','enum':['YES','NO','UNKNOWN']}},'required':['sufficient','answer'],'additionalProperties':False}


def chat(directory,messages,max_tokens=128,schema=None):
    payload={'model':'Qwen3-8B','messages':messages,'temperature':0.,'max_tokens':max_tokens,
             'chat_template_kwargs':{'enable_thinking':False}}
    if schema:payload['response_format']={'type':'json_schema','json_schema':{'name':'scientific_response','strict':True,'schema':schema}}
    req=urllib.request.Request('http://127.0.0.1:8018/v1/chat/completions',data=json.dumps(payload).encode(),headers={'Content-Type':'application/json'},method='POST')
    start=time.monotonic();record={'request':payload}
    try:
        opener=urllib.request.build_opener(urllib.request.ProxyHandler({}))
        with opener.open(req,timeout=600) as r:body=json.load(r)
        record.update(response=body,seconds=time.monotonic()-start)
    except Exception as exc:
        record.update(error=repr(exc),seconds=time.monotonic()-start)
        with (directory/'calls.jsonl').open('a') as f:f.write(json.dumps(record)+'\n')
        raise
    with (directory/'calls.jsonl').open('a') as f:f.write(json.dumps(record)+'\n')
    content=body['choices'][0]['message']['content']
    return content,parse(content)


DOCUMENTED_RULES='''Tool-field definitions and an existing numerical-rule baseline:
1. context_ncc=1 means the candidate driving context matches the observed source; small values do not match. All records in one bundle share context. Use the bundle with the largest context_ncc. Null means association is genuinely unknown, not zero.
2. After any fetch, matches_source=true identifies that bundle as relevant. If false, the other of the two bundles is relevant. Do not keep fetching a known-wrong bundle.
3. Exact evidence required: response plus clock1 if clock_depth>=1, plus clock2 if clock_depth>=2. The proxy and unneeded clock links cannot replace these.
4. If all exact records for the relevant bundle have been acquired, STOP and set sufficient=true. Compute lag=(response_phase-source_phase-sum(required clock phases)) modulo 8; answer YES for lag 2, NO for lag 6.
5. Otherwise choose a not-yet-acquired exact record from the relevant bundle. If association is unknown, an exact response record from either bundle is a legitimate first probe; it reveals association.
6. When budget is exhausted without all exact records, STOP sufficient=false, answer UNKNOWN.
These are public physics/tool semantics, not hidden outcomes or answer labels.'''


def agent(f,e,dest,documented=False,neutral_stop=False):
    d=dest/e['id'];d.mkdir(exist_ok=True)
    if (d/'record.json').exists():return json.loads((d/'record.json').read_text())
    assert not (d/'calls.jsonl').exists(),'Unfinished episode must be diagnosed, not silently replayed'
    b=Broker(f,e,3);decisions=[];status='budget_exhausted';pred='UNKNOWN';start=time.monotonic()
    for step in range(4):
        obs=b.public(raw=False)
        instruction='Decide the next action. action must be exactly FETCH or STOP. id must be an available candidate for FETCH, or NONE for STOP. sufficient is a boolean. answer must be exactly YES, NO, or UNKNOWN. Example valid stop: {"action":"STOP","id":"NONE","sufficient":false,"answer":"UNKNOWN"}. FETCH must name one not-yet-acquired candidate; STOP may give YES/NO only if the evidence proves it. Do not spend on a coarse proxy if the required exact response/calibration set is obtainable within budget. The source phase and context_ncc are fixed numerical measurements, not answer labels. Proxy phase = delay+E modulo 8; P(E=0)=0.5 and P(E=j)=0.5/7 for each j=1..7.'
        if neutral_stop:instruction=instruction.replace('Example valid stop: {"action":"STOP","id":"NONE","sufficient":false,"answer":"UNKNOWN"}. ', '')
        if documented:instruction+='\n'+DOCUMENTED_RULES
        state=b.state();available=[x['id'] for x in b.index if x['id'] not in b.selected]
        raw,obj=chat(d,[{'role':'system','content':SYSTEM},{'role':'user','content':instruction+'\n'+json.dumps(obs)}],schema=action_schema(available,len(b.selected)<3))
        decision={'step':step,'public_state':obs,'numeric_state_before':state,'raw':raw,'parsed':obj}
        decisions.append(decision)
        if not isinstance(obj,dict) or obj.get('action') not in ['FETCH','STOP']:
            status='format_error';break
        if obj['action']=='STOP':
            status='stopped';pred=obj.get('answer','UNKNOWN');break
        try:
            event=b.fetch(obj.get('id'))
            decision['obtained']=event;decision['numeric_state_after']=b.state()
        except Exception as exc:
            decision['tool_error']=str(exc);status='tool_error';break
    rec={'episode':e,'status':status,'prediction':pred,'truth':'YES' if e['ys'][e['source']]==0 else 'NO',
         'decisions':decisions,'selected':b.selected,'final_numeric':b.state(),'cost':len(b.selected),
         'seconds':time.monotonic()-start}
    save(d/'record.json',rec)
    return rec


def full_reader(f,e,facts=False,native=False):
    b=Broker(f,e,e['depth']+1)
    while not b.state()['sufficient']:b.fetch(choose(b,'conditional_numeric')['id'])
    intro=QUESTION+f"\nRequired clock links: {list(required(e['depth'])[1:])}. Raw traces have 48 points; phase is the index of the unique global maximum divided by 6. Subtract the source phase and required clock offsets from response phase, modulo 8. Return exactly one JSON object with two keys: sufficient (a boolean), and answer (a string chosen from YES, NO, UNKNOWN). Do not include any other text."
    if facts:
        text=intro+'\n'+json.dumps({'source_phase':phase(b.source),'observations':[{'kind':x['kind'],'phase':x['observed_phase']} for x in b.events]})
        return text,[],b.state()
    arrays=[b.source]+[x['values'] for x in b.events]
    labels=['source']+[x['kind'] for x in b.events]
    lines=[intro]
    for label,values in zip(labels,arrays):lines.append(label+': '+('<ts><ts/>' if native else json.dumps(values)))
    return '\n'.join(lines),arrays,b.state()


def reader(f,e,dest,condition):
    d=dest/(e['id']+'-'+condition);d.mkdir(exist_ok=True)
    if (d/'record.json').exists():return json.loads((d/'record.json').read_text())
    assert not (d/'calls.jsonl').exists()
    if condition=='raw_first_action':
        b=Broker(f,e,3)
        prompt='Choose the first retrieval action using only this public source waveform and index. action must be exactly FETCH or STOP, id is an available candidate for FETCH or NONE for STOP, sufficient is a boolean, answer is YES, NO or UNKNOWN. No candidate target values have been acquired. Use context waveform matching and the stated clock dependencies.\n'+json.dumps(b.public(raw=True))
    elif condition=='reader_lag':
        _,_,state=full_reader(f,e,facts=True)
        obs=state['observations'];lag=(obs['response']-sum(obs[k] for k in required(e['depth'])[1:]))%8
        prompt=QUESTION+'\nA fixed numerical tool has already processed the COMPLETE required source, response and clock-calibration records. All required offsets have been subtracted. The corrected true delay is '+str(lag)+' phase bins. No further records are needed. Return only JSON with sufficient (boolean) and answer (YES, NO or UNKNOWN).'
    else:prompt,_,_=full_reader(f,e,facts=condition=='reader_facts')
    schema=action_schema([x['id'] for x in b.index]) if condition=='raw_first_action' else ANSWER_SCHEMA
    raw,obj=chat(d,[{'role':'system','content':SYSTEM},{'role':'user','content':prompt}],128 if condition=='raw_first_action' else 64,schema=schema)
    rec={'episode':e,'condition':condition,'raw':raw,'parsed':obj,'truth':'YES' if e['ys'][e['source']]==0 else 'NO'}
    save(d/'record.json',rec);return rec


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--stage',choices=['agents','readers','lag-control'],required=True);ap.add_argument('--workers',type=int,default=4);ap.add_argument('--documented-rules',action='store_true');ap.add_argument('--neutral-stop-example',action='store_true');a=ap.parse_args()
    assert json.loads((OUT/'audit.complete.json').read_text())['gpu_gate_passed']
    fs={f['id']:f for f in json.loads((OUT/'families-private.json').read_text())}
    es=json.loads((OUT/('gpu-episodes-private.json' if a.stage=='agents' and not a.neutral_stop_example else 'reader-episodes-private.json')).read_text())
    stage_name=('qwen-agents-documented' if a.documented_rules else 'qwen-agents-schema') if a.stage=='agents' else 'qwen-readers'
    if a.neutral_stop_example:
        assert a.stage=='agents' and a.documented_rules
        stage_name='qwen-agents-neutral'
    if a.stage=='lag-control':stage_name='qwen-lag-control'
    dest=OUT/stage_name;dest.mkdir(exist_ok=True)
    config={'stage':a.stage,'model':'Qwen3-8B','workers':a.workers,'temperature':0.,'thinking':False,'budget':3,
        'test_families':48,'episodes':len(es),'documented_rules':a.documented_rules,'neutral_stop_example':a.neutral_stop_example,'source_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            'input_sha256':hashlib.sha256((OUT/('gpu-episodes-private.json' if a.stage=='agents' and not a.neutral_stop_example else 'reader-episodes-private.json')).read_bytes()).hexdigest()}
    if (dest/'config.json').exists():assert json.loads((dest/'config.json').read_text())==config
    else:save(dest/'config.json',config)
    jobs=[(e,None) for e in es] if a.stage=='agents' else [(e,c) for e in es for c in (['reader_lag'] if a.stage=='lag-control' else ['raw_first_action','reader_raw','reader_facts'])]
    results=[];begin=time.monotonic()
    with cf.ThreadPoolExecutor(max_workers=a.workers) as pool:
        futs=[pool.submit(agent,fs[e['family']],e,dest,a.documented_rules,a.neutral_stop_example) if c is None else pool.submit(reader,fs[e['family']],e,dest,c) for e,c in jobs]
        for fut in cf.as_completed(futs):
            r=fut.result();results.append(r)
            if len(results)%24==0:
                print(json.dumps({'stage':a.stage,'done':len(results),'total':len(jobs),'seconds':round(time.monotonic()-begin,1)}),flush=True)
    save(dest/'records.json',results)
    save(dest/'complete.json',{'complete':True,'records':len(results),'seconds':time.monotonic()-begin})
    print(json.dumps({'complete':True,'stage':a.stage,'records':len(results)}),flush=True)


if __name__=='__main__':main()
