"""Small GPU pilot; official planner/generator functions, explicitly adapted prompts.

The adapter is a generous tool-assisted protocol comparator, not a reproduction
of Sonar-TS's SAX/SQL retrieval performance. Qwen's independent judgments are
reported separately from exact-verifier-controlled retrieval performance.
"""
import argparse
import importlib.util
import json
from pathlib import Path
import sys
import time
from task import Broker,dump,verify
from bounded_exec import execute

ROOT=Path(__file__).resolve().parents[2]
HERE=Path(__file__).parent
OUT=ROOT/'results/v017-conditional-complementary-retrieval'
RULES='Complete same-episode traces only count for the requested target channels. Context equality identifies the episode. A complete absent pulse on either target establishes NO; otherwise both event onsets are required. No labels are in the index. Use verify() for exact numeric calculations.'


def schema(b):
    return json.dumps({'initial':b.evidence,'targets':b.public['targets'],
        'episode_context':b.public['episode_context'],'candidate_index':b.index(),
        'remaining_budget':b.budget-len(b.selected),
        'tools':{'index()':'metadata and 4 context values only, no target trace values',
                 'fetch(candidate_id)':'one full trace, costs one of two total fetches',
                 'verify()':'exact sufficiency/answer for only the evidence fetched so far; no pool access'}},ensure_ascii=False)


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--official',type=Path,required=True)
    a=ap.parse_args()
    assert json.loads((OUT/'cpu.complete.json').read_text())['complete']
    sys.path.insert(0,str(a.official))
    from sonar_ts import planner,generator
    planner._PROMPT_PATH=HERE/'planner.txt';generator._INITIAL=HERE/'generator.txt';generator._FIX=HERE/'fix.txt'
    spec=importlib.util.spec_from_file_location('local_v016',ROOT/'experiments/v016-sonarts-qwen-local/run.py')
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
    episodes=json.loads((OUT/'pilot-private.json').read_text())
    dest=OUT/'pilot';dest.mkdir(exist_ok=False)
    records=[]
    for e in episodes:
        d=dest/e['id'];d.mkdir();client=m.LocalClient('http://127.0.0.1:8016/v1',d)
        b=Broker(e);started=time.monotonic();attempts=[]
        plan=planner.plan(e['public']['question'],schema(b),'- bounded-retrieval: budgeted context matching and exact numeric verification',client)
        code=generator.generate(e['public']['question'],schema(b),plan.plan_text,RULES,'bounded_retrieval',client)
        for attempt in range(4):
            (d/f'code-{attempt}.py').write_text(code)
            try:result=execute(code,b)
            except Exception as exc:result={'result':None,'error':str(exc),'tool_calls':[]}
            attempts.append(result)
            if result['error'] is None:break
            if attempt<3:
                code=generator.regenerate(e['public']['question'],schema(b),plan.plan_text,RULES,'bounded_retrieval',
                    previous_code=code,error_status='bounded_execution_error',error_message=result['error'],client=client)
        declared=attempts[-1]['result'] if attempts else None
        rec={'episode_id':e['id'],'family':e['family'],'ai':e['ai'],'bi':e['bi'],'visible':e['visible'],
             'answer':e['answer'],'initial_sufficient':e['initial_sufficient'],'public':e['public'],
             'plan':plan.plan_text,'skills':plan.skill_ids,'attempts':attempts,'declared':declared,
             'retrieval':b.result(),'wall_seconds':time.monotonic()-started}
        dump(d/'retrieval.json',rec)
        # Independent Qwen judgment: no answer, hidden label, verifier output,
        # plan or candidate pool passed. Evaluates model answering separately.
        judgments=[]
        for phase,evidence in [('initial',e['public']['initial']),('retrieved',b.evidence)]:
            if phase=='retrieved' and not b.selected:
                reused=dict(judgments[0],phase=phase,reused_identical_input=True)
                judgments.append(reused)
                continue
            prompt=(e['public']['question']+'\n'+RULES+
                '\nJudge only supplied observations; do not assume omitted records. '
                'Return one JSON object: {"sufficient":true/false,"answer":"YES/NO/UNKNOWN"}.\n'+
                json.dumps({'targets':e['public']['targets'],'episode_context':e['public']['episode_context'],'evidence':evidence}))
            raw=client.chat([{'role':'user','content':prompt}])
            try:
                obj=json.loads(raw.strip().removeprefix('```json').removesuffix('```').strip())
            except Exception:obj=None
            judgments.append({'phase':phase,'raw':raw,'parsed':obj,'numeric':verify(e['public'],evidence)})
        rec['qwen_judgments']=judgments
        rec['llm_calls']=len(client.calls)
        rec['input_tokens']=sum(c['response']['usage']['prompt_tokens'] for c in client.calls)
        rec['output_tokens']=sum(c['response']['usage']['completion_tokens'] for c in client.calls)
        dump(d/'complete.json',rec);records.append(rec)
        print(json.dumps({'id':e['id'],'fetches':len(b.selected),'numeric':b.verify(),
                          'declared':declared,'calls':len(client.calls)},ensure_ascii=False),flush=True)
    dump(dest/'records.json',records)
    dump(dest/'complete.json',{'complete':True,'episodes':len(records),'calls':sum(r['llm_calls'] for r in records)})


if __name__=='__main__':main()
