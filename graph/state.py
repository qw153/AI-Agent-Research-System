from typing import TypedDict, List, Dict, Any, Annotated
import operator


class ResearchState(TypedDict, total=False):

    # =========================================================
    # User Input
    # =========================================================

    query: str


    # =========================================================
    # Planner
    # =========================================================

    # Planner 生成的研究目标
    research_goal: str

    # 研究问题复杂度：
    # simple / medium / complex
    research_complexity: str

    # 是否需要进行 Web Search
    needs_web_search: bool

    # Planner 生成的研究任务列表
    research_plan: List[Dict[str, Any]]


    # =========================================================
    # Current Research Task
    # =========================================================

    # LangGraph Send 分发给 Research Worker 的当前任务
    task: Dict[str, Any]


    # =========================================================
    # Research Worker
    #
    # 多个 Research Worker 自动合并
    # =========================================================

    research_results: Annotated[
        List[Dict[str, Any]],
        operator.add
    ]


    # =========================================================
    # Evidence Normalizer
    #
    # 多个 Evidence 自动合并
    # =========================================================

    evidence: Annotated[
        List[Dict[str, Any]],
        operator.add
    ]


    # =========================================================
    # Analyst
    # =========================================================

    # Analyst 生成的研究结论
    claims: List[Dict[str, Any]]


    # =========================================================
    # Reviewer
    #
    # 对 Analyst 生成的研究结论进行质量检查
    # =========================================================

    # Reviewer 输出的审核结果
    #
    # 通常包含：
    # claim_index / verdict / score / issues / reason
    review_results: List[Dict[str, Any]]


    # =========================================================
    # Writer
    #
    # 将经过审核的研究结论整理成最终研究报告
    # =========================================================

    # Writer 生成的最终 Research Report
    report: Dict[str, Any]


    # =========================================================
    # Direct Answer
    # =========================================================

    # 不需要 Web Search 时，
    # 由 Direct Answer Agent 直接回答用户
    direct_answer: str
