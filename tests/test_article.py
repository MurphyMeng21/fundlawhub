#!/usr/bin/env python3
"""Unit tests for scripts/article.py."""

import argparse
import sys
import unittest
from io import StringIO
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import article as art


class TestNumberConversion(unittest.TestCase):
    def test_arabic_to_chinese(self):
        cases = [
            (0, "零"),
            (1, "一"),
            (10, "十"),
            (14, "十四"),
            (217, "二百一十七"),
            (1001, "一千零一"),
            (10000, "一万"),
            (99999, "九万九千九百九十九"),
        ]
        for n, expected in cases:
            self.assertEqual(art.arabic_to_chinese(n), expected, f"failed for {n}")

    def test_chinese_to_arabic(self):
        cases = [
            ("零", 0),
            ("一", 1),
            ("十", 10),
            ("十四", 14),
            ("二百一十七", 217),
            ("一千零一", 1001),
            ("九万九千九百九十九", 99999),
        ]
        for s, expected in cases:
            self.assertEqual(art.chinese_to_arabic(s), expected, f"failed for {s}")


class TestHeadingPatterns(unittest.TestCase):
    def test_chinese_pattern(self):
        p = art._build_heading_regex("chinese")
        self.assertIsNotNone(p.match("第二百一十七条"))
        self.assertIsNotNone(p.match("第 二百一十七 条"))
        self.assertIsNone(p.match("第217条"))

    def test_arabic_pattern(self):
        p = art._build_heading_regex("arabic")
        self.assertIsNotNone(p.match("第217条"))
        self.assertIsNotNone(p.match("第 217 条"))
        self.assertIsNone(p.match("第二百一十七条"))

    def test_dotted_pattern(self):
        p = art._build_heading_regex("dotted")
        self.assertIsNotNone(p.match("1."))
        self.assertIsNotNone(p.match("217、"))
        self.assertIsNone(p.match("第二百一十七条"))

    def test_auto_pattern(self):
        p = art._build_heading_regex("auto")
        self.assertIsNotNone(p.match("第二百一十七条"))
        self.assertIsNotNone(p.match("第217条"))
        self.assertIsNotNone(p.match("1."))


class TestDetectNumberingStyle(unittest.TestCase):
    def test_chinese_from_toc(self):
        toc = [
            {"title": "第一章 总则"},
            {"title": "第二百一十七条 不动产登记"},
        ]
        self.assertEqual(art.detect_numbering_style({"data": {"content": {"children": toc}}}), "chinese")

    def test_arabic_from_toc(self):
        toc = [
            {"title": "第1条"},
            {"title": "第217条"},
        ]
        self.assertEqual(art.detect_numbering_style({"data": {"content": {"children": toc}}}), "arabic")

    def test_dotted_from_toc(self):
        toc = [
            {"title": "1."},
            {"title": "2."},
        ]
        self.assertEqual(art.detect_numbering_style({"data": {"content": {"children": toc}}}), "dotted")

    def test_empty_toc(self):
        self.assertEqual(art.detect_numbering_style({}), "auto")


class MockParagraph:
    def __init__(self, text):
        self.text = text


class MockDocument:
    def __init__(self, texts):
        self.paragraphs = [MockParagraph(t) for t in texts]


def _make_docx(texts):
    def _factory(path):
        return MockDocument(texts)
    return _factory


class TestExtractArticles(unittest.TestCase):
    @mock.patch("article.docx.Document", side_effect=_make_docx([
        "第一章 总则",
        "第一条 为了规范...",
        "第二条 本法所称...",
        "第三条 民事主体...",
        "第四条 民事主体...",
        "第二章 物权",
        "第二百一十七条 不动产物权的设立...",
        "第二百一十八条 权利人享有...",
        "第二百一十九条 利害关系人...",
    ]))
    def test_single_article_with_context(self, _):
        result = art.extract_articles_from_docx("fake.docx", [217], context=1)
        self.assertIn(217, result["found"])
        texts = [s["text"] for s in result["segments"]]
        self.assertTrue(any("第二百一十七条" in t for t in texts))
        self.assertTrue(any("第二百一十八条" in t for t in texts))
        self.assertFalse(any("第一条" in t for t in texts))

    @mock.patch("article.docx.Document", side_effect=_make_docx([
        "第1条 为了规范...",
        "第2条 本法所称...",
        "第217条 不动产物权...",
        "第218条 权利人享有...",
    ]))
    def test_arabic_style(self, _):
        result = art.extract_articles_from_docx("fake.docx", [217], context=0, style="arabic")
        self.assertEqual(result["found"], [217])
        texts = [s["text"] for s in result["segments"]]
        self.assertEqual(texts, ["第217条 不动产物权..."])

    @mock.patch("article.docx.Document", side_effect=_make_docx([
        "1. 为了规范...",
        "2. 本法所称...",
        "3. 不动产物权...",
    ]))
    def test_dotted_style(self, _):
        result = art.extract_articles_from_docx("fake.docx", [2], context=1, style="dotted")
        self.assertEqual(result["found"], [2])
        texts = [s["text"] for s in result["segments"]]
        self.assertEqual(len(texts), 3)

    @mock.patch("article.docx.Document", side_effect=_make_docx([
        "第一条 为了规范...",
        "第二百一十七条 不动产物权...",
        "第二百一十八条 权利人享有...",
    ]))
    def test_batch_with_overlap(self, _):
        result = art.extract_articles_from_docx("fake.docx", [1, 217], context=1)
        self.assertEqual(result["found"], [1, 217])
        # target 1 wants {0,1,2}; target 217 wants {216,217,218}. Available articles are 1, 217, 218.
        self.assertEqual(len(result["segments"]), 3)

    @mock.patch("article.docx.Document", side_effect=_make_docx([
        "第一条 为了规范...",
        "第二条 本法所称...",
    ]))
    def test_not_found(self, _):
        result = art.extract_articles_from_docx("fake.docx", [217], context=0)
        self.assertEqual(result["found"], [])
        self.assertEqual(result["not_found"], [217])


class TestResolveLawId(unittest.TestCase):
    def test_hex_identifier(self):
        with mock.patch("article.dl.fetch_detail") as fetch, mock.patch("article.dl.parse_detail") as parse:
            fetch.return_value = {"code": 200}
            parse.return_value = {"title": "民法典", "bbbs": "a" * 32}
            bbbs, detail = art.resolve_law_id("a" * 32)
            self.assertEqual(bbbs, "a" * 32)
            self.assertEqual(detail["title"], "民法典")

    def test_keyword_search(self):
        with mock.patch("article.dl.search_laws") as search, mock.patch("article.dl.fetch_detail") as fetch, mock.patch("article.dl.parse_detail") as parse:
            search.return_value = {"code": 200, "rows": [{"bbbs": "b" * 32}]}
            fetch.return_value = {"code": 200}
            parse.return_value = {"title": "民法典", "bbbs": "b" * 32}
            bbbs, detail = art.resolve_law_id("民法典")
            self.assertEqual(bbbs, "b" * 32)
            self.assertEqual(detail["title"], "民法典")


class TestParseArticleNumbers(unittest.TestCase):
    def test_single(self):
        self.assertEqual(art.parse_article_numbers("217"), [217])

    def test_multiple(self):
        self.assertEqual(art.parse_article_numbers("51,211,347"), [51, 211, 347])

    def test_invalid(self):
        with self.assertRaises(argparse.ArgumentTypeError):
            art.parse_article_numbers("abc")


class TestCLI(unittest.TestCase):
    def test_parser(self):
        args = art.build_parser().parse_args(["217", "民法典", "--context", "0", "--json"])
        self.assertEqual(args.articles, "217")
        self.assertEqual(args.law, "民法典")
        self.assertEqual(args.context, 0)
        self.assertTrue(args.json)


if __name__ == "__main__":
    unittest.main()
