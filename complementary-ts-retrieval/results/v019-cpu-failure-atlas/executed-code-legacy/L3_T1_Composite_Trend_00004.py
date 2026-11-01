import re

YEAR = 2021
CH = '123'
K    = 5
pattern_phrase = 'rapid rise, then fall'

# --- 1. Parse the kind sequence ------------------------------------
kinds = []
for part in pattern_phrase.replace("then", ",").split(","):
    toks = part.strip().split()
    if toks:
        kinds.append(toks[-1].lower())

def kind_to_regex(kind):
    if kind == "rise":   return r"[ab]+.*[de]+"
    if kind == "fall":   return r"[de]+.*[ab]+"
    if kind == "stable": return r"(.)\1{3,}"
    return r".*"
sax_regex = ".*".join(kind_to_regex(k) for k in kinds)

# --- 2. Parse target adj / kind / superlative ----------------------
m = re.search(r"the (\w+) (rise|fall|stable) segment is the (\w+)",
              question.lower())
target_adj, target_kind, sup = (m.group(1), m.group(2), m.group(3)) if m \
    else ("rapid", "rise", "fastest")

# --- 3. SAX search -------------------------------------------------
sax_hits = pd.read_sql_query(
    """SELECT window_start FROM daily_feature
       WHERE channel_id = ? AND window_start >= ? AND window_start < ?
             AND sax REGEXP ?""",
    conn, params=(CH, f"{YEAR}-01-01", f"{YEAR + 1}-01-01", sax_regex))
sax_dates = {pd.Timestamp(s).date() for s in sax_hits["window_start"]}

# --- 4. Pull the year of raw data ----------------------------------
year_df = pd.read_sql_query(
    f'SELECT timestamp, "{CH}" FROM raw_data '
    "WHERE timestamp >= ? AND timestamp < ? ORDER BY timestamp",
    conn, params=(f"{YEAR}-01-01", f"{YEAR + 1}-01-01"))
year_df["timestamp"] = pd.to_datetime(year_df["timestamp"])
year_df["date"] = year_df["timestamp"].dt.date

def longest_run(mask):
    best = None
    i = 0
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

def day_metric(v, kind):
    if len(v) < 8:
        return None
    smooth = pd.Series(v).rolling(4, center=True).mean().bfill().ffill().values
    diffs = np.diff(smooth)
    if kind == "rise":
        run = longest_run(diffs > 0)
        return float(smooth[run[1]] - smooth[run[0]]) if run else None
    if kind == "fall":
        run = longest_run(diffs < 0)
        return float(smooth[run[0]] - smooth[run[1]]) if run else None
    # stable: flat run, metric is in-run std
    rstd = pd.Series(diffs).rolling(4, center=True).std().bfill().ffill().values
    flat = longest_run(rstd < float(np.nanmedian(rstd)))
    if flat is None:
        return None
    return float(np.std(v[flat[0]:flat[1] + 1]))

# --- 5. Per-day metric --------------------------------------------
per_day = []
for date, sub in year_df.groupby("date"):
    v = sub[CH].astype(float).values
    m_val = day_metric(v, target_kind)
    if m_val is None:
        continue
    per_day.append({"date": date, "metric": m_val,
                    "in_sax": date in sax_dates})

# --- 6. Direction from the superlative ----------------------------
desc_words = {"fastest", "biggest", "largest", "strongest", "highest",
              "deepest", "most", "sharpest", "steepest"}
asc_words  = {"slowest", "smallest", "least", "mildest",
              "steadiest", "calmest"}
descending = sup in desc_words
if target_kind == "stable" and target_adj == "steady":
    descending = False

# --- 7. Data-driven signal floor ----------------------------------
metrics = np.array([d["metric"] for d in per_day])
if not descending:                          # slowest / smallest / steadiest
    floor = float(np.quantile(metrics, 0.80))
else:                                       # fastest / biggest / most
    floor = float(np.quantile(metrics, 0.50))
per_day = [d for d in per_day if d["metric"] >= floor]

# --- 8. SAX pool first, fallbacks second --------------------------
sax_pool = sorted([d for d in per_day if d["in_sax"]],
                  key=lambda d: d["metric"], reverse=descending)
rest = sorted([d for d in per_day if not d["in_sax"]],
              key=lambda d: d["metric"], reverse=descending)
final = sax_pool + rest
_result = [str(d["date"]) for d in final[:K]]
