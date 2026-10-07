"""核心纯函数单元测试（不调用 LLM，零成本、零网络）。

运行：
    python -m unittest tests.test_core -v

覆盖：
- tools/json_utils.extract_json_text
- agents/researcher.normalize_url / deduplicate_sources
- agents/evidence_normalizer.parse_json_response
- agents/reviewer.parse_json_response
- agents/writer.parse_json_response
"""
import os
import sys
import unittest
from pathlib import Path

# 兜底环境变量：避免 import llm 时因缺少 .env 而失败（测试不调用 LLM）
os.environ.setdefault("LLM_API_KEY", "test-key")
os.environ.setdefault("LLM_BASE_URL", "https://api.deepseek.com/v1")
os.environ.setdefault("LLM_MODEL", "deepseek-chat")

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from tools.json_utils import extract_json_text
from agents.researcher import normalize_url, deduplicate_sources
from agents.evidence_normalizer import parse_json_response as normalizer_parse
from agents.reviewer import parse_json_response as reviewer_parse
from agents.writer import parse_json_response as writer_parse


class TestExtractJsonText(unittest.TestCase):
    def test_pure_object(self):
        self.assertEqual(extract_json_text('{"a": 1}'), '{"a": 1}')

    def test_fenced_json(self):
        s = '```json\n{"a": 1}\n```'
        import json
        self.assertEqual(json.loads(extract_json_text(s)), {"a": 1})

    def test_text_around_json(self):
        import json
        self.assertEqual(json.loads(extract_json_text('结果是：{"a": 1}，完毕')), {"a": 1})

    def test_array(self):
        import json
        self.assertEqual(json.loads(extract_json_text("[1, 2, 3]")), [1, 2, 3])


class TestNormalizeUrl(unittest.TestCase):
    def test_lowercase_scheme_netloc_and_strip_fragment(self):
        self.assertEqual(
            normalize_url("HTTPS://Example.COM/path/#frag"),
            "https://example.com/path",
        )

    def test_strip_trailing_slash(self):
        self.assertEqual(normalize_url("https://example.com/path/"), "https://example.com/path")

    def test_empty(self):
        self.assertEqual(normalize_url(""), "")


class TestDeduplicateSources(unittest.TestCase):
    def test_dedup_by_normalized_url(self):
        sources = [
            {"url": "https://a.com/x", "title": "A"},
            {"url": "https://a.com/x/", "title": "A 重复"},  # 归一化后与上一条相同
            {"url": "https://b.com/y", "title": "B"},
        ]
        self.assertEqual(len(deduplicate_sources(sources)), 2)

    def test_keep_sources_without_url(self):
        sources = [{"title": "no url"}, {"url": "https://a.com", "title": "A"}]
        self.assertEqual(len(deduplicate_sources(sources)), 2)

    def test_skip_non_dict(self):
        sources = ["不是字典", {"url": "https://a.com", "title": "A"}]
        self.assertEqual(len(deduplicate_sources(sources)), 1)


class TestNormalizerParse(unittest.TestCase):
    def test_object(self):
        self.assertEqual(normalizer_parse('{"evidence": []}'), {"evidence": []})

    def test_array_wrapped(self):
        self.assertEqual(
            normalizer_parse('[{"claim": "x"}]'),
            {"evidence": [{"claim": "x"}]},
        )

    def test_fenced(self):
        self.assertEqual(
            normalizer_parse('```json\n{"evidence": []}\n```'),
            {"evidence": []},
        )

    def test_invalid_returns_none(self):
        self.assertIsNone(normalizer_parse("不是 JSON"))


class TestReviewerParse(unittest.TestCase):
    def test_object(self):
        self.assertEqual(reviewer_parse('{"reviews": []}'), {"reviews": []})

    def test_fenced(self):
        self.assertEqual(
            reviewer_parse('```json\n{"reviews": []}\n```'),
            {"reviews": []},
        )

    def test_invalid_raises(self):
        with self.assertRaises(ValueError):
            reviewer_parse("不是 JSON")


class TestWriterParse(unittest.TestCase):
    def test_object(self):
        self.assertEqual(writer_parse('{"report": {}}'), {"report": {}})

    def test_fenced(self):
        self.assertEqual(
            writer_parse('```json\n{"report": {}}\n```'),
            {"report": {}},
        )

    def test_invalid_raises(self):
        with self.assertRaises(ValueError):
            writer_parse("不是 JSON")


if __name__ == "__main__":
    unittest.main()
