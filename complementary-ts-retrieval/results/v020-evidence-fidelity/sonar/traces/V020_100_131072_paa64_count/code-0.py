import sqlite3
import pandas as pd
import numpy as np
import json

# Step 1: Extract ECG1 values and timestamps from raw_data
sql = """
    SELECT timestamp, "ECG1" AS value
    FROM raw_data
    ORDER BY timestamp
"""
df = pd.read_sql_query(sql, conn)

# Step 2: Identify contiguous runs of ECG1 >= 0.5
runs = []
current_run = None

for index, row in df.iterrows():
    value = row['value']
    if value >= 0.5:
        if current_run is None:
            current_run = {'start': row['timestamp'], 'end': row['timestamp']}
        current_run['end'] = row['timestamp']
    else:
        if current_run is not None:
            runs.append(current_run)
            current_run = None
if current_run is not None:
    runs.append(current_run)

# Step 3: Count the number of maximal contiguous runs
run_count = len(runs)

# Final result
_result = run_count
import json
print(json.dumps({"_result": _result}))