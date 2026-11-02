import sqlite3
import pandas as pd
import numpy as np
import json

# Query raw_data for ECG1 samples with value >= 1.0
sql = """
    SELECT "ECG1" AS value
    FROM raw_data
    WHERE "ECG1" >= 1.0
"""
df = pd.read_sql_query(sql, conn)

# Count the number of samples
count = df.shape[0]

# Convert to native Python type
_result = count.item()

import json
print(json.dumps({"_result": _result}))