import json
import os
from pathlib import Path
from typing import Any, Dict

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

PROMPT_PATH = BASE_DIR / "prompts" / "writer.txt"


def load_prompt() -> str:
    with open(PROMPT_PATH, "r", encoding="utf-8") as f:
        return f.read()


# =========================================================
# JSON Parser
# =========================================================

def parse_json_response(content: str) -> Dict[str, Any]:

    if not content:
        raise ValueError("Writer returned empty output.")

    content = content.strip()

    try:
        data = json.loads(content)

        if isinstance(data, dict):
            return data

    except json.JSONDecodeError:
        pass

    if "```" in content:

        for part in content.split("```"):

            candidate = part.strip()

            if candidate.lower().startswith("json"):
                candidate = candidate[4:].strip()

            try:
                data = json.loads(candidate)

                if isinstance(data, dict):
                    return data

            except json.JSONDecodeError:
                continue

    start = content.find("{")
    end = content.rfind("}")

    if start != -1 and end > start:

        try:
            data = json.loads(
                content[start:end + 1]
            )

            if isinstance(data, dict):
                return data

        except json.JSONDecodeError:
            pass

    raise ValueError("Writer returned invalid JSON.")


# =========================================================
# Writer Node
# =========================================================

def writer_node(state: ResearchState):

    query = state.get("query", "")
    research_goal = state.get("research_goal", "")
    claims = state.get("claims", [])
    evidence = state.get("evidence", [])
    review_results = state.get("review_results", [])

    print("\n" + "=" * 60)
    print("✍️ Writer Agent")
    print("=" * 60)

    print(f"\nClaims: {len(claims)}")
    print(f"Evidence: {len(evidence)}")
    print(f"Reviews: {len(review_results)}")

    # ---------------------------------------------------------
    # Writer receives reviewed findings.
    # Rejected findings are explicitly marked so they are not
    # accidentally presented as verified conclusions.
    # ---------------------------------------------------------

    claims_text = json.dumps(
        claims,
        ensure_ascii=False,
        indent=2
    )

    evidence_text = json.dumps(
        evidence,
        ensure_ascii=False,
        indent=2
    )

    reviews_text = json.dumps(
        review_results,
        ensure_ascii=False,
        indent=2
    )

    prompt = load_prompt()

    # Do not use .format(), because writer.txt contains JSON {}.
    prompt = prompt.replace(
        "{query}",
        query
    )

    prompt = prompt.replace(
        "{research_goal}",
        research_goal
    )

    prompt = prompt.replace(
        "{claims}",
        claims_text
    )

    prompt = prompt.replace(
        "{evidence}",
        evidence_text
    )

    prompt = prompt.replace(
        "{review_results}",
        reviews_text
    )

    print("\n🤖 Calling Writer LLM...")

    response = client.chat.completions.create(
        model=LLM_MODEL,
        messages=[
            {
                "role": "system",
                "content": (
                    "You are a professional research report writer. "
                    "Return valid JSON only."
                ),
            },
            {
                "role": "user",
                "content": prompt,
            },
        ],
        temperature=0.1,
        max_tokens=6000,
    )

    content = (
        response
        .choices[0]
        .message
        .content
        or ""
    ).strip()

    print(
        f"📦 Writer output length: "
        f"{len(content)} characters"
    )

    result = parse_json_response(content)

    report = result.get("report")

    if not isinstance(report, dict):
        raise ValueError(
            "Writer 'report' must be an object."
        )

    # ---------------------------------------------------------
    # Minimal validation
    # ---------------------------------------------------------

    title = str(
        report.get("title", "")
    ).strip()

    executive_summary = str(
        report.get("executive_summary", "")
    ).strip()

    sections = report.get(
        "sections",
        []
    )

    overall_analysis = str(
        report.get("overall_analysis", "")
    ).strip()

    if not title:
        title = "Research Report"

    if not isinstance(sections, list):
        sections = []

    # ---------------------------------------------------------
    # Preserve source traceability.
    # Writer may reorganize evidence, but it must not create
    # new URLs.
    # ---------------------------------------------------------

    valid_urls = {
        str(item.get("source_url", "")).strip()
        for item in evidence
        if isinstance(item, dict)
        and item.get("source_url")
    }

    for section in sections:

        if not isinstance(section, dict):
            continue

        section_evidence = section.get(
            "supporting_evidence",
            []
        )

        if not isinstance(
            section_evidence,
            list
        ):
            section["supporting_evidence"] = []
            continue

        valid_section_evidence = []

        for item in section_evidence:

            if not isinstance(item, dict):
                continue

            url = str(
                item.get("source_url", "")
            ).strip()

            if not url:
                continue

            if url not in valid_urls:
                continue

            valid_section_evidence.append(
                {
                    "evidence": str(
                        item.get(
                            "evidence",
                            ""
                        )
                    ).strip(),

                    "source_title": str(
                        item.get(
                            "source_title",
                            ""
                        )
                    ).strip(),

                    "source_url": url,
                }
            )

        section["supporting_evidence"] = (
            valid_section_evidence
        )

    report = {
        "title": title,
        "executive_summary": executive_summary,
        "sections": sections,
        "overall_analysis": overall_analysis,
    }

    print("\n" + "=" * 60)
    print("✅ Research Report Generated")
    print("=" * 60)

    return {
        "report": report
    }
