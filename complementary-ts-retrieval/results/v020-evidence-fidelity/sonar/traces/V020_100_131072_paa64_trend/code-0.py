import sqlite3
import pandas as pd
import numpy as np
import json

# Step 1: Load raw_data
raw_data = pd.read_sql_query("SELECT * FROM raw_data", conn)

# Step 2: Split the data into two halves based on the number of rows
num_rows = len(raw_data)
half = num_rows // 2
first_half = raw_data.iloc[:half]
second_half = raw_data.iloc[half:]

# Step 3: Calculate the mean ECG1 for each half
mean_first_half = first_half['ECG1'].mean()
mean_second_half = second_half['ECG1'].mean()

# Step 4: Compare the means and return 1 or 0
_result = 1 if mean_second_half > mean_first_half else 0

import json
print(json.dumps({"_result": _result}))