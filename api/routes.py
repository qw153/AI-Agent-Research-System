import json
import os
import queue
import threading
import uuid
from datetime import datetime, timezone
from typing import Any, Dict

from fastapi import Depends, FastAPI, Header, HTTPException, Response
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from llm import estimate_cost, get_usage, reset_usage
from main import build_graph
from memory.reports import (
    get_report as get_stored_report,
    list_reports,
    report_to_markdown,
    save_report,
)
from memory.store import (
    load_prior_context,
    new_thread_id,
    remember_report,
    thread_config,
)


app = FastAPI(
    title="AI Agent Research System",
    description="LangGraph-based AI Research Agent API（异步任务）",
    version="1.1.0",
)

# 编译一次 Graph，后续请求直接复用
graph = build_graph()

# API 认证：请求头 X-API-Key 需匹配 .env 里的 API_AUTH_TOKEN；
# 未配置 token 时自动关闭（本地开发方便）。
API_AUTH_TOKEN = os.getenv("API_AUTH_TOKEN", "")


def verify_api_key(
    x_api_key: str = Header(default=None, alias="X-API-Key"),
) -> None:
    if not API_AUTH_TOKEN:
        return
    if x_api_key != API_AUTH_TOKEN:
        raise HTTPException(status_code=403, detail="无效的 API Key")


# 内存任务存储：task_id -> 任务状态（进程重启后丢失，演示够用）
_tasks: Dict[str, Dict[str, Any]] = {}
_tasks_lock = threading.Lock()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _build_payload(query: str, result: Dict[str, Any]) -> Dict[str, Any]:
    """把 LangGraph 结果整理成前端要的 payload。"""
    if result.get("needs_web_search", False):
        return {
            "mode": "research",
            "query": query,
            "research_goal": result.get("research_goal", ""),
            "research_complexity": result.get("research_complexity", ""),
            "research_plan": result.get("research_plan", []),
            "report": result.get("report", {}),
        }
    return {
        "mode": "direct_answer",
        "query": query,
        "research_goal": result.get("research_goal", ""),
        "research_complexity": result.get("research_complexity", ""),
        "answer": result.get("direct_answer", ""),
    }


def _run_research(task_id: str, query: str, conversation_id: str) -> None:
    """后台线程：跑 LangGraph 研究流程，更新任务状态。"""
    with _tasks_lock:
        _tasks[task_id]["status"] = "running"
        _tasks[task_id]["started_at"] = _now()

    try:
        reset_usage()

        prior = load_prior_context(conversation_id)
        effective_query = query
        if prior:
            effective_query = (
                f"{query}\n\n【追问背景：请结合上轮研究结论回答】\n{prior}"
            )

        events = _tasks[task_id]["events"]
        config = thread_config(new_thread_id(conversation_id))

        # 用 stream 逐步推送每个 Agent 的进度事件
        for chunk in graph.stream(
            {"query": effective_query},
            config=config,
            stream_mode="updates",
        ):
            for node, update in chunk.items():
                if isinstance(update, dict):
                    events.put({"type": "node", "node": node, "data": update})
                _tasks[task_id]["stage"] = node

        result = graph.get_state(config).values

        remember_report(conversation_id, result.get("report"))

        payload = _build_payload(query, result)
        usage = get_usage()
        payload["usage"] = usage
        payload["cost_rmb"] = round(estimate_cost(usage), 4)
        report_id = save_report(conversation_id, query, payload)

        with _tasks_lock:
            _tasks[task_id]["status"] = "completed"
            _tasks[task_id]["result"] = payload
            _tasks[task_id]["report_id"] = report_id
            _tasks[task_id]["completed_at"] = _now()

        events.put({"type": "done", "result": payload})

    except Exception as e:
        with _tasks_lock:
            _tasks[task_id]["status"] = "failed"
            _tasks[task_id]["error"] = f"{type(e).__name__}: {e}"
            _tasks[task_id]["completed_at"] = _now()
        try:
            _tasks[task_id]["events"].put(
                {"type": "error", "error": f"{type(e).__name__}: {e}"}
            )
        except Exception:
            pass


class ResearchRequest(BaseModel):
    """Research Agent API 请求体"""

    query: str = Field(
        ...,
        min_length=1,
        description="用户的研究问题",
        examples=["2026年AI Agent的发展趋势是什么？"],
    )

    conversation_id: str = Field(
        "default",
        description="会话 ID；同一 ID 的追问会共享上下文（记忆）",
    )


@app.get("/")
def root():
    return {
        "name": "AI Agent Research System",
        "status": "running",
        "docs": "/docs",
    }


@app.get("/health")
def health():
    return {
        "status": "ok",
        "service": "research-agent",
    }


@app.post("/research", status_code=202, dependencies=[Depends(verify_api_key)])
def create_research(request: ResearchRequest) -> Dict[str, Any]:
    """创建研究任务：立即返回 task_id，后台异步执行。"""
    query = request.query.strip()
    if not query:
        raise HTTPException(status_code=400, detail="query 不能为空")

    task_id = uuid.uuid4().hex

    with _tasks_lock:
        _tasks[task_id] = {
            "task_id": task_id,
            "status": "queued",
            "stage": "queued",
            "query": query,
            "conversation_id": request.conversation_id,
            "created_at": _now(),
            "started_at": None,
            "completed_at": None,
            "result": None,
            "error": None,
            "events": queue.Queue(),
        }

    thread = threading.Thread(
        target=_run_research,
        args=(task_id, query, request.conversation_id),
        daemon=True,
    )
    thread.start()

    return {"task_id": task_id, "status": "queued"}


@app.get("/research/{task_id}", dependencies=[Depends(verify_api_key)])
def get_research(task_id: str) -> Dict[str, Any]:
    """查询任务状态与结果。"""
    with _tasks_lock:
        task = _tasks.get(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="任务不存在")
    # events 是 queue.Queue，无法 JSON 序列化，返回时剔除
    return {k: v for k, v in task.items() if k != "events"}


@app.get("/research/{task_id}/stream", dependencies=[Depends(verify_api_key)])
def stream_research(task_id: str):
    """SSE 流式推送研究进度（每个 Agent 节点一个事件）。"""
    with _tasks_lock:
        task = _tasks.get(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="任务不存在")

    events = task["events"]

    def event_generator():
        while True:
            try:
                item = events.get(timeout=20)
            except queue.Empty:
                # 心跳，保持连接
                yield ": heartbeat\n\n"
                with _tasks_lock:
                    status = task["status"]
                if status in ("completed", "failed"):
                    break
                continue
            yield f"data: {json.dumps(item, ensure_ascii=False)}\n\n"
            if item.get("type") in ("done", "error"):
                break

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.get("/reports", dependencies=[Depends(verify_api_key)])
def reports(limit: int = 50) -> Dict[str, Any]:
    """列出历史报告（仅元信息，不含正文）。"""
    return {"reports": list_reports(limit=limit)}


@app.get("/reports/{report_id}", dependencies=[Depends(verify_api_key)])
def report_detail(report_id: str) -> Dict[str, Any]:
    """查询单个历史报告的完整内容。"""
    report = get_stored_report(report_id)
    if report is None:
        raise HTTPException(status_code=404, detail="报告不存在")
    return report


@app.get("/reports/{report_id}/export", dependencies=[Depends(verify_api_key)])
def report_export(report_id: str):
    """导出历史报告为 Markdown。"""
    report = get_stored_report(report_id)
    if report is None:
        raise HTTPException(status_code=404, detail="报告不存在")
    md = report_to_markdown(report["payload"])
    return Response(
        content=md,
        media_type="text/markdown; charset=utf-8",
        headers={
            "Content-Disposition": f"attachment; filename=report-{report_id[:8]}.md"
        },
    )
