import sqlite3
import pandas as pd
import numpy as np
import json

# Query raw_data to find the maximum value of ECG1
sql = 'SELECT "ECG1" FROM raw_data'
df = pd.read_sql_query(sql, conn)

# Find the maximum value of ECG1
max_ecg1 = df.max().item()

# Round the maximum value to three decimal places
rounded_max_ecg1 = np.round(max_ecg1, 3)

# Assign the result
_result = rounded_max_ecg1

import json
print(json.dumps({"_result": _result}))