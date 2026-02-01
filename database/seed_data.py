from __future__ import annotations

import argparse
import datetime as dt
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

try:
    from utils.csv_parser import ParsedGraph, ParsedNode, ParsedUser, parse_feishu_tasks_csv
except ModuleNotFoundError:  # pragma: no cover
    import sys

    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from utils.csv_parser import ParsedGraph, ParsedNode, ParsedUser, parse_feishu_tasks_csv


_SEED_NAMESPACE = uuid.UUID("7b0b3475-f87f-4fdc-8a25-3e4aa6b1b135")


@dataclass(frozen=True)
class SeedUser:
    id: uuid.UUID
    username: str
    reputation_score: float = 0.0
    contribution_score: int = 0
    level: str = "novice"
    violation_count: int = 0
    created_at: dt.datetime | None = None


@dataclass(frozen=True)
class SeedNode:
    id: uuid.UUID
    title: str
    node_type: str = "task"
    creator_id: uuid.UUID | None = None
    created_at: dt.datetime | None = None
    api_call_count: int = 0
    citation_count: int = 0
    source: str = "manual"
    source_ref: str | None = None


@dataclass(frozen=True)
class SeedCitation:
    id: uuid.UUID
    from_node_id: uuid.UUID
    to_node_id: uuid.UUID
    weight: float = 1.0
    created_at: dt.datetime | None = None


@dataclass(frozen=True)
class SeedRevenueDistribution:
    id: uuid.UUID
    task_id: uuid.UUID
    node_id: uuid.UUID
    user_id: uuid.UUID
    amount: str
    source: str
    propagation_level: int
    created_at: dt.datetime | None = None


@dataclass(frozen=True)
class SeedData:
    users: tuple[SeedUser, ...]
    nodes: tuple[SeedNode, ...]
    citations: tuple[SeedCitation, ...]
    revenue_distributions: tuple[SeedRevenueDistribution, ...]


def _sql_text(value: str | None) -> str:
    if value is None:
        return "NULL"
    return "'" + value.replace("'", "''") + "'"


def _sql_uuid(value: uuid.UUID | None) -> str:
    if value is None:
        return "NULL"
    return f"'{value}'::uuid"


def _sql_timestamptz(value: dt.datetime | None) -> str:
    if value is None:
        return "DEFAULT"
    if value.tzinfo is None:
        value = value.replace(tzinfo=dt.timezone.utc)
    return _sql_text(value.isoformat())


def _uuid5(key: str) -> uuid.UUID:
    return uuid.uuid5(_SEED_NAMESPACE, key)


def _user_id(username: str) -> uuid.UUID:
    return _uuid5(f"user:{username}")


def _node_id(node: ParsedNode) -> uuid.UUID:
    return _uuid5(f"node:{node.source}:{node.source_ref}:{node.title}")


def _citation_id(from_node_id: uuid.UUID, to_node_id: uuid.UUID) -> uuid.UUID:
    return _uuid5(f"citation:{from_node_id}:{to_node_id}")


def _revenue_id(
    *, task_id: uuid.UUID, node_id: uuid.UUID, user_id: uuid.UUID, source: str, level: int
) -> uuid.UUID:
    return _uuid5(f"revenue:{task_id}:{node_id}:{user_id}:{source}:{level}")


def generate_seed_from_graph(graph: ParsedGraph, *, now: dt.datetime | None = None) -> SeedData:
    now = now or dt.datetime.now(tz=dt.timezone.utc)

    seed_users = tuple(
        SeedUser(id=_user_id(u.username), username=u.username, created_at=now) for u in graph.users
    )
    user_id_by_username = {u.username: u.id for u in seed_users}

    node_id_by_source_ref: dict[str, uuid.UUID] = {}
    node_by_source_ref: dict[str, ParsedNode] = {}
    seed_nodes: list[SeedNode] = []
    for n in graph.nodes:
        nid = _node_id(n)
        node_id_by_source_ref[n.source_ref] = nid
        node_by_source_ref[n.source_ref] = n

        creator_username = (n.managers[0] if n.managers else None) or (
            n.executors[0] if n.executors else None
        )
        creator_id = user_id_by_username.get(creator_username) if creator_username else None
        created_at = (
            dt.datetime.combine(n.created_date, dt.time(0, 0), tzinfo=dt.timezone.utc)
            if n.created_date
            else now
        )
        seed_nodes.append(
            SeedNode(
                id=nid,
                title=n.title,
                node_type=n.node_type,
                creator_id=creator_id,
                created_at=created_at,
                source=n.source,
                source_ref=n.source_ref,
            )
        )

    node_ids_by_title: dict[str, list[uuid.UUID]] = {}
    for n in seed_nodes:
        node_ids_by_title.setdefault(n.title, []).append(n.id)

    seed_citations: list[SeedCitation] = []
    for c in graph.citations:
        from_id = node_id_by_source_ref.get(c.from_source_ref) or node_ids_by_title.get(
            c.from_title, [None]
        )[0]
        to_id = node_id_by_source_ref.get(c.to_source_ref) or node_ids_by_title.get(
            c.to_title, [None]
        )[0]
        if from_id is None or to_id is None:
            continue
        seed_citations.append(
            SeedCitation(
                id=_citation_id(from_id, to_id),
                from_node_id=from_id,
                to_node_id=to_id,
                weight=c.weight,
                created_at=now,
            )
        )

    # Simple, deterministic sample revenue rows (for integration testing).
    seed_revenue: list[SeedRevenueDistribution] = []
    for n in graph.nodes:
        task_id = node_id_by_source_ref[n.source_ref]
        executors = n.executors
        if executors:
            per_user_amount = "100.00"
            for username in executors:
                uid = user_id_by_username.get(username)
                if uid is None:
                    continue
                seed_revenue.append(
                    SeedRevenueDistribution(
                        id=_revenue_id(
                            task_id=task_id,
                            node_id=task_id,
                            user_id=uid,
                            source="direct",
                            level=0,
                        ),
                        task_id=task_id,
                        node_id=task_id,
                        user_id=uid,
                        amount=per_user_amount,
                        source="direct",
                        propagation_level=0,
                        created_at=now,
                    )
                )

    for c in graph.citations:
        child_id = node_id_by_source_ref.get(c.from_source_ref)
        parent_id = node_id_by_source_ref.get(c.to_source_ref)
        if child_id is None or parent_id is None:
            continue

        parent_node = node_by_source_ref.get(c.to_source_ref)
        if parent_node is None:
            continue
        beneficiary = (parent_node.managers[0] if parent_node.managers else None) or (
            parent_node.executors[0] if parent_node.executors else None
        )
        if beneficiary is None:
            continue
        uid = user_id_by_username.get(beneficiary)
        if uid is None:
            continue

        seed_revenue.append(
            SeedRevenueDistribution(
                id=_revenue_id(
                    task_id=child_id,
                    node_id=parent_id,
                    user_id=uid,
                    source="propagation",
                    level=1,
                ),
                task_id=child_id,
                node_id=parent_id,
                user_id=uid,
                amount="50.00",
                source="propagation",
                propagation_level=1,
                created_at=now,
            )
        )

    return SeedData(
        users=seed_users,
        nodes=tuple(seed_nodes),
        citations=tuple(seed_citations),
        revenue_distributions=tuple(seed_revenue),
    )


def generate_seed_from_feishu_csv(csv_path: str | Path) -> SeedData:
    graph = parse_feishu_tasks_csv(csv_path)
    return generate_seed_from_graph(graph)


def seed_to_sql(seed: SeedData) -> str:
    lines: list[str] = []
    lines.append("BEGIN;")
    lines.append("")

    for u in seed.users:
        lines.append(
            "INSERT INTO users (id, username, reputation_score, contribution_score, level, violation_count, created_at)"
            f" VALUES ({_sql_uuid(u.id)}, {_sql_text(u.username)}, {u.reputation_score}, {u.contribution_score},"
            f" {_sql_text(u.level)}::user_level, {u.violation_count}, {_sql_timestamptz(u.created_at)})"
            " ON CONFLICT (username) DO NOTHING;"
        )
    lines.append("")

    for n in seed.nodes:
        lines.append(
            "INSERT INTO nodes (id, title, type, creator_id, created_at, api_call_count, citation_count, source, source_ref)"
            f" VALUES ({_sql_uuid(n.id)}, {_sql_text(n.title)}, {_sql_text(n.node_type)}::node_type,"
            f" {_sql_uuid(n.creator_id)}, {_sql_timestamptz(n.created_at)}, {n.api_call_count}, {n.citation_count},"
            f" {_sql_text(n.source)}, {_sql_text(n.source_ref)})"
            " ON CONFLICT (id) DO NOTHING;"
        )
    lines.append("")

    for c in seed.citations:
        lines.append(
            "INSERT INTO citations (id, from_node_id, to_node_id, weight, created_at)"
            f" VALUES ({_sql_uuid(c.id)}, {_sql_uuid(c.from_node_id)}, {_sql_uuid(c.to_node_id)}, {c.weight},"
            f" {_sql_timestamptz(c.created_at)})"
            " ON CONFLICT ON CONSTRAINT citations_unique_edge DO NOTHING;"
        )
    lines.append("")

    for r in seed.revenue_distributions:
        lines.append(
            "INSERT INTO revenue_distributions (id, task_id, node_id, user_id, amount, source, propagation_level, created_at)"
            f" VALUES ({_sql_uuid(r.id)}, {_sql_uuid(r.task_id)}, {_sql_uuid(r.node_id)}, {_sql_uuid(r.user_id)},"
            f" {r.amount}::numeric(10,2), {_sql_text(r.source)}::revenue_source, {r.propagation_level},"
            f" {_sql_timestamptz(r.created_at)})"
            " ON CONFLICT (id) DO NOTHING;"
        )

    lines.append("")
    lines.append("COMMIT;")
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate seed SQL for the MVP database.")
    parser.add_argument(
        "--csv",
        help="Feishu CSV path (default: .claude/08小队网站V2项目管理_任务管理.csv if exists)",
    )
    parser.add_argument("--out", help="Write SQL to this file (default: stdout)")
    args = parser.parse_args()

    default_csv = Path(".claude/08小队网站V2项目管理_任务管理.csv")
    csv_path = Path(args.csv) if args.csv else default_csv
    if not csv_path.exists():
        raise FileNotFoundError(f"CSV not found: {csv_path}")

    seed = generate_seed_from_feishu_csv(csv_path)
    sql = seed_to_sql(seed)
    if args.out:
        Path(args.out).write_text(sql, encoding="utf-8")
    else:
        print(sql)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
