import sqlite3
import pandas as pd
import numpy as np
import json

# Query raw_data for channel "147" between 2020-05-20 and 2020-05-31
sql = """
    SELECT timestamp, "147" AS value
    FROM raw_data
    WHERE timestamp BETWEEN '2020-05-20' AND '2020-05-31'
"""
df = pd.read_sql_query(sql, conn)

# Compute the median value
median_value = df['value'].median().item()

# Format the result to 3 decimal places
_result = round(median_value, 3)

import json
print(json.dumps({"_result": _result}))