"""Fixed 20-episode answering control after rejecting an unfair Sonar adaptation.

No inference-dependent selection or replacements. The simple state rule retrieves
the evidence, and Qwen is judged only on the actual raw observations, with no
numeric answers or sufficiency labels in its prompt. The incomplete adapter
precheck remains in its own directory and is not a valid comparative baseline.
"""
import importlib.util
import json
from pathlib import Path
import time
from task import dump,policy,verify

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'results/v017-conditional-complementary-retrieval'
RULES='Count only complete traces for the requested channels whose eight context values equal the requested episode_context. If either observed target has no pulse anywhere in its complete 42-point trace, the conjunction is NO even without the other target. Ordinary noise is within [-0.09,0.09]; a pulse first exceeds 1.5. Otherwise both event onsets are necessary. No unseen values may be assumed.'


def main():
    assert json.loads((OUT/'cpu.complete.json').read_text())['complete']
    assert json.loads((OUT/'boundary.complete.json').read_text())['complete']
    spec=importlib.util.spec_from_file_location('local_v016',ROOT/'experiments/v016-sonarts-qwen-local/run.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    episodes=json.loads((OUT/'pilot-private.json').read_text())
    dest=OUT/'controls';dest.mkdir(exist_ok=False)
    records=[]
    for e in episodes:
        d=dest/e['id'];d.mkdir();client=module.LocalClient('http://127.0.0.1:8016/v1',d)
        retrieval=policy(e,'state_rule',2)
        judgments=[]
        for phase,evidence in [('initial',e['public']['initial']),('retrieved',retrieval['evidence'])]:
            if phase=='retrieved' and not retrieval['selected']:
                judgments.append(dict(judgments[0],phase=phase,reused_identical_input=True));continue
            prompt=e['public']['question']+'\n'+RULES+'\nOnly supplied observations are available. Return one JSON object: {"sufficient":true/false,"answer":"YES/NO/UNKNOWN"}.\n'+json.dumps({'targets':e['public']['targets'],'episode_context':e['public']['episode_context'],'evidence':evidence})
            raw=client.chat([{'role':'user','content':prompt}])
            try:parsed=json.loads(raw.strip().removeprefix('```json').removesuffix('```').strip())
            except Exception:parsed=None
            judgments.append({'phase':phase,'raw':raw,'parsed':parsed,'numeric':verify(e['public'],evidence)})
        r={'episode_id':e['id'],'family':e['family'],'ai':e['ai'],'bi':e['bi'],'visible':e['visible'],
            'answer':e['answer'],'initial_sufficient':e['initial_sufficient'],
            'public':e['public'],'retrieval':retrieval,'qwen_judgments':judgments,
            'llm_calls':len(client.calls),'input_tokens':sum(c['response']['usage']['prompt_tokens'] for c in client.calls),
            'output_tokens':sum(c['response']['usage']['completion_tokens'] for c in client.calls)}
        dump(d/'complete.json',r);records.append(r)
        print(json.dumps({'id':e['id'],'initial':judgments[0]['parsed'],'retrieved':judgments[-1]['parsed']},ensure_ascii=False),flush=True)
    dump(dest/'records.json',records)
    dump(dest/'complete.json',{'complete':True,'episodes':20,'calls':sum(r['llm_calls'] for r in records)})


if __name__=='__main__':main()
