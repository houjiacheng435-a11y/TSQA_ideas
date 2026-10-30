"""Check score/provenance consistency; annotate observed, not presumed, failures."""
import argparse
import hashlib
import json
from pathlib import Path

ap = argparse.ArgumentParser()
ap.add_argument('--out',type=Path,required=True)
a=ap.parse_args()
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
records=json.loads((a.out/'pilot10/records.json').read_text())
official=json.loads((a.out/'official-per-task.json').read_text())
selection=json.loads((a.out/'selection.json').read_text())
prepared=json.loads((a.out/'preparation.complete.json').read_text())
assert [r['task_id'] for r in records]==selection['ids']
for r,o in zip(records,official):
    assert r['task_id']==o['task_id'] and abs(r['score']-o['score'])<1e-12
for src in selection['sources'].values():assert sha(src['path'])==src['sha256']
for r in prepared['records']:assert sha(a.out/'databases'/f"{r['id']}.sqlite")==r['database_sha256']
calls=[]
for r in records:
    d=Path(r.get('reused_smoke_trace',a.out/'pilot10'/r['task_id']))
    calls.extend(json.loads(s) for s in (d/'llm-calls.jsonl').read_text().splitlines())
assert len(calls)==26
assert all(c['response']['choices'][0]['finish_reason']=='stop' for c in calls)
assert all('<think>' not in c['response']['choices'][0]['message']['content'] for c in calls)
assert sum(c['response']['usage']['completion_tokens'] for c in calls)==sum(r['output_tokens'] for r in records)
observations={
 'L2_T3_Subsequence_Matching_00332':('success','Reference/context raw slices retrieved; normalized subsequence match returned the exact reference interval.'),
 'L2_T3_Subsequence_Matching_00339':('success','Reference/context raw slices retrieved; exact reference interval returned.'),
 'L3_T3_Causal_Anomaly_00386':('execution_error','Both raw channels fetched, including the reference interval. All four attempts fail on str.strftime; no final answer. Not an evidence omission diagnosis.'),
 'L3_T3_Causal_Anomaly_00387':('execution_error','Both raw channels fetched across attempts. Initial None indexing, then int.strftime errors. Three regenerations exhausted; no final answer.'),
 'L3_T3_Causal_Anomaly_00388':('query_and_fallback_error','Yearly std < yearly AVG(std) has no candidates with one annual row per channel. No raw rows fetched. Generated fallback emits the entire year; shape validation accepts it. Query translation and unsupported stopping, not proven complementarity failure.'),
 'L3_T1_Composite_Trend_00014':('semantic_verification_error','All five reference dates retrieved among 241 days, but target_kind="slow rise" falls into the stable branch (only "rise"/"fall" recognized). Pattern list is also malformed. One of five final dates matches.'),
 'L3_T1_Composite_Trend_00025':('query_translation_error','Question asks rise then rise, but generated kinds=["fall","rise"]. 45 candidates contain none of the five reference dates. This is observed candidate omission with a concrete query translation defect, not a demonstrated joint evidence selection gap.'),
 'L3_T1_Composite_Trend_00034':('verification_or_rule_label_mismatch','SAX returns two days, fewer than five; official-style fallback reads all 365 days, including all reference dates. Numerical scoring/ranking returns none of the reference dates. Upstream recipe is substantially copied; retrieval omission is excluded, semantic correctness of the heuristic is not certified.'),
 'L4_T1_Insight_Synthesis_00001':('mostly_success','Entire target month fetched; trend and adjective scores 1, interval score 0.93546, outlier score 1. Boundary approximately 20h15m early.'),
 'L4_T1_Insight_Synthesis_00002':('segmentation_error','Entire target month fetched; middle gradual-rise stage is labeled fluctuating stable and boundaries shift. Outlier score remains 1. No evidence access omission observed.'),
}
audit=[]
for r in records:
    cause,note=observations[r['task_id']]
    hashes=[hashlib.sha256(s.encode()).hexdigest() for s in r['code_attempts']]
    audit.append({'task_id':r['task_id'],'observed_primary_category':cause,'evidence':note,
                  'identical_code_repeats':len(hashes)-len(set(hashes)),
                  'code_attempt_sha256':hashes,
                  'complementarity_defect_established':False})
with (a.out/'failure-audit.json').open('x') as f:json.dump(audit,f,ensure_ascii=False,indent=2)
with (a.out/'audit.complete.json').open('x') as f:json.dump({
    'complete':True,'records':10,'calls':26,'official_scores_equal':True,
    'source_csv_hashes_unchanged':True,'database_hashes_unchanged':True,
    'all_finish_reasons_stop':True,'visible_thinking_blocks':0,
    'score_and_token_totals_consistent':True},f,indent=2)
print('10 scores match official CLI; 26 stopped calls; source CSV/database hashes unchanged.')
