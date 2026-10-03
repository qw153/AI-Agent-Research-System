import re


def extract_json_text(text: str) -> str:
    """
    从 LLM 输出中提取 JSON 文本。

    兼容两种情况：
    1. 被 ```json ... ``` 代码围栏包裹
    2. 纯 JSON（对象或数组），前后可能带有少量说明文字
    """

    text = text.strip()

    # 情况 1：代码围栏
    fence_match = re.search(r"```(?:json)?\s*(.+?)\s*```", text, re.DOTALL)

    if fence_match:
        text = fence_match.group(1).strip()

    # 情况 2：截取第一个 { 或 [ 到最后一个 } 或 ]
    start = min(
        (
            i
            for i in (text.find("{"), text.find("["))
            if i != -1
        ),
        default=-1
    )

    if start == -1:
        return text

    end = max(text.rfind("}"), text.rfind("]"))

    if end <= start:
        return text

    return text[start:end + 1]
