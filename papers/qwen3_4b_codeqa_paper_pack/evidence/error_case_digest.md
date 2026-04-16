# Error Case Digest

本页不是统计主表，而是“论文里可以讲的例子池”。

## 使用规则

- 这些案例用于解释机制和边界
- 不替代正式统计结果
- 正例和反例都要用

## Case A: `multi_doc_qa` 的强正例

### A1. MuSiQue 年份推理

- ID: `lb_musique_0efe9b8bd5ade04ff3030e3d944b21b0ac4aa952`
- 问题：`What year did the company that published Starship Command end?`
- 金答案：`1986`
- baseline：输出了与问题无关的中文说明残片
- edge_agent：直接输出 `1986`

可写结论：

> 在需要跨实体链追踪的 MuSiQue 样例中，单轮 baseline 容易给出与问题结构不匹配的解释性残片，而 agent 协议能够收敛到正确年份答案。

### A2. HotpotQA 实体归并

- ID: `lb_hotpotqa_c274ce731f680eb107c70386e2e341615378165e`
- 问题：`What Lithuanian producer is best known for a song that was one of the most popular songs in Ibiza in 2014?`
- 金答案：`Ten Walls`
- baseline：生成了包含证据说明的长句，但没有收敛到最简答案
- edge_agent：直接输出 `Ten Walls`

可写结论：

> 对于需要跨段归并实体的多文档问答，agent 协议的收益之一是把“证据描述”压缩成“最终答案”，减少了回答格式漂移。

## Case B: `code_qa` 的亮点样例

### B1. RepoBench-P 的函数签名恢复

- ID: `lb_repobench-p_3a6d8605dd073af9bf25f05b3895c469345cccd5`
- 金答案：`UserName parseNames(InputStream inputStream);`
- baseline：只输出 `*`
- edge_agent：虽然仍未完全命中金答案，但输出已进入目标代码片段附近，F1 明显提升

可写结论：

> 在仓库级代码补全样例中，baseline 常常直接坍缩为无效符号或提示污染，而 agent 至少能够把输出推进到正确代码区域附近，这也是 `code_qa` 整体收益较高的重要原因。

### B2. LCC 的局部代码定位

- ID: `lb_lcc_79cd419a6f2198575f4b878105dcc71a5fbd4737`
- 金答案：`notifyListeners(new EventObject(this), EventStatusType.ERROR,`
- baseline：输出了提示式废话
- edge_agent：输出进入目标调用附近，F1 从 `0.0` 提升到约 `0.739`

可写结论：

> 对短代码片段定位任务，agent 的优势并不总表现为“完全精确生成”，更常见的是把回答从无关文本推进到目标调用周围，从而显著提升 token-level F1。

## Case C: `single_doc_qa` 的失败模式

### C1. 英文数值抽取被过度协议化

- ID: `lb_multifieldqa_en_238c4efe738cecd8346abfdc57707996aef30f9b`
- 问题：`How many massive star-forming regions were studied?`
- 金答案：`21.`
- baseline：`21`
- edge_agent：输出了关于文本内容的解释性废话，完全偏离目标答案

可写结论：

> 在答案本身很短、定位路径明确的样例中，额外的协议步骤可能把原本可直接抽取的问题变成“解释文本内容”的任务，造成明显回撤。

### C2. 中文数值问答被无关上下文污染

- ID: `lb_multifieldqa_zh_9d2576657011dd8e755c9839af967b132274559e`
- 问题：`玉溪市的旅游总收入增长了多少？`
- 金答案：`35.1%。`
- baseline：`35.1%`
- edge_agent：输出了与工业内容相关的无关描述

可写结论：

> `single_doc_qa` 中的回撤并不局限于英文样例，中文数值抽取同样会受到协议引入的检索与格式污染影响。

## Case D: `multi_doc_qa` 中仍存在的反例

### D1. 2WikiMQA 的 yes/no 问题过生成

- ID: `lb_2wikimqa_cc32d31bbeb3e0d8787e963cf0843ae6b22f3381`
- 问题：`Are both villages, Rhosgoch and Qaleh-Ye Sahar, located in the same country?`
- 金答案：`no`
- baseline：`No`
- edge_agent：输出了实体介绍文本，未收敛到 yes/no

可写结论：

> 尽管 `multi_doc_qa` 整体上获益，但二元判断类问题仍可能因为过度检索和过度生成而受损，说明协议收益并非在所有多文档子类型上均匀分布。

## 推荐在正文里的组织方式

1. 用 A1 或 A2 说明 `multi_doc_qa` 为什么能受益
2. 用 B1 或 B2 说明 `code_qa` 为什么能成为亮点
3. 用 C1 和 C2 解释 `single_doc_qa` 的回撤机制
4. 用 D1 提醒读者：即使多文档整体提升，也仍有失败边界

