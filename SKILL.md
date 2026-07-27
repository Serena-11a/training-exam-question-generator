---
name: training-exam-question-generator
description: This skill should be used when generating enterprise training, onboarding, or new-employee exam question banks from source materials (PDF/PPTX/DOCX). Trigger scenarios include the user asking to "出培训题/新人考试题/出N道题目/根据PPT出考题", providing training slides/decks and requesting a question bank, or needing to verify/fix an existing question bank against source materials. It enforces a 7-step workflow (read material → parse material → parse template → define requirements → generate → check → finalize) with mandatory consistency verification to prevent the common errors of answer/option/explanation mismatch and data-extraction distortion (wrong numbers, flipped process order, misreading color-coded timelines).
---

# 企业培训考试出题流程

## Overview
本技能将"企业培训/新人考试题库生成"固化为标准七步流程，覆盖从材料读取到试题产出的全过程，并在"检查"环节内置硬核校验，避免批量出题时常见的答案标错、数据提取失真、流程顺序反转、读图漏看颜色框等问题（均来自真实事故复盘）。

## When to Use
- 用户要求根据培训 PPT/PDF/文档出考试题（如"出150道题""根据这5份材料出题库"）
- 用户要求补充出题、按指定题型/模块出题、或要求题目不重复
- 用户要求核查/修复已有题库与原始材料的一致性
- 涉及题型：单选题、多选题、判断题、填空题、简答题

## 七步标准流程

### 第1步：读取材料
- 识别用户提供的源材料（PDF/PPTX/DOCX），确认文件路径与数量
- PDF 文本提取用 PyPDF2；PPTX 提取用 python-pptx（含表格）
- 文本提取质量差（扫描件/图片型）时，用 pymupdf 将关键页渲染为 PNG 供读图
- 将全部源文本汇总到一个带"文档名 + 页码"标记的工作文件（如 `source_full.txt`），便于结构化解析与回溯

### 第2步：解析材料
- 通读提取文本，区分两类知识点：
  - **纯文字型**（定义、理念、制度条文）——出错风险低
  - **结构化型（高风险）**——数字/系数/百分比、日期/时间节点、步骤/流程顺序、表格数据、带颜色范围框的流程图/时间轴
- 对高风险内容，记录"原始文字 + 所属页 + 类型标注"，形成事实清单（唯一事实源）
- 带颜色/色块的流程图或时间轴：**必须按颜色范围框界定的时间区间判定事件归属**，绝不能仅看文字紧邻哪个日期圆圈（典型误判：把粉色范围框归6日的活动错判到28日）

### 第3步：解析试题模板
- **首先加载 `references/sample_output.txt`（黄金标准样例），逐行对照理解正确输出长什么样**
- 然后加载 `references/question_templates.md`，确认五类题型的精确格式规范
- 每题含：题干、选项/答案、解析、难易度、分数；填空含填空项；简答含正确答案/考核点
- 若用户提供自定义模板，以其为准；否则严格沿用 `references/question_templates.md` + `references/sample_output.txt`
- **⛔ 格式红线**：绝对禁止输出"试卷式"格式（答案速查表 + 逐题解析分离），必须每题自含（题干+选项+答案+解析+难易度+分数 全在一起）

### 第4步：确定试题要求
- 与用户确认或默认以下参数：
  - 总题量（如150题）、各题型数量与分布
  - 覆盖模块（如集团简介/企业文化/规章/绩效/报账/信息安全/行业介绍）
  - 难易度与分数权重
  - 是否与已有题库重复（如"不要与之前出的重合"）——需先读取已有题库逐题比对
  - 输出格式（.txt 或考试系统导入格式）

### 第5步：出试题
- **以"事实清单"为唯一事实源**，每道题只引用已核实的原文事实，禁止凭记忆或推断
- **严格按 `sample_output.txt` 的格式输出**：每道题自含（题型标记+题干(答案)+选项+解析+难易度+分数），用空行分隔
- 打乱选项顺序后再标注答案字母；答案字母必须指向正确选项
- 解析文字必须与所标答案一致（解析中出现的关键词/数值/列表应出现在正确选项中）
- 数字、日期、流程顺序逐字照原文，不可简化或"合并"（典型错误：把两个不同等级的系数/日期合并成一个值）

### 第6步：检查试题（关键，不可跳过）
对照 `references/pitfalls_and_checks.md` 执行硬性检查，并运行校验脚本：
- 调用 `scripts/consistency_check.py` 对产出题库做自动化扫描，核查"答案字母 ↔ 选项文字 ↔ 解析文字"三者一致性
- 人工复核高风险题（含数字/日期/顺序/流程），逐题回看源材料原页或截图
- 重点排查四类已知错误模式（详见 references）：
  1. 答案字母标错（答案指向错误选项，但解析文字是对的）
  2. 数字值写错（系数/日期/百分比错填、不同项被合并）
  3. 日期-动作错位（时间线节点对应错误）
  4. 流程顺序反转（步骤先后理解反，常见于流程图提取）
- 对发现的矛盾逐条修正，并记录在题库旁或工作日志中

### 第7步：最终确定产出
- 用脚本精确统计总题数及各题型/模块分布，确认与"第4步要求"完全一致（如要求150题则必须恰好150题）
- 若用户反馈某题有误，回到第2/3步复核原文，修正后同步更新事实清单
- 通过 `present_files` 交付最终题库文件

## Resources
- `references/sample_output.txt` — **⭐ 黄金标准输出样例（必读，优先级最高）**，含正确格式、格式要点对照表、禁止格式示例
- `references/question_templates.md` — 五类题型格式规范与模板定义
- `references/pitfalls_and_checks.md` — 高风险点核查清单与读图方法论（含五类错误模式）
- `scripts/consistency_check.py` — 题库答案/选项/解析一致性自动校验
