"""Version-matched, single-factor CPU interventions. Never reads evaluation labels until scoring."""
from run import *

def main():
    dump(OUT/'legacy-interventions-protocol.json',{'timing':'Defined after discovering result/template commit mismatch; applied to all 12 original cases, no reselection or parameter tuning.','reference':'f2d61852498f1e406effc9d2696c512d2b3a2180 CT template','arms':['released legacy template','remove SAX priority only: same full-year raw, same per-day metric, same global quantile floor, global numerical sort instead of SAX-first concatenation','correct monotone endpoint only: same full-year access, same legacy SAX priority and quantile rule'],'caution':'Removing SAX priority also removes its shape-eligibility preference. Better label score alone does not establish better literal pattern verification.'})
    legacy=read(OUT/'legacy-template-results.json');rows=[]
    for z in legacy:
        metrics=read(OUT/'day-metrics'/f'{z["id"]}.json');p=read(OUT/'cases'/f'{z["id"]}.json')['parameters'];desc=p['sup'] in {'fastest','biggest','largest','strongest','highest','deepest','most','sharpest','steepest'}
        if p['target_kind']=='stable' and p['target_adj']=='steady':desc=False
        standard=[{'date':d['date'],'metric':d['official_metric']} for d in metrics if d['official_metric'] is not None]
        kept=[d for d in standard if d['metric']>=z['floor']]
        pool=set(z['sax_candidate_days'])
        ordered=lambda a:sorted(a,key=lambda d:d['metric'],reverse=desc)
        reconstructed=ordered([d for d in kept if d['date'] in pool])+ordered([d for d in kept if d['date'] not in pool])
        assert [d['date'] for d in reconstructed[:5]]==z['prediction']
        corrected=[{'date':d['date'],'metric':d['endpoint_corrected_metric']} for d in metrics if d['endpoint_corrected_metric'] is not None]
        corrected_floor=float(np.quantile([d['metric'] for d in corrected],.5 if desc else .8));corrected=[d for d in corrected if d['metric']>=corrected_floor]
        fixed=ordered([d for d in corrected if d['date'] in pool])+ordered([d for d in corrected if d['date'] not in pool])
        rows.append({'id':z['id'],'arms':{'released_legacy':z['prediction'],'remove_sax_priority':[d['date'] for d in ordered(kept)[:5]],'correct_endpoint_only':[d['date'] for d in fixed[:5]]},'raw_access_points_all_arms':z['raw_points'],'same_global_floor_remove_priority':z['floor'],'corrected_endpoint_floor':corrected_floor,'sax_pool_above_floor':sum(d['date'] in pool for d in kept),'outside_pool_above_floor':sum(d['date'] not in pool for d in kept),'top_global_metric':ordered(kept)[:5]})
    dump(OUT/'legacy-interventions.json',rows)
    labels={x['id']:x for x in read(OUT/'evaluation-only.json')};ev=loadmod('ev','sonar_ts/evaluator.py');scores=[]
    for z in rows:scores.append({'id':z['id'],**{arm:ev.score_one('set_f1',pred,labels[z['id']]['ground_truth'])[0] for arm,pred in z['arms'].items()}})
    dump(OUT/'legacy-intervention-scores.json',scores);pd.DataFrame(scores).to_csv(OUT/'legacy-intervention-scores.csv',index=False)
    print(pd.DataFrame(scores).to_string(index=False))

if __name__=='__main__':main()
