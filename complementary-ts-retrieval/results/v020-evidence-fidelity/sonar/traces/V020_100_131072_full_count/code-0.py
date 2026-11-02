import sqlite3
import pandas as pd
import numpy as np
import json

# Step 1: Scan the raw_data table to identify all samples where ECG1 is >= 0.5
sql = """
    SELECT timestamp, "ECG1"
    FROM raw_data
    ORDER BY timestamp
"""
df = pd.read_sql_query(sql, conn)

# Step 2: Iterate through the samples to detect maximal contiguous runs
run_count = 0
in_run = False

for index, row in df.iterrows():
    if row["ECG1"] >= 0.5:
        if not in_run:
            run_count += 1
            in_run = True
    else:
        in_run = False

# Step 3: Return the total count of maximal contiguous runs
_result = run_count

import json
print(json.dumps({"_result": _result}))