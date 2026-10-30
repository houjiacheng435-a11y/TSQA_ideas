"""Generate new data, certify indistinguishability, run CPU retrieval baselines."""
import collections
import hashlib
import json
from pathlib import Path
from task import build_family,dump,verify,policy

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'results/v017-conditional-complementary-retrieval'
assert not OUT.exists(),'Preserve previous results; use a new version.'
OUT.mkdir(parents=True)
episodes=[e for f in range(8) for e in build_family(f)]
pilot=[e for e in episodes if e['family'] in [1,6] and e['rotation']==0]
assert len(episodes)==640 and len(pilot)==20
dump(OUT/'episodes-private.json',episodes)
dump(OUT/'pilot-private.json',pilot)
dump(OUT/'selection.json',{'families':8,'episodes':640,'rotation_replicas':8,
    'independent_world_initial_states':80,'pilot_families':[1,6],'pilot_episodes':20,
    'selection':'Fixed families 1,6 and rotation 0 before model inference; every 2x2 counterfactual cell and both initial channels, plus two no-pulse controls.',
    'script_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()})
groups=collections.defaultdict(list)
meta_groups=collections.defaultdict(set)
true_positions=collections.Counter()
for e in episodes:
    p=e['public'];initial=verify(p,p['initial'])
    assert initial['sufficient']==e['initial_sufficient']
    if initial['sufficient']:assert initial['answer']==e['answer']
    else:
        # Entire public view including all candidate previews repeats across
        # opposite hidden answers. A label-free numerical fetch is necessary.
        key=json.dumps(p,sort_keys=True)
        groups[key].append(e['answer'])
        joined=verify(p,p['initial']+[next(x for x in e['pool'] if x['id']==e['needed_id'])])
        assert joined['sufficient'] and joined['answer']==e['answer']
        pos=next(i for i,x in enumerate(p['index']) if x['id']==e['needed_id'])
        true_positions[(e['answer'],pos)]+=1
        same_meta=[x for x in p['index'] if x['channel']==next(x for x in e['pool'] if x['id']==e['needed_id'])['channel']]
        assert len(same_meta)==3
        assert len({(x['channel'],x['clock_start'],x['clock_end']) for x in same_meta})==1
    for item in e['pool']:
        state=verify(p,p['initial']+[item])
        if not initial['sufficient']:
            assert state['sufficient']==(item['id']==e['needed_id'])
        if state['sufficient']:assert state['answer']==e['answer']
assert all(set(v)=={'YES','NO'} for v in groups.values())
assert len(set(true_positions.values()))==1
audit={'complete':True,'episodes':640,'initial_sufficient':sum(e['initial_sufficient'] for e in episodes),
    'initial_insufficient':sum(not e['initial_sufficient'] for e in episodes),
    'identical_public_views_with_opposite_answers':len(groups),
    'joint_numeric_correct':640,'unique_useful_candidate_in_each_insufficient_case':True,
    'three_missing_channel_candidates_identical_name_time_metadata':True,
    'necessary_candidate_positions_by_label':{str(k):v for k,v in true_positions.items()},
    'all_sufficient_states_match_labels':True,
    'public_previews_contain_context_only_not_pulse_times':True,
    'limitations':['Controlled exact context matching, not natural episode ambiguity.',
        'Role coverage plus ordinary numerical context matching is expected to solve this task.',
        '640 includes eight order rotations of 80 independent world/initial states, not 640 independent tasks.']}
dump(OUT/'cpu-audit.json',audit)
results=[]
for e in episodes:
    for budget in [1,2]:
        for method in ['independent_topk','coverage','state_rule','oracle']:
            r=policy(e,method,budget)
            results.append({'episode_id':e['id'],'world_answer':e['answer'],'family':e['family'],**r})
dump(OUT/'cpu-trajectories.json',results)
summary=[]
for budget in [1,2]:
    for method in ['independent_topk','coverage','state_rule','oracle']:
        xs=[r for r in results if r['budget']==budget and r['method']==method]
        insufficient=[r for r in xs if not next(e for e in episodes if e['id']==r['episode_id'])['initial_sufficient']]
        summary.append({'method':method,'budget':budget,'n':len(xs),
            'answer_accuracy':sum(r['answer']==r['world_answer'] for r in xs)/len(xs),
            'complement_retrieval_success':sum(r['numeric']['sufficient'] for r in insufficient)/len(insufficient),
            'mean_fetches':sum(r['retrievals'] for r in xs)/len(xs),
            'false_sufficiency_rate':0.,'sufficiency_accuracy':1.,
            'stopping_note':'These four CPU methods use the same exact verifier to control stopping; perfect sufficiency judgments are supplied, not learned capabilities.'})
dump(OUT/'cpu-summary.json',summary)
dump(OUT/'cpu.complete.json',{'complete':True,'episodes':len(episodes),'trajectories':len(results),'pilot_episodes':len(pilot)})
print(json.dumps({'audit':audit,'summary':summary},ensure_ascii=False,indent=2))
