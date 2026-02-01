#!/usr/bin/env python3
"""
引用关系分析工具
分析CSV中的任务引用关系，生成统计报告
"""

from pathlib import Path
from collections import defaultdict
from utils.csv_parser import parse_feishu_tasks_csv


def analyze_citations(csv_path: Path):
    """分析引用关系"""
    print("=" * 80)
    print("📊 引用关系分析报告")
    print("=" * 80)

    # 解析CSV
    parsed = parse_feishu_tasks_csv(csv_path)

    # 基本统计
    print(f"\n【基本统计】")
    print(f"  总任务数: {len(parsed.nodes)}")
    print(f"  总引用数: {len(parsed.citations)}")
    print(f"  总用户数: {len(parsed.users)}")

    # 执行人分配统计
    nodes_with_executor = sum(1 for n in parsed.nodes if n.executors)
    nodes_without_executor = len(parsed.nodes) - nodes_with_executor
    print(f"\n【执行人分配】")
    print(f"  有执行人的任务: {nodes_with_executor} ({nodes_with_executor/len(parsed.nodes)*100:.1f}%)")
    print(f"  无执行人的任务: {nodes_without_executor} ({nodes_without_executor/len(parsed.nodes)*100:.1f}%)")

    # 引用关系统计
    nodes_with_parents = sum(1 for n in parsed.nodes if n.parents)
    root_nodes = len(parsed.nodes) - nodes_with_parents
    print(f"\n【引用关系】")
    print(f"  根节点（无父任务）: {root_nodes}")
    print(f"  子节点（有父任务）: {nodes_with_parents}")

    # 构建父子关系映射
    parent_to_children = defaultdict(list)
    for node in parsed.nodes:
        for parent in node.parents:
            parent_to_children[parent].append(node.title)

    # 被引用次数排行
    print(f"\n【被引用次数 TOP 10】")
    citation_counts = sorted(
        [(parent, len(children)) for parent, children in parent_to_children.items()],
        key=lambda x: x[1],
        reverse=True
    )
    for i, (task, count) in enumerate(citation_counts[:10], 1):
        # 找到对应节点的执行人
        node = next((n for n in parsed.nodes if n.title == task), None)
        executor = list(node.executors)[0] if node and node.executors else "未分配"
        print(f"  {i:2d}. {task[:40]:40s} → 被引用{count}次 (👤{executor})")

    # 按执行人统计任务数
    user_task_counts = defaultdict(int)
    for node in parsed.nodes:
        if node.executors:
            executor = list(node.executors)[0]  # 只取第一个执行人
            user_task_counts[executor] += 1
        else:
            user_task_counts["未分配"] += 1

    print(f"\n【执行人任务数 TOP 10】")
    sorted_users = sorted(user_task_counts.items(), key=lambda x: x[1], reverse=True)
    for i, (user, count) in enumerate(sorted_users[:10], 1):
        print(f"  {i:2d}. {user:20s} → {count:3d} 个任务")

    # 深度分析（找出最长引用链）
    def get_depth(task_title, visited=None):
        """递归计算任务的最大深度"""
        if visited is None:
            visited = set()
        if task_title in visited:
            return 0
        visited.add(task_title)

        node = next((n for n in parsed.nodes if n.title == task_title), None)
        if not node or not node.parents:
            return 0

        max_parent_depth = max(
            get_depth(parent, visited.copy()) for parent in node.parents
        )
        return max_parent_depth + 1

    print(f"\n【引用链深度分析】")
    task_depths = [(node.title, get_depth(node.title)) for node in parsed.nodes]
    max_depth = max(depth for _, depth in task_depths)
    print(f"  最大引用深度: {max_depth} 层")

    # 显示最深的引用链
    deepest_tasks = [title for title, depth in task_depths if depth == max_depth]
    print(f"  最深引用链示例（{max_depth}层）:")

    for task in deepest_tasks[:3]:  # 只显示前3个
        chain = [task]
        current = task
        for _ in range(max_depth):
            node = next((n for n in parsed.nodes if n.title == current), None)
            if node and node.parents:
                parent = list(node.parents)[0]
                chain.append(parent)
                current = parent

        print(f"\n    {task[:30]}...")
        for i, t in enumerate(chain):
            indent = "  " * i
            node = next((n for n in parsed.nodes if n.title == t), None)
            executor = list(node.executors)[0] if node and node.executors else "未分配"
            print(f"      {indent}└─ {t[:40]} (👤{executor})")

    print("\n" + "=" * 80)
    print("✓ 分析完成！可视化图表已生成:")
    print("  - logs/citation_graph.html (浏览器打开)")
    print("  - logs/citation_graph.mmd (Mermaid格式，可在 mermaid.live 查看)")
    print("=" * 80)


if __name__ == "__main__":
    csv_path = Path("csv/08小队网站V2项目管理_任务管理.csv")
    analyze_citations(csv_path)
