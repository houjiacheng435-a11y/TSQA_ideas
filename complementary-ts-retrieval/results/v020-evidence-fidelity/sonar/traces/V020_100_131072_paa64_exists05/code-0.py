import sqlite3
import pandas as pd
import numpy as np
import json

# Step 1: Count the number of distinct rows where ECG1 >= 0.5
sql = """
    SELECT DISTINCT "ECG1"
    FROM raw_data
    WHERE "ECG1" >= 0.5
"""
distinct_rows = pd.read_sql_query(sql, conn)

# Step 2: Multiply the count by 64
total_samples = len(distinct_rows) * 64

# Step 3: Return 1 if total_samples > 0, else 0
_result = 1 if total_samples > 0 else 0

import json
print(json.dumps({"_result": _result}))