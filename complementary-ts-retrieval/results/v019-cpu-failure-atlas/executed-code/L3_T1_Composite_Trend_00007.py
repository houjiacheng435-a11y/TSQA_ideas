import re
import numpy as np, pandas as pd

CH = '147'
YEAR = 2022
K     = 5
kinds = ['stable', 'stable']
target_kind = 'stable'
target_adj = 'fluctuating'
sup = 'most'

# ---------- SEARCH: SAX regex over the feature index (plain SAX, paper §5.3) ----------
# The paper's own tight fuzzy bands, backref-FREE (so they survive as a SQL string param).
# Do NOT collapse repeated kinds — every requested segment must appear in order. This is the
# paper's original behaviour and is what makes the SAX search actually prune (it verifies only
# ~1/4 of the year, not all of it).
def kind_to_regex(k):
    if k == "rise":   return r"[ab].*[de]"
    if k == "fall":   return r"[de].*[ab]"
    if k == "stable": return r"(?:a{3,}|b{3,}|c{3,}|d{3,}|e{3,})"
    return r".*"
sax_regex = ".*".join(kind_to_regex(k) for k in kinds)
hits = pd.read_sql_query(
    "SELECT window_start FROM daily_feature "
    "WHERE channel_id = ? AND window_start >= ? AND window_start < ? AND sax REGEXP ?",
    conn, params=(CH, f"{YEAR}-01-01", f"{YEAR+1}-01-01", sax_regex))
cand_days = sorted({pd.Timestamp(s).date() for s in hits["window_start"]})

# ---------- FALLBACK (paper Fig.4: SAX too strict -> raw data) ----------
# Fig.4 says an empty SAX result means the approximation was too strict and you must fall back to
# raw data. The same applies when it returns fewer than K days — you cannot rank a top-K answer
# from them. In both cases verify the whole year for this (rare) task; most tasks keep their
# pruned candidate set.
if len(cand_days) < K:
    alld = pd.read_sql_query(
        "SELECT DISTINCT window_start FROM daily_feature "
        "WHERE channel_id = ? AND window_start >= ? AND window_start < ?",
        conn, params=(CH, f"{YEAR}-01-01", f"{YEAR+1}-01-01"))
    cand_days = sorted({pd.Timestamp(s).date() for s in alld["window_start"]})

# ---------- VERIFY: raw data for CANDIDATE days ONLY ----------
cand_strs = [d.isoformat() for d in cand_days]
ph = ",".join("?" * len(cand_strs))
df = pd.read_sql_query(
    f'SELECT timestamp, "{CH}" FROM raw_data '
    f"WHERE substr(timestamp,1,10) IN ({ph}) ORDER BY timestamp",
    conn, params=cand_strs)
df["timestamp"] = pd.to_datetime(df["timestamp"])
df["date"] = df["timestamp"].dt.date

def longest_run(mask):
    best, i = None, 0
    while i < len(mask):
        if mask[i]:
            j = i
            while j + 1 < len(mask) and mask[j + 1]:
                j += 1
            if best is None or (j - i) > (best[1] - best[0]):
                best = (i, j)
            i = j + 1
        else:
            i += 1
    return best

def day_metric(v, kind):                     # amplitude of the longest monotone run (NOT slope)
    if len(v) < 8:
        return None
    sm = pd.Series(v).rolling(4, center=True).mean().bfill().ffill().values
    dd = np.diff(sm)
    if kind == "rise":
        r = longest_run(dd > 0);  return float(sm[r[1]] - sm[r[0]]) if r else None
    if kind == "fall":
        r = longest_run(dd < 0);  return float(sm[r[0]] - sm[r[1]]) if r else None
    rstd = pd.Series(dd).rolling(4, center=True).std().bfill().ffill().values
    f = longest_run(rstd < float(np.nanmedian(rstd)))
    return float(np.std(v[f[0]:f[1] + 1])) if f else None

per_day = []
for date, sub in df.groupby("date"):
    m = day_metric(sub[CH].astype(float).values, target_kind)
    if m is not None:
        per_day.append({"date": date, "metric": m})

# ---------- RANK among candidates -> top-K (keep this floor + ranking exactly) ----------
descending = sup in {"fastest","biggest","largest","strongest","highest",
                     "deepest","most","sharpest","steepest"}
if target_kind == "stable" and target_adj == "steady":
    descending = False
if per_day:
    mvals = np.array([d["metric"] for d in per_day])
    floor = float(np.quantile(mvals, 0.80 if not descending else 0.50))
    kept = [d for d in per_day if d["metric"] >= floor] or per_day
    kept.sort(key=lambda d: d["metric"], reverse=descending)
    _result = [str(d["date"]) for d in kept[:K]]
else:
    _result = []
