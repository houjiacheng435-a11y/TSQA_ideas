"""Constrained program broker: child receives no pool, labels, filesystem/API.

This is a restricted diagnostic DSL implemented with a validated Python AST,
not a general-purpose untrusted-Python security sandbox. Only literal/list/dict
computations and broker calls are allowed; failed attempts share one fetch budget.
"""
import ast
import multiprocessing as mp
import time

SAFE={'len':len,'range':range,'enumerate':enumerate,'min':min,'max':max,'sorted':sorted,
      'sum':sum,'abs':abs,'bool':bool,'str':str,'int':int,'float':float,'list':list,
      'dict':dict,'set':set,'tuple':tuple,'zip':zip,'all':all,'any':any}
ATTRS={'get','append','items','keys','values','copy','sort','index','pop'}
BANNED={'open','globals','locals','vars','getattr','setattr','eval','exec','compile','help',
        'dir','type','object','__import__','breakpoint','input','exit','quit','super','hasattr','delattr'}


def validate(code):
    tree=ast.parse(code)
    for node in ast.walk(tree):
        if isinstance(node,(ast.Import,ast.ImportFrom,ast.ClassDef,ast.With,ast.AsyncWith,ast.Global,ast.Nonlocal,ast.Delete)):
            raise ValueError('unsupported program construct: '+type(node).__name__)
        if isinstance(node,ast.Name) and (node.id.startswith('_') or node.id in BANNED):
            raise ValueError('forbidden name: '+node.id)
        if isinstance(node,ast.Attribute) and node.attr not in ATTRS:
            raise ValueError('unsupported attribute: '+node.attr)
    return tree


def child(pipe,code,public,evidence,remaining):
    def request(op,**kwargs):
        pipe.send({'op':op,**kwargs});reply=pipe.recv()
        if 'error' in reply:raise ValueError(reply['error'])
        return reply['value']
    env={'__builtins__':SAFE,'initial':evidence,'targets':public['targets'],
         'episode_context':public['episode_context'],'remaining_budget':remaining,
         'index':lambda:request('index'),'fetch':lambda candidate_id:request('fetch',candidate_id=candidate_id),
         'verify':lambda:request('verify')}
    try:
        tree=validate(code)
        exec(compile(tree,'<bounded-retrieval-program>','exec'),env)
        pipe.send({'op':'finish','result':env.get('result')})
    except Exception as exc:pipe.send({'op':'error','error':type(exc).__name__+': '+str(exc)})
    finally:pipe.close()


def execute(code,broker,timeout=10.):
    validate(code)
    ctx=mp.get_context('spawn');parent,remote=ctx.Pipe()
    proc=ctx.Process(target=child,args=(remote,code,broker.public,broker.evidence,broker.budget-len(broker.selected)))
    proc.start();remote.close();deadline=time.monotonic()+timeout
    calls=[];result=None;error=None
    try:
        while time.monotonic()<deadline:
            if not parent.poll(.05):
                if not proc.is_alive():break
                continue
            msg=parent.recv();op=msg['op'];calls.append(msg)
            if op=='finish':result=msg['result'];break
            if op=='error':error=msg['error'];break
            try:
                if op=='index':value=broker.index()
                elif op=='fetch':value=broker.fetch(msg['candidate_id'])
                elif op=='verify':value=broker.verify()
                else:raise ValueError('unknown broker operation')
                parent.send({'value':value})
            except Exception as exc:parent.send({'error':str(exc)})
        else:error='execution timeout'
    except EOFError:error='child exited without result'
    finally:
        if proc.is_alive():proc.terminate()
        proc.join();parent.close()
    if not isinstance(result,dict):error=error or 'result must be a dict'
    return {'result':result,'error':error,'tool_calls':calls}
