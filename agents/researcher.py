import time
from urllib.parse import urlsplit, urlunsplit

from graph.state import ResearchState
from tools.search_tool import web_search


# =========================================================
# Configuration
# =========================================================

MAX_RETRIES = 3
RETRY_DELAY = 2

MAX_SEARCH_RESULTS = 5


# =========================================================
# URL Normalization
# =========================================================

def normalize_url(url: str) -> str:
    """
    标准化 URL，用于搜索结果去重。
    """

    if not url:
        return ""

    try:
        parts = urlsplit(url)

        # 去掉 fragment
        normalized = urlunsplit(
            (
                parts.scheme.lower(),
                parts.netloc.lower(),
                parts.path.rstrip("/"),
                parts.query,
                "",
            )
        )

        return normalized

    except Exception:
        return url.strip()


# =========================================================
# Search Result Deduplication
# =========================================================

def deduplicate_sources(
    sources: list
) -> list:
    """
    根据 URL 对搜索结果去重。
    """

    unique_sources = []

    seen_urls = set()

    for source in sources:

        if not isinstance(source, dict):
            continue

        url = source.get(
            "url",
            ""
        )

        normalized_url = normalize_url(
            url
        )

        # -------------------------------------------------
        # 有 URL：按 URL 去重
        # -------------------------------------------------

        if normalized_url:

            if normalized_url in seen_urls:
                continue

            seen_urls.add(
                normalized_url
            )

        # -------------------------------------------------
        # 没有 URL：保留
        # -------------------------------------------------

        unique_sources.append(
            source
        )

    return unique_sources


# =========================================================
# Search With Retry
# =========================================================

def search_with_retry(
    search_query: str,
    max_retries: int = MAX_RETRIES,
):
    """
    Tavily 搜索失败时自动重试。

    Example:

        attempt 1 ❌
        attempt 2 ❌
        attempt 3 ✅
    """

    last_error = None

    for attempt in range(
        1,
        max_retries + 1
    ):

        print(
            f"   🔎 Search attempt "
            f"{attempt}/{max_retries}"
        )

        try:

            results = web_search(
                search_query,
                max_results=MAX_SEARCH_RESULTS,
                search_depth="basic",
            )

            if results is None:
                results = []

            print(
                f"   ✅ Search succeeded "
                f"on attempt {attempt}"
            )

            return results

        except Exception as e:

            last_error = e

            print(
                f"   ⚠️ Search attempt "
                f"{attempt} failed: "
                f"{type(e).__name__}: {e}"
            )

            # 最后一次失败，不再等待
            if attempt >= max_retries:
                break

            print(
                f"   ⏳ Retrying in "
                f"{RETRY_DELAY}s..."
            )

            time.sleep(
                RETRY_DELAY
            )

    # =====================================================
    # All retries failed
    # =====================================================

    raise RuntimeError(
        f"Search failed after "
        f"{max_retries} attempts: "
        f"{last_error}"
    )


# =========================================================
# Search Query Generation
# =========================================================

def generate_search_query(
    task: dict
) -> str:
    """
    根据 Planner Task 生成搜索关键词。

    不额外调用 LLM，先使用结构化 Task。
    """

    topic = task.get(
        "topic",
        ""
    )

    objective = task.get(
        "objective",
        ""
    )

    source_types = task.get(
        "required_source_types",
        []
    )

    source_hint = " ".join(
        source_types
    )

    query_parts = [
        topic,
        objective,
        source_hint,
    ]

    query = " ".join(
        part.strip()
        for part in query_parts
        if part
    )

    return query.strip()


# =========================================================
# Research Worker
# =========================================================

def research_worker_node(
    state: ResearchState
):
    """
    单个 Research Worker。

    一个 Worker 只负责一个 Task。

    LangGraph Send 会创建多个 Worker：

        Task 1 → Worker 1
        Task 2 → Worker 2
        Task 3 → Worker 3
        Task 4 → Worker 4
    """

    task = state["task"]

    query = state["query"]

    task_id = task.get(
        "id"
    )

    topic = task.get(
        "topic",
        ""
    )

    print("\n")
    print("-" * 60)

    print(
        f"🔎 Research Worker started "
        f"for Task {task_id}"
    )

    print(
        f"   Topic: {topic}"
    )

    # =====================================================
    # Generate Search Query
    # =====================================================

    search_query = generate_search_query(
        task
    )

    print(
        f"   Search Query: "
        f"{search_query}"
    )

    # =====================================================
    # Search + Retry
    # =====================================================

    try:

        search_results = search_with_retry(
            search_query
        )

    except Exception as e:

        # -------------------------------------------------
        # 单 Worker 失败
        #
        # 不让整个 Workflow 崩溃。
        # -------------------------------------------------

        print(
            f"\n   ❌ Task {task_id} "
            f"research failed."
        )

        print(
            f"   Error: "
            f"{type(e).__name__}: {e}"
        )

        failed_result = {
            "task_id": task_id,

            "topic": topic,

            "objective": task.get(
                "objective",
                ""
            ),

            "search_query": search_query,

            "sources": [],

            "status": "failed",

            "error": str(e),
        }

        return {
            "research_results": [
                failed_result
            ]
        }

    # =====================================================
    # Deduplicate
    # =====================================================

    original_count = len(
        search_results
    )

    search_results = deduplicate_sources(
        search_results
    )

    deduplicated_count = len(
        search_results
    )

    print(
        f"   📚 Raw sources: "
        f"{original_count}"
    )

    print(
        f"   ♻️ Unique sources: "
        f"{deduplicated_count}"
    )

    # =====================================================
    # Build Research Result
    # =====================================================

    research_result = {

        "task_id": task_id,

        "topic": topic,

        "objective": task.get(
            "objective",
            ""
        ),

        "search_query": search_query,

        "sources": search_results,

        "status": "success",

        "error": None,
    }

    # =====================================================
    # Finished
    # =====================================================

    print(
        f"   ✅ Research Worker finished "
        f"for Task {task_id}"
    )

    print("-" * 60)

    # =====================================================
    # Return
    # =====================================================

    return {
        "research_results": [
            research_result
        ]
    }