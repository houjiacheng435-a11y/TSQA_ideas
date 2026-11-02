import sqlite3
import pandas as pd
import numpy as np
import json

# Query raw_data for ECG1 values
sql = 'SELECT "ECG1" FROM raw_data'
ecg1_values = pd.read_sql_query(sql, conn)

# Check if any value is >= 0.5
has_value = ecg1_values[ecg1_values >= 0.5].shape[0] > 0

# Assign result
_result = 1 if has_value else 0

import json
print(json.dumps({"_result": _result}))