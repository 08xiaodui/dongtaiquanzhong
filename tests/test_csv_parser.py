import tempfile
import unittest
from pathlib import Path

from utils.csv_parser import parse_feishu_tasks_csv


class TestCsvParser(unittest.TestCase):
    def test_parse_sample_feishu_csv(self) -> None:
        graph = parse_feishu_tasks_csv(Path(".claude/08小队网站V2项目管理_任务管理.csv"))
        self.assertGreater(len(graph.nodes), 0)
        self.assertGreater(len(graph.citations), 0)

        usernames = {u.username for u in graph.users}
        self.assertIn("梁耀文", usernames)

        edges = {(c.from_title, c.to_title) for c in graph.citations}
        self.assertIn(("邀请码", "搜索和发现学友"), edges)

    def test_creates_missing_parent_nodes(self) -> None:
        content = "\n".join(
            [
                "任务名称,任务执行人,任务管理人,父记录",
                "子任务,A,B,不存在的父任务",
            ]
        )
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "x.csv"
            p.write_text(content, encoding="utf-8")
            graph = parse_feishu_tasks_csv(p, create_missing_parents=True)
            titles = {n.title for n in graph.nodes}
            self.assertIn("不存在的父任务", titles)
            edges = {(c.from_title, c.to_title) for c in graph.citations}
            self.assertIn(("子任务", "不存在的父任务"), edges)

