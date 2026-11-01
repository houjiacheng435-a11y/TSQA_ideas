"""Post-hoc case illustration, not a candidate-generation input."""
from run import *
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

def main():
    i='L3_T1_Composite_Trend_00007';date='2022-11-27'
    paths={x['id']:ROOT/x['path'] for x in read(OUT/'raw-manifest.json')}
    raw=pd.read_csv(paths[i]);raw.timestamp=pd.to_datetime(raw.timestamp);sub=raw[raw.timestamp.dt.strftime('%Y-%m-%d')==date];v=sub['147'].to_numpy()
    code=(OUT/'executed-code'/f'{i}.py').read_text();functions=code[code.index('def longest_run('):code.index('\nper_day = []')];env={'np':np,'pd':pd};exec(functions,env)
    sm=pd.Series(v).rolling(4,center=True).mean().bfill().ffill().values;dd=np.diff(sm);rstd=pd.Series(dd).rolling(4,center=True).std().bfill().ffill().values
    a,b=env['longest_run'](rstd<float(np.nanmedian(rstd)))
    case={'id':i,'date':date,'released_metric_span_indices_inclusive':[a,b],'released_metric_span_times':[str(sub.timestamp.iloc[a]),str(sub.timestamp.iloc[b])],'released_metric_std':float(np.std(v[a:b+1])),'whole_day_std':float(np.std(v)),'first_48_points_std':float(np.std(v[:48])),'last_48_points_std':float(np.std(v[48:])),'scope':'Ground-truth day chosen only after predictions for illustration. No metadata segment boundaries used.'};dump(OUT/'illustrative-case.json',case)
    fig,ax=plt.subplots(figsize=(9,3.7));hours=np.arange(len(v))/4;ax.plot(hours,v,lw=1.4,color='#234e70');ax.axvspan(a/4,b/4,color='#f3a712',alpha=.35,label='Interval actually measured by released stable metric');ax.set(xlabel='Hour of day (15-minute observations)',ylabel='Channel 147',title=f'CT 00007 | {date} | requested: fluctuating stable segment');ax.legend(fontsize=8,loc='upper left');ax.grid(alpha=.2);fig.tight_layout();fig.savefig(OUT/'ct00007-measured-interval.png',dpi=150);plt.close(fig)

if __name__=='__main__':main()
