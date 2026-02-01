from __future__ import annotations

import argparse
import csv
import dataclasses
import datetime as dt
import json
import re
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable


_DEFAULT_PARENT_COLUMNS = ("父记录", "父记录 副本")
_DEFAULT_TITLE_COLUMN = "任务名称"
_DEFAULT_EXECUTORS_COLUMN = "任务执行人"
_DEFAULT_MANAGERS_COLUMN = "任务管理人"
_DEFAULT_DESCRIPTION_COLUMN = "任务详细描述"
_DEFAULT_CREATED_DATE_COLUMN = "创建日期"
_DEFAULT_DEADLINE_COLUMN = "截止日期"


@dataclasses.dataclass(frozen=True)
class ParsedUser:
    username: str


@dataclasses.dataclass(frozen=True)
class ParsedNode:
    title: str
    node_type: str
    source: str
    source_ref: str
    created_date: dt.date | None = None
    deadline_date: dt.date | None = None
    description: str | None = None
    executors: tuple[str, ...] = ()
    managers: tuple[str, ...] = ()
    parents: tuple[str, ...] = ()
    is_api: bool = False
    api_call_count: int = 0


@dataclasses.dataclass(frozen=True)
class ParsedCitation:
    from_title: str
    to_title: str
    from_source_ref: str
    to_source_ref: str
    weight: float = 1.0


@dataclasses.dataclass(frozen=True)
class ParseWarning:
    code: str
    message: str
    row_index: int | None = None


@dataclasses.dataclass(frozen=True)
class ParsedGraph:
    users: tuple[ParsedUser, ...]
    nodes: tuple[ParsedNode, ...]
    citations: tuple[ParsedCitation, ...]
    warnings: tuple[ParseWarning, ...] = ()


def _normalize_text(value: str | None) -> str:
    if value is None:
        return ""
    return re.sub(r"\s+", " ", value.replace("\u3000", " ")).strip()


def _split_multivalue(value: str | None) -> tuple[str, ...]:
    text = _normalize_text(value)
    if not text:
        return ()
    parts: list[str] = []
    for token in re.split(r"[,\uFF0C;\uFF1B\n]+", text):
        token = _normalize_text(token)
        if token:
            parts.append(token)
    return tuple(parts)


def _parse_date(value: str | None) -> dt.date | None:
    text = _normalize_text(value)
    if not text:
        return None
    for fmt in ("%Y/%m/%d", "%Y-%m-%d", "%Y.%m.%d"):
        try:
            return dt.datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None


def parse_feishu_tasks_csv(
    csv_path: str | Path,
    *,
    source: str = "feishu_csv",
    parent_columns: Iterable[str] = _DEFAULT_PARENT_COLUMNS,
    create_missing_parents: bool = True,
) -> ParsedGraph:
    """
    Parse a Feishu-exported task management CSV into a node/citation graph.

    The CSV is expected to contain Chinese headers (e.g. 任务名称, 父记录).
    Parent relations are converted into directed citations: child -> parent.
    """
    csv_path = Path(csv_path)
    warnings: list[ParseWarning] = []

    with csv_path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames is None:
            raise ValueError("CSV has no header row")

        fieldnames = tuple(_normalize_text(name) for name in reader.fieldnames if name is not None)
        if _DEFAULT_TITLE_COLUMN not in fieldnames:
            raise ValueError(f"CSV missing required column: {_DEFAULT_TITLE_COLUMN}")

        normalized_parent_columns = tuple(col for col in parent_columns if col in fieldnames)
        if not normalized_parent_columns:
            warnings.append(
                ParseWarning(
                    code="missing_parent_columns",
                    message=f"CSV missing parent columns: {', '.join(parent_columns)}",
                )
            )

        raw_rows: list[dict[str, str]] = []
        for row in reader:
            normalized_row: dict[str, str] = {}
            for key, value in row.items():
                if key is None:
                    continue
                normalized_row[_normalize_text(key)] = "" if value is None else value
            raw_rows.append(normalized_row)

    title_counts: dict[str, int] = defaultdict(int)
    nodes_by_key: dict[str, ParsedNode] = {}
    nodes_by_title: dict[str, list[str]] = defaultdict(list)
    usernames: set[str] = set()

    def allocate_key_for_title(title: str) -> str:
        normalized = _normalize_text(title)
        title_counts[normalized] += 1
        suffix = title_counts[normalized]
        if suffix == 1:
            return normalized
        return f"{normalized}#{suffix}"

    for i, row in enumerate(raw_rows, start=1):
        title = _normalize_text(row.get(_DEFAULT_TITLE_COLUMN))
        if not title:
            warnings.append(
                ParseWarning(code="missing_title", message="Row missing 任务名称", row_index=i)
            )
            continue

        source_ref = f"row:{i}"
        node_key = allocate_key_for_title(title)
        created_date = _parse_date(row.get(_DEFAULT_CREATED_DATE_COLUMN))
        deadline_date = _parse_date(row.get(_DEFAULT_DEADLINE_COLUMN))
        description = _normalize_text(row.get(_DEFAULT_DESCRIPTION_COLUMN)) or None
        executors = _split_multivalue(row.get(_DEFAULT_EXECUTORS_COLUMN))
        managers = _split_multivalue(row.get(_DEFAULT_MANAGERS_COLUMN))

        parent_titles: list[str] = []
        for parent_col in normalized_parent_columns:
            for parent_title in _split_multivalue(row.get(parent_col)):
                if parent_title and parent_title != title:
                    parent_titles.append(parent_title)

        # 解析API相关字段
        is_api = False
        api_call_count = 0

        is_api_str = _normalize_text(row.get("是否是API"))
        if is_api_str and is_api_str not in ("", "nan", "NaN", "None"):
            try:
                is_api = bool(float(is_api_str))
            except ValueError:
                is_api = is_api_str.lower() in ("是", "true", "yes", "1")

        api_count_str = _normalize_text(row.get("API调用次数"))
        if api_count_str and api_count_str not in ("", "nan", "NaN", "None"):
            try:
                api_call_count = int(float(api_count_str))
            except ValueError:
                pass

        parent_titles = sorted(set(parent_titles))
        usernames.update(executors)
        usernames.update(managers)

        node = ParsedNode(
            title=title,
            node_type="task",
            source=source,
            source_ref=source_ref,
            created_date=created_date,
            deadline_date=deadline_date,
            description=description,
            executors=executors,
            managers=managers,
            parents=tuple(parent_titles),
            is_api=is_api,
            api_call_count=api_call_count,
        )
        nodes_by_key[node_key] = node
        nodes_by_title[title].append(node_key)

    if create_missing_parents:
        referenced_parents = set()
        for node in nodes_by_key.values():
            referenced_parents.update(node.parents)

        for parent_title in sorted(referenced_parents):
            if parent_title in nodes_by_title:
                continue
            node_key = allocate_key_for_title(parent_title)
            nodes_by_key[node_key] = ParsedNode(
                title=parent_title,
                node_type="task",
                source=source,
                source_ref="synthetic:missing_parent",
                parents=(),
            )
            nodes_by_title[parent_title].append(node_key)
            warnings.append(
                ParseWarning(
                    code="missing_parent_node_created",
                    message=f"Created missing parent node: {parent_title}",
                )
            )

    citations: list[ParsedCitation] = []
    for node_key, node in nodes_by_key.items():
        for parent_title in node.parents:
            parent_candidates = nodes_by_title.get(parent_title, [])
            if not parent_candidates:
                warnings.append(
                    ParseWarning(
                        code="missing_parent_node",
                        message=f"Parent node not found: {parent_title}",
                    )
                )
                continue
            if len(parent_candidates) > 1:
                warnings.append(
                    ParseWarning(
                        code="ambiguous_parent_title",
                        message=f"Parent title maps to multiple nodes: {parent_title}",
                    )
                )
            parent_key = parent_candidates[0]
            citations.append(
                ParsedCitation(
                    from_title=node.title,
                    to_title=parent_title,
                    from_source_ref=node.source_ref,
                    to_source_ref=nodes_by_key[parent_key].source_ref,
                    weight=1.0,
                )
            )

    users = tuple(sorted((ParsedUser(username=u) for u in usernames), key=lambda x: x.username))
    nodes = tuple(nodes_by_key.values())

    return ParsedGraph(
        users=users,
        nodes=nodes,
        citations=tuple(citations),
        warnings=tuple(warnings),
    )


def graph_to_jsonable(graph: ParsedGraph) -> dict[str, Any]:
    def date_to_str(value: dt.date | None) -> str | None:
        return value.isoformat() if value is not None else None

    return {
        "users": [dataclasses.asdict(u) for u in graph.users],
        "nodes": [
            {
                **dataclasses.asdict(n),
                "created_date": date_to_str(n.created_date),
                "deadline_date": date_to_str(n.deadline_date),
            }
            for n in graph.nodes
        ],
        "citations": [dataclasses.asdict(c) for c in graph.citations],
        "warnings": [dataclasses.asdict(w) for w in graph.warnings],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Parse Feishu CSV to node/citation graph (JSON).")
    parser.add_argument("--input", required=True, help="Path to Feishu-exported CSV")
    parser.add_argument("--output", help="Output JSON file path (default: stdout)")
    parser.add_argument("--no-create-missing-parents", action="store_true")
    args = parser.parse_args()

    graph = parse_feishu_tasks_csv(
        args.input, create_missing_parents=not args.no_create_missing_parents
    )
    payload = graph_to_jsonable(graph)
    content = json.dumps(payload, ensure_ascii=False, indent=2)
    if args.output:
        Path(args.output).write_text(content, encoding="utf-8")
    else:
        print(content)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
