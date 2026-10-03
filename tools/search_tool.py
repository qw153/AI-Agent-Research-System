import os
from typing import List, Dict, Any
from dotenv import load_dotenv
from tavily import TavilyClient

# 加载项目根目录.env
BASE_DIR = os.path.abspath(os.path.join(__file__, "../.."))
load_dotenv(dotenv_path=os.path.join(BASE_DIR, ".env"))

TAVILY_API_KEY = os.getenv("TAVILY_API_KEY")

if not TAVILY_API_KEY:
    raise RuntimeError("请在.env配置 TAVILY_API_KEY，获取地址：https://tavily.com/")

tavily_client = TavilyClient(api_key=TAVILY_API_KEY)


def web_search(
    query: str,
    max_results: int = 5,
    search_depth: str = "basic"
) -> List[Dict[str, Any]]:
    """
    网页搜索工具
    :param query: 搜索关键词
    :param max_results: 返回最多几条结果
    :param search_depth: basic快速 / advanced深度搜索(消耗更多额度)
    :return: list[ {"title":标题, "url":链接, "content":摘要} ]
    """
    response = tavily_client.search(
        query=query,
        max_results=max_results,
        search_depth=search_depth
    )
    return response["results"]


def batch_web_search(query_list: List[str], max_results: int = 3) -> List[Dict[str, Any]]:
    """
    批量搜索：输入多个查询词，合并全部搜索结果
    """
    all_results = []
    for q in query_list:
        res = web_search(q.strip(), max_results=max_results)
        all_results.extend(res)
    return all_results


if __name__ == "__main__":
    # 本地测试工具
    test_res = web_search("工业无人机巡检算法研究现状", max_results=3)
    for item in test_res:
        print(f"【标题】{item['title']}")
        print(f"【URL】{item['url']}")
        print(f"【摘要】{item['content']}\n")
