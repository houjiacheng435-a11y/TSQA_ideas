"""CPU-only access/budget tests before invoking a model."""
import json
from pathlib import Path
from task import Broker,dump
from bounded_exec import execute,validate

def main():
    out=Path(__file__).resolve().parents[2]/'results/v017-conditional-complementary-retrieval'
    e=json.loads((out/'pilot-private.json').read_text())[0]
    for code in ["import os", "result = open('secret')", "result = fetch.__globals__"]:
        try:validate(code)
        except ValueError:pass
        else:raise AssertionError('boundary failed')
    b=Broker(e)
    code='''items = index()
seen = [x['channel'] for x in initial]
candidates = [x for x in items if x['channel'] in targets and x['channel'] not in seen]
best = min(candidates, key=lambda x: sum((a-b)*(a-b) for a,b in zip(x['context_sketch'],episode_context[:4])))
fetch(best['id'])
result = verify()
'''
    x=execute(code,b)
    assert x['error'] is None and b.verify()['sufficient'] and len(b.selected)==1,x
    b=Broker(e,budget=1)
    x=execute("items=index()\nfetch(items[0]['id'])\nfetch(items[1]['id'])\nresult=verify()",b)
    assert x['error'] and len(b.selected)==1
    dump(out/'boundary.complete.json',{'complete':True,'imports_files_introspection_blocked':True,
        'content_matching_program_succeeds':True,'budget_exhaustion_enforced':True,
        'child_inputs':'public state and pipe only, no private pool or labels',
        'scope':'Restricted diagnostic DSL, not a general security sandbox.'})
    print('Boundary and budget checks passed.')

if __name__=='__main__':main()
