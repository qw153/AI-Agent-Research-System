import json
import os
from pathlib import Path
from typing import Any, Dict, List

from dotenv import load_dotenv
from openai import OpenAI
from graph.state import ResearchState

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

LLM_API_KEY = os.getenv("LLM_API_KEY")
LLM_BASE_URL = os.getenv("LLM_BASE_URL")
LLM_MODEL = os.getenv("LLM_MODEL")

if not all([LLM_API_KEY, LLM_BASE_URL, LLM_MODEL]):
    raise RuntimeError("Missing LLM_API_KEY / LLM_BASE_URL / LLM_MODEL in .env")

client = OpenAI(api_key=LLM_API_KEY, base_url=LLM_BASE_URL)
PROMPT_PATH = BASE_DIR / "prompts" / "reviewer.txt"


def load_prompt() -> str:
    with open(PROMPT_PATH, "r", encoding="utf-8") as f:
        return f.read()


def parse_json_response(content: str) -> Dict[str, Any]:
    if not content:
        raise ValueError("Reviewer returned empty output.")

    content = content.strip()

    for candidate in [content]:
        try:
            parsed = json.loads(candidate)
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            pass

    if "```" in content:
        for part in content.split("```"):
            candidate = part.strip()
            if candidate.startswith("json"):
                candidate = candidate[4:].strip()
            try:
                parsed = json.loads(candidate)
                if isinstance(parsed, dict):
                    return parsed
            except json.JSONDecodeError:
                pass

    start, end = content.find("{"), content.rfind("}")
    if start != -1 and end > start:
        try:
            parsed = json.loads(content[start:end + 1])
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            pass

    raise ValueError("Reviewer returned invalid JSON.")


def reviewer_node(state: ResearchState):
    query = state.get("query", "")
    claims = state.get("claims", [])
    evidence = state.get("evidence", [])

    print("\n" + "=" * 60)
    print("🔍 Reviewer Agent")
    print("=" * 60)
    print(f"\nClaims to review: {len(claims)}")
    print(f"Available evidence: {len(evidence)}")

    if not claims:
        return {"review_results": []}

    valid_urls = {
        str(item.get("source_url", "")).strip()
        for item in evidence
        if isinstance(item, dict) and item.get("source_url")
    }

    reviewable_claims = []

    for index, claim in enumerate(claims, start=1):
        if not isinstance(claim, dict):
            continue

        supporting = claim.get("supporting_evidence", [])
        if not isinstance(supporting, list):
            supporting = []

        normalized = []
        for item in supporting:
            if not isinstance(item, dict):
                continue
            url = str(item.get("source_url", "")).strip()
            normalized.append({
                "evidence": str(item.get("evidence", "")).strip(),
                "source_title": str(item.get("source_title", "")).strip(),
                "source_url": url,
                "url_exists_in_evidence": url in valid_urls,
            })

        reviewable_claims.append({
            "claim_index": index,
            "title": claim.get("title", ""),
            "finding": claim.get("finding", ""),
            "analysis": claim.get("analysis", ""),
            "confidence": claim.get("confidence", ""),
            "related_task_ids": claim.get("related_task_ids", []),
            "supporting_evidence": normalized,
        })

    claims_text = json.dumps(reviewable_claims, ensure_ascii=False, indent=2)

    evidence_text = json.dumps([
        {
            "task_id": item.get("task_id"),
            "claim": item.get("claim", ""),
            "evidence": item.get("evidence", ""),
            "source_title": item.get("source_title", ""),
            "source_url": item.get("source_url", ""),
            "confidence": item.get("confidence", "low"),
        }
        for item in evidence
        if isinstance(item, dict)
    ], ensure_ascii=False, indent=2)

    prompt = load_prompt()
    prompt = prompt.replace("{query}", query)
    prompt = prompt.replace("{claims}", claims_text)
    prompt = prompt.replace("{evidence}", evidence_text)

    print("\n🤖 Calling Reviewer LLM...")

    response = client.chat.completions.create(
        model=LLM_MODEL,
        messages=[
            {
                "role": "system",
                "content": "You are a strict research reviewer. Return valid JSON only."
            },
            {"role": "user", "content": prompt},
        ],
        temperature=0.0,
        max_tokens=4000,
    )

    content = (response.choices[0].message.content or "").strip()
    print(f"📦 Reviewer output length: {len(content)} characters")

    try:
        result = parse_json_response(content)
    except ValueError:
        print("\n" + "=" * 60)
        print("❌ Reviewer JSON Parse Failed")
        print("=" * 60)
        print("\nRaw output:")
        print(content)
        raise

    raw_reviews = result.get("reviews", [])
    if not isinstance(raw_reviews, list):
        raise ValueError("Reviewer 'reviews' must be a list.")

    review_results = []

    for review in raw_reviews:
        if not isinstance(review, dict):
            continue

        claim_index = review.get("claim_index")
        verdict = review.get("verdict", "revise")
        if verdict not in {"pass", "revise", "reject"}:
            verdict = "revise"

        try:
            score = int(review.get("score", 0))
        except (TypeError, ValueError):
            score = 0
        score = max(0, min(100, score))

        issues = review.get("issues", [])
        if not isinstance(issues, list):
            issues = [str(issues)]

        if isinstance(claim_index, int) and 1 <= claim_index <= len(reviewable_claims):
            cited = reviewable_claims[claim_index - 1].get("supporting_evidence", [])
            invalid = [
                x.get("source_url", "")
                for x in cited
                if x.get("source_url") and not x.get("url_exists_in_evidence", False)
            ]
            if invalid:
                verdict = "reject"
                issues.append("Supporting evidence contains a URL not present in normalized evidence.")

        review_results.append({
            "claim_index": claim_index,
            "title": review.get("title", ""),
            "verdict": verdict,
            "score": score,
            "issues": issues,
            "reason": review.get("reason", ""),
            "checked_source_urls": review.get("checked_source_urls", []),
        })

    print("\n" + "=" * 60)
    print("✅ Review completed")
    print(f"Reviewed claims: {len(review_results)}")
    print("=" * 60)

    return {"review_results": review_results}
