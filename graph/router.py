from langgraph.types import Send

from graph.state import ResearchState


def route_research_tasks(
    state: ResearchState
):

    query = state["query"]

    research_plan = state.get(
        "research_plan",
        []
    )

    sends = []

    for task in research_plan:

        sends.append(
            Send(
                "research_worker",
                {
                    "query": query,
                    "task": task,
                }
            )
        )

    return sends