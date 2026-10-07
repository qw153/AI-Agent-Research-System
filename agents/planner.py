import json
from pathlib import Path
from typing import Dict, Any

from llm import chat_completion
from graph.state import ResearchState
from tools.json_utils import extract_json_text


# ============================================================
# 项目根目录
# ============================================================

BASE_DIR = Path(__file__).resolve().parent.parent


# ============================================================
# Planner Prompt
# ============================================================

PROMPT_PATH = (
    BASE_DIR
    / "prompts"
    / "planner.txt"
)


def load_prompt() -> str:
    """
    加载 prompts/planner.txt
    """

    with open(
        PROMPT_PATH,
        "r",
        encoding="utf-8"
    ) as f:

        return f.read()


# ============================================================
# Planner Agent
# ============================================================

def planner_node(
    state: ResearchState
) -> Dict[str, Any]:
    """
    Planner Agent

    输入：
        ResearchState.query

    输出：
        research_plan
        research_complexity
        needs_web_search
        research_goal
    """

    # ========================================================
    # 获取用户问题
    # ========================================================

    query = state.get(
        "query",
        ""
    ).strip()


    if not query:

        raise ValueError(
            "Research query cannot be empty."
        )


    # ========================================================
    # 加载 Prompt
    # ========================================================

    prompt_template = load_prompt()

    # 不使用 str.format()，避免 planner.txt 中的 JSON {} 被误认为模板变量
    prompt = prompt_template.replace(
        "{query}",
        query
    )


    # ========================================================
    # 打印 Planner 信息
    # ========================================================

    print("\n" + "=" * 60)
    print("🧠 Planner Agent")
    print("=" * 60)

    print(
        "Research question:"
    )

    print(query)


    # ========================================================
    # 调用 LLM
    # ========================================================

    raw_output = chat_completion(
        messages=[
            {
                "role": "user",
                "content": prompt
            }
        ],
        temperature=0.1,
    )


    print("\nRaw Planner Output:")

    print(raw_output)


    # ========================================================
    # JSON 解析
    # ========================================================

    try:

        plan = json.loads(
            extract_json_text(
                raw_output
            )
        )

    except json.JSONDecodeError as e:

        raise ValueError(
            "Planner returned invalid JSON.\n"
            f"Raw output:\n{raw_output}"
        ) from e


    # ========================================================
    # Planner 输出必须是 Object
    # ========================================================

    if not isinstance(
        plan,
        dict
    ):

        raise ValueError(
            "Planner output must be a JSON object.\n"
            f"Output:\n{raw_output}"
        )


    # ========================================================
    # 获取基本规划信息
    # ========================================================

    complexity = plan.get(
        "complexity"
    )

    task_count = plan.get(
        "task_count"
    )

    reason = plan.get(
        "reason",
        ""
    )

    research_goal = plan.get(
        "research_goal",
        query
    )

    needs_web_search = plan.get(
        "needs_web_search",
        True
    )


    # ========================================================
    # 校验 complexity
    # ========================================================

    valid_complexities = [
        "simple",
        "medium",
        "complex",
        "very_complex"
    ]


    if complexity not in valid_complexities:

        raise ValueError(
            "Invalid Planner complexity: "
            f"{complexity}\n"
            "Expected one of: "
            f"{valid_complexities}"
        )


    # ========================================================
    # 校验 needs_web_search
    # ========================================================

    if not isinstance(
        needs_web_search,
        bool
    ):

        raise ValueError(
            "Planner 'needs_web_search' "
            "must be boolean."
        )


    # ========================================================
    # 获取 Tasks
    # ========================================================

    if "tasks" in plan:

        tasks = plan["tasks"]

    elif "research_plan" in plan:

        tasks = plan["research_plan"]

    else:

        raise ValueError(
            "Planner output does not contain "
            "'tasks' or 'research_plan'.\n"
            f"Output:\n{raw_output}"
        )


    # ========================================================
    # Tasks 必须是 List
    # ========================================================

    if not isinstance(
        tasks,
        list
    ):

        raise ValueError(
            "Planner tasks must be a list."
        )


    # ========================================================
    # 简单问题的特殊处理
    # ========================================================

    # 如果 Planner 判断不需要搜索，
    # 那么不应该生成大量 Research Tasks。

    


    # ========================================================
    # 校验 Task Count
    # ========================================================

    if not isinstance(
        task_count,
        int
    ):

        raise ValueError(
            "Planner 'task_count' "
            "must be an integer."
        )


    # ========================================================
    # Task 数量范围
    # ========================================================

    if task_count < 1:

        raise ValueError(
            "Planner task_count must be >= 1."
        )


    if task_count > 8:

        raise ValueError(
            "Planner task_count cannot "
            "be greater than 8."
        )


    # ========================================================
    # 确保 task_count 与实际 Tasks 一致
    # ========================================================

    actual_task_count = len(tasks)


    if task_count != actual_task_count:

        raise ValueError(
            "Planner task_count does not match "
            "actual number of tasks.\n"
            f"task_count = {task_count}\n"
            f"actual tasks = {actual_task_count}\n"
            f"Output:\n{raw_output}"
        )


    # ========================================================
    # Task 字段校验
    # ========================================================

    required_fields = [
        "id",
        "topic",
        "objective",
        "required_source_types",
        "priority"
    ]


    valid_priorities = [
        "high",
        "medium",
        "low"
    ]


    for index, task in enumerate(
        tasks
    ):

        # ----------------------------------------------------
        # Task 必须是 Dict
        # ----------------------------------------------------

        if not isinstance(
            task,
            dict
        ):

            raise ValueError(
                f"Task {index} "
                "is not a JSON object."
            )


        # ----------------------------------------------------
        # 检查字段
        # ----------------------------------------------------

        missing_fields = [
            field
            for field in required_fields
            if field not in task
        ]


        if missing_fields:

            raise ValueError(
                f"Task {index} "
                f"is missing fields: "
                f"{missing_fields}"
            )


        # ----------------------------------------------------
        # priority 校验
        # ----------------------------------------------------

        if task["priority"] not in valid_priorities:

            raise ValueError(
                f"Task {index} has invalid "
                f"priority: {task['priority']}\n"
                f"Expected: {valid_priorities}"
            )


        # ----------------------------------------------------
        # source types 必须是 List
        # ----------------------------------------------------

        if not isinstance(
            task["required_source_types"],
            list
        ):

            raise ValueError(
                f"Task {index} "
                "'required_source_types' "
                "must be a list."
            )


    # ========================================================
    # 打印 Planner 决策
    # ========================================================

    print("\n" + "-" * 60)

    print(
        f"Complexity: {complexity}"
    )

    print(
        f"Needs web search: "
        f"{needs_web_search}"
    )

    print(
        f"Task count: "
        f"{len(tasks)}"
    )

    print(
        f"Reason: "
        f"{reason}"
    )


    # ========================================================
    # 打印 Tasks
    # ========================================================

    print("\nResearch Tasks:")


    for task in tasks:

        print(
            f"\nTask {task['id']}"
        )

        print(
            f"Topic: "
            f"{task['topic']}"
        )

        print(
            f"Objective: "
            f"{task['objective']}"
        )

        print(
            f"Priority: "
            f"{task['priority']}"
        )

        print(
            "Source Types: "
            f"{', '.join(task['required_source_types'])}"
        )


    # ========================================================
    # Planner 完成
    # ========================================================

    print("\n" + "=" * 60)

    print(
        "✅ Planner completed."
    )

    print(
        f"Complexity: {complexity}"
    )

    print(
        f"Needs web search: "
        f"{needs_web_search}"
    )

    print(
        f"Generated "
        f"{len(tasks)} research tasks."
    )

    print("=" * 60)


    # ========================================================
    # 写入 LangGraph State
    # ========================================================

    return {

        "research_plan": tasks,

        "research_complexity": complexity,

        "research_goal": research_goal,

        "needs_web_search": needs_web_search
    }