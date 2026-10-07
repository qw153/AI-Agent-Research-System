"""研究报告持久化存储。

优先用 SQLite 持久化；SQLite 打不开（目录不可写等）时自动回退到内存，
保证接口始终可用。用户正常机器上 SQLite 会正常持久化。
"""
import json
import os
import sqlite3
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = Path(os.getenv("REPORTS_DB_PATH", str(BASE_DIR / "research_reports.sqlite")))

# SQLite 不可用时的内存后备（进程内有效）
_lock = threading.Lock()
_mem: Dict[str, Dict[str, Any]] = {}
_mem_seq: List[str] = []
_sqlite_usable: Optional[bool] = None


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    return conn


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _use_sqlite() -> bool:
    """首次调用时检测 SQLite 是否可用（目录是否可写）。"""
    global _sqlite_usable
    if _sqlite_usable is None:
        try:
            with _connect() as conn:
                conn.execute(
                    "CREATE TABLE IF NOT EXISTS reports ("
                    "id TEXT PRIMARY KEY, conversation_id TEXT, query TEXT, "
                    "mode TEXT, title TEXT, summary TEXT, payload_json TEXT, "
                    "created_at TEXT)"
                )
            _sqlite_usable = True
        except Exception:
            _sqlite_usable = False
    return _sqlite_usable


def save_report(conversation_id: str, query: str, payload: Dict[str, Any]) -> str:
    """保存一次研究结果，返回 report id。"""
    report_id = uuid.uuid4().hex

    mode = payload.get("mode", "research")
    if mode == "direct_answer":
        answer = str(payload.get("answer", "")).strip()
        title = query[:60] or "直接回答"
        summary = answer[:200]
    else:
        report = payload.get("report") or {}
        title = str(report.get("title", "")).strip() or query[:60] or "研究报告"
        summary = str(report.get("executive_summary", "")).strip()[:200]

    created_at = _now()

    if _use_sqlite():
        try:
            with _connect() as conn:
                conn.execute(
                    "INSERT INTO reports "
                    "(id, conversation_id, query, mode, title, summary, payload_json, created_at) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    (report_id, conversation_id, query, mode, title, summary,
                     json.dumps(payload, ensure_ascii=False), created_at),
                )
            return report_id
        except Exception:
            pass  # 中途失败，走内存

    with _lock:
        _mem[report_id] = {
            "id": report_id,
            "conversation_id": conversation_id,
            "query": query,
            "mode": mode,
            "title": title,
            "summary": summary,
            "payload": payload,
            "created_at": created_at,
        }
        _mem_seq.insert(0, report_id)
    return report_id


def list_reports(limit: int = 50) -> List[Dict[str, Any]]:
    """列出历史报告（仅元信息，不含正文）。"""
    if _use_sqlite():
        try:
            with _connect() as conn:
                rows = conn.execute(
                    "SELECT id, title, query, mode, created_at FROM reports "
                    "ORDER BY created_at DESC LIMIT ?",
                    (limit,),
                ).fetchall()
            return [dict(r) for r in rows]
        except Exception:
            pass

    with _lock:
        result = []
        for rid in _mem_seq[:limit]:
            rec = _mem.get(rid)
            if rec is None:
                continue
            result.append({
                "id": rec["id"],
                "title": rec["title"],
                "query": rec["query"],
                "mode": rec["mode"],
                "created_at": rec["created_at"],
            })
        return result


def get_report(report_id: str) -> Optional[Dict[str, Any]]:
    """查询单个报告的完整内容。"""
    if _use_sqlite():
        try:
            with _connect() as conn:
                row = conn.execute(
                    "SELECT * FROM reports WHERE id = ?", (report_id,)
                ).fetchone()
            if row is not None:
                data = dict(row)
                data["payload"] = json.loads(data.pop("payload_json"))
                return data
        except Exception:
            pass

    with _lock:
        rec = _mem.get(report_id)
    return dict(rec) if rec else None


def report_to_markdown(payload: Dict[str, Any]) -> str:
    """把研究结果 payload 转成 Markdown 文本。"""
    mode = payload.get("mode", "research")
    lines: List[str] = []

    if mode == "direct_answer":
        lines.append(f"# {payload.get('query', '回答')}")
        lines.append("")
        lines.append(str(payload.get("answer", "")))
        return "\n".join(lines)

    report = payload.get("report") or {}
    lines.append(f"# {report.get('title', '研究报告')}")
    lines.append("")

    summary = str(report.get("executive_summary", "")).strip()
    if summary:
        lines.append("## 摘要")
        lines.append("")
        lines.append(summary)
        lines.append("")

    sections = report.get("sections", []) or []
    for i, sec in enumerate(sections, start=1):
        if not isinstance(sec, dict):
            continue
        lines.append(f"## {i}. {sec.get('title', f'结论 {i}')}")
        lines.append("")
        finding = str(sec.get("finding", "")).strip()
        if finding:
            lines.append(f"**发现**：{finding}")
            lines.append("")
        analysis = str(sec.get("analysis", "")).strip()
        if analysis:
            lines.append(f"**分析**：{analysis}")
            lines.append("")
        verdict = sec.get("review_verdict")
        score = sec.get("review_score")
        if verdict or score is not None:
            lines.append(f"**审核**：{str(verdict).upper()}（{score}/100）")
            lines.append("")
        supporting = sec.get("supporting_evidence", []) or []
        if supporting:
            lines.append("**来源**：")
            for s in supporting:
                if isinstance(s, dict) and s.get("source_url"):
                    label = s.get("source_title") or "链接"
                    lines.append(f"- [{label}]({s.get('source_url')})")
            lines.append("")

    overall = str(report.get("overall_analysis", "")).strip()
    if overall:
        lines.append("## 综合分析")
        lines.append("")
        lines.append(overall)
        lines.append("")

    return "\n".join(lines)
