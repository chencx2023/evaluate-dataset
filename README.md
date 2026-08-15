# OS Agent 记忆评测资料说明

## 文件与用途

命名规则：**不带 `_judge` 的目录是问题/运行输入集**，供被测 Agent 使用；**带 `_judge` 的目录是答案集**，包含 Gold、证据映射、人工复审材料和评分脚本，不能暴露给被测 Agent。

| 目录 | 作用 |
| --- | --- |
| `os_agent_memory_query_benchmark_v5.3.3_20260812/` | 当前使用的 v5.3.3 问题/运行输入集；属于无 Manual Config 的在线记忆基线。 |
| `os_agent_memory_query_benchmark_v5.3.3_20260812_judge/` | v5.3.3 对应的答案集和评分工具。 |
| `os_agent_memory_query_benchmark_v5.4.3_20260812/` | v5.4.3 问题/运行输入集；加入 Manual Config，当前作为已经完成人工打分的版本。 |
| `os_agent_memory_query_benchmark_v5.4.3_20260812_judge/` | v5.4.3 对应的答案集、复审表和评分工具。 |
| `os_agent_memory_query_benchmark_v5.4.4_20260812/` | v5.4.3 的优化版问题/运行输入集；正式能力沿用 v5.4.3，实验部分新增精准遗忘、敏感信息识别、配置与近期偏好判断。 |
| `os_agent_memory_query_benchmark_v5.4.4_20260812_judge/` | v5.4.4 对应的答案集、复审表和评分工具；新增能力目前标为 experimental。 |
| `processed_data/` | 代码组依据早期评测集整理的功能回归集，用于检查检索、证据选择、状态判断、动作和答案生成等功能是否异常。含 200 个答案组，每组 4 种 Query 改写，共 800 条 Query。 |
| `processed_data_v5.4.4_200x4/` | v5.4.4 功能测试集，仍为 200 个案例 × 4 种 Query，共 800 条；其中配置读入 40 例、遗忘后抑制 20 例、敏感信息识别 30 例、正常记忆任务 110 例。 |
| `报告文件/` | 新算法文档，分别说明 Observation、Episode、Candidate、Conflict、Activation、Recession 和 Reflection 模块。 |

原始 `.zip` 均保留。`os_agent_memory_query_benchmark_v5.4.4_20260812(1).zip` 已同时包含 v5.4.4 问题集和 Judge 答案集；单独的 `os_agent_memory_query_benchmark_v5.4.4_20260812_judge(1).zip` 与其中的 Judge 内容逐文件一致。

## 双人评分一致性

1–5 分属于有序等级，因此统一采用 **ordinal-weighted Gwet’s AC2**：它关注两位评审者是否给出相同或相近等级，并对相邻等级给予部分一致权重，比把 1–5 分当作普通连续数值更合适。评分矩阵按“一行一个样本、一列一个评审者”组织。Config 数据第 61 条中的 `138` 按 **4 分**处理。

| 数据集 | Gwet’s AC2 | 完全同分 | 相差不超过 1 分 |
| --- | ---: | ---: | ---: |
| Query Review 200 | **0.934** | 72.5% | 98.0% |
| Config Review 200 | **0.951** | 74.5% | 97.0% |
| 合并 400 条 | **0.943** | 73.5% | 97.5% |

报告中可写：

> 为衡量两位人工评审者在五级有序评分体系下的评分一致性，采用 ordinal-weighted Gwet’s AC2。Query Review 和 Config Review 上的 AC2 分别达到 0.934 和 0.951，合并 400 条样本后的 AC2 为 0.943，表明两位评审者在两类数据上均表现出高度一致的评分结果。

建议表述为“评分结果高度一致”或“采用了高度相近的评分尺度”，不要仅凭最终分数写成“证明两人使用了完全相同的评分标准”。
