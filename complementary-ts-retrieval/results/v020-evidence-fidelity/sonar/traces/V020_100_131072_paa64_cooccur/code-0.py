import sqlite3
import pandas as pd
import numpy as np
import json

# Step 1: Count the number of rows where both ECG1 and ECG2 are >= 0.5
sql_query = """
    SELECT COUNT(*) 
    FROM raw_data 
    WHERE "ECG1" >= 0.5 AND "ECG2" >= 0.5
"""
count = pd.read_sql_query(sql_query, conn).iloc[0, 0].item()

# Step 2: Multiply the count by 64
total_samples = count * 64

# Step 3: Return 1 if the result is greater than 0, otherwise return 0
_result = 1 if total_samples > 0 else 0

import json
print(json.dumps({"_result": _result}))