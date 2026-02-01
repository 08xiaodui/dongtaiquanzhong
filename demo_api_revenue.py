#!/usr/bin/env python3
"""
基于API调用次数的动态权重分配系统
输入: 飞书导出的CSV任务表格（包含"是否是API"和"API调用次数"列）
输出: 基于API调用次数的用户收益分配结果
"""

import argparse
import datetime as dt
import json
from decimal import Decimal
from pathlib import Path
from collections import defaultdict

from utils.csv_parser import parse_feishu_tasks_csv
from core.revenue_calculator import RevenueCalculator, RevenueGraph, RevenueNode, RevenueEdge


def save_intermediate_data(data, filename, description):
    """保存中间数据到JSON文件"""
    filepath = Path("logs") / filename
    filepath.parent.mkdir(exist_ok=True)

    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2, default=str)

    print(f"   💾 {description} -> {filepath}")


def main():
    parser = argparse.ArgumentParser(description="基于API调用次数的动态权重分配")
    parser.add_argument("--csv", required=True, help="飞书CSV文件路径")
    parser.add_argument("--revenue-per-call", type=float, default=1.0, help="每次API调用的收益金额（默认1元）")
    parser.add_argument("--output", help="输出JSON文件路径（可选）")
    parser.add_argument("--debug", action="store_true", help="启用调试模式（保存所有中间结果）")
    args = parser.parse_args()

    # Step 1: 解析CSV
    print(f"\n{'='*70}")
    print(f"📊 Step 1: 解析CSV文件")
    print(f"{'='*70}")
    print(f"文件路径: {args.csv}")

    parsed = parse_feishu_tasks_csv(Path(args.csv))

    # 统计API任务
    api_tasks = [n for n in parsed.nodes if n.is_api and n.api_call_count > 0]

    csv_parse_result = {
        "nodes_count": len(parsed.nodes),
        "citations_count": len(parsed.citations),
        "users_count": len(parsed.users),
        "api_tasks_count": len(api_tasks),
        "total_api_calls": sum(n.api_call_count for n in api_tasks),
        "api_tasks_sample": [
            {
                "title": n.title,
                "executors": list(n.executors),
                "api_call_count": n.api_call_count,
                "parents": list(n.parents)
            }
            for n in api_tasks[:10]
        ]
    }

    if args.debug:
        save_intermediate_data(csv_parse_result, "api_01_csv_parse_result.json", "CSV解析结果")

    if parsed.warnings:
        print(f"\n⚠️  警告 ({len(parsed.warnings)} 条):")
        for w in parsed.warnings[:5]:
            print(f"   - {w.message}")

    print(f"\n✓ 解析完成:")
    print(f"   总任务数: {len(parsed.nodes)}")
    print(f"   总引用数: {len(parsed.citations)}")
    print(f"   API任务数: {len(api_tasks)}")
    print(f"   总API调用: {csv_parse_result['total_api_calls']:,} 次")

    if not api_tasks:
        print(f"\n❌ 错误: CSV中没有标记API调用次数的任务")
        print(f"   请检查CSV文件中的\"是否是API\"和\"API调用次数\"列")
        return

    # Step 2: 构建收益计算图
    print(f"\n{'='*70}")
    print(f"🔧 Step 2: 构建收益分配图")
    print(f"{'='*70}")

    # 创建节点映射
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

    # 创建引用边
    edges = []
    for citation in parsed.citations:
        if citation.from_title in node_map and citation.to_title in node_map:
            edges.append(RevenueEdge(
                from_node_id=citation.from_title,
                to_node_id=citation.to_title,
                weight=Decimal(str(citation.weight))
            ))

    nodes_construction = {
        "total_nodes": len(node_map),
        "nodes_with_executors": sum(1 for n in node_map.values() if n.creator_id != "未分配"),
        "api_nodes": len(api_tasks)
    }

    if args.debug:
        save_intermediate_data(nodes_construction, "api_02_nodes_construction.json", "节点构建结果")

    print(f"✓ 图构建完成:")
    print(f"   节点数: {len(node_map)}")
    print(f"   边数: {len(edges)}")
    print(f"   API节点数: {len(api_tasks)}")

    # Step 3: 为每个API任务计算收益分配
    print(f"\n{'='*70}")
    print(f"💰 Step 3: 基于API调用次数计算收益分配")
    print(f"{'='*70}")
    print(f"每次API调用收益: ¥{args.revenue_per_call:.2f}")

    graph = RevenueGraph(
        nodes=list(node_map.values()),
        edges=edges
    )

    calculator = RevenueCalculator(graph=graph)

    # 汇总所有API任务的收益分配
    all_allocations = []
    api_task_details = []

    for api_node in api_tasks:
        total_revenue = Decimal(str(api_node.api_call_count * args.revenue_per_call))

        print(f"\n  处理API: {api_node.title[:40]}")
        print(f"    调用次数: {api_node.api_call_count:,} 次")
        print(f"    总收益: ¥{float(total_revenue):,.2f}")

        results = calculator.distribute(
            task_id=api_node.title,
            node_id=api_node.title,
            total_revenue=total_revenue
        )

        all_allocations.extend(results)

        api_task_details.append({
            "task": api_node.title,
            "executor": api_node.executors[0] if api_node.executors else "未分配",
            "api_call_count": api_node.api_call_count,
            "total_revenue": float(total_revenue),
            "allocations_count": len(results)
        })

    if args.debug:
        save_intermediate_data({
            "api_tasks": api_task_details,
            "total_allocations": len(all_allocations)
        }, "api_03_distribution_details.json", "收益分配详情")

    # Step 4: 汇总用户收益
    print(f"\n{'='*70}")
    print(f"📈 Step 4: 用户收益汇总")
    print(f"{'='*70}")

    user_totals = defaultdict(lambda: {"direct": Decimal("0"), "propagation": Decimal("0")})

    for r in all_allocations:
        user = r.user_id
        if r.source == "direct":
            user_totals[user]["direct"] += r.amount
        else:
            user_totals[user]["propagation"] += r.amount

    # 按总收益排序
    sorted_users = sorted(
        user_totals.items(),
        key=lambda x: x[1]["direct"] + x[1]["propagation"],
        reverse=True
    )

    print(f"{'用户':<20} {'直接收益':>12} {'传导收益':>12} {'总计':>12} {'来源任务':>8}")
    print("-" * 72)

    for user, amounts in sorted_users:
        total = amounts["direct"] + amounts["propagation"]
        task_count = len(set(r.task_id for r in all_allocations if r.user_id == user))
        print(f"{user:<20} ¥{amounts['direct']:>10.2f} ¥{amounts['propagation']:>10.2f} ¥{total:>10.2f} {task_count:>8}")

    print("-" * 72)
    total_distributed = sum(amounts["direct"] + amounts["propagation"] for _, amounts in user_totals.items())
    total_expected = sum(n.api_call_count * args.revenue_per_call for n in api_tasks)
    print(f"{'总计':<20} {'':>12} {'':>12} ¥{total_distributed:>10.2f}")

    # 验证金额
    if abs(float(total_distributed) - total_expected) > 0.01:
        print(f"\n⚠️  警告: 分配总额 ¥{total_distributed:.2f} 与预期 ¥{total_expected:.2f} 不符")
    else:
        print(f"\n✓ 验证通过: 分配总额与预期一致")

    # 输出统计
    print(f"\n总API调用: {csv_parse_result['total_api_calls']:,} 次")
    print(f"总收益: ¥{total_expected:,.2f}")
    print(f"受益用户数: {len(user_totals)}")
    print(f"分配记录数: {len(all_allocations)}")

    # 最终结果: 输出JSON
    final_output = {
        "revenue_per_call": args.revenue_per_call,
        "total_api_calls": csv_parse_result['total_api_calls'],
        "total_revenue": total_expected,
        "api_tasks": api_task_details,
        "user_summary": {
            user: {
                "direct": float(amounts["direct"]),
                "propagation": float(amounts["propagation"]),
                "total": float(amounts["direct"] + amounts["propagation"])
            }
            for user, amounts in user_totals.items()
        },
        "statistics": {
            "total_users": len(user_totals),
            "total_allocations": len(all_allocations),
            "api_tasks_count": len(api_tasks)
        }
    }

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(final_output, f, ensure_ascii=False, indent=2)
        print(f"\n💾 最终结果已保存到: {args.output}")

    if args.debug:
        save_intermediate_data(final_output, "api_04_final_output.json", "最终输出结果")
        print(f"\n✓ 所有中间结果已保存到 logs/ 目录")


if __name__ == "__main__":
    main()
