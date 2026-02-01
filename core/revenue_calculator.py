from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from decimal import Decimal, ROUND_DOWN, ROUND_HALF_UP
from typing import Any, Iterable

from core.weight_calculator import WeightCalculator, calculate_reference_weight


_MONEY_QUANT = Decimal("0.01")


def _to_decimal(value: Any, *, field: str) -> Decimal:
    if isinstance(value, Decimal):
        return value
    if isinstance(value, int):
        return Decimal(value)
    if isinstance(value, str):
        return Decimal(value)
    if isinstance(value, float):
        return Decimal(str(value))
    raise TypeError(f"{field} must be Decimal|int|str|float, got {type(value).__name__}")


def _quantize_money(value: Decimal, *, rounding: str = ROUND_HALF_UP) -> Decimal:
    return value.quantize(_MONEY_QUANT, rounding=rounding)


@dataclass(frozen=True)
class RevenueNode:
    id: str
    creator_id: str
    created_at: dt.datetime
    citation_count: int = 0
    creativity_factor: Decimal = Decimal("1")
    propagation_rate: Decimal = Decimal("0")
    estimated_hours: Decimal | None = None
    actual_hours: Decimal | None = None

    def __post_init__(self) -> None:
        if not self.id:
            raise ValueError("node.id must be non-empty")
        if not self.creator_id:
            raise ValueError(f"node.creator_id must be non-empty for node {self.id}")
        if self.citation_count < 0:
            raise ValueError("citation_count must be >= 0")

        propagation_rate = _to_decimal(self.propagation_rate, field="propagation_rate")
        if propagation_rate < 0 or propagation_rate > 1:
            raise ValueError("propagation_rate must be in [0, 1]")
        object.__setattr__(self, "propagation_rate", propagation_rate)

        creativity_factor = _to_decimal(self.creativity_factor, field="creativity_factor")
        if creativity_factor < 0:
            raise ValueError("creativity_factor must be >= 0")
        object.__setattr__(self, "creativity_factor", creativity_factor)

        if self.estimated_hours is not None:
            object.__setattr__(
                self, "estimated_hours", _to_decimal(self.estimated_hours, field="estimated_hours")
            )
        if self.actual_hours is not None:
            object.__setattr__(
                self, "actual_hours", _to_decimal(self.actual_hours, field="actual_hours")
            )


@dataclass(frozen=True)
class RevenueEdge:
    from_node_id: str
    to_node_id: str
    weight: Decimal = Decimal("1")

    def __post_init__(self) -> None:
        weight = _to_decimal(self.weight, field="weight")
        if weight <= 0:
            raise ValueError("edge.weight must be > 0")
        object.__setattr__(self, "weight", weight)


@dataclass(frozen=True)
class RevenueAllocation:
    task_id: str
    node_id: str
    user_id: str
    amount: Decimal
    source: str
    propagation_level: int

    def __post_init__(self) -> None:
        if self.amount < 0:
            raise ValueError("allocation.amount must be >= 0")
        if self.propagation_level < 0:
            raise ValueError("allocation.propagation_level must be >= 0")


class RevenueGraph:
    def __init__(self, *, nodes: Iterable[RevenueNode], edges: Iterable[RevenueEdge] = ()) -> None:
        nodes_by_id: dict[str, RevenueNode] = {}
        for node in nodes:
            if node.id in nodes_by_id:
                raise ValueError(f"duplicate node id: {node.id}")
            nodes_by_id[node.id] = node

        upstream_by_node_id: dict[str, list[RevenueEdge]] = {nid: [] for nid in nodes_by_id}
        incoming_citation_count: dict[str, int] = {nid: 0 for nid in nodes_by_id}
        for edge in edges:
            if edge.from_node_id == edge.to_node_id:
                raise ValueError("self-loop edges are not allowed")
            if edge.from_node_id not in nodes_by_id:
                raise ValueError(f"edge.from_node_id not found: {edge.from_node_id}")
            if edge.to_node_id not in nodes_by_id:
                raise ValueError(f"edge.to_node_id not found: {edge.to_node_id}")
            upstream_by_node_id[edge.from_node_id].append(edge)
            incoming_citation_count[edge.to_node_id] += 1

        for lst in upstream_by_node_id.values():
            lst.sort(key=lambda e: (e.to_node_id, str(e.weight)))

        self._nodes_by_id = nodes_by_id
        self._upstream_by_node_id = upstream_by_node_id
        self._incoming_citation_count = incoming_citation_count

    def node(self, node_id: str) -> RevenueNode:
        return self._nodes_by_id[node_id]

    def upstream_edges(self, node_id: str) -> tuple[RevenueEdge, ...]:
        return tuple(self._upstream_by_node_id.get(node_id, ()))

    def incoming_citation_count(self, node_id: str) -> int:
        return self._incoming_citation_count.get(node_id, 0)


@dataclass(frozen=True)
class RevenueCalculatorConfig:
    max_propagation_depth: int = 5
    min_propagation_amount: Decimal = Decimal("0.01")
    max_retention_multiplier: Decimal = Decimal("1.75")

    def __post_init__(self) -> None:
        if self.max_propagation_depth < 0:
            raise ValueError("max_propagation_depth must be >= 0")
        min_amt = _to_decimal(self.min_propagation_amount, field="min_propagation_amount")
        if min_amt < 0:
            raise ValueError("min_propagation_amount must be >= 0")
        object.__setattr__(self, "min_propagation_amount", min_amt)
        max_mult = _to_decimal(self.max_retention_multiplier, field="max_retention_multiplier")
        if max_mult <= 0:
            raise ValueError("max_retention_multiplier must be > 0")
        object.__setattr__(self, "max_retention_multiplier", max_mult)


class RevenueCalculator:
    def __init__(
        self,
        *,
        graph: RevenueGraph,
        now: dt.datetime | None = None,
        config: RevenueCalculatorConfig | None = None,
        weight_calculator: WeightCalculator | None = None,
    ) -> None:
        self._graph = graph
        self._now = now or dt.datetime.now(tz=dt.timezone.utc)
        self._config = config or RevenueCalculatorConfig()
        self._weight_calculator = weight_calculator or WeightCalculator(now=self._now)

    def distribute(self, *, task_id: str, node_id: str, total_revenue: Decimal | int | str) -> tuple[RevenueAllocation, ...]:
        amount = _to_decimal(total_revenue, field="total_revenue")
        if amount < 0:
            raise ValueError("total_revenue must be >= 0")
        amount = _quantize_money(amount)

        allocations: list[RevenueAllocation] = []
        self._distribute_recursive(
            task_id=task_id,
            node_id=node_id,
            amount=amount,
            propagation_level=0,
            path=set(),
            out=allocations,
        )

        return tuple(a for a in allocations if a.amount >= _MONEY_QUANT)

    def _effective_propagation_rate(self, node: RevenueNode) -> Decimal:
        base_rate = node.propagation_rate
        base_retention = Decimal("1") - base_rate

        difficulty_factor = Decimal("1")
        if node.estimated_hours is not None and node.actual_hours is not None:
            if node.estimated_hours > 0 and node.actual_hours > 0:
                difficulty_factor = node.actual_hours / node.estimated_hours

        capped_factor = min(difficulty_factor, self._config.max_retention_multiplier)
        effective_retention = base_retention * capped_factor
        if effective_retention < 0:
            effective_retention = Decimal("0")
        if effective_retention > 1:
            effective_retention = Decimal("1")

        return Decimal("1") - effective_retention

    def _distribute_recursive(
        self,
        *,
        task_id: str,
        node_id: str,
        amount: Decimal,
        propagation_level: int,
        path: set[str],
        out: list[RevenueAllocation],
    ) -> None:
        if amount < _MONEY_QUANT:
            return

        node = self._graph.node(node_id)

        path_key = node_id
        if path_key in path:
            propagation_rate = Decimal("0")
        elif propagation_level >= self._config.max_propagation_depth:
            propagation_rate = Decimal("0")
        else:
            propagation_rate = self._effective_propagation_rate(node)

        pool = _quantize_money(amount * propagation_rate, rounding=ROUND_DOWN)
        if pool < self._config.min_propagation_amount:
            pool = Decimal("0.00")
        retention = amount - pool

        if retention >= _MONEY_QUANT:
            out.append(
                RevenueAllocation(
                    task_id=task_id,
                    node_id=node.id,
                    user_id=node.creator_id,
                    amount=retention,
                    source="direct" if propagation_level == 0 else "propagation",
                    propagation_level=propagation_level,
                )
            )

        if pool < _MONEY_QUANT:
            return

        upstream_edges = self._graph.upstream_edges(node_id)
        if not upstream_edges:
            out.append(
                RevenueAllocation(
                    task_id=task_id,
                    node_id=node.id,
                    user_id=node.creator_id,
                    amount=pool,
                    source="direct" if propagation_level == 0 else "propagation",
                    propagation_level=propagation_level,
                )
            )
            return

        weight_items: list[tuple[str, Decimal]] = []
        for edge in upstream_edges:
            upstream_node = self._graph.node(edge.to_node_id)
            effective_citation_count = max(
                upstream_node.citation_count,
                self._graph.incoming_citation_count(upstream_node.id),
            )
            node_weight = calculate_reference_weight(
                created_at=upstream_node.created_at,
                now=self._weight_calculator.now,
                citation_count=effective_citation_count,
                creativity_factor=upstream_node.creativity_factor,
            )
            combined_weight = node_weight * edge.weight
            if combined_weight <= 0:
                continue
            weight_items.append((upstream_node.id, combined_weight))

        total_weight = sum((w for _, w in weight_items), Decimal("0"))
        if total_weight <= 0:
            out.append(
                RevenueAllocation(
                    task_id=task_id,
                    node_id=node.id,
                    user_id=node.creator_id,
                    amount=pool,
                    source="direct" if propagation_level == 0 else "propagation",
                    propagation_level=propagation_level,
                )
            )
            return

        raw_shares: list[tuple[str, Decimal, Decimal, Decimal]] = []
        floor_sum = Decimal("0")
        for upstream_id, weight in weight_items:
            raw = (pool * weight) / total_weight
            floored = _quantize_money(raw, rounding=ROUND_DOWN)
            remainder = raw - floored
            raw_shares.append((upstream_id, raw, floored, remainder))
            floor_sum += floored

        remaining = pool - floor_sum
        remaining_cents = int((remaining / _MONEY_QUANT).to_integral_value(rounding=ROUND_DOWN))
        raw_shares.sort(key=lambda item: (-item[3], item[0]))

        shares_by_node: dict[str, Decimal] = {nid: floored for nid, _, floored, _ in raw_shares}
        for i in range(remaining_cents):
            nid = raw_shares[i % len(raw_shares)][0]
            shares_by_node[nid] = shares_by_node[nid] + _MONEY_QUANT

        new_path = set(path)
        new_path.add(path_key)
        for upstream_id, share in sorted(shares_by_node.items(), key=lambda item: item[0]):
            share = _quantize_money(share)
            if share < _MONEY_QUANT:
                continue
            self._distribute_recursive(
                task_id=task_id,
                node_id=upstream_id,
                amount=share,
                propagation_level=propagation_level + 1,
                path=new_path,
                out=out,
            )
