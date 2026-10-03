import sys

from langgraph.graph import StateGraph, START, END

from graph.state import ResearchState
from agents.planner import planner_node
from agents.researcher import research_worker_node
from agents.evidence_normalizer import evidence_normalizer_node
from agents.analyst import analyst_node
from agents.reviewer import reviewer_node
from agents.writer import writer_node
from agents.direct_answer import direct_answer_node
from graph.router import route_research_tasks


# Windows 控制台 UTF-8
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


# =========================================================
# Planner Routing
# =========================================================

def route_after_planner(state: ResearchState):

    if state.get("needs_web_search", False):
        return "research"

    return "direct_answer"


# =========================================================
# Output: Research Plan
# =========================================================

def print_research_plan(result: ResearchState):

    research_plan = result.get(
        "research_plan",
        []
    )

    print("\n" + "=" * 60)
    print("📋 Research Plan")
    print("=" * 60)

    for task in research_plan:

        print(f"\nTask {task.get('id')}")
        print(
            f"Topic: "
            f"{task.get('topic', '')}"
        )
        print(
            f"Objective: "
            f"{task.get('objective', '')}"
        )
        print(
            "Sources: "
            f"{', '.join(task.get('required_source_types', []))}"
        )
        print(
            f"Priority: "
            f"{task.get('priority', '')}"
        )


# =========================================================
# Output: Final Research Report
# =========================================================

def print_report(result: ResearchState):

    report = result.get(
        "report",
        {}
    )

    print("\n" + "=" * 60)
    print("📄 Final Research Report")
    print("=" * 60)

    if not report:
        print("\nNo report generated.")
        return

    print(
        f"\n# {report.get('title', 'Research Report')}"
    )

    print("\n## Executive Summary")
    print(
        report.get(
            "executive_summary",
            ""
        )
    )

    sections = report.get(
        "sections",
        []
    )

    for index, section in enumerate(
        sections,
        start=1
    ):

        if not isinstance(section, dict):
            continue

        print(
            f"\n## {index}. "
            f"{section.get('title', '')}"
        )

        print(
            f"\nFinding: "
            f"{section.get('finding', '')}"
        )

        print(
            f"\nAnalysis: "
            f"{section.get('analysis', '')}"
        )

        print(
            f"\nReviewer: "
            f"{str(section.get('review_verdict', '')).upper()} "
            f"({section.get('review_score', 0)}/100)"
        )

        supporting = section.get(
            "supporting_evidence",
            []
        )

        if supporting:

            print("\nSources:")

            for item in supporting:

                if not isinstance(item, dict):
                    continue

                print(
                    f"  - {item.get('source_title', '')}"
                )

                print(
                    f"    {item.get('source_url', '')}"
                )

    print("\n## Overall Analysis")
    print(
        report.get(
            "overall_analysis",
            ""
        )
    )


# =========================================================
# Output: Direct Answer
# =========================================================

def print_direct_answer(result: ResearchState):

    print("\n" + "=" * 60)
    print("💬 Direct Answer")
    print("=" * 60)

    print(
        f"\n{result.get('direct_answer', '')}"
    )


# =========================================================
# Build Graph
# =========================================================

def build_graph():

    builder = StateGraph(
        ResearchState
    )


    # =====================================================
    # Nodes
    # =====================================================

    builder.add_node(
        "planner",
        planner_node
    )

    builder.add_node(
        "research_router",
        lambda state: {}
    )

    builder.add_node(
        "research_worker",
        research_worker_node
    )

    builder.add_node(
        "evidence_normalizer",
        evidence_normalizer_node
    )

    builder.add_node(
        "analyst",
        analyst_node
    )

    builder.add_node(
        "reviewer",
        reviewer_node
    )

    builder.add_node(
        "writer",
        writer_node
    )

    builder.add_node(
        "direct_answer",
        direct_answer_node
    )


    # =====================================================
    # START → Planner
    # =====================================================

    builder.add_edge(
        START,
        "planner"
    )


    # =====================================================
    # Planner → Research / Direct Answer
    # =====================================================

    builder.add_conditional_edges(
        "planner",
        route_after_planner,
        {
            "research":
                "research_router",

            "direct_answer":
                "direct_answer",
        }
    )


    # =====================================================
    # Research Router → Parallel Workers
    # =====================================================

    builder.add_conditional_edges(
        "research_router",
        route_research_tasks
    )


    # =====================================================
    # Research Worker → Evidence Normalizer
    # =====================================================

    builder.add_edge(
        "research_worker",
        "evidence_normalizer"
    )


    # =====================================================
    # Evidence Normalizer → Analyst
    # =====================================================

    builder.add_edge(
        "evidence_normalizer",
        "analyst"
    )


    # =====================================================
    # Analyst → Reviewer
    # =====================================================

    builder.add_edge(
        "analyst",
        "reviewer"
    )


    # =====================================================
    # Reviewer → Writer
    # =====================================================

    builder.add_edge(
        "reviewer",
        "writer"
    )


    # =====================================================
    # Writer → END
    # =====================================================

    builder.add_edge(
        "writer",
        END
    )


    # =====================================================
    # Direct Answer → END
    # =====================================================

    builder.add_edge(
        "direct_answer",
        END
    )


    return builder.compile()


# =========================================================
# Main
# =========================================================

def main():

    print("=" * 60)
    print("       AI Agent Research System")
    print("=" * 60)

    query = input(
        "\n请输入你的研究问题：\n> "
    ).strip()

    if not query:

        print(
            "❌ Research question cannot be empty."
        )

        return

    initial_state: ResearchState = {
        "query": query
    }

    graph = build_graph()

    print(
        "\n🚀 Starting research workflow..."
    )

    try:

        result = graph.invoke(
            initial_state
        )

    except Exception as e:

        print("\n" + "=" * 60)
        print("❌ Workflow Failed")
        print("=" * 60)

        print(
            f"\nError Type: "
            f"{type(e).__name__}"
        )

        print(
            f"\nError: "
            f"{str(e)}"
        )

        return


    # =====================================================
    # Planner Decision
    # =====================================================

    print("\n" + "=" * 60)
    print("🧠 Planner Decision")
    print("=" * 60)

    print(
        f"\nResearch Goal: "
        f"{result.get('research_goal', 'N/A')}"
    )

    print(
        f"\nComplexity: "
        f"{result.get('research_complexity', 'N/A')}"
    )

    print(
        f"\nNeeds Web Search: "
        f"{result.get('needs_web_search', 'N/A')}"
    )


    # =====================================================
    # Final Output
    # =====================================================

    if result.get(
        "needs_web_search",
        False
    ):

        print_research_plan(
            result
        )

        print_report(
            result
        )

    else:

        print_direct_answer(
            result
        )


    print("\n" + "=" * 60)
    print("✅ Workflow completed.")
    print("=" * 60)


if __name__ == "__main__":
    main()
