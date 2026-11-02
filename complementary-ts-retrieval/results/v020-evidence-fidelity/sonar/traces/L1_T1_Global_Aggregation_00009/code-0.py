import sqlite3
import pandas as pd
import numpy as np
import json

# Step 1: Query raw_data for channel "154" in June 2019
sql = """
    SELECT "154" AS value
    FROM raw_data
    WHERE timestamp BETWEEN '2019-06-01' AND '2019-06-30'
"""
df = pd.read_sql_query(sql, conn)

# Step 2: Compute the minimum value
min_value = df['value'].min().item()

# Step 3: Round to 3 decimal places
rounded_min_value = round(min_value, 3)

_result = rounded_min_value
import json
print(json.dumps({"_result": _result}))