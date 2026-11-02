import json
import pandas as pd

# Step 1: Load raw_data into a DataFrame
raw_data_df = pd.read_sql_query("SELECT * FROM raw_data", conn)

# Step 2: Sort the DataFrame by timestamp to ensure chronological order
raw_data_df = raw_data_df.sort_values(by='timestamp')

# Step 3: Split the data into two halves
half = len(raw_data_df) // 2
first_half = raw_data_df.iloc[:half]
second_half = raw_data_df.iloc[half:]

# Step 4: Calculate the mean ECG1 value for each half
mean_first_half = first_half['ECG1'].mean()
mean_second_half = second_half['ECG1'].mean()

# Step 5: Compare the means and return 1 or 0
_result = 1 if mean_second_half > mean_first_half else 0

import json
print(json.dumps({"_result": _result}))