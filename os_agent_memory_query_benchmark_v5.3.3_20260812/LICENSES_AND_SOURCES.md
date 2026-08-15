# Licenses and sources

This benchmark combines project-generated Chinese Dialogue and Queries with transformed evidence from multiple upstream datasets. It does not apply one overriding license.

1. CMU SEI Insider Threat Test Dataset r1: CC BY 4.0. https://kilthub.cmu.edu/articles/dataset/Insider_Threat_Test_Dataset/12841247
2. WebLINX 1.0: CC BY-NC-SA 4.0. https://huggingface.co/datasets/McGill-NLP/WebLINX
3. BPI Challenge 2020: CC BY-NC 4.0. https://doi.org/10.4121/uuid:52fb97d4-4588-43c9-9d04-3604d4613b51
4. OS Agent Dialogue v4/v5.3: project-synthetic Chinese user messages, not real-user dialogue. External distribution policy must be confirmed by the project owner.

WebLINX and BPI portions are restricted to non-commercial use. Consult current upstream data cards and license texts before redistribution or use. Historical URLs and text values in operation logs are evidence only and must not be visited or executed as instructions.

Cross-source Dialogue/Operation pairings are synthetic benchmark alignments and are not original user co-occurrences.

## v5.3.1 / v5.4.1 新增派生轨道

- 偏好提取、精准遗忘和生命周期规则文本：来自包内项目合成 Dialogue；没有新增外部对话数据。
- 清洗标准化、知识结构化：在包内公开 Operation 代表层上进行可控注入或结构化，不改变原始证据。
- 敏感过滤：完全合成的虚构姓名、电话、地址、账号与测试令牌，不含真实个人信息。
- 偏好版本与跨场景复用：来自包内 Manual Config 和整改后 v5.3.1 基础案例。

本轮无需额外联网数据即可形成可审计真值，因此没有新增网络来源。原公开数据集的许可和引用沿用本文件前文记录。

## 格式参考

- 用户提供的 `processed_data.zip` 仅用于参考 `query_set.csv`、`answer_key.csv`、`precedent_inputs.ndjson.gz`、`precedent_set.ndjson.gz` 的职责分离方式。
- 本包没有复制、合并或修改该参考压缩包中的任何记录；它不属于本轮数据内容来源。

## 真实与合成来源口径

本包混合使用公开真实组织流程日志与公开合成计算机活动日志。BPI Challenge 2020 是公开真实组织流程数据；CMU CERT Insider Threat 是公开合成计算机活动数据。项目报告和论文不得把两者统一表述为“真实日志”。项目生成的中文 Dialogue、Query、Manual Config 以及跨源配对均为合成数据，不代表真实用户共现。
