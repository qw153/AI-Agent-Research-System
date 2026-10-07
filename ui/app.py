import json
import time
from typing import Any, Dict, List

import requests
import streamlit as st


DEFAULT_API_URL = "http://127.0.0.1:8000"

st.set_page_config(
    page_title="AI Research Agent",
    page_icon="🔬",
    layout="wide",
    initial_sidebar_state="expanded",
)


# -----------------------------
# Page styling
# -----------------------------
st.markdown(
    """
    <style>
    .block-container {
        max-width: 1180px;
        padding-top: 2rem;
        padding-bottom: 3rem;
    }

    .hero {
        padding: 2rem 2.2rem;
        border-radius: 18px;
        background: linear-gradient(135deg, #eef5ff 0%, #f8fbff 55%, #ffffff 100%);
        border: 1px solid #dbe7f5;
        margin-bottom: 1.5rem;
    }

    .hero h1 {
        margin: 0 0 .45rem 0;
        font-size: 2.35rem;
    }

    .hero p {
        margin: 0;
        color: #526174;
        font-size: 1.02rem;
    }

    .status-card {
        padding: 1rem 1.2rem;
        border-radius: 12px;
        border: 1px solid #e4eaf2;
        background: #ffffff;
    }

    .source-card {
        padding: .8rem 1rem;
        margin-bottom: .7rem;
        border-radius: 10px;
        background: #f8fafc;
        border: 1px solid #e5eaf0;
    }

    .small-muted {
        color: #718096;
        font-size: .88rem;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


# -----------------------------
# API helpers
# -----------------------------
def _auth_headers() -> Dict[str, str]:
    token = st.session_state.get("api_key", "").strip()
    return {"X-API-Key": token} if token else {}


def api_get(base_url: str, path: str) -> Dict[str, Any]:
    response = requests.get(
        f"{base_url.rstrip('/')}{path}", timeout=10, headers=_auth_headers()
    )
    response.raise_for_status()
    return response.json()


def create_research_task(base_url: str, query: str) -> Dict[str, Any]:
    response = requests.post(
        f"{base_url.rstrip('/')}/research",
        json={"query": query},
        timeout=15,
        headers=_auth_headers(),
    )
    response.raise_for_status()
    return response.json()


def get_task(base_url: str, task_id: str) -> Dict[str, Any]:
    return api_get(base_url, f"/research/{task_id}")


def list_reports(base_url: str) -> List[Dict[str, Any]]:
    response = requests.get(
        f"{base_url.rstrip('/')}/reports", timeout=10, headers=_auth_headers()
    )
    response.raise_for_status()
    return response.json().get("reports", [])


def get_report(base_url: str, report_id: str) -> Dict[str, Any]:
    response = requests.get(
        f"{base_url.rstrip('/')}/reports/{report_id}",
        timeout=10,
        headers=_auth_headers(),
    )
    response.raise_for_status()
    return response.json()


def fetch_export(base_url: str, report_id: str) -> str:
    response = requests.get(
        f"{base_url.rstrip('/')}/reports/{report_id}/export",
        timeout=10,
        headers=_auth_headers(),
    )
    response.raise_for_status()
    return response.text


def stream_research(base_url: str, task_id: str):
    """订阅研究进度 SSE，逐个 yield 事件 dict。"""
    url = f"{base_url.rstrip('/')}/research/{task_id}/stream"
    with requests.get(
        url, stream=True, timeout=(10, 600), headers=_auth_headers()
    ) as response:
        response.raise_for_status()
        for line in response.iter_lines(decode_unicode=True):
            if not line or not line.startswith("data: "):
                continue
            payload = line[len("data: "):]
            try:
                yield json.loads(payload)
            except json.JSONDecodeError:
                continue


# -----------------------------
# Report rendering
# -----------------------------
def render_sources(sections: List[Dict[str, Any]]) -> None:
    seen = set()
    sources = []

    for section in sections:
        for item in section.get("supporting_evidence", []) or []:
            url = item.get("source_url", "")
            title = item.get("source_title", "") or url
            if url and url not in seen:
                seen.add(url)
                sources.append((title, url))

    if not sources:
        st.info("当前报告没有提取到可展示的来源链接。")
        return

    st.subheader("📚 Evidence & Sources")
    for index, (title, url) in enumerate(sources, start=1):
        st.markdown(
            f"**{index}. {title}**  \n"
            f"<a href=\"{url}\" target=\"_blank\">{url}</a>",
            unsafe_allow_html=True,
        )


def render_report(result: Dict[str, Any]) -> None:
    mode = result.get("mode")

    if mode == "direct_answer":
        st.subheader("💡 Direct Answer")
        st.write(result.get("answer", ""))
        return

    report = result.get("report") or {}

    st.subheader(report.get("title", "Research Report"))

    summary = report.get("executive_summary", "")
    if summary:
        st.markdown("### 📝 Executive Summary")
        st.info(summary)

    sections = report.get("sections", []) or []
    if sections:
        st.markdown("### 🔎 Research Findings")

    for index, section in enumerate(sections, start=1):
        title = section.get("title", f"Finding {index}")
        verdict = section.get("review_verdict", "")
        score = section.get("review_score")

        with st.expander(f"{index}. {title}", expanded=index == 1):
            if verdict or score is not None:
                left, right = st.columns([1, 1])
                with left:
                    st.caption(f"Review verdict: {verdict or 'N/A'}")
                with right:
                    st.caption(f"Review score: {score if score is not None else 'N/A'}")

            finding = section.get("finding", "")
            analysis = section.get("analysis", "")

            if finding:
                st.markdown("**研究发现**")
                st.write(finding)

            if analysis:
                st.markdown("**分析**")
                st.write(analysis)

            evidence = section.get("supporting_evidence", []) or []
            if evidence:
                st.markdown("**Supporting Evidence**")
                for item in evidence:
                    evidence_text = item.get("evidence", "")
                    source_title = item.get("source_title", "")
                    source_url = item.get("source_url", "")

                    st.markdown(f"- {evidence_text}")
                    if source_url:
                        label = source_title or source_url
                        st.markdown(
                            f"  - 来源：[{label}]({source_url})"
                        )

    overall = report.get("overall_analysis", "")
    if overall:
        st.markdown("### 📊 Overall Analysis")
        st.write(overall)

    render_sources(sections)


def render_node_progress(node: str, data: Dict[str, Any]) -> None:
    """根据节点名实时展示研究进度。"""
    if node == "planner":
        st.markdown("**🧠 Planner（规划）**")
        st.write(
            f"研究目标：{data.get('research_goal', '')} ｜ "
            f"复杂度：{data.get('research_complexity', '')} ｜ "
            f"联网搜索：{'是' if data.get('needs_web_search') else '否'}"
        )
        plan = data.get("research_plan", [])
        if plan:
            st.write(f"拆解为 {len(plan)} 个子任务：")
            for t in plan:
                if isinstance(t, dict):
                    st.write(f"- `{t.get('priority', '')}` {t.get('topic', '')}")
    elif node == "research_worker":
        results = data.get("research_results", [])
        st.markdown("**🔎 Researcher（搜索）**")
        for r in results:
            if isinstance(r, dict):
                n = len(r.get("sources", []))
                st.write(f"- 任务 {r.get('task_id')}：{r.get('status')}，{n} 个来源")
    elif node == "evidence_normalizer":
        st.markdown(f"**📚 证据归一化**：{len(data.get('evidence', []))} 条证据")
    elif node == "analyst":
        st.markdown(f"**🧠 Analyst（分析）**：{len(data.get('claims', []))} 个结论")
    elif node == "reviewer":
        st.markdown(f"**🔍 Reviewer（审核）**：{len(data.get('review_results', []))} 条审核")
    elif node == "writer":
        st.markdown("**✍️ Writer（撰写）**：报告已生成")
    elif node == "direct_answer":
        st.markdown("**💬 直接回答**")


# -----------------------------
# Sidebar
# -----------------------------
st.sidebar.title("⚙️ Settings")
api_url = st.sidebar.text_input("FastAPI 地址", DEFAULT_API_URL)

api_key = st.sidebar.text_input(
    "API Key（可选）",
    type="password",
    help="后端 .env 设置了 API_AUTH_TOKEN 时才需要填",
)
st.session_state["api_key"] = api_key

st.sidebar.markdown("---")
st.sidebar.markdown(
    "**当前架构**\n\n"
    "UI → FastAPI → task_id → LangGraph → Research Report"
)

if st.sidebar.button("检查 API 状态"):
    try:
        health = api_get(api_url, "/health")
        st.sidebar.success(f"API 正常：{health.get('status', 'ok')}")
    except Exception as exc:
        st.sidebar.error(f"API 连接失败：{exc}")

st.sidebar.markdown("---")
st.sidebar.markdown("### 📚 历史报告")
try:
    reports = list_reports(api_url)
    if not reports:
        st.sidebar.caption("暂无历史报告")
    for rep in reports[:20]:
        label = (rep.get("title") or rep.get("query") or "未命名")[:28]
        if st.sidebar.button(
            label, key=f"report_{rep['id']}", use_container_width=True
        ):
            st.session_state["selected_report_id"] = rep["id"]
            st.rerun()
except Exception:
    st.sidebar.caption("后端未启动，无法加载历史")


# -----------------------------
# Main UI
# -----------------------------
st.markdown(
    """
    <div class="hero">
        <h1>🔬 AI Research Agent</h1>
        <p>基于 LangGraph 的智能研究与分析系统</p>
    </div>
    """,
    unsafe_allow_html=True,
)

# 会话内对话历史（保留之前的问答，支持接着问）
if "history" not in st.session_state:
    st.session_state["history"] = []

for item in st.session_state["history"]:
    st.markdown(f"### 💬 {item['query']}")
    result = item["result"]
    render_report(result)
    usage = result.get("usage")
    if usage:
        cost = result.get("cost_rmb")
        cost_text = f" ｜ 估算成本 ¥{cost}" if cost is not None else ""
        st.caption(
            f"📊 Token：输入 {usage.get('prompt_tokens', 0)} ｜ "
            f"输出 {usage.get('completion_tokens', 0)} ｜ "
            f"共 {usage.get('total_tokens', 0)}{cost_text}"
        )
    st.markdown("---")

if st.session_state["history"] and st.button("🗑️ 清空对话"):
    st.session_state["history"] = []
    st.rerun()

st.markdown("### 研究问题")
query = st.text_area(
    "",
    placeholder="例如：2026年 AI Agent 的发展趋势是什么？",
    height=120,
    label_visibility="collapsed",
)

example_queries = [
    "2026年AI Agent的发展趋势是什么？",
    "当前企业为什么开始使用AI Agent？",
    "RAG和Agent未来会如何结合？",
]

st.caption("示例问题：")
example_cols = st.columns(len(example_queries))
for col, example in zip(example_cols, example_queries):
    if col.button(example, use_container_width=True):
        query = example

start = st.button("🔍 Start Research", type="primary", use_container_width=True)

if start:
    query = query.strip()

    if not query:
        st.warning("请输入研究问题。")
        st.stop()

    # 1. Create task
    try:
        with st.spinner("正在创建 Research Agent 任务..."):
            task = create_research_task(api_url, query)
    except requests.RequestException as exc:
        st.error(
            "无法连接 FastAPI。请先在另一个终端运行：\n\n"
            "`uvicorn api.routes:app --reload`"
        )
        st.exception(exc)
        st.stop()

    task_id = task["task_id"]
    st.session_state["task_id"] = task_id
    st.session_state["last_query"] = query

    st.success(f"任务已创建：`{task_id}`")

    # 2. 流式订阅研究进度（SSE）
    st.markdown("## 🔄 研究过程")
    result = None
    try:
        for event in stream_research(api_url, task_id):
            etype = event.get("type")
            if etype == "node":
                render_node_progress(event.get("node", ""), event.get("data") or {})
            elif etype == "done":
                result = event.get("result") or {}
                break
            elif etype == "error":
                st.error(f"研究失败：{event.get('error')}")
                st.stop()
    except requests.RequestException as exc:
        st.error(f"流式连接失败：{exc}")
        st.stop()

    if result is None:
        st.warning("未获取到研究结果。")
        st.stop()

    # 3. 存入对话历史并刷新，保留之前的问答
    st.session_state["history"].append({"query": query, "result": result})
    st.rerun()


# -----------------------------
# 历史报告查看
# -----------------------------
selected_id = st.session_state.get("selected_report_id")
if selected_id:
    try:
        rep = get_report(api_url, selected_id)
        payload = rep.get("payload") or {}
        st.markdown("---")
        st.markdown("## 📄 历史报告")
        st.caption(f"原始问题：{rep.get('query', '')}")
        render_report(payload)

        md = fetch_export(api_url, selected_id)
        st.download_button(
            "⬇️ 导出 Markdown",
            data=md,
            file_name=f"report-{selected_id[:8]}.md",
            mime="text/markdown",
        )

        if st.button("← 返回研究"):
            del st.session_state["selected_report_id"]
            st.rerun()
    except Exception as exc:
        st.error(f"加载历史报告失败：{exc}")
