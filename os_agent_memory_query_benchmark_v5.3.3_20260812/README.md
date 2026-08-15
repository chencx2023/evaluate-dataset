# OS Agent 在线记忆评测集 v5.3.3 - Agent Release

本包是无 Manual Config 的持续在线基线，只包含 Agent 可见的初始 Memory Pool、3-10 轮在线 stream、输出 schema 和裁判控制 runner，不包含 Gold、相关性标签或人工复审材料。

每轮实际 Query、系统实际回答和实际 memory delta 会写回同一 stream；下一轮继续加入环境反馈。正式运行默认使用 test 分区。精准遗忘算法尚未冻结，相关完整 stream 只保留在 experimental runtime，不进入正式分数。

正式测试必须将 Agent Release 与 Judge Release 放在不同权限边界中；目录分开本身不构成防泄漏边界。


## 运行隔离

runner 为每条 stream 创建独立临时工作目录，并提供查询超时、持续 stderr 读取及 terminate/kill 兜底。`--system-workdir` 仅作为隔离目录的父目录使用。
