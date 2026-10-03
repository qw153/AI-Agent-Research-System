import json
import os
from pathlib import Path
from typing import Any, Dict, List

from dotenv import load_dotenv
from openai import OpenAI

from graph.state import ResearchState


# =========================================================
# Environment
# =========================================================

BASE_DIR = Path(__file__).resolve().parent.parent

load_dotenv(BASE_DIR / ".env")

LLM_API_KEY = os.getenv("LLM_API_KEY")
LLM_BASE_URL = os.getenv("LLM_BASE_URL")
LLM_MODEL = os.getenv("LLM_MODEL")

if not all([LLM_API_KEY, LLM_BASE_URL, LLM_MODEL]):
    raise RuntimeError(
        "Missing LLM_API_KEY / LLM_BASE_URL / LLM_MODEL in .env"
    )


# =========================================================
# LLM Client
# =========================================================

client = OpenAI(
    api_key=LLM_API_KEY,
    base_url=LLM_BASE_URL,
)


# =========================================================
# Prompt
# =========================================================

PROMPT_PATH = BASE_DIR / "prompts" / "evidence_normalizer.txt"


def load_prompt() -> str:
    with open(PROMPT_PATH, "r", encoding="utf-8") as f:
        return f.read()


# =========================================================
# JSON Parser
# =========================================================

def parse_json_response(content: str) -> Dict[str, Any] | None:
    """
    Robust JSON parser.

    Supports:
    1. Standard JSON object
    2. ```json ... ```
    3. Extra text before/after JSON
    4. JSON array as root -> converted to {"evidence": [...]}
    """

    if not content:
        return None

    content = content.strip()

    # -----------------------------------------------------
    # Remove code fences
    # -----------------------------------------------------

    if "```" in content:
        parts = content.split("```")

        # Prefer fenced JSON block
        for part in parts:
            candidate = part.strip()

            if candidate.startswith("json"):
                candidate = candidate[4:].strip()

            if not candidate:
                continue

            try:
                parsed = json.loads(candidate)

                if isinstance(parsed, dict):
                    return parsed

                if isinstance(parsed, list):
                    return {"evidence": parsed}

            except json.JSONDecodeError:
                continue

    # -----------------------------------------------------
    # Direct JSON object / array
    # -----------------------------------------------------

    try:
        parsed = json.loads(content)

        if isinstance(parsed, dict):
            return parsed

        if isinstance(parsed, list):
            return {"evidence": parsed}

    except json.JSONDecodeError:
        pass

    # -----------------------------------------------------
    # Extract JSON object
    # -----------------------------------------------------

    start = content.find("{")
    end = content.rfind("}")

    if start != -1 and end != -1 and end > start:

        candidate = content[start:end + 1]

        try:
            parsed = json.loads(candidate)

            if isinstance(parsed, dict):
                return parsed

        except json.JSONDecodeError:
            pass

    # -----------------------------------------------------
    # Extract JSON array
    # -----------------------------------------------------

    start = content.find("[")
    end = content.rfind("]")

    if start != -1 and end != -1 and end > start:

        candidate = content[start:end + 1]

        try:
            parsed = json.loads(candidate)

            if isinstance(parsed, list):
                return {"evidence": parsed}

        except json.JSONDecodeError:
            pass

    # -----------------------------------------------------
    # Failed
    # -----------------------------------------------------

    return None


# =========================================================
# Deterministic Fallback
# =========================================================

def build_fallback_evidence(
    task_id: Any,
    topic: str,
    sources: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """LLM JSON 失败时直接使用 Research Worker 原始结果。"""

    fallback = []

    for source in sources:
        if not isinstance(source, dict):
            continue

        title = str(source.get("title", "")).strip()
        url = str(source.get("url", "")).strip()
        content = str(source.get("content", "")).strip()

        if not url or not content:
            continue

        fallback.append({
            "task_id": task_id,
            "claim": topic,
            "evidence": content[:800],
            "source_title": title,
            "source_url": url,
            "source_type": "other",
            "confidence": "low",
        })

    return fallback


# =========================================================
# Normalize One Task
# =========================================================

def normalize_task(
    query: str,
    research_result: Dict[str, Any],
) -> List[Dict[str, Any]]:

    task_id = research_result.get("task_id")
    topic = research_result.get("topic", "")
    objective = research_result.get("objective", "")
    sources = research_result.get("sources", [])

    if not sources:
        print(f"⚠️ Task {task_id}: no sources.")
        return []

    source_blocks = []
    source_map = {}

    for index, source in enumerate(sources, start=1):

        if not isinstance(source, dict):
            continue

        title = str(source.get("title", "")).strip()
        url = str(source.get("url", "")).strip()
        content = str(source.get("content", "")).strip()

        if not url:
            continue

        source_map[url] = {
            "title": title,
            "url": url,
        }

        source_blocks.append(
            f"""
SOURCE {index}

Title:
{title}

URL:
{url}

Content:
{content}
"""
        )

    if not source_blocks:
        return []

    sources_text = "\n".join(source_blocks)

    # -----------------------------------------------------
    # Build Prompt
    # -----------------------------------------------------

    prompt = load_prompt()

    # IMPORTANT:
    # Do NOT use .format(), because the prompt contains JSON
    # braces. Only replace our explicit placeholders.

    prompt = prompt.replace(
        "{query}",
        query,
    )

    prompt = prompt.replace(
        "{task}",
        json.dumps(
            {
                "task_id": task_id,
                "topic": topic,
                "objective": objective,
            },
            ensure_ascii=False,
            indent=2,
        ),
    )

    prompt = prompt.replace(
        "{sources}",
        sources_text,
    )

    # =====================================================
    # Call LLM
    # =====================================================

    print(
        f"\n🧠 Evidence Normalizer started "
        f"for Task {task_id}"
    )

    try:
        response = client.chat.completions.create(
            model=LLM_MODEL,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a strict JSON generator. "
                        "Return valid JSON only. "
                        "Do not use Markdown fences. "
                        "Do not add explanations."
                    ),
                },
                {
                    "role": "user",
                    "content": prompt,
                },
            ],
            temperature=0.0,
            max_tokens=3000,
        )

    except Exception as e:

        print(
            f"❌ Evidence Normalizer LLM failed "
            f"for Task {task_id}: "
            f"{type(e).__name__}: {e}"
        )

        raise

    content = (
        response.choices[0]
        .message
        .content
    )

    if content is None:
        content = ""

    content = content.strip()

    print(
        f"📦 Normalizer output length: "
        f"{len(content)} characters"
    )

    # -----------------------------------------------------
    # IMPORTANT DEBUG OUTPUT
    # -----------------------------------------------------

    if not content:
        print(
            f"❌ Empty Evidence Normalizer output "
            f"for Task {task_id}"
        )

    result = parse_json_response(content)

    if result is None:

        print("\n" + "=" * 60)
        print("⚠️ Evidence Normalizer JSON Parse Failed")
        print("=" * 60)
        print("\nRaw LLM output:")
        print(content)
        print("\n⚠️ Falling back to original Research Worker sources.")
        print("=" * 60)

        return build_fallback_evidence(
            task_id=task_id,
            topic=topic,
            sources=sources,
        )

    # =====================================================
    # Validate
    # =====================================================

    raw_evidence = result.get("evidence", [])

    if not isinstance(raw_evidence, list):
        print(
            "⚠️ Normalizer 'evidence' is not a list. "
            "Falling back to original sources."
        )
        return build_fallback_evidence(
            task_id=task_id,
            topic=topic,
            sources=sources,
        )

    normalized = []

    for item in raw_evidence:

        if not isinstance(item, dict):
            continue

        source_url = str(
            item.get("source_url", "")
        ).strip()

        evidence_text = str(
            item.get("evidence", "")
        ).strip()

        claim = str(
            item.get("claim", "")
        ).strip()

        if not source_url:
            continue

        if source_url not in source_map:
            print(
                f"⚠️ Ignoring URL not present "
                f"in original sources:\n{source_url}"
            )
            continue

        if not claim or not evidence_text:
            continue

        original_source = source_map[source_url]

        source_type = item.get(
            "source_type",
            "other",
        )

        if source_type not in {
            "official",
            "news",
            "research",
            "community",
            "other",
        }:
            source_type = "other"

        confidence = item.get(
            "confidence",
            "low",
        )

        if confidence not in {
            "high",
            "medium",
            "low",
        }:
            confidence = "low"

        normalized.append(
            {
                "task_id": task_id,
                "claim": claim,
                "evidence": evidence_text,

                # Always copy from original Tavily source.
                "source_title": original_source["title"],
                "source_url": original_source["url"],

                "source_type": source_type,
                "confidence": confidence,
            }
        )

    if not normalized:
        print(
            f"⚠️ Task {task_id} produced no valid evidence. "
            f"Falling back to original sources."
        )
        return build_fallback_evidence(
            task_id=task_id,
            topic=topic,
            sources=sources,
        )

    print(
        f"✅ Task {task_id} normalized "
        f"{len(normalized)} evidence items."
    )

    return normalized


# =========================================================
# Evidence Normalizer Node
# =========================================================

def evidence_normalizer_node(
    state: ResearchState,
):

    query = state["query"]

    research_results = state.get(
        "research_results",
        [],
    )

    print("\n" + "=" * 60)
    print("📚 Evidence Normalizer")
    print("=" * 60)

    print(
        f"\nResearch Results: "
        f"{len(research_results)}"
    )

    all_evidence = []

    for research_result in research_results:

        if not isinstance(research_result, dict):
            continue

        task_evidence = normalize_task(
            query=query,
            research_result=research_result,
        )

        all_evidence.extend(task_evidence)

    print("\n" + "=" * 60)
    print("✅ Evidence Normalization Completed")
    print(
        f"Total Evidence: {len(all_evidence)}"
    )
    print("=" * 60)

    return {
        "evidence": all_evidence,
    }
