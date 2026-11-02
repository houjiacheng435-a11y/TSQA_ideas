import json
import sqlite3
import pandas as pd

# Step 1: Query raw_data to find the maximum value of ECG1
sql = 'SELECT "ECG1" FROM raw_data'
df = pd.read_sql_query(sql, conn)

# Step 2: Find the maximum value and round it to three decimal places
max_ecg1 = df['ECG1'].max().item()
rounded_max_ecg1 = round(max_ecg1, 3)

# Step 3: Output the rounded maximum value
_result = rounded_max_ecg1
import json
print(json.dumps({"_result": _result}))