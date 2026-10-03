# AI Agent Research Intelligence System

> A multi-agent research system built with LangGraph, designed to automatically plan research tasks, conduct parallel web research, normalize evidence, analyze findings, review source traceability, and generate structured research reports.

**中文名称：AI Agent Research Intelligence System**

---

## 📌 项目简介

AI Agent Research Intelligence System 是一个基于 **LangGraph** 构建的多 Agent 研究分析系统。

用户只需要输入一个研究问题，系统会根据问题的复杂度自动决定是否需要进行 Web Research，并在需要时将复杂问题拆分成多个 Research Task。

随后，多个 Research Worker 可以通过 LangGraph `Send` 机制进行并行研究，并将搜索结果交给 Evidence Normalizer 进行结构化处理。

最终经过：

```text
Planner
   ↓
Research Worker
   ↓
Evidence Normalizer
   ↓
Analyst
   ↓
Reviewer
   ↓
Writer
   ↓
Research Report
```

形成具有**证据来源追踪能力**的研究结果。

对于不需要联网搜索的简单问题，系统可以直接进入 Direct Answer 路径，避免不必要的 Web Search 和 API 调用。

---

## ✨ 核心特性

### 1. Dynamic Research Planning

Planner Agent 不再简单地对所有问题进行固定数量的任务拆分，而是根据用户问题判断：

- Research Goal
- Research Complexity
- 是否需要 Web Search
- Research Task 数量
- 每个 Task 的研究目标
- 所需来源类型
- Task Priority

例如：

```text
什么是 AI Agent？
        ↓
Simple
        ↓
无需 Web Search
        ↓
Direct Answer
```

而对于：

```text
分析 2026 年 AI Agent 的发展趋势
```

系统可以判断为需要进行 Research，并生成多个研究任务。

---

### 2. Conditional Research Routing

Planner 完成决策后，系统根据：

```python
needs_web_search
```

选择不同执行路径。

```text
                 ┌── needs_web_search=False ──→ Direct Answer
User → Planner ──┤
                 └── needs_web_search=True ───→ Research Pipeline
```

这样可以避免所有问题都经过搜索流程。

---

### 3. LangGraph Send Parallel Research

对于复杂研究问题，Planner 会生成多个 Research Tasks。

系统通过 LangGraph 的 `Send` 机制动态创建 Research Worker：

```text
                Planner
                   │
          Research Task List
                   │
        ┌──────────┼──────────┐
        ↓          ↓          ↓
     Worker 1   Worker 2   Worker 3
        │          │          │
        └──────────┼──────────┘
                   ↓
          Research Results
```

每个 Worker 只负责一个 Task。

这种设计使 Research Worker 可以独立执行不同研究方向，而不是由一个 Agent 顺序完成所有搜索任务。

---

### 4. Web Research with Tavily

Research Worker 使用 Tavily 进行网页搜索。

Research Pipeline：

```text
Research Task
     ↓
Generate Search Query
     ↓
Tavily Web Search
     ↓
Collect Sources
     ↓
Research Results
```

每个 Research Result 会保留：

- Task ID
- Topic
- Objective
- Search Query
- Source Title
- Source URL
- Source Content

从而为后续 Evidence Normalization 和 Analysis 提供输入。

---

### 5. Evidence Normalization

Research Worker 获取的搜索结果属于原始研究数据，结构并不适合直接交给 Analyst。

因此系统增加了独立的：

> **Evidence Normalizer Agent**

将原始搜索结果转换成统一结构：

```json
{
  "task_id": 1,
  "claim": "A factual claim",
  "evidence": "Supporting information",
  "source_title": "Original source title",
  "source_url": "https://example.com",
  "source_type": "official",
  "confidence": "high"
}
```

---

## 🔗 Source Traceability

项目特别关注研究结果的**来源可追溯性**。

核心数据链路：

```text
Claim
  ↓
Evidence
  ↓
Source Title
  ↓
Source URL
```

Evidence Normalizer 会验证：

1. `source_url` 必须存在
2. URL 必须来自 Research Worker 原始搜索结果
3. 不允许 LLM 自行生成 URL
4. 不允许修改或替换原始 URL
5. 不同 URL 支持同一 Claim 时分别保留
6. Source Title 从原始搜索结果复制

因此最终 Analyst 的每一个重要 Finding 都可以追溯到具体网页来源。

---

### 6. Analyst Agent

Analyst Agent 不执行新的 Web Search。

它只基于 Evidence Normalizer 提供的结构化 Evidence 进行分析。

主要任务：

- 提取核心 Findings
- 合并重复信息
- 识别技术趋势
- 对比不同技术或方案
- 区分事实与分析
- 识别来源之间的冲突
- 判断 Finding 的 confidence
- 保留对应的 Task ID
- 保留 Supporting Evidence 和 Source URL

每次最多输出 5 个核心 Findings。

示例结构：

```json
{
  "claims": [
    {
      "title": "核心结论",
      "finding": "核心发现",
      "supporting_evidence": [
        {
          "evidence": "支持该结论的证据",
          "source_title": "Source Title",
          "source_url": "https://example.com/source"
        }
      ],
      "analysis": "基于证据的分析。",
      "confidence": "high",
      "related_task_ids": [1, 2]
    }
  ]
}
```

---

### 7. Reviewer Agent

Reviewer Agent 对 Analyst 生成的 Findings 进行进一步检查。

重点检查：

- Claim 是否有 Evidence 支持
- Evidence 是否存在对应来源
- Source URL 是否有效
- Findings 是否存在明显问题
- Evidence 与 Claim 是否匹配
- 来源是否可以追溯

Reviewer 的作用不是重新进行研究，而是作为一个独立的质量控制环节。

整体流程：

```text
Research
   ↓
Evidence Normalizer
   ↓
Analyst
   ↓
Reviewer
   ↓
Writer
```

---

### 8. Writer Agent

Writer Agent 根据经过 Analyst 和 Reviewer 处理后的研究结果生成最终研究报告。

Writer 负责：

- 整理研究结果
- 组织报告结构
- 汇总核心 Findings
- 保留分析结论
- 保留证据来源
- 输出最终 Research Report

最终用户看到的是经过多个 Agent 处理后的结构化研究结果，而不是简单的搜索结果拼接。

---

### 9. Direct Answer Path

并不是所有问题都需要 Web Search。

对于不需要实时信息的简单问题，Planner 可以直接将请求路由到：

```text
Direct Answer
```

例如：

```text
什么是 RAG？
```

执行：

```text
User
 ↓
Planner
 ↓
needs_web_search = False
 ↓
Direct Answer
 ↓
END
```

而不是：

```text
Planner
 ↓
Tavily
 ↓
Research Worker
 ↓
Evidence Normalizer
 ↓
Analyst
```

从而减少不必要的搜索和 API 调用。

---

### 10. LLM Output Validation

LLM 输出并不总能保证严格符合 JSON 格式，因此项目增加了 JSON 解析和验证机制。

系统会处理：

- JSON Code Fence
- 多余文本
- JSON 提取
- JSON Parse Error
- Root Type Validation
- List Type Validation
- Evidence Field Validation
- Source URL Validation

例如 Analyst 输出异常时：

```text
LLM Output
    ↓
JSON Parser
    ↓
Validation
    ↓
Valid → Continue
    │
    └── Invalid → Raise Error
```

避免错误格式的 LLM 输出直接污染后续 Agent State。

---

## 🏗️ System Architecture

整体架构：

```text
                              ┌──────────────────┐
                              │      User        │
                              └────────┬─────────┘
                                       │
                                       ▼
                              ┌──────────────────┐
                              │     Planner      │
                              │                  │
                              │ Goal             │
                              │ Complexity       │
                              │ Task Planning    │
                              │ Web Search?      │
                              └────────┬─────────┘
                                       │
                         ┌─────────────┴─────────────┐
                         │                           │
                Web Search = False          Web Search = True
                         │                           │
                         ▼                           ▼
                ┌────────────────┐        ┌──────────────────┐
                │ Direct Answer  │        │ Research Router  │
                └───────┬────────┘        └────────┬─────────┘
                        │                          │
                        │                    LangGraph Send
                        │                          │
                        │              ┌───────────┼───────────┐
                        │              ▼           ▼           ▼
                        │         ┌─────────┐ ┌─────────┐ ┌─────────┐
                        │         │Worker 1 │ │Worker 2 │ │Worker N │
                        │         └────┬────┘ └────┬────┘ └────┬────┘
                        │              │           │           │
                        │              └───────────┼───────────┘
                        │                          ▼
                        │                ┌─────────────────────┐
                        │                │ Evidence Normalizer │
                        │                └──────────┬──────────┘
                        │                           │
                        │                           ▼
                        │                ┌─────────────────────┐
                        │                │       Analyst       │
                        │                └──────────┬──────────┘
                        │                           │
                        │                           ▼
                        │                ┌─────────────────────┐
                        │                │      Reviewer       │
                        │                └──────────┬──────────┘
                        │                           │
                        │                           ▼
                        │                ┌─────────────────────┐
                        │                │       Writer        │
                        │                └──────────┬──────────┘
                        │                           │
                        └───────────────┬───────────┘
                                        ▼
                                      END
```

---

## 🔄 Agent Workflow

### Research Path

```text
User Query
    ↓
Planner
    ↓
Research Plan
    ↓
Research Router
    ↓
LangGraph Send
    ↓
Parallel Research Workers
    ↓
Research Results
    ↓
Evidence Normalizer
    ↓
Structured Evidence
    ↓
Analyst
    ↓
Findings
    ↓
Reviewer
    ↓
Validated Findings
    ↓
Writer
    ↓
Final Research Report
```

### Direct Answer Path

```text
User Query
    ↓
Planner
    ↓
needs_web_search = False
    ↓
Direct Answer
    ↓
END
```

---

# 📁 Project Structure

```text
AI Agent Research System/
│
├── agents/
│   ├── planner.py
│   ├── researcher.py
│   ├── evidence_normalizer.py
│   ├── analyst.py
│   ├── reviewer.py
│   ├── writer.py
│   └── direct_answer.py
│
├── graph/
│   ├── state.py
│   └── router.py
│
├── memory/
│   └── store.py
│
├── prompts/
│   ├── planner.txt
│   ├── evidence_normalizer.txt
│   ├── analyst.txt
│   └── ...
│
├── tools/
│   ├── search_tool.py
│   └── json_utils.py
│
├── tests/
│
├── main.py
├── ui.py
├── requirements.txt
├── .env.example
├── .gitignore
└── README.md
```

---

# 🧩 Core Modules

## Planner

```text
agents/planner.py
```

负责：

- 分析用户研究问题
- 判断研究复杂度
- 生成 Research Goal
- 判断是否需要 Web Search
- 生成 Research Plan

Planner 输出的核心状态包括：

```text
research_goal
research_complexity
needs_web_search
research_plan
```

---

## Research Worker

```text
agents/researcher.py
```

负责：

- 根据 Research Task 生成 Search Query
- 调用 Tavily
- 获取网页搜索结果
- 保存 Source
- 返回 Research Result

一个 Worker 一次只负责一个 Task。

多个 Task 的并行执行由 LangGraph `Send` 完成。

---

## Research Router

```text
graph/router.py
```

负责将 Planner 生成的 Research Tasks 转换成 LangGraph `Send`。

核心逻辑：

```python
Send(
    "research_worker",
    {
        "query": query,
        "task": task
    }
)
```

---

## Evidence Normalizer

```text
agents/evidence_normalizer.py
```

负责：

```text
Raw Search Results
       ↓
Structured Evidence
```

并验证：

```text
source_url
     ↓
是否来自原始 Search Results
```

从而阻止 LLM 产生不存在的来源。

---

## Analyst

```text
agents/analyst.py
```

负责：

```text
Evidence
   ↓
Findings
   ↓
Analysis
```

最多输出 5 个核心 Findings。

每个 Finding 都要求保留：

```text
supporting_evidence
source_title
source_url
confidence
related_task_ids
```

---

## Reviewer

```text
agents/reviewer.py
```

负责对 Analyst 结果进行质量检查。

主要检查：

```text
Claim
 ↓
Evidence
 ↓
Source
```

是否能够形成完整的证据链。

---

## Writer

```text
agents/writer.py
```

负责将经过分析和审查后的结果组织为最终 Research Report。

---

## Direct Answer

```text
agents/direct_answer.py
```

对于无需联网研究的问题，直接生成答案。

这样可以绕过：

```text
Research Worker
Evidence Normalizer
Analyst
Reviewer
Writer
```

减少不必要的计算和 Web Search。

---

# 🧠 State Design

项目使用 LangGraph `StateGraph` 管理 Agent 之间的数据流。

核心 State：

```python
class ResearchState(TypedDict, total=False):

    query: str

    research_goal: str

    research_complexity: str

    needs_web_search: bool

    research_plan: List[Dict[str, Any]]

    task: Dict[str, Any]

    research_results: Annotated[
        List[Dict[str, Any]],
        operator.add
    ]

    claims: List[Dict[str, Any]]

    direct_answer: str
```

其中：

```python
Annotated[
    List[Dict[str, Any]],
    operator.add
]
```

用于合并多个并行 Research Worker 返回的结果。

例如：

```text
Worker 1 → [Result 1]
Worker 2 → [Result 2]
Worker 3 → [Result 3]
```

最终：

```text
research_results
=
[
    Result 1,
    Result 2,
    Result 3
]
```

---

# 🔍 Evidence Traceability

这是本项目的重要设计之一。

普通 Research Agent 通常容易出现：

```text
LLM → Conclusion
```

但无法回答：

> 这个结论来自哪里？

本项目设计了：

```text
Source
  ↓
Evidence
  ↓
Claim
  ↓
Finding
```

例如：

```json
{
  "claim": "某技术正在被更多企业采用",
  "evidence": "来源中的具体支持信息",
  "source_title": "Original Source",
  "source_url": "https://example.com",
  "confidence": "high"
}
```

Analyst 最终输出：

```json
{
  "title": "核心发现",
  "finding": "研究结论",
  "supporting_evidence": [
    {
      "evidence": "支持信息",
      "source_title": "Original Source",
      "source_url": "https://example.com"
    }
  ]
}
```

这样可以实现：

```text
Finding
   ↓
Supporting Evidence
   ↓
Original Source URL
```

---

# 🛡️ Reliability & Error Handling

项目针对 Agent 系统中常见的 LLM 非结构化输出问题进行了处理。

## JSON Parsing

LLM 可能返回：

```text
```json
{
    ...
}
```
```

或者：

```text
Here is the result:

{
    ...
}
```

因此系统通过 JSON parsing utility 对输出进行提取和解析。

---

## JSON Validation

系统会验证：

```text
Root Object
      ↓
Expected Field
      ↓
List Type
      ↓
Item Type
      ↓
Required Fields
```

例如：

```text
Analyst
 ↓
claims
 ↓
list?
 ↓
claim object?
 ↓
supporting_evidence?
 ↓
source_url?
```

---

## Source URL Validation

Evidence Normalizer 会检查：

```text
LLM generated URL
       ↓
是否存在于原始搜索结果？
       │
    ┌──┴──┐
   Yes    No
    │      │
 Accept   Reject
```

这可以降低 LLM 幻觉来源的问题。

---

## Context Size Control

Research 过程中可能产生大量搜索结果。

因此 Analyst 会限制传入的 Evidence 数量：

```python
MAX_EVIDENCE = 30
```

避免一次向 LLM 注入过多上下文。

---

# 💾 Memory

项目包含 `memory/` 模块，为后续 Memory 能力提供基础。

当前 Memory 模块主要用于持久化存储研究系统相关信息，为后续实现：

- Short-term Memory
- Long-term Memory
- Memory Retrieval
- Context Compression
- Relevant Memory Selection

提供基础结构。

Memory 方向的设计目标是避免长期运行的 Agent 将所有历史信息直接塞入 Context Window。

后续可以进一步扩展：

```text
User Query
    ↓
Memory Retrieval
    ↓
Relevant Memories
    ↓
Context Construction
    ↓
Agent
```

以及：

```text
Short-term Memory
       ↓
Sliding Window
       ↓
Context Compression
       ↓
Long-term Memory
```

---

# 🛠️ Tech Stack

| Technology | Purpose |
|---|---|
| Python | Core programming language |
| LangGraph | Agent workflow orchestration |
| OpenAI SDK | LLM API client |
| DeepSeek-compatible API | LLM backend |
| Tavily | Web Search |
| SQLite | Local memory persistence |
| python-dotenv | Environment configuration |
| JSON | Structured Agent communication |

---

# ⚙️ Environment Setup

## 1. Clone Repository

```bash
git clone https://github.com/<your-username>/ai-agent-research-intelligence.git
```

进入项目：

```bash
cd ai-agent-research-intelligence
```

---

## 2. Create Virtual Environment

推荐使用 Python 3.11+。

```bash
python -m venv .venv
```

Windows：

```bash
.venv\Scripts\activate
```

Linux / macOS：

```bash
source .venv/bin/activate
```

---

## 3. Install Dependencies

```bash
pip install -r requirements.txt
```

---

## 4. Configure Environment Variables

复制：

```text
.env.example
```

创建：

```text
.env
```

然后填写：

```env
LLM_API_KEY=your_llm_api_key
LLM_BASE_URL=your_llm_base_url
LLM_MODEL=your_llm_model

TAVILY_API_KEY=your_tavily_api_key
```

例如：

```env
LLM_API_KEY=xxxxxxxx
LLM_BASE_URL=https://your-compatible-api-endpoint/v1
LLM_MODEL=your-model

TAVILY_API_KEY=xxxxxxxx
```

> **不要将 `.env` 提交到 GitHub。**

---

# ▶️ Run

在项目根目录运行：

```bash
python main.py
```

然后输入研究问题：

```text
请输入你的研究问题：
> 分析 2026 年 AI Agent 的发展趋势
```

系统会启动 Research Workflow。

---

# 🧪 Example Workflow

例如输入：

```text
分析 2026 年 AI Agent 的发展趋势
```

Planner 可能生成：

```text
Research Goal:
全面分析 AI Agent 的技术、应用和产业发展趋势

Complexity:
medium

Needs Web Search:
True
```

然后生成多个 Research Tasks：

```text
Task 1
Topic: AI Agent 技术发展
Objective: 分析核心技术演进

Task 2
Topic: AI Agent 应用
Objective: 分析主要应用方向

Task 3
Topic: AI Agent 产业生态
Objective: 分析主要平台和企业布局
```

随后：

```text
Task 1 ──→ Research Worker
Task 2 ──→ Research Worker
Task 3 ──→ Research Worker
                 ↓
        Evidence Normalizer
                 ↓
              Analyst
                 ↓
              Reviewer
                 ↓
              Writer
```

最终生成结构化研究结果。

---

# 📊 Example Output

终端会输出类似：

```text
============================================================
🧠 Planner Decision
============================================================

Research Goal:
全面分析当前 AI Agent 的技术与产业发展趋势

Complexity:
medium

Needs Web Search:
True


============================================================
📋 Research Plan
============================================================

Task 1
Topic: AI Agent Technology
Objective: ...

Task 2
Topic: AI Agent Applications
Objective: ...

============================================================
📚 Evidence Normalizer
============================================================

Total Evidence: 10


============================================================
🧠 Analyst Agent
============================================================

Analyst generated 5 findings


============================================================
🔎 Reviewer Agent
============================================================

Claims to review: 5
Available evidence: 10

Review completed


============================================================
✍️ Writer Agent
============================================================

Generating final report...


============================================================
✅ Workflow completed.
============================================================
```

---

# 🧱 Design Principles

## 1. Separation of Responsibilities

每个 Agent 只负责自己的职责：

```text
Planner
→ Planning

Researcher
→ Searching

Evidence Normalizer
→ Evidence Structuring

Analyst
→ Analysis

Reviewer
→ Quality Control

Writer
→ Report Generation
```

避免让一个 Agent 同时承担：

```text
Planning
Search
Analysis
Verification
Writing
```

---

## 2. Structured State

Agent 之间不直接依赖自然语言传递上下文，而是通过 LangGraph State 传递结构化数据。

例如：

```text
Planner
    ↓
research_plan

Research Worker
    ↓
research_results

Evidence Normalizer
    ↓
evidence

Analyst
    ↓
claims
```

这样可以降低 Agent 之间的数据耦合。

---

## 3. Evidence First

分析 Agent 不应该直接根据搜索结果自由发挥。

系统采用：

```text
Search
 ↓
Evidence
 ↓
Analysis
```

而不是：

```text
Search
 ↓
LLM
 ↓
Conclusion
```

从架构上强化研究结果的可追溯性。

---

## 4. Fail Fast

对于结构化输出错误：

```text
Invalid JSON
Invalid Field
Invalid Source URL
Invalid Data Type
```

系统优先进行验证并暴露错误，而不是继续向后传播错误数据。

---

# 📈 Future Improvements

当前项目已经完成核心 Research Agent Pipeline，后续可以继续扩展：

### Memory

```text
Short-term Memory
        ↓
Sliding Window
        ↓
Memory Compression
        ↓
Long-term Memory
        ↓
Relevant Memory Retrieval
```

---

### Semantic Memory Retrieval

目前 Memory Retrieval 可以进一步升级为：

```text
Query
 ↓
Embedding
 ↓
Vector Search
 ↓
Relevant Memories
 ↓
Reranking
```

---

### Research Cache

针对相同或高度相似的研究问题，可以增加：

```text
Query
 ↓
Cache Check
 ↓
Existing Research?
 ├── Yes → Reuse
 └── No  → New Research
```

减少重复 Web Search。

---

### Better Source Ranking

未来可以对来源进行更加细粒度的排序：

```text
Official Documentation
        ↓
Research Paper
        ↓
Major News
        ↓
Community
```

结合：

- source type
- confidence
- relevance
- recency

进行综合排序。

---

### Human-in-the-loop

未来可以增加人工审核：

```text
Planner
   ↓
Research
   ↓
Analyst
   ↓
Human Review
   ↓
Writer
```

允许用户在最终报告生成前修改或确认关键 Findings。

---

# 🎯 Project Highlights

这个项目重点解决的并不是“调用一次 LLM API”。

核心设计集中在：

```text
1. Dynamic Planning
        ↓
2. Parallel Agent Execution
        ↓
3. Evidence Normalization
        ↓
4. Source Traceability
        ↓
5. Multi-Agent Analysis
        ↓
6. Independent Review
        ↓
7. Structured Report Generation
```

相比简单的：

```text
User → LLM → Answer
```

该系统更关注：

- Agent Workflow
- State Management
- Parallel Execution
- Tool Calling
- Structured Output
- Evidence Traceability
- Error Handling
- Context Management
- Multi-Agent Collaboration

---

# 📚 Project Learning Goals

通过该项目实践以下 Agent Engineering 能力：

- LangGraph `StateGraph`
- LangGraph `Send`
- Multi-Agent Workflow
- Agent State Design
- Dynamic Routing
- Web Search Tool Integration
- LLM Structured Output
- JSON Parsing & Validation
- Evidence Traceability
- Source Verification
- Research Agent Design
- Memory Architecture
- Context Window Management

---

# 👨‍💻 Author

**范益民**

AI / Agent Application Development

GitHub:

```text
https://github.com/<your-username>
```

---

# 📄 License

This project is for learning, research, and portfolio purposes.