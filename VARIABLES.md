# 变量字典文档 (VARIABLES.md)

本文档详细记录了动态权重分配系统中所有关键变量的数据结构、含义和使用场景。

---

## 目录

1. [CSV解析阶段变量](#1-csv解析阶段变量)
2. [图构建阶段变量](#2-图构建阶段变量)
3. [收益分配阶段变量](#3-收益分配阶段变量)
4. [输出结果变量](#4-输出结果变量)
5. [核心数据类型定义](#5-核心数据类型定义)

---

## 1. CSV解析阶段变量

### `parsed`
- **类型**: `ParsedGraph` (来自 `utils.csv_parser`)
- **说明**: CSV文件解析后的完整图结构
- **字段**:
  ```python
  {
    "users": tuple[ParsedUser, ...],      # 所有用户列表
    "nodes": tuple[ParsedNode, ...],      # 所有节点（任务）列表
    "citations": tuple[ParsedCitation, ...],  # 所有引用关系列表
    "warnings": tuple[ParseWarning, ...]  # 解析警告列表
  }
  ```
- **中间结果文件**: `logs/01_csv_parse_result.json`

### `csv_parse_result`
- **类型**: `dict`
- **说明**: CSV解析结果的统计摘要
- **字段**:
  ```python
  {
    "nodes_count": int,           # 节点总数
    "citations_count": int,       # 引用关系总数
    "users_count": int,           # 用户总数
    "warnings_count": int,        # 警告数量
    "nodes_sample": [             # 前5个节点样本
      {
        "title": str,             # 任务名称
        "executors": [str, ...],  # 执行人列表
        "managers": [str, ...],   # 管理人列表
        "parents": [str, ...]     # 父任务列表
      }
    ],
    "citations_sample": [         # 前5个引用样本
      {
        "from": str,              # 引用源任务名称
        "to": str,                # 被引用任务名称
        "weight": float           # 引用权重
      }
    ]
  }
  ```

### `ParsedNode` (数据类)
- **字段说明**:
  - `title`: 任务名称（唯一标识）
  - `executors`: 任务执行人列表（从CSV"任务执行人"列提取，逗号分隔）
  - `managers`: 任务管理人列表（从CSV"任务管理人"列提取）
  - `parents`: 父任务列表（从CSV"父记录"或"父记录 副本"列提取）
  - `created_date`: 创建日期（用于时间优先系数计算）
  - `description`: 任务详细描述

### `ParsedCitation` (数据类)
- **字段说明**:
  - `from_title`: 引用源任务（子任务）
  - `to_title`: 被引用任务（父任务）
  - `weight`: 引用权重（默认1.0）

---

## 2. 图构建阶段变量

### `node_map`
- **类型**: `dict[str, RevenueNode]`
- **说明**: 任务名称到收益节点对象的映射表
- **Key**: 任务名称（str）
- **Value**: `RevenueNode` 对象
- **用途**: 快速查找任务对应的收益节点
- **示例**:
  ```python
  {
    "邀请码": RevenueNode(
      id="邀请码",
      creator_id="木木",
      created_at=datetime.date(2025, 3, 2),
      citation_count=5,
      propagation_rate=Decimal("0.3")
    )
  }
  ```

### `nodes_construction`
- **类型**: `dict`
- **说明**: 节点构建过程的统计信息
- **字段**:
  ```python
  {
    "total_nodes": int,                   # 节点总数
    "nodes_with_executors": int,          # 有执行人的节点数
    "nodes_without_executors": int,       # 无执行人的节点数（显示为"未分配"）
    "sample_nodes": [                     # 前10个节点样本
      {
        "id": str,                        # 节点ID（任务名称）
        "creator_id": str,                # 创建者/执行人
        "citation_count": int,            # 被引用次数
        "propagation_rate": float         # 传导率（默认0.3 = 30%）
      }
    ]
  }
  ```
- **中间结果文件**: `logs/02_nodes_construction.json`

### `edges`
- **类型**: `list[RevenueEdge]`
- **说明**: 所有有效的引用边列表
- **用途**: 表示任务间的引用关系和权重

### `edges_construction`
- **类型**: `dict`
- **说明**: 引用边构建过程的统计信息
- **字段**:
  ```python
  {
    "total_edges": int,           # 有效边总数
    "edge_errors": int,           # 构建失败的边数量
    "sample_edges": [             # 前10条边样本
      {
        "from": str,              # 源节点ID
        "to": str,                # 目标节点ID
        "weight": float           # 边权重
      }
    ],
    "errors_sample": [            # 错误样本（如果有）
      {
        "from": str,
        "to": str,
        "reason": str
      }
    ]
  }
  ```
- **中间结果文件**: `logs/03_edges_construction.json`

### `RevenueNode` (数据类)
- **字段说明**:
  - `id`: 节点唯一标识（任务名称）
  - `creator_id`: 创建者/执行人ID（第一个执行人，无则"未分配"）
  - `created_at`: 创建时间（用于计算时间优先系数）
  - `citation_count`: 被引用次数（影响上游权重）
  - `creativity_factor`: 创造性系数（默认1.0）
  - `propagation_rate`: 传导率（默认0.3，表示30%传导给上游）
  - `estimated_hours`: 预估工时（用于难度补偿，当前未使用）
  - `actual_hours`: 实际工时（用于难度补偿，当前未使用）

### `RevenueEdge` (数据类)
- **字段说明**:
  - `from_node_id`: 引用源节点ID（子任务）
  - `to_node_id`: 被引用节点ID（父任务）
  - `weight`: 引用权重（默认1.0，表示完全引用）

---

## 3. 收益分配阶段变量

### `trigger_task`
- **类型**: `str`
- **说明**: 触发收益分配的任务名称
- **来源**: 命令行参数 `--task` 或默认使用第一个任务
- **用途**: 确定从哪个任务开始分配收益

### `trigger_node`
- **类型**: `RevenueNode`
- **说明**: 触发任务对应的节点对象
- **用途**: 获取触发任务的执行人、传导率等信息

### `graph`
- **类型**: `RevenueGraph` (来自 `core.revenue_calculator`)
- **说明**: 收益分配图结构
- **组成**:
  - 所有节点的集合
  - 所有边的集合
  - 节点上游关系索引（内部优化）
- **用途**: 提供给 `RevenueCalculator` 执行分配算法

### `calculator`
- **类型**: `RevenueCalculator`
- **说明**: 收益分配计算器实例
- **配置**:
  - `max_propagation_depth`: 最大传导深度（默认5层）
  - `min_propagation_amount`: 最小传导金额（默认0.01元）
  - `max_retention_multiplier`: 最大保留率倍数（用于难度补偿，默认1.75）

### `results`
- **类型**: `tuple[RevenueAllocation, ...]`
- **说明**: 所有收益分配记录的列表
- **元素类型**: `RevenueAllocation`
- **用途**: 记录每笔收益分配的详细信息

### `RevenueAllocation` (数据类)
- **字段说明**:
  - `task_id`: 触发任务ID（根任务）
  - `node_id`: 接收收益的节点ID
  - `user_id`: 接收收益的用户ID
  - `amount`: 收益金额（Decimal类型，保证精度）
  - `source`: 收益来源类型
    - `"direct"`: 直接收益（执行者保留部分）
    - `"propagation"`: 传导收益（从下游传导而来）
  - `propagation_level`: 传导层级
    - `0`: 直接收益
    - `1`: 第1层传导（直接上游）
    - `2`: 第2层传导（上游的上游）
    - ... 最多5层

### `distribution_details`
- **类型**: `dict`
- **说明**: 分配过程的详细信息和统计
- **字段**:
  ```python
  {
    "trigger_task": str,                # 触发任务名称
    "trigger_executor": str,            # 触发任务执行人
    "total_revenue": float,             # 总收益金额
    "propagation_rate": float,          # 传导率
    "allocations": [                    # 所有分配记录
      {
        "user_id": str,
        "node_id": str,
        "amount": float,
        "source": "direct" | "propagation",
        "propagation_level": int
      }
    ],
    "allocation_by_level": {            # 按层级统计
      0: {"count": int, "total_amount": float},  # 直接收益统计
      1: {"count": int, "total_amount": float},  # 第1层传导统计
      2: {"count": int, "total_amount": float},  # 第2层传导统计
      ...
    }
  }
  ```
- **中间结果文件**: `logs/04_distribution_details.json`

---

## 4. 输出结果变量

### `user_totals`
- **类型**: `dict[str, dict]`
- **说明**: 每个用户的收益汇总
- **结构**:
  ```python
  {
    "木木": {
      "direct": Decimal("70.00"),       # 直接收益
      "propagation": Decimal("0.00")    # 传导收益
    },
    "王添乐": {
      "direct": Decimal("0.00"),
      "propagation": Decimal("21.00")
    }
  }
  ```
- **计算过程**: 遍历 `results`，按 `user_id` 和 `source` 累加金额

### `sorted_users`
- **类型**: `list[tuple[str, dict]]`
- **说明**: 按总收益降序排列的用户列表
- **用途**: 生成最终的收益排行榜

### `final_output`
- **类型**: `dict`
- **说明**: 最终输出的完整结果（JSON格式）
- **字段**:
  ```python
  {
    "trigger_task": str,                # 触发任务
    "total_revenue": float,             # 总收益
    "distribution": [                   # 所有分配记录
      {
        "user_id": str,
        "node_id": str,
        "amount": float,
        "source": str,
        "propagation_level": int
      }
    ],
    "user_summary": {                   # 用户收益汇总
      "用户名": {
        "direct": float,
        "propagation": float,
        "total": float
      }
    },
    "statistics": {                     # 统计信息
      "total_users": int,               # 参与用户数
      "total_allocations": int,         # 分配记录总数
      "by_level": {                     # 按层级统计
        "0": {"count": int, "total_amount": float},
        "1": {"count": int, "total_amount": float},
        ...
      }
    }
  }
  ```
- **输出文件**:
  - 命令行参数指定: `--output result.json`
  - 调试模式: `logs/05_final_output.json`

---

## 5. 核心数据类型定义

### Decimal 类型
- **来源**: Python标准库 `decimal.Decimal`
- **用途**: 所有金额计算使用此类型，避免浮点数精度问题
- **精度**: 保留2位小数（0.01元）
- **示例**:
  ```python
  Decimal("100.00")   # 正确：字符串初始化
  Decimal(100)        # 正确：整数初始化
  Decimal(100.0)      # 错误：浮点数可能丢失精度
  ```

### 权重计算公式

#### 时间优先系数
```python
time_priority = 1 / (1 + days_elapsed / 365)
```
- **days_elapsed**: 从节点创建到现在的天数
- **含义**: 越早创建的节点，系数越高
- **范围**: (0, 1]
- **示例**:
  - 今天创建: 1.0
  - 1天前: 0.997
  - 半年前: 0.67
  - 1年前: 0.5

#### 节点引用权重
```python
node_weight = time_priority × citation_count × creativity_factor
```
- **citation_count**: 节点被引用的次数
- **creativity_factor**: 创造性系数（默认1.0）

#### 收益分配公式
```python
# 执行者保留
retention = total_revenue × (1 - propagation_rate)

# 传导池
pool = total_revenue × propagation_rate

# 上游分配
for upstream_node:
    share = pool × (upstream_node.weight / total_weight)
    # 递归向上传导
```

---

## 6. 调试模式使用

### 启用调试模式
```bash
python demo.py --csv data.csv --revenue 100 --debug
```

### 生成的中间结果文件

| 文件 | 说明 | 关键字段 |
|------|------|----------|
| `logs/01_csv_parse_result.json` | CSV解析结果 | nodes_count, citations_count |
| `logs/02_nodes_construction.json` | 节点构建统计 | nodes_with_executors |
| `logs/03_edges_construction.json` | 引用边构建统计 | total_edges, edge_errors |
| `logs/04_distribution_details.json` | 收益分配详情 | allocations, allocation_by_level |
| `logs/05_final_output.json` | 最终输出结果 | user_summary, statistics |

### 查看中间结果
```bash
# 查看CSV解析结果
cat logs/01_csv_parse_result.json | jq .

# 查看收益分配详情
cat logs/04_distribution_details.json | jq .allocation_by_level

# 查看用户收益汇总
cat logs/05_final_output.json | jq .user_summary
```

---

## 7. 常见问题排查

### Q: 为什么有些用户显示"未分配"？
**A**: CSV中对应任务的"任务执行人"列为空。检查 `logs/02_nodes_construction.json` 中的 `nodes_without_executors` 字段。

### Q: 收益总额为什么不等于预期？
**A**: 可能存在以下情况：
1. 最小传导金额过滤（< 0.01元的传导会被丢弃）
2. 浮点数精度问题（已使用Decimal避免）
3. 检查 `logs/04_distribution_details.json` 查看每笔分配详情

### Q: 如何追踪某个用户的收益来源？
**A**: 查看 `logs/04_distribution_details.json`，筛选 `allocations` 中 `user_id` 匹配的记录，查看 `node_id` 和 `propagation_level`。

---

## 8. 扩展说明

### 未来可配置参数

| 参数 | 当前值 | 说明 | 位置 |
|------|--------|------|------|
| `propagation_rate` | 0.3 | 传导率（30%） | demo.py:99 |
| `creativity_factor` | 1.0 | 创造性系数 | demo.py:98 |
| `max_depth` | 5 | 最大传导深度 | RevenueCalculatorConfig |
| `min_amount` | 0.01 | 最小传导金额 | RevenueCalculatorConfig |

这些参数未来可以从配置文件或命令行参数读取，实现更灵活的分配策略。
