import datetime as dt
import unittest
from decimal import Decimal

from core.revenue_calculator import (
    RevenueCalculator,
    RevenueCalculatorConfig,
    RevenueEdge,
    RevenueGraph,
    RevenueNode,
)
from core.weight_calculator import calculate_reference_weight


class TestRevenueDistribution(unittest.TestCase):
    def setUp(self) -> None:
        self.now = dt.datetime(2026, 1, 1, tzinfo=dt.timezone.utc)

    def test_reference_weight_time_citation_creativity(self) -> None:
        created_at = self.now - dt.timedelta(days=365)
        weight = calculate_reference_weight(
            created_at=created_at,
            now=self.now,
            citation_count=10,
            creativity_factor=Decimal("2"),
        )
        self.assertEqual(weight, Decimal("10"))

    def test_difficulty_compensation_adjusts_upstream_pool(self) -> None:
        task = RevenueNode(
            id="task",
            creator_id="executor",
            created_at=self.now,
            propagation_rate=Decimal("0.6"),
            estimated_hours=Decimal("100"),
            actual_hours=Decimal("300"),
        )
        upstream = RevenueNode(
            id="upstream",
            creator_id="upstream_owner",
            created_at=self.now,
            propagation_rate=Decimal("0"),
        )
        graph = RevenueGraph(
            nodes=[task, upstream],
            edges=[RevenueEdge(from_node_id="task", to_node_id="upstream")],
        )
        calc = RevenueCalculator(graph=graph, now=self.now)
        allocations = calc.distribute(task_id="task", node_id="task", total_revenue=Decimal("100"))

        by_user: dict[str, Decimal] = {}
        for a in allocations:
            by_user[a.user_id] = by_user.get(a.user_id, Decimal("0")) + a.amount

        # base retention=0.4, difficulty=3, cap=1.75 => retention=0.7, propagation=0.3
        self.assertEqual(by_user["executor"], Decimal("70.00"))
        self.assertEqual(by_user["upstream_owner"], Decimal("30.00"))
        self.assertEqual(sum(by_user.values(), Decimal("0")), Decimal("100.00"))

    def test_prd_example_ten_upstream_nodes(self) -> None:
        task = RevenueNode(
            id="article",
            creator_id="author",
            created_at=self.now,
            propagation_rate=Decimal("0.85"),
        )

        core = RevenueNode(
            id="core_theory",
            creator_id="core_author",
            created_at=self.now,
            citation_count=5,
            creativity_factor=Decimal("8"),  # weight 40
            propagation_rate=Decimal("0"),
        )
        method = RevenueNode(
            id="method",
            creator_id="method_author",
            created_at=self.now,
            citation_count=3,
            creativity_factor=Decimal("10"),  # weight 30
            propagation_rate=Decimal("0"),
        )
        others: list[RevenueNode] = []
        for i in range(8):
            others.append(
                RevenueNode(
                    id=f"other_{i+1}",
                    creator_id=f"other_author_{i+1}",
                    created_at=self.now,
                    citation_count=1,
                    creativity_factor=Decimal("3.75"),  # 8 * 3.75 = 30
                    propagation_rate=Decimal("0"),
                )
            )

        nodes = [task, core, method, *others]
        edges = [
            RevenueEdge(from_node_id="article", to_node_id="core_theory"),
            RevenueEdge(from_node_id="article", to_node_id="method"),
            *[RevenueEdge(from_node_id="article", to_node_id=n.id) for n in others],
        ]
        graph = RevenueGraph(nodes=nodes, edges=edges)
        calc = RevenueCalculator(graph=graph, now=self.now)
        allocations = calc.distribute(task_id="article", node_id="article", total_revenue=Decimal("100"))

        by_user: dict[str, Decimal] = {}
        for a in allocations:
            by_user[a.user_id] = by_user.get(a.user_id, Decimal("0")) + a.amount

        self.assertEqual(sum(by_user.values(), Decimal("0")), Decimal("100.00"))
        self.assertEqual(by_user["author"], Decimal("15.00"))
        self.assertEqual(by_user["core_author"], Decimal("34.00"))
        self.assertEqual(by_user["method_author"], Decimal("25.50"))

        other_total = sum(
            (by_user[f"other_author_{i+1}"] for i in range(8)),
            Decimal("0"),
        )
        self.assertEqual(other_total, Decimal("25.50"))
        for i in range(8):
            self.assertIn(by_user[f"other_author_{i+1}"], {Decimal("3.18"), Decimal("3.19")})

    def test_max_depth_stops_recursive_propagation(self) -> None:
        nodes: list[RevenueNode] = []
        edges: list[RevenueEdge] = []
        chain_length = 8
        for i in range(chain_length):
            nodes.append(
                RevenueNode(
                    id=f"n{i}",
                    creator_id=f"u{i}",
                    created_at=self.now,
                    propagation_rate=Decimal("1"),
                )
            )
            if i > 0:
                edges.append(RevenueEdge(from_node_id=f"n{i-1}", to_node_id=f"n{i}"))

        graph = RevenueGraph(nodes=nodes, edges=edges)
        config = RevenueCalculatorConfig(max_propagation_depth=5, min_propagation_amount=Decimal("0.01"))
        calc = RevenueCalculator(graph=graph, now=self.now, config=config)
        allocations = calc.distribute(task_id="n0", node_id="n0", total_revenue=Decimal("10.00"))

        by_user: dict[str, Decimal] = {}
        for a in allocations:
            by_user[a.user_id] = by_user.get(a.user_id, Decimal("0")) + a.amount

        # With full propagation, only the depth-capped node retains.
        self.assertEqual(sum(by_user.values(), Decimal("0")), Decimal("10.00"))
        self.assertEqual(by_user.get("u5"), Decimal("10.00"))
        self.assertNotIn("u6", by_user)

    def test_cycle_detection_prevents_infinite_recursion(self) -> None:
        a = RevenueNode(
            id="a",
            creator_id="ua",
            created_at=self.now,
            propagation_rate=Decimal("1"),
        )
        b = RevenueNode(
            id="b",
            creator_id="ub",
            created_at=self.now,
            propagation_rate=Decimal("0.5"),
        )
        graph = RevenueGraph(
            nodes=[a, b],
            edges=[
                RevenueEdge(from_node_id="a", to_node_id="b"),
                RevenueEdge(from_node_id="b", to_node_id="a"),
            ],
        )
        calc = RevenueCalculator(graph=graph, now=self.now, config=RevenueCalculatorConfig(max_propagation_depth=50))
        allocations = calc.distribute(task_id="a", node_id="a", total_revenue=Decimal("10.00"))

        by_user: dict[str, Decimal] = {}
        for alloc in allocations:
            by_user[alloc.user_id] = by_user.get(alloc.user_id, Decimal("0")) + alloc.amount

        self.assertEqual(sum(by_user.values(), Decimal("0")), Decimal("10.00"))
        self.assertEqual(by_user["ub"], Decimal("5.00"))
        self.assertEqual(by_user["ua"], Decimal("5.00"))


if __name__ == "__main__":  # pragma: no cover
    unittest.main()

