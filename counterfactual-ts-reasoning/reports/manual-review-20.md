# 反事实样本人工审阅包

这份文件只用于在模型推理前检查生成的数据是否自然。它不包含模型输出，也不替代程序化公式核验。长序列不全文展开，而是显示改动位置和关键统计量。

- 固定抽样种子：`manual-review-v1`
- 每组抽取数量：5
- 合计样本：20

| 题目类型 | 反事实类型 | 可用样本 | 本次抽取 |
| --- | --- | ---: | ---: |
| paired_max_flow | answer_changing | 45 | 5 |
| paired_max_flow | answer_preserving | 50 | 5 |
| wind_capacity_factor | answer_changing | 50 | 5 |
| wind_capacity_factor | answer_preserving | 50 | 5 |

<details>
<summary>样本 1：paired_max_flow / 答案应当改变 / tsr-numerical_reasoning-241</summary>

- 父题ID：`tsr-numerical_reasoning-241`
- 题目：The following time series shows traffic density (vehicles/km) and average speed (km/h) on a highway segment during morning rush hour (6:00-9:00 AM). Using the relationship **Flow (q) = Density (k) × Speed (v)**, calculate the **maximum traffic flow capacity** (in vehicles/hour) observed during this period. What is this maximum flow value?
- 选项：A. 72.4；B. 10730.9；C. 4345.6；D. 3935.8
- 原题正确项：C（数值 4345.65）
- 变体正确项：D（数值 3935.8）
- 序列字段：Traffic Density (veh/km)；Average Speed (km/h)
- 实际修改数：11
- 原最大流量：4345.65；修改后最大流量：3935.8
  - t=15：密度 63.8 → 59.8145；速度保持 65.8；流量 4198.04 → 3935.8
  - t=17：密度 67.7 → 66.1478；速度保持 59.5；流量 4028.15 → 3935.8
  - t=18：密度 71.5 → 71.1717；速度保持 55.3；流量 3953.95 → 3935.8
  - t=20：密度 78.3 → 70.9153；速度保持 55.5；流量 4345.65 → 3935.8
  - t=21：密度 68.4 → 64.2055；速度保持 61.3；流量 4192.92 → 3935.8
  - t=22：密度 71.8 → 71.6903；速度保持 54.9；流量 3941.82 → 3935.8
  - t=26：密度 83.6 → 78.2464；速度保持 50.3；流量 4205.08 → 3935.8
  - t=28：密度 84.8 → 81.6555；速度保持 48.2；流量 4087.36 → 3935.8
  - t=32：密度 82 → 77.7825；速度保持 50.6；流量 4149.2 → 3935.8
  - t=35：密度 87.7 → 83.5625；速度保持 47.1；流量 4130.67 → 3935.8
  - t=36：密度 92 → 90.4781；速度保持 43.5；流量 4002 → 3935.8

人工检查：题干和选项未变；修改是否合理；答案保持/改变关系是否符合直觉。

</details>

<details>
<summary>样本 2：paired_max_flow / 答案应当改变 / tsr-numerical_reasoning-235</summary>

- 父题ID：`tsr-numerical_reasoning-235`
- 题目：The following time series shows traffic density (vehicles/km) and average speed (km/h) on a highway segment during morning rush hour (6:00-9:00 AM). Using the relationship **Flow (q) = Density (k) × Speed (v)**, calculate the **maximum traffic flow capacity** (in vehicles/hour) observed during this period. What is this maximum flow value?
- 选项：A. 71.4；B. 4282.8；C. 3858.3；D. 11170.8
- 原题正确项：B（数值 4282.8）
- 变体正确项：C（数值 3858.3）
- 序列字段：Traffic Density (veh/km)；Average Speed (km/h)
- 实际修改数：8
- 原最大流量：4282.8；修改后最大流量：3858.3
  - t=16：密度 75.1 → 68.531；速度保持 56.3；流量 4228.13 → 3858.3
  - t=18：密度 82.1 → 81.0566；速度保持 47.6；流量 3907.96 → 3858.3
  - t=24：密度 82.2 → 78.5804；速度保持 49.1；流量 4036.02 → 3858.3
  - t=26：密度 87 → 85.3605；速度保持 45.2；流量 3932.4 → 3858.3
  - t=28：密度 88.3 → 85.5498；速度保持 45.1；流量 3982.33 → 3858.3
  - t=33：密度 86 → 77.4759；速度保持 49.8；流量 4282.8 → 3858.3
  - t=40：密度 96.1 → 91.8642；速度保持 42；流量 4036.2 → 3858.3
  - t=47：密度 96.3 → 96.2169；速度保持 40.1；流量 3861.63 → 3858.3

人工检查：题干和选项未变；修改是否合理；答案保持/改变关系是否符合直觉。

</details>

<details>
<summary>样本 3：paired_max_flow / 答案应当改变 / tsr-numerical_reasoning-247</summary>

- 父题ID：`tsr-numerical_reasoning-247`
- 题目：The following time series shows traffic density (vehicles/km) and average speed (km/h) on a highway segment during morning rush hour (6:00-9:00 AM). Using the relationship **Flow (q) = Density (k) × Speed (v)**, calculate the **maximum traffic flow capacity** (in vehicles/hour) observed during this period. What is this maximum flow value?
- 选项：A. 3799.1；B. 63.3；C. 10067.7；D. 3530.2
- 原题正确项：A（数值 3799.11）
- 变体正确项：D（数值 3530.2）
- 序列字段：Traffic Density (veh/km)；Average Speed (km/h)
- 实际修改数：9
- 原最大流量：3799.11；修改后最大流量：3530.2
  - t=23：密度 64.9 → 61.1819；速度保持 57.7；流量 3744.73 → 3530.2
  - t=25：密度 58.6 → 55.6813；速度保持 63.4；流量 3715.24 → 3530.2
  - t=26：密度 68.7 → 63.8373；速度保持 55.3；流量 3799.11 → 3530.2
  - t=27：密度 69.6 → 65.4953；速度保持 53.9；流量 3751.44 → 3530.2
  - t=28：密度 73.7 → 68.8147；速度保持 51.3；流量 3780.81 → 3530.2
  - t=30：密度 69.1 → 64.4196；速度保持 54.8；流量 3786.68 → 3530.2
  - t=31：密度 66.8 → 62.261；速度保持 56.7；流量 3787.56 → 3530.2
  - t=33：密度 80.8 → 79.3303；速度保持 44.5；流量 3595.6 → 3530.2
  - t=44：密度 87.8 → 85.065；速度保持 41.5；流量 3643.7 → 3530.2

人工检查：题干和选项未变；修改是否合理；答案保持/改变关系是否符合直觉。

</details>

<details>
<summary>样本 4：paired_max_flow / 答案应当改变 / tsr-numerical_reasoning-231</summary>

- 父题ID：`tsr-numerical_reasoning-231`
- 题目：The following time series shows traffic density (vehicles/km) and average speed (km/h) on a highway segment during morning rush hour (6:00-9:00 AM). Using the relationship **Flow (q) = Density (k) × Speed (v)**, calculate the **maximum traffic flow capacity** (in vehicles/hour) observed during this period. What is this maximum flow value?
- 选项：A. 3834.2；B. 3661.3；C. 9711.3；D. 63.9
- 原题正确项：A（数值 3834.23）
- 变体正确项：B（数值 3661.3）
- 序列字段：Traffic Density (veh/km)；Average Speed (km/h)
- 实际修改数：8
- 原最大流量：3834.23；修改后最大流量：3661.3
  - t=21：密度 68.9 → 68.0538；速度保持 53.8；流量 3706.82 → 3661.3
  - t=23：密度 73.2 → 72.0728；速度保持 50.8；流量 3718.56 → 3661.3
  - t=26：密度 75.7 → 74.1153；速度保持 49.4；流量 3739.58 → 3661.3
  - t=29：密度 85.7 → 84.3617；速度保持 43.4；流量 3719.38 → 3661.3
  - t=30：密度 83.9 → 80.116；速度保持 45.7；流量 3834.23 → 3661.3
  - t=32：密度 90 → 89.7377；速度保持 40.8；流量 3672 → 3661.3
  - t=33：密度 88.7 → 88.4371；速度保持 41.4；流量 3672.18 → 3661.3
  - t=49：密度 98.8 → 97.3749；速度保持 37.6；流量 3714.88 → 3661.3

人工检查：题干和选项未变；修改是否合理；答案保持/改变关系是否符合直觉。

</details>

<details>
<summary>样本 5：paired_max_flow / 答案应当改变 / tsr-numerical_reasoning-210</summary>

- 父题ID：`tsr-numerical_reasoning-210`
- 题目：The following time series shows traffic density (vehicles/km) and average speed (km/h) on a highway segment during morning rush hour (6:00-9:00 AM). Using the relationship **Flow (q) = Density (k) × Speed (v)**, calculate the **maximum traffic flow capacity** (in vehicles/hour) observed during this period. What is this maximum flow value?
- 选项：A. 3141.1；B. 58.1；C. 9013.3；D. 3485.3
- 原题正确项：D（数值 3485.34）
- 变体正确项：A（数值 3141.1）
- 序列字段：Traffic Density (veh/km)；Average Speed (km/h)
- 实际修改数：10
- 原最大流量：3485.34；修改后最大流量：3141.1
  - t=15：密度 57.8 → 52.0912；速度保持 60.3；流量 3485.34 → 3141.1
  - t=19：密度 60.2 → 56.6985；速度保持 55.4；流量 3335.08 → 3141.1
  - t=24：密度 71.4 → 65.9894；速度保持 47.6；流量 3398.64 → 3141.1
  - t=25：密度 80.4 → 77.1768；速度保持 40.7；流量 3272.28 → 3141.1
  - t=26：密度 67.6 → 64.3667；速度保持 48.8；流量 3298.88 → 3141.1
  - t=27：密度 72 → 71.8786；速度保持 43.7；流量 3146.4 → 3141.1
  - t=33：密度 73.5 → 68.8837；速度保持 45.6；流量 3351.6 → 3141.1
  - t=41：密度 89.6 → 88.2331；速度保持 35.6；流量 3189.76 → 3141.1
  - t=42：密度 77.4 → 73.9082；速度保持 42.5；流量 3289.5 → 3141.1
  - t=51：密度 87.1 → 81.3756；速度保持 38.6；流量 3362.06 → 3141.1

人工检查：题干和选项未变；修改是否合理；答案保持/改变关系是否符合直觉。

</details>

<details>
<summary>样本 6：paired_max_flow / 答案保持不变 / tsr-numerical_reasoning-225</summary>

- 父题ID：`tsr-numerical_reasoning-225`
- 题目：The following time series shows traffic density (vehicles/km) and average speed (km/h) on a highway segment during morning rush hour (6:00-9:00 AM). Using the relationship **Flow (q) = Density (k) × Speed (v)**, calculate the **maximum traffic flow capacity** (in vehicles/hour) observed during this period. What is this maximum flow value?
- 选项：A. 3664.8；B. 9857.3；C. 61.1；D. 3480.2
- 原题正确项：A（数值 3664.77）
- 变体正确项：A（数值 3664.77）
- 序列字段：Traffic Density (veh/km)；Average Speed (km/h)
- 实际修改数：1
- 原最大流量：3664.77；修改后最大流量：3664.77
  - t=0：密度 10 → 11；速度保持 90.1；流量 901 → 991.1

人工检查：题干和选项未变；修改是否合理；答案保持/改变关系是否符合直觉。

</details>

<details>
<summary>样本 7：paired_max_flow / 答案保持不变 / tsr-numerical_reasoning-245</summary>

- 父题ID：`tsr-numerical_reasoning-245`
- 题目：The following time series shows traffic density (vehicles/km) and average speed (km/h) on a highway segment during morning rush hour (6:00-9:00 AM). Using the relationship **Flow (q) = Density (k) × Speed (v)**, calculate the **maximum traffic flow capacity** (in vehicles/hour) observed during this period. What is this maximum flow value?
- 选项：A. 3757.2；B. 3269.0；C. 9194.3；D. 62.6
- 原题正确项：A（数值 3757.15）
- 变体正确项：A（数值 3757.15）
- 序列字段：Traffic Density (veh/km)；Average Speed (km/h)
- 实际修改数：1
- 原最大流量：3757.15；修改后最大流量：3757.15
  - t=0：密度 10.1 → 11.11；速度保持 87.9；流量 887.79 → 976.569

人工检查：题干和选项未变；修改是否合理；答案保持/改变关系是否符合直觉。

</details>

<details>
<summary>样本 8：paired_max_flow / 答案保持不变 / tsr-numerical_reasoning-212</summary>

- 父题ID：`tsr-numerical_reasoning-212`
- 题目：The following time series shows traffic density (vehicles/km) and average speed (km/h) on a highway segment during morning rush hour (6:00-9:00 AM). Using the relationship **Flow (q) = Density (k) × Speed (v)**, calculate the **maximum traffic flow capacity** (in vehicles/hour) observed during this period. What is this maximum flow value?
- 选项：A. 8525.1；B. 3019.9；C. 3283.3；D. 54.7
- 原题正确项：C（数值 3283.29）
- 变体正确项：C（数值 3283.29）
- 序列字段：Traffic Density (veh/km)；Average Speed (km/h)
- 实际修改数：1
- 原最大流量：3283.29；修改后最大流量：3283.29
  - t=0：密度 10 → 11；速度保持 90.5；流量 905 → 995.5

人工检查：题干和选项未变；修改是否合理；答案保持/改变关系是否符合直觉。

</details>

<details>
<summary>样本 9：paired_max_flow / 答案保持不变 / tsr-numerical_reasoning-248</summary>

- 父题ID：`tsr-numerical_reasoning-248`
- 题目：The following time series shows traffic density (vehicles/km) and average speed (km/h) on a highway segment during morning rush hour (6:00-9:00 AM). Using the relationship **Flow (q) = Density (k) × Speed (v)**, calculate the **maximum traffic flow capacity** (in vehicles/hour) observed during this period. What is this maximum flow value?
- 选项：A. 62.0；B. 3717.6；C. 9381.8；D. 3504.7
- 原题正确项：B（数值 3717.55）
- 变体正确项：B（数值 3717.55）
- 序列字段：Traffic Density (veh/km)；Average Speed (km/h)
- 实际修改数：1
- 原最大流量：3717.55；修改后最大流量：3717.55
  - t=0：密度 10 → 11；速度保持 94.1；流量 941 → 1035.1

人工检查：题干和选项未变；修改是否合理；答案保持/改变关系是否符合直觉。

</details>

<details>
<summary>样本 10：paired_max_flow / 答案保持不变 / tsr-numerical_reasoning-221</summary>

- 父题ID：`tsr-numerical_reasoning-221`
- 题目：The following time series shows traffic density (vehicles/km) and average speed (km/h) on a highway segment during morning rush hour (6:00-9:00 AM). Using the relationship **Flow (q) = Density (k) × Speed (v)**, calculate the **maximum traffic flow capacity** (in vehicles/hour) observed during this period. What is this maximum flow value?
- 选项：A. 3410.7；B. 10058.1；C. 65.2；D. 3910.2
- 原题正确项：D（数值 3910.2）
- 变体正确项：D（数值 3910.2）
- 序列字段：Traffic Density (veh/km)；Average Speed (km/h)
- 实际修改数：1
- 原最大流量：3910.2；修改后最大流量：3910.2
  - t=0：密度 19.3 → 21.23；速度保持 94.5；流量 1823.85 → 2006.24

人工检查：题干和选项未变；修改是否合理；答案保持/改变关系是否符合直觉。

</details>

<details>
<summary>样本 11：wind_capacity_factor / 答案应当改变 / tsr-numerical_reasoning-314</summary>

- 父题ID：`tsr-numerical_reasoning-314`
- 题目：The following time series shows hourly wind speeds (m/s) and actual power output (MW) for a wind turbine with rated capacity of 1.5 MW. The turbine has cut-in speed 4.0 m/s, rated speed 12.0 m/s, and cut-out speed 25 m/s. Calculate the **capacity factor** (%), defined as: (Total Actual Energy Output / (Rated Power × Hours)) × 100%.
- 选项：A. 62.71；B. 48.98；C. 0.59；D. 58.58
- 原题正确项：D（数值 58.5787）
- 变体正确项：B（数值 48.98）
- 序列字段：Wind Speed (m/s)；Power Output (MW)
- 实际修改数：72
- 原容量因子：58.5787%；修改后容量因子：48.98%
- 原功率序列：长度=72，最小=0.002，最大=1.459，总和=63.265
- 新功率序列：长度=72，最小=0.00167228，最大=1.21993，总和=52.8984
- 修改方式：全部非零功率按 0.83614 倍缩放。

人工检查：题干和选项未变；修改是否合理；答案保持/改变关系是否符合直觉。

</details>

<details>
<summary>样本 12：wind_capacity_factor / 答案应当改变 / tsr-numerical_reasoning-332</summary>

- 父题ID：`tsr-numerical_reasoning-332`
- 题目：The following time series shows hourly wind speeds (m/s) and actual power output (MW) for a wind turbine with rated capacity of 1.5 MW. The turbine has cut-in speed 3.4 m/s, rated speed 12.4 m/s, and cut-out speed 25 m/s. Calculate the **capacity factor** (%), defined as: (Total Actual Energy Output / (Rated Power × Hours)) × 100%.
- 选项：A. 27.62；B. 30.27；C. 23.34；D. 0.28
- 原题正确项：A（数值 27.6215）
- 变体正确项：C（数值 23.34）
- 序列字段：Wind Speed (m/s)；Power Output (MW)
- 实际修改数：60
- 原容量因子：27.6215%；修改后容量因子：23.34%
- 原功率序列：长度=65，最小=0，最大=1.401，总和=26.931
- 新功率序列：长度=65，最小=0，最大=1.18383，总和=22.7565
- 修改方式：全部非零功率按 0.844993 倍缩放。

人工检查：题干和选项未变；修改是否合理；答案保持/改变关系是否符合直觉。

</details>

<details>
<summary>样本 13：wind_capacity_factor / 答案应当改变 / tsr-numerical_reasoning-316</summary>

- 父题ID：`tsr-numerical_reasoning-316`
- 题目：The following time series shows hourly wind speeds (m/s) and actual power output (MW) for a wind turbine with rated capacity of 2.0 MW. The turbine has cut-in speed 3.1 m/s, rated speed 12.8 m/s, and cut-out speed 25 m/s. Calculate the **capacity factor** (%), defined as: (Total Actual Energy Output / (Rated Power × Hours)) × 100%.
- 选项：A. 35.28；B. 37.47；C. 31.28；D. 0.35
- 原题正确项：A（数值 35.28）
- 变体正确项：C（数值 31.28）
- 序列字段：Wind Speed (m/s)；Power Output (MW)
- 实际修改数：75
- 原容量因子：35.28%；修改后容量因子：31.28%
- 原功率序列：长度=80，最小=0，最大=1.91，总和=56.448
- 新功率序列：长度=80，最小=0，最大=1.69345，总和=50.048
- 修改方式：全部非零功率按 0.886621 倍缩放。

人工检查：题干和选项未变；修改是否合理；答案保持/改变关系是否符合直觉。

</details>

<details>
<summary>样本 14：wind_capacity_factor / 答案应当改变 / tsr-numerical_reasoning-333</summary>

- 父题ID：`tsr-numerical_reasoning-333`
- 题目：The following time series shows hourly wind speeds (m/s) and actual power output (MW) for a wind turbine with rated capacity of 3.0 MW. The turbine has cut-in speed 3.1 m/s, rated speed 13.9 m/s, and cut-out speed 25 m/s. Calculate the **capacity factor** (%), defined as: (Total Actual Energy Output / (Rated Power × Hours)) × 100%.
- 选项：A. 11.01；B. 0.14；C. 15.57；D. 14.45
- 原题正确项：D（数值 14.4541）
- 变体正确项：C（数值 15.57）
- 序列字段：Wind Speed (m/s)；Power Output (MW)
- 实际修改数：77
- 原容量因子：14.4541%；修改后容量因子：15.57%
- 原功率序列：长度=82，最小=0，最大=2.169，总和=35.557
- 新功率序列：长度=82，最小=0，最大=2.33646，总和=38.3022
- 修改方式：全部非零功率按 1.07721 倍缩放。

人工检查：题干和选项未变；修改是否合理；答案保持/改变关系是否符合直觉。

</details>

<details>
<summary>样本 15：wind_capacity_factor / 答案应当改变 / tsr-numerical_reasoning-335</summary>

- 父题ID：`tsr-numerical_reasoning-335`
- 题目：The following time series shows hourly wind speeds (m/s) and actual power output (MW) for a wind turbine with rated capacity of 1.5 MW. The turbine has cut-in speed 3.8 m/s, rated speed 12.2 m/s, and cut-out speed 25 m/s. Calculate the **capacity factor** (%), defined as: (Total Actual Energy Output / (Rated Power × Hours)) × 100%.
- 选项：A. 37.84；B. 28.83；C. 42.28；D. 0.38
- 原题正确项：A（数值 37.8421）
- 变体正确项：B（数值 28.83）
- 序列字段：Wind Speed (m/s)；Power Output (MW)
- 实际修改数：76
- 原容量因子：37.8421%；修改后容量因子：28.83%
- 原功率序列：长度=76，最小=0.001，最大=1.382，总和=43.14
- 新功率序列：长度=76，最小=0.00076185，最大=1.05288，总和=32.8662
- 修改方式：全部非零功率按 0.76185 倍缩放。

人工检查：题干和选项未变；修改是否合理；答案保持/改变关系是否符合直觉。

</details>

<details>
<summary>样本 16：wind_capacity_factor / 答案保持不变 / tsr-numerical_reasoning-300</summary>

- 父题ID：`tsr-numerical_reasoning-300`
- 题目：The following time series shows hourly wind speeds (m/s) and actual power output (MW) for a wind turbine with rated capacity of 1.5 MW. The turbine has cut-in speed 3.8 m/s, rated speed 12.6 m/s, and cut-out speed 25 m/s. Calculate the **capacity factor** (%), defined as: (Total Actual Energy Output / (Rated Power × Hours)) × 100%.
- 选项：A. 0.36；B. 31.48；C. 36.42；D. 39.33
- 原题正确项：C（数值 36.4156）
- 变体正确项：C（数值 36.4156）
- 序列字段：Wind Speed (m/s)；Power Output (MW)
- 实际修改数：2
- 原容量因子：36.4156%；修改后容量因子：36.4156%
- 原功率序列：长度=77，最小=0，最大=1.438，总和=42.06
- 新功率序列：长度=77，最小=0，最大=1.438，总和=42.06
  - t=1：功率 0.435 → 0.36；该时刻风速保持 9.7
  - t=12：功率 0.418 → 0.493；该时刻风速保持 9.7

人工检查：题干和选项未变；修改是否合理；答案保持/改变关系是否符合直觉。

</details>

<details>
<summary>样本 17：wind_capacity_factor / 答案保持不变 / tsr-numerical_reasoning-308</summary>

- 父题ID：`tsr-numerical_reasoning-308`
- 题目：The following time series shows hourly wind speeds (m/s) and actual power output (MW) for a wind turbine with rated capacity of 3.0 MW. The turbine has cut-in speed 3.3 m/s, rated speed 13.9 m/s, and cut-out speed 25 m/s. Calculate the **capacity factor** (%), defined as: (Total Actual Energy Output / (Rated Power × Hours)) × 100%.
- 选项：A. 0.16；B. 13.14；C. 16.49；D. 17.38
- 原题正确项：C（数值 16.4942）
- 变体正确项：C（数值 16.4942）
- 序列字段：Wind Speed (m/s)；Power Output (MW)
- 实际修改数：2
- 原容量因子：16.4942%；修改后容量因子：16.4942%
- 原功率序列：长度=69，最小=0，最大=2.796，总和=34.143
- 新功率序列：长度=69，最小=0，最大=2.796，总和=34.143
  - t=0：功率 0.199 → 0.132667；该时刻风速保持 7.7
  - t=60：功率 0.196 → 0.262333；该时刻风速保持 7.7

人工检查：题干和选项未变；修改是否合理；答案保持/改变关系是否符合直觉。

</details>

<details>
<summary>样本 18：wind_capacity_factor / 答案保持不变 / tsr-numerical_reasoning-334</summary>

- 父题ID：`tsr-numerical_reasoning-334`
- 题目：The following time series shows hourly wind speeds (m/s) and actual power output (MW) for a wind turbine with rated capacity of 3.0 MW. The turbine has cut-in speed 3.9 m/s, rated speed 13.9 m/s, and cut-out speed 25 m/s. Calculate the **capacity factor** (%), defined as: (Total Actual Energy Output / (Rated Power × Hours)) × 100%.
- 选项：A. 42.18；B. 0.42；C. 44.61；D. 32.4
- 原题正确项：A（数值 42.1776）
- 变体正确项：A（数值 42.1776）
- 序列字段：Wind Speed (m/s)；Power Output (MW)
- 实际修改数：2
- 原容量因子：42.1776%；修改后容量因子：42.1776%
- 原功率序列：长度=73，最小=0，最大=2.904，总和=92.369
- 新功率序列：长度=73，最小=0，最大=2.904，总和=92.369
  - t=1：功率 1.993 → 1.843；该时刻风速保持 12.9
  - t=7：功率 2.055 → 2.205；该时刻风速保持 12.9

人工检查：题干和选项未变；修改是否合理；答案保持/改变关系是否符合直觉。

</details>

<details>
<summary>样本 19：wind_capacity_factor / 答案保持不变 / tsr-numerical_reasoning-317</summary>

- 父题ID：`tsr-numerical_reasoning-317`
- 题目：The following time series shows hourly wind speeds (m/s) and actual power output (MW) for a wind turbine with rated capacity of 1.5 MW. The turbine has cut-in speed 3.5 m/s, rated speed 13.9 m/s, and cut-out speed 25 m/s. Calculate the **capacity factor** (%), defined as: (Total Actual Energy Output / (Rated Power × Hours)) × 100%.
- 选项：A. 23.57；B. 17.76；C. 22.1；D. 0.22
- 原题正确项：C（数值 22.1048）
- 变体正确项：C（数值 22.1048）
- 序列字段：Wind Speed (m/s)；Power Output (MW)
- 实际修改数：2
- 原容量因子：22.1048%；修改后容量因子：22.1048%
- 原功率序列：长度=77，最小=0，最大=1.459，总和=25.531
- 新功率序列：长度=77，最小=0，最大=1.459，总和=25.531
  - t=0：功率 0.384 → 0.309；该时刻风速保持 10.3
  - t=7：功率 0.393 → 0.468；该时刻风速保持 10.3

人工检查：题干和选项未变；修改是否合理；答案保持/改变关系是否符合直觉。

</details>

<details>
<summary>样本 20：wind_capacity_factor / 答案保持不变 / tsr-numerical_reasoning-307</summary>

- 父题ID：`tsr-numerical_reasoning-307`
- 题目：The following time series shows hourly wind speeds (m/s) and actual power output (MW) for a wind turbine with rated capacity of 3.0 MW. The turbine has cut-in speed 3.7 m/s, rated speed 12.3 m/s, and cut-out speed 25 m/s. Calculate the **capacity factor** (%), defined as: (Total Actual Energy Output / (Rated Power × Hours)) × 100%.
- 选项：A. 0.3；B. 33.65；C. 23.46；D. 29.92
- 原题正确项：D（数值 29.9164）
- 变体正确项：D（数值 29.9164）
- 序列字段：Wind Speed (m/s)；Power Output (MW)
- 实际修改数：2
- 原容量因子：29.9164%；修改后容量因子：29.9164%
- 原功率序列：长度=69，最小=0，最大=2.709，总和=61.927
- 新功率序列：长度=69，最小=0，最大=2.709，总和=61.927
  - t=0：功率 0.263 → 0.175333；该时刻风速保持 7.7
  - t=22：功率 0.275 → 0.362667；该时刻风速保持 7.7

人工检查：题干和选项未变；修改是否合理；答案保持/改变关系是否符合直觉。

</details>
