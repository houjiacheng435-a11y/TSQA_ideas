import sqlite3
import pandas as pd
import numpy as np
import json

# Step 1: Query raw_data for rows where both ECG1 and ECG2 are >= 0.5
sql = """
    SELECT timestamp, "ECG1", "ECG2"
    FROM raw_data
    WHERE "ECG1" >= 0.5 AND "ECG2" >= 0.5
"""
df = pd.read_sql_query(sql, conn)

# Step 2: Check if there is at least one row that meets the condition
has_row = not df.empty

# Step 3: Return 1 if such a row exists, otherwise return 0
_result = 1 if has_row else 0

import json
print(json.dumps({"_result": _result}))