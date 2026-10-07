"""记忆 / 持久化支持。

两层设计：
1. Checkpointer（LangGraph 原生）：为每次研究保留完整状态快照，支持恢复与检查。
2. 对话记忆（JSON 文件）：按 conversation_id 记录上一轮报告摘要，用于追问时注入上下文。

注意：每次研究用「全新 thread」，避免 LangGraph 里 operator.add 归并器
（research_results / evidence）跨轮累积旧数据、污染新一轮结果。
"""
import json
import os
import uuid
from pathlib import Path
from typing import Any, Dict, Optional

BASE_DIR = Path(__file__).resolve().parent.parent

MEMORY_PATH = Path(
    os.getenv("MEMORY_PATH", str(BASE_DIR / "research_memory.json"))
)
DEFAULT_DB_PATH = os.getenv("CHECKPOINT_DB_PATH", "research_checkpoints.sqlite")

# 缓存 saver 单例；SQLite 的 context manager 需要保持引用，避免被 GC 关闭连接
_saver = None
_saver_cm = None


def _dir_writable(db_path: str) -> bool:
    """检测数据库所在目录是否可写（只读目录会导致 checkpoint 写入失败）。"""
    p = Path(db_path)
    directory = p.parent if p.parent != Path("") else Path(".")
    try:
        probe = directory / f".write_probe_{uuid.uuid4().hex}"
        probe.write_text("", encoding="utf-8")
        probe.unlink()
        return True
    except Exception:
        return False


def get_checkpointer():
    """优先 SQLite 持久化；不可用时回退到内存（重启后不保留）。

    注意：langgraph-checkpoint-sqlite 3.x 的 from_conn_string() 返回的是
    context manager，需要手动 __enter__ 并保持引用，不能直接传给 compile。
    """
    global _saver, _saver_cm
    if _saver is not None:
        return _saver

    try:
        from langgraph.checkpoint.sqlite import SqliteSaver
    except ImportError:
        print(
            "[memory] 未安装 langgraph-checkpoint-sqlite，"
            "使用内存记忆（重启后不保留）。"
        )
        from langgraph.checkpoint.memory import InMemorySaver
        _saver = InMemorySaver()
        return _saver

    # 打开前先检测目录可写，避免后续 checkpoint 写入时报 readonly
    if not _dir_writable(DEFAULT_DB_PATH):
        print("[memory] 数据库目录不可写，使用内存记忆（重启后不保留）。")
        from langgraph.checkpoint.memory import InMemorySaver
        _saver = InMemorySaver()
        return _saver

    try:
        _saver_cm = SqliteSaver.from_conn_string(DEFAULT_DB_PATH)
        _saver = _saver_cm.__enter__()
        return _saver
    except Exception as e:
        print(f"[memory] SQLite 初始化失败，回退内存记忆：{e}")
        from langgraph.checkpoint.memory import InMemorySaver
        _saver = InMemorySaver()
        return _saver


def new_thread_id(conversation_id: str = "default") -> str:
    """每次研究用全新 thread_id，避免 reducer 跨轮累积旧状态。"""
    return f"{conversation_id}-{uuid.uuid4().hex[:12]}"


def thread_config(thread_id: str) -> Dict[str, Any]:
    return {"configurable": {"thread_id": thread_id}}


def load_prior_context(conversation_id: str = "default") -> Optional[str]:
    """从对话记忆读取上一轮报告摘要，用于追问时注入上下文。"""
    entry = _load_memory().get(conversation_id)
    if not isinstance(entry, dict):
        return None
    title = str(entry.get("title", "")).strip()
    summary = str(entry.get("summary", "")).strip()
    if not title and not summary:
        return None
    return f"主题：{title}\n摘要：{summary}"


def remember_report(conversation_id: str = "default", report=None) -> None:
    """把本轮报告的标题与摘要写入对话记忆。"""
    if not isinstance(report, dict):
        return
    data = _load_memory()
    data[conversation_id] = {
        "title": str(report.get("title", "")).strip(),
        "summary": str(report.get("executive_summary", "")).strip(),
    }
    _save_memory(data)


def _load_memory() -> Dict[str, Any]:
    try:
        if MEMORY_PATH.exists():
            with open(MEMORY_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data if isinstance(data, dict) else {}
    except Exception:
        pass
    return {}


def _save_memory(data: Dict[str, Any]) -> None:
    try:
        MEMORY_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(MEMORY_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"[memory] 保存对话记忆失败：{e}")
