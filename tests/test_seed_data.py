import unittest
from pathlib import Path

from database.seed_data import generate_seed_from_feishu_csv, seed_to_sql


class TestSeedData(unittest.TestCase):
    def test_seed_sql_contains_core_inserts(self) -> None:
        seed = generate_seed_from_feishu_csv(Path(".claude/08小队网站V2项目管理_任务管理.csv"))
        sql = seed_to_sql(seed)
        self.assertIn("INSERT INTO users", sql)
        self.assertIn("INSERT INTO nodes", sql)
        self.assertIn("INSERT INTO citations", sql)
        self.assertIn("INSERT INTO revenue_distributions", sql)
        self.assertIn("ON CONFLICT ON CONSTRAINT citations_unique_edge DO NOTHING", sql)

