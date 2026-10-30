"""Standalone scientific figure; all bars read actual held-out CPU estimates."""
import json
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

HERE=Path(__file__).parent;ROOT=HERE.parents[1];OUT=ROOT/'results/v018-conditional-evidence-value'


def main():
    rs=json.loads((OUT/'cpu-test-summary.json').read_text())
    def row(method,vis):return next(r for r in rs if r['method']==method and r['depth']==2 and r['budget']==3 and r['proxy'] and r['visibility']==vis)
    methods=['content_topk','dependency_topk','conditional_numeric','answer_ig','joint_state_ig','lookahead2']
    labels=['Context Top-K','Dependency Top-K','Conditional numeric','Answer IG (1 step)','Joint-state IG','Lookahead 2 + ties']
    plt.rcParams.update({'font.size':10,'axes.spines.top':False,'axes.spines.right':False})
    fig,axes=plt.subplots(1,2,figsize=(11,4.8),sharey=True,layout='constrained')
    for ax,vis,title,bound in zip(axes,['clear','blind'],['Public driver previews','Hidden driver association'],[1,.5]):
        vals=[];errs=[]
        for m in methods:
            z=row(m,vis)['sufficiency_rate'];vals.append(100*z['mean']);errs.append([100*(z['mean']-z['family_bootstrap_95'][0]),100*(z['family_bootstrap_95'][1]-z['mean'])])
        ax.bar(np.arange(len(methods)),vals,yerr=np.array(errs).T,capsize=3,color=['#aeb5be','#2675a8','#398e60','#b87638','#6e5aa5','#409c9a'])
        ax.axhline(bound*100,color='#b3313c',linestyle='--',label='Public-information upper bound')
        ax.set_xticks(np.arange(len(methods)),labels,rotation=48,ha='right');ax.set_ylim(0,108);ax.set_title(title);ax.legend(fontsize=8,loc='upper left')
    axes[0].set_ylabel('Certified evidence sufficiency (%)')
    fig.suptitle('B3: three fetches, 48 held-out parameter families\nExact numerical verifier; no LLM answering errors included',fontsize=12)
    target=ROOT/'reports/figures/v018-cpu-b3.png';target.parent.mkdir(exist_ok=True)
    assert not target.exists();fig.savefig(target,dpi=180);plt.close(fig);print(target)


if __name__=='__main__':main()
