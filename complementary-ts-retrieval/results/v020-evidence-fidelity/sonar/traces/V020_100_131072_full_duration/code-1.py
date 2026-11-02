import sqlite3
import pandas as pd
import numpy as np
import json

# Connect to the database (assuming the connection is already established)
# For the purpose of this code, we'll assume 'conn' is a valid SQLite connection object

# Query raw_data for ECG1 samples with value >= 1.0
sql = """
    SELECT "ECG1" AS value
    FROM raw_data
    WHERE "ECG1" >= 1.0
"""
df = pd.read_sql_query(sql, conn)

# Count the number of samples
count = df.shape[0]

# Convert to native Python type (count is already an integer, so .item() is not needed)
_result = count

# Print the result in the required JSON format
print(json.dumps({"_result": _result}))