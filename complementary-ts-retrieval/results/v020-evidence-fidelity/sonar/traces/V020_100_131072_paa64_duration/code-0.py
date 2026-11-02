import sqlite3
import pandas as pd
import numpy as np
import json

# Step 1: Count the number of rows in raw_data where "ECG1" >= 1.0
sql_query = 'SELECT COUNT(*) FROM raw_data WHERE "ECG1" >= 1.0'
result = pd.read_sql_query(sql_query, conn).iloc[0, 0].item()

# Step 2: Multiply the count by 64 to get the total number of samples meeting the threshold
total_samples = int(result * 64)

# Step 3: Return the resulting integer value
_result = total_samples

import json
print(json.dumps({"_result": _result}))