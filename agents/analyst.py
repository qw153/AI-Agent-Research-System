import os
import json

from dotenv import load_dotenv
from openai import OpenAI

from graph.state import ResearchState


# =========================================================
# Environment
# =========================================================

load_dotenv()

LLM_API_KEY = os.getenv("LLM_API_KEY")
LLM_BASE_URL = os.getenv("LLM_BASE_URL")
LLM_MODEL = os.getenv("LLM_MODEL")


# =========================================================
# LLM Client
# =========================================================

client = OpenAI(
    api_key=LLM_API_KEY,
    base_url=LLM_BASE_URL,
)


# =========================================================
# JSON Parser
# =========================================================

def parse_json_response(content: str) -> dict:
    """
    尝试解析 Analyst 的 JSON 输出。

    支持：
    1. 标准 JSON
    2. ```json ... ```
    3. 前后带解释文字
    """

    content = content.strip()

    # -----------------------------------------------------
    # Remove Markdown code fence
    # -----------------------------------------------------

    if content.startswith("```"):

        lines = content.splitlines()

        if lines:
            lines = lines[1:]

        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]

        content = "\n".join(lines).strip()

    # -----------------------------------------------------
    # Direct JSON
    # -----------------------------------------------------

    try:

        return json.loads(content)

    except json.JSONDecodeError:
        pass

    # -----------------------------------------------------
    # Extract outer JSON object
    # -----------------------------------------------------

    start = content.find("{")
    end = content.rfind("}")

    if start != -1 and end != -1:

        candidate = content[start:end + 1]

        try:

            return json.loads(candidate)

        except json.JSONDecodeError:
            pass

    # -----------------------------------------------------
    # Failed
    # -----------------------------------------------------

    raise ValueError(
        "Analyst returned invalid JSON."
    )


# =========================================================
# Analyst
# =========================================================

def analyst_node(state: ResearchState):

    query = state["query"]

    evidence = state.get(
        "evidence",
        []
    )

    print("\n")
    print("=" * 60)
    print("🧠 Analyst started")
    print("=" * 60)

    print(
        f"\nNormalized Evidence: "
        f"{len(evidence)}"
    )

    # Evidence Normalizer 的标准输出字段
    normalized_evidence = []

    for item in evidence:
        if not isinstance(item, dict):
            continue

        normalized_evidence.append(
            {
                "task_id": item.get("task_id"),
                "claim": item.get("claim", ""),
                "evidence": item.get("evidence", ""),
                "source_title": item.get("source_title", ""),
                "source_url": item.get("source_url", ""),
                "source_type": item.get("source_type", "other"),
                "confidence": item.get("confidence", "low"),
            }
        )

    MAX_EVIDENCE = 30
    evidence = normalized_evidence[:MAX_EVIDENCE]

    evidence_text = json.dumps(
        evidence,
        ensure_ascii=False,
        indent=2
    )

    # =====================================================
    # Analyst Prompt
    # =====================================================

    prompt = f"""
你是一名专业的 AI Research Analyst。

你的任务是基于 Evidence Normalizer 提供的结构化证据，
回答用户的研究问题，并生成可以追溯到原始网页的研究结论。

用户研究问题：

{query}

Evidence Normalizer 提供的结构化证据：

{evidence_text}

要求：

1. 只使用提供的 evidence 作为事实依据。
2. 不得进行新的 Web 搜索。
3. 不得编造事实、数据、来源或 URL。
4. 每个 finding 必须由一个或多个 evidence 支持。
5. 合并重复或高度相似的观点。
6. 如果不同来源存在冲突，明确指出冲突。
7. 区分来源直接支持的事实和你的分析判断。
8. 最多输出 5 个核心 finding。
9. 每个 finding 的 analysis 最多 2 句话。
10. 每个 finding 最多引用 2 条 supporting_evidence。
11. supporting_evidence 必须是对象数组。
12. 每条 supporting_evidence 必须包含 evidence、source_title、source_url。
13. source_url 必须直接复制自输入 evidence。
14. 绝对不能自行生成、猜测或修改 source_url。
15. 没有 source_url 的 evidence 不得作为 supporting_evidence。
16. confidence 只能是 high、medium、low。
17. related_task_ids 必须使用输入 evidence 中真实存在的 Task ID。
18. 如果证据不足，明确写“证据不足”。
19. 必须输出完整 JSON。
20. 不要输出 Markdown。
21. 不要输出 JSON 之外的任何文字。

JSON 格式：

{{
  "claims": [
    {{
      "title": "核心结论标题",
      "finding": "核心发现",
      "supporting_evidence": [
        {{
          "evidence": "支持该结论的具体证据",
          "source_title": "来源网页标题",
          "source_url": "https://example.com/source"
        }}
      ],
      "analysis": "基于证据的分析。",
      "confidence": "high",
      "related_task_ids": [1, 2]
    }}
  ]
}}


    """


    # =====================================================
    # Call LLM
    # =====================================================

    print("\n🤖 Calling Analyst LLM...")

    try:

        response = client.chat.completions.create(
            model=LLM_MODEL,
            messages=[
                {
                    "role": "user",
                    "content": prompt,
                }
            ],
            temperature=0.1,

            # 限制输出长度
            max_tokens=3000,
        )

    except Exception as e:

        print(
            f"\n❌ Analyst LLM failed: "
            f"{type(e).__name__}: {e}"
        )

        raise

    # =====================================================
    # Get Content
    # =====================================================

    content = (
        response.choices[0]
        .message
        .content
        .strip()
    )

    print(
        f"\n📦 Analyst output length: "
        f"{len(content)} characters"
    )

    # =====================================================
    # Parse
    # =====================================================

    try:

        result = parse_json_response(
            content
        )

    except ValueError:

        print("\n")
        print("=" * 60)
        print("❌ Analyst JSON Parse Failed")
        print("=" * 60)

        print("\nRaw output:")
        print(content)

        print("\n" + "=" * 60)

        raise

    # =====================================================
    # Validate
    # =====================================================

    if not isinstance(result, dict):

        raise ValueError(
            "Analyst JSON root must be an object."
        )

    claims = result.get(
        "claims",
        []
    )

    if not isinstance(claims, list):

        raise ValueError(
            "Analyst 'claims' must be a list."
        )

    # =====================================================
    # Limit Claims
    # =====================================================

    claims = claims[:5]

    # =====================================================
    # Validate Source Traceability
    # =====================================================

    validated_claims = []

    for claim in claims:
        if not isinstance(claim, dict):
            continue

        raw_evidence = claim.get(
            "supporting_evidence",
            []
        )

        if not isinstance(raw_evidence, list):
            continue

        validated_evidence = []

        for item in raw_evidence[:2]:
            if not isinstance(item, dict):
                continue

            evidence_text_item = str(
                item.get("evidence", "")
            ).strip()

            source_title = str(
                item.get("source_title", "")
            ).strip()

            source_url = str(
                item.get("source_url", "")
            ).strip()

            if not evidence_text_item or not source_url:
                continue

            validated_evidence.append(
                {
                    "evidence": evidence_text_item,
                    "source_title": source_title,
                    "source_url": source_url,
                }
            )

        if validated_evidence:
            claim["supporting_evidence"] = validated_evidence
            validated_claims.append(claim)

    claims = validated_claims

    print(
        f"\n✅ Analyst generated "
        f"{len(claims)} findings"
    )

    # =====================================================
    # Return
    # =====================================================

    return {
        "claims": claims
    }