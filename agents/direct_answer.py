from llm import chat_completion
from graph.state import ResearchState


# =========================
# Direct Answer Agent
# =========================

def direct_answer_node(state: ResearchState):
    """
    对不需要联网搜索的问题直接生成回答。

    适用于：
    - 简单知识问答
    - 概念解释
    - 技术概念对比
    - 不需要最新信息的问题
    """

    query = state["query"]

    prompt = f"""
你是一个专业的 AI 技术助手。

请直接回答用户的问题。

用户问题：
{query}

要求：

1. 直接回答问题，不要进行网页搜索。
2. 如果是概念问题，先给出清晰定义。
3. 如果是比较问题，可以使用表格。
4. 如果存在明显的优缺点，可以进行总结。
5. 不要编造实时数据。
6. 回答应该准确、清晰、结构化。
7. 使用中文回答。
"""

    answer = chat_completion(
        messages=[
            {
                "role": "user",
                "content": prompt,
            }
        ],
        temperature=0.2,
    )

    return {
        "direct_answer": answer
    }