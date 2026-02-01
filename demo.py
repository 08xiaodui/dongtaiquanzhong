#!/usr/bin/env python3
"""
动态权重分配系统 - 简单演示（增强版）
输入: 飞书导出的CSV任务表格
输出: 用户收益分配结果 + 中间过程日志
"""

import argparse
import datetime as dt
import json
from decimal import Decimal
from pathlib import Path

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
    parser = argparse.ArgumentParser(description="动态权重分配演示")
    parser.add_argument("--csv", required=True, help="飞书CSV文件路径")
    parser.add_argument("--revenue", type=float, default=100.0, help="总收益金额（默认100元）")
    parser.add_argument("--task", help="触发收益分配的任务名称（默认使用CSV第一行）")
    parser.add_argument("--output", help="输出JSON文件路径（可选）")
    parser.add_argument("--debug", action="store_true", help="启用调试模式（保存所有中间结果）")
    args = parser.parse_args()

    # Step 1: 解析CSV
    print(f"\n{'='*70}")
    print(f"📊 Step 1: 解析CSV文件")
    print(f"{'='*70}")
    print(f"文件路径: {args.csv}")

    parsed = parse_feishu_tasks_csv(Path(args.csv))

    # 中间结果1: CSV解析结果
    csv_parse_result = {
        "nodes_count": len(parsed.nodes),
        "citations_count": len(parsed.citations),
        "users_count": len(parsed.users),
        "warnings_count": len(parsed.warnings),
        "nodes_sample": [
            {
                "title": n.title,
                "executors": list(n.executors),
                "managers": list(n.managers),
                "parents": list(n.parents)
            }
            for n in list(parsed.nodes)[:5]  # 只保存前5个样本
        ],
        "citations_sample": [
            {
                "from": c.from_title,
                "to": c.to_title,
                "weight": c.weight
            }
            for c in list(parsed.citations)[:5]
        ]
    }

    if args.debug:
        save_intermediate_data(csv_parse_result, "01_csv_parse_result.json", "CSV解析结果")

    if parsed.warnings:
        print(f"\n⚠️  警告 ({len(parsed.warnings)} 条):")
        for w in parsed.warnings[:5]:  # 只显示前5条
            print(f"   - {w.message}")

    print(f"\n✓ 解析完成:")
    print(f"   节点数: {len(parsed.nodes)}")
    print(f"   引用数: {len(parsed.citations)}")
    print(f"   用户数: {len(parsed.users)}")

    # Step 2: 构建收益计算图
    print(f"\n{'='*70}")
    print(f"🔧 Step 2: 构建收益分配图")
    print(f"{'='*70}")

    # 创建节点映射
    node_map = {}
    for node in parsed.nodes:
        # 使用title作为节点ID（简化演示）
        node_map[node.title] = RevenueNode(
            id=node.title,
            creator_id=node.executors[0] if node.executors else "未分配",
            created_at=node.created_date or dt.date.today(),
            citation_count=sum(1 for c in parsed.citations if c.to_title == node.title),
            creativity_factor=Decimal("1.0"),  # 简化：统一设为1.0
            propagation_rate=Decimal("0.3"),  # 简化：统一30%传导率
        )

    # 中间结果2: 节点构建结果
    nodes_construction = {
        "total_nodes": len(node_map),
        "nodes_with_executors": sum(1 for n in node_map.values() if n.creator_id != "未分配"),
        "nodes_without_executors": sum(1 for n in node_map.values() if n.creator_id == "未分配"),
        "sample_nodes": [
            {
                "id": n.id,
                "creator_id": n.creator_id,
                "citation_count": n.citation_count,
                "propagation_rate": float(n.propagation_rate)
            }
            for n in list(node_map.values())[:10]
        ]
    }

    if args.debug:
        save_intermediate_data(nodes_construction, "02_nodes_construction.json", "节点构建结果")

    # 创建引用边
    edges = []
    edge_errors = []
    for citation in parsed.citations:
        if citation.from_title in node_map and citation.to_title in node_map:
            edges.append(RevenueEdge(
                from_node_id=citation.from_title,
                to_node_id=citation.to_title,
                weight=Decimal(str(citation.weight))
            ))
        else:
            edge_errors.append({
                "from": citation.from_title,
                "to": citation.to_title,
                "reason": "节点不存在"
            })

    # 中间结果3: 边构建结果
    edges_construction = {
        "total_edges": len(edges),
        "edge_errors": len(edge_errors),
        "sample_edges": [
            {
                "from": e.from_node_id,
                "to": e.to_node_id,
                "weight": float(e.weight)
            }
            for e in edges[:10]
        ],
        "errors_sample": edge_errors[:5] if edge_errors else []
    }

    if args.debug:
        save_intermediate_data(edges_construction, "03_edges_construction.json", "引用边构建结果")

    print(f"✓ 图构建完成:")
    print(f"   节点数: {len(node_map)}")
    print(f"   边数: {len(edges)}")
    print(f"   有执行人的节点: {nodes_construction['nodes_with_executors']}")
    print(f"   无执行人的节点: {nodes_construction['nodes_without_executors']}")

    # Step 3: 选择触发任务
    print(f"\n{'='*70}")
    print(f"💰 Step 3: 计算收益分配")
    print(f"{'='*70}")

    trigger_task = args.task
    if not trigger_task:
        trigger_task = parsed.nodes[0].title if parsed.nodes else None

    if not trigger_task or trigger_task not in node_map:
        print(f"❌ 错误: 任务 '{trigger_task}' 不存在")
        return

    trigger_node = node_map[trigger_task]
    print(f"触发任务: {trigger_task}")
    print(f"执行人: {trigger_node.creator_id}")
    print(f"总收益: ¥{args.revenue:.2f}")
    print(f"传导率: {float(trigger_node.propagation_rate) * 100:.0f}%")

    # Step 4: 执行收益分配
    graph = RevenueGraph(
        nodes=list(node_map.values()),
        edges=edges
    )

    calculator = RevenueCalculator(graph=graph)

    results = calculator.distribute(
        task_id=trigger_task,
        node_id=trigger_task,
        total_revenue=Decimal(str(args.revenue))
    )

    # 中间结果4: 分配结果详情
    distribution_details = {
        "trigger_task": trigger_task,
        "trigger_executor": trigger_node.creator_id,
        "total_revenue": args.revenue,
        "propagation_rate": float(trigger_node.propagation_rate),
        "allocations": [
            {
                "user_id": r.user_id,
                "node_id": r.node_id,
                "amount": float(r.amount),
                "source": r.source,
                "propagation_level": r.propagation_level
            }
            for r in results
        ],
        "allocation_by_level": {}
    }

    # 按传导层级统计
    for r in results:
        level = r.propagation_level
        if level not in distribution_details["allocation_by_level"]:
            distribution_details["allocation_by_level"][level] = {
                "count": 0,
                "total_amount": 0.0
            }
        distribution_details["allocation_by_level"][level]["count"] += 1
        distribution_details["allocation_by_level"][level]["total_amount"] += float(r.amount)

    if args.debug:
        save_intermediate_data(distribution_details, "04_distribution_details.json", "收益分配详情")

    # Step 5: 输出结果
    print(f"\n{'='*70}")
    print(f"📈 Step 4: 分配结果汇总")
    print(f"{'='*70}")
    print(f"{'用户':<20} {'直接收益':>12} {'传导收益':>12} {'总计':>12} {'来源节点':>6}")
    print("-" * 70)

    user_totals = {}
    for r in results:
        user = r.user_id
        if user not in user_totals:
            user_totals[user] = {"direct": Decimal("0"), "propagation": Decimal("0")}

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

    for user, amounts in sorted_users:
        total = amounts["direct"] + amounts["propagation"]
        node_count = len([r for r in results if r.user_id == user])
        print(f"{user:<20} ¥{amounts['direct']:>10.2f} ¥{amounts['propagation']:>10.2f} ¥{total:>10.2f} {node_count:>6}")

    print("-" * 70)
    total_distributed = sum(amounts["direct"] + amounts["propagation"] for _, amounts in user_totals.items())
    print(f"{'总计':<20} {'':>12} {'':>12} ¥{total_distributed:>10.2f}")

    # 验证金额
    expected = Decimal(str(args.revenue))
    if abs(total_distributed - expected) > Decimal("0.01"):
        print(f"\n⚠️  警告: 分配总额 ¥{total_distributed:.2f} 与预期 ¥{expected:.2f} 不符")
    else:
        print(f"\n✓ 验证通过: 分配总额与预期一致")

    # 输出按层级的统计
    print(f"\n传导层级统计:")
    for level in sorted(distribution_details["allocation_by_level"].keys()):
        stats = distribution_details["allocation_by_level"][level]
        level_name = "直接收益" if level == 0 else f"第{level}层传导"
        print(f"   {level_name}: {stats['count']}笔, ¥{stats['total_amount']:.2f}")

    # 最终结果: 输出JSON
    final_output = {
        "trigger_task": trigger_task,
        "total_revenue": float(args.revenue),
        "distribution": [
            {
                "user_id": r.user_id,
                "node_id": r.node_id,
                "amount": float(r.amount),
                "source": r.source,
                "propagation_level": r.propagation_level
            }
            for r in results
        ],
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
            "total_allocations": len(results),
            "by_level": distribution_details["allocation_by_level"]
        }
    }

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(final_output, f, ensure_ascii=False, indent=2)
        print(f"\n💾 最终结果已保存到: {args.output}")

    if args.debug:
        save_intermediate_data(final_output, "05_final_output.json", "最终输出结果")
        print(f"\n✓ 所有中间结果已保存到 logs/ 目录")
        print(f"   查看变量说明: 参考 VARIABLES.md")


if __name__ == "__main__":
    main()
