#!/usr/bin/env python3
"""
计算所有人的动态权重
基于任务引用关系和被引用次数，计算每个用户在整个项目中的权重
"""

import argparse
import json
from decimal import Decimal
from pathlib import Path
from collections import defaultdict
from utils.csv_parser import parse_feishu_tasks_csv
from core.revenue_calculator import RevenueNode, RevenueEdge, RevenueGraph
import datetime as dt


def calculate_user_weights(csv_path: Path, save_debug: bool = False):
    """计算所有用户的动态权重"""

    print("=" * 80)
    print("📊 计算所有用户动态权重")
    print("=" * 80)

    # Step 1: 解析CSV
    print("\n[Step 1] 解析CSV...")
    parsed = parse_feishu_tasks_csv(csv_path)
    print(f"  ✓ 解析完成: {len(parsed.nodes)} 个任务, {len(parsed.citations)} 条引用")

    # Step 2: 构建节点映射
    print("\n[Step 2] 构建节点映射...")
    node_map = {}
    for node in parsed.nodes:
        node_map[node.title] = RevenueNode(
            id=node.title,
            creator_id=node.executors[0] if node.executors else "未分配",
            created_at=node.created_date or dt.date.today(),
            citation_count=sum(1 for c in parsed.citations if c.to_title == node.title),
            creativity_factor=Decimal("1.0"),
            propagation_rate=Decimal("0.3"),
        )
    print(f"  ✓ 创建了 {len(node_map)} 个节点")

    # Step 3: 构建引用边
    print("\n[Step 3] 构建引用边...")
    edges = []
    for citation in parsed.citations:
        if citation.from_title in node_map and citation.to_title in node_map:
            edges.append(RevenueEdge(
                from_node_id=citation.from_title,
                to_node_id=citation.to_title,
                weight=Decimal(str(citation.weight))
            ))
    print(f"  ✓ 创建了 {len(edges)} 条引用边")

    # Step 4: 计算每个用户的任务权重
    print("\n[Step 4] 计算用户任务权重...")
    user_stats = defaultdict(lambda: {
        "task_count": 0,  # 任务数量
        "direct_citations": 0,  # 作为执行人的任务被引用次数
        "total_citation_weight": Decimal("0"),  # 总引用权重
        "tasks": []  # 任务列表
    })

    for node in node_map.values():
        user = node.creator_id
        user_stats[user]["task_count"] += 1
        user_stats[user]["direct_citations"] += node.citation_count

        # 计算该节点的权重贡献
        # 权重 = 被引用次数 × 创造性系数 × 时间优先系数
        days_elapsed = (dt.date.today() - node.created_at).days
        time_priority = 1 / (1 + days_elapsed / 365)
        node_weight = Decimal(str(node.citation_count)) * node.creativity_factor * Decimal(str(time_priority))

        user_stats[user]["total_citation_weight"] += node_weight
        user_stats[user]["tasks"].append({
            "title": node.id,
            "citations": node.citation_count,
            "weight": float(node_weight)
        })

    print(f"  ✓ 统计了 {len(user_stats)} 个用户")

    # Step 5: 计算标准化权重（占比）
    print("\n[Step 5] 计算标准化权重...")
    total_weight = sum(stats["total_citation_weight"] for stats in user_stats.values())

    user_weights = []
    for user, stats in user_stats.items():
        weight = stats["total_citation_weight"]
        normalized_weight = float(weight / total_weight * 100) if total_weight > 0 else 0

        user_weights.append({
            "user": user,
            "task_count": stats["task_count"],
            "total_citations": stats["direct_citations"],
            "raw_weight": float(weight),
            "normalized_weight": normalized_weight,  # 百分比
            "tasks": sorted(stats["tasks"], key=lambda x: x["weight"], reverse=True)[:5]  # 只保留前5个任务
        })

    # 按权重排序
    user_weights.sort(key=lambda x: x["normalized_weight"], reverse=True)

    # Step 6: 输出结果
    print("\n" + "=" * 80)
    print("📈 用户动态权重排行榜")
    print("=" * 80)
    print(f"{'排名':>4} {'用户':^20} {'任务数':>8} {'被引用':>8} {'权重占比':>12} {'权重值':>12}")
    print("-" * 80)

    for i, item in enumerate(user_weights, 1):
        print(f"{i:4d} {item['user']:^20} {item['task_count']:8d} {item['total_citations']:8d} "
              f"{item['normalized_weight']:11.2f}% {item['raw_weight']:12.4f}")

    print("-" * 80)
    print(f"{'合计':^24} {sum(u['task_count'] for u in user_weights):8d} "
          f"{sum(u['total_citations'] for u in user_weights):8d} "
          f"{sum(u['normalized_weight'] for u in user_weights):11.2f}%")

    # Step 7: 保存详细结果
    output_data = {
        "summary": {
            "total_users": len(user_weights),
            "total_tasks": sum(u["task_count"] for u in user_weights),
            "total_citations": sum(u["total_citations"] for u in user_weights),
            "total_weight": float(total_weight)
        },
        "user_weights": user_weights
    }

    output_path = Path("logs/user_weights.json")
    output_path.parent.mkdir(exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output_data, f, ensure_ascii=False, indent=2)

    print(f"\n💾 详细结果已保存到: {output_path}")

    # Step 8: 显示TOP 5用户的详细任务
    print("\n" + "=" * 80)
    print("🔍 TOP 5 用户的重要任务")
    print("=" * 80)

    for item in user_weights[:5]:
        if item["user"] == "未分配":
            continue
        print(f"\n【{item['user']}】权重占比: {item['normalized_weight']:.2f}%")
        for i, task in enumerate(item["tasks"][:3], 1):
            print(f"  {i}. {task['title'][:50]:50s} (被引用{task['citations']}次, 权重{task['weight']:.4f})")

    print("\n" + "=" * 80)
    print("✓ 权重计算完成！")
    print("=" * 80)

    return user_weights


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="计算所有用户的动态权重")
    parser.add_argument("--csv", default="csv/08小队网站V2项目管理_任务管理.csv", help="CSV文件路径")
    parser.add_argument("--debug", action="store_true", help="保存调试信息")
    args = parser.parse_args()

    calculate_user_weights(Path(args.csv), args.debug)
