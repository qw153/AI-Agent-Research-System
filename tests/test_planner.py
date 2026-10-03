import sys
import traceback
from pathlib import Path


# ============================================================
# 项目根目录
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parent.parent

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


# ============================================================
# 导入 Planner Agent
# ============================================================

from agents.planner import planner_node


# ============================================================
# 打印 Planner 结果
# ============================================================

def print_planner_result(result: dict):
    """
    格式化输出 Planner 的决策结果
    """

    print("\n")
    print("=" * 80)
    print("📋 PLANNER DECISION")
    print("=" * 80)

    # --------------------------------------------------------
    # Research Goal
    # --------------------------------------------------------

    print("\n🎯 Research Goal:")
    print(
        result.get(
            "research_goal",
            "N/A"
        )
    )

    # --------------------------------------------------------
    # Complexity
    # --------------------------------------------------------

    print("\n🧠 Complexity:")
    print(
        result.get(
            "research_complexity",
            "N/A"
        )
    )

    # --------------------------------------------------------
    # Web Search
    # --------------------------------------------------------

    print("\n🌐 Needs Web Search:")
    print(
        result.get(
            "needs_web_search",
            "N/A"
        )
    )

    # --------------------------------------------------------
    # Tasks
    # --------------------------------------------------------

    tasks = result.get(
        "research_plan",
        []
    )

    print("\n📊 Task Count:")
    print(
        len(tasks)
    )

    print("\n📚 Research Tasks:")

    for task in tasks:

        print("\n" + "-" * 60)

        print(
            f"ID: "
            f"{task.get('id')}"
        )

        print(
            f"Topic: "
            f"{task.get('topic')}"
        )

        print(
            f"Objective: "
            f"{task.get('objective')}"
        )

        print(
            f"Priority: "
            f"{task.get('priority')}"
        )

        print(
            f"Source Types: "
            f"{task.get('required_source_types')}"
        )

    print("\n" + "=" * 80)


# ============================================================
# 单独测试一个问题
# ============================================================

def test_planner(query: str):
    """
    独立运行 Planner Agent
    """

    print("\n\n")
    print("#" * 80)
    print("🧪 PLANNER AGENT TEST")
    print("#" * 80)

    print("\n用户问题：")
    print(query)

    print("\n🚀 Calling Planner Agent...")

    # --------------------------------------------------------
    # 构造最小 State
    # --------------------------------------------------------

    state = {
        "query": query
    }

    try:

        # ----------------------------------------------------
        # 调用 Planner
        # ----------------------------------------------------

        result = planner_node(
            state
        )

        # ----------------------------------------------------
        # 输出结果
        # ----------------------------------------------------

        print_planner_result(
            result
        )

        print("\n✅ Planner test passed.")

        return True

    except Exception as e:

        # ----------------------------------------------------
        # 捕获完整异常
        # ----------------------------------------------------

        print("\n")
        print("=" * 80)
        print("❌ PLANNER TEST FAILED")
        print("=" * 80)

        print("\n错误类型：")
        print(
            type(e).__name__
        )

        print("\n错误信息：")
        print(
            str(e)
        )

        print("\n完整 Traceback：")
        traceback.print_exc()

        print("\n" + "=" * 80)

        return False


# ============================================================
# 预设测试
# ============================================================

def run_demo_tests():
    """
    运行预设测试案例
    """

    test_queries = [

        # ----------------------------------------------------
        # Case 1
        # ----------------------------------------------------

        "什么是 Agent？",

        # ----------------------------------------------------
        # Case 2
        # ----------------------------------------------------

        "LangGraph 和 LangChain 有什么区别？",

        # ----------------------------------------------------
        # Case 3
        # ----------------------------------------------------

        "分析 2026 年 AI Agent 的发展趋势。",

        # ----------------------------------------------------
        # Case 4
        # ----------------------------------------------------

        (
            "分析 2026 年 AI Agent 的发展趋势，"
            "重点比较 OpenAI、Anthropic 和 Google 的技术路线，"
            "并分析未来企业 Agent 的发展方向。"
        )
    ]

    total = len(
        test_queries
    )

    passed = 0

    print("\n")
    print("=" * 80)
    print("🧪 PLANNER TEST SUITE")
    print("=" * 80)

    print(
        f"\n共 {total} 个测试案例"
    )

    # ========================================================
    # 逐个测试
    # ========================================================

    for index, query in enumerate(
        test_queries,
        start=1
    ):

        print("\n\n")

        print(
            f"################ TEST {index}/{total} ################"
        )

        success = test_planner(
            query
        )

        if success:
            passed += 1


    # ========================================================
    # 测试总结
    # ========================================================

    print("\n\n")
    print("=" * 80)
    print("📊 TEST SUMMARY")
    print("=" * 80)

    print(
        f"\nPassed: "
        f"{passed}/{total}"
    )

    print(
        f"Failed: "
        f"{total - passed}/{total}"
    )

    print("\n" + "=" * 80)


# ============================================================
# 交互模式
# ============================================================

def interactive_mode():
    """
    手动输入问题测试 Planner
    """

    print("\n")
    print("=" * 80)
    print("🤖 Planner Interactive Mode")
    print("=" * 80)

    print(
        "\n输入你的研究问题。"
    )

    print(
        "输入 exit / quit 退出。"
    )

    while True:

        print("\n" + "-" * 80)

        query = input(
            "\nResearch Question > "
        ).strip()

        if query.lower() in [
            "exit",
            "quit"
        ]:

            print(
                "\n👋 Exit."
            )

            break

        if not query:

            print(
                "⚠️ 问题不能为空。"
            )

            continue

        test_planner(
            query
        )


# ============================================================
# 主程序
# ============================================================

if __name__ == "__main__":

    print("\n")
    print("=" * 80)
    print("🧠 AI Agent Research System")
    print("Planner Agent Standalone Test")
    print("=" * 80)

    print(
        "\n选择测试模式："
    )

    print(
        "\n1. 运行预设测试"
    )

    print(
        "2. 手动输入问题"
    )

    print(
        "3. 退出"
    )

    choice = input(
        "\n请选择 [1/2/3]："
    ).strip()

    # --------------------------------------------------------
    # Demo Tests
    # --------------------------------------------------------

    if choice == "1":

        run_demo_tests()

    # --------------------------------------------------------
    # Interactive
    # --------------------------------------------------------

    elif choice == "2":

        interactive_mode()

    # --------------------------------------------------------
    # Exit
    # --------------------------------------------------------

    elif choice == "3":

        print(
            "\n👋 Exit."
        )

    else:

        print(
            "\n⚠️ 无效选择。"
        )