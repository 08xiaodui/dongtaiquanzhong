# 动态权重分配系统 - MVP 演示

## 快速开始

### 方式1：基于单个任务的收益分配（demo.py）

```bash
# 基本用法：使用飞书CSV计算收益分配
python demo.py --csv csv/08小队网站V2项目管理_任务管理.csv --revenue 100

# 指定触发任务（展示多层传导）
python demo.py --csv csv/08小队网站V2项目管理_任务管理.csv --revenue 100 --task "移动端邀请码联调"

# 输出到JSON文件
python demo.py --csv csv/08小队网站V2项目管理_任务管理.csv --revenue 100 --task "移动端邀请码联调" --output result.json --debug
```

### 方式2：基于API调用次数的收益分配（demo_api_revenue.py）⭐

```bash
# 基础用法：根据CSV中的"API调用次数"列自动计算所有API的收益分配
python demo_api_revenue.py --csv "csv/08小队网站V2项目管理_任务管理 (1).csv" --revenue-per-call 0.01

# 启用调试模式（保存中间结果）
python demo_api_revenue.py --csv "csv/08小队网站V2项目管理_任务管理 (1).csv" --revenue-per-call 0.01 --debug

# 自定义每次调用收益
python demo_api_revenue.py --csv "csv/08小队网站V2项目管理_任务管理 (1).csv" --revenue-per-call 0.1 --output api_result.json
```

### 输出示例

```
📊 解析CSV: csv/08小队网站V2项目管理_任务管理.csv
✓ 解析完成: 123 个节点, 96 条引用

🔧 构建收益分配图...
✓ 图构建完成: 123 个节点, 96 条边

💰 计算收益分配...
   触发任务: 移动端邀请码联调
   总收益: ¥100.00

📈 分配结果:
用户                           直接收益         传导收益           总计   来源节点
----------------------------------------------------------------------
王添乐                  ¥     70.00 ¥      0.00 ¥     70.00      1
木木                   ¥      0.00 ¥     21.00 ¥     21.00      1
未分配                  ¥      0.00 ¥      9.00 ¥      9.00      2
----------------------------------------------------------------------
总计                                             ¥    100.00

✓ 验证通过: 分配总额与预期一致
💾 结果已保存到: result.json
```

## 项目结构

```
.
├── demo.py                           # 🚀 演示脚本（CSV输入 → 权重分配输出）
├── README.md                         # 📖 本文档
│
├── core/                             # 核心算法模块
│   ├── revenue_calculator.py        # 收益分配计算器（递归传导算法）
│   └── weight_calculator.py         # 引用权重计算（时间优先 × 引用次数 × 创造性）
│
├── utils/                            # 工具模块
│   └── csv_parser.py                # 飞书CSV解析器
│
├── database/                         # 数据库相关
│   ├── schema.sql                   # PostgreSQL表结构（users/nodes/citations/revenue_distributions）
│   ├── migrations/                  # 数据库迁移脚本（幂等可重复执行）
│   └── seed_data.py                 # 种子数据生成器
│
├── tests/                            # 单元测试
│   ├── test_csv_parser.py           # CSV解析测试
│   ├── test_seed_data.py            # 种子数据测试
│   └── test_revenue_distribution.py # 收益分配算法测试
│
└── csv/                              # CSV数据目录
    └── 08小队网站V2项目管理_任务管理.csv  # 飞书导出的任务表格
```

## 核心算法说明

### 1. 引用权重计算

每个被引用节点的权重 = **时间优先系数** × **引用次数** × **创造性系数**

- **时间优先系数**：`1 / (1 + days_elapsed / 365)`
  - 越早创建的节点权重越高
  - 示例：1天前 = 0.997, 1年前 = 0.5

- **引用次数**：被引用的总次数（CSV中的"父记录"关系）

- **创造性系数**：当前简化为 1.0（未来可根据节点类型调整）

### 2. 收益分配流程

```
Step 1: 执行者保留部分
retention = total_revenue × (1 - propagation_rate)

Step 2: 上游传导池
pool = total_revenue × propagation_rate

Step 3: 按权重分配给上游节点
for upstream_node in referenced_nodes:
    upstream_share = pool × (node_weight / total_weight)

Step 4: 递归向上传导（最多5层）
    distribute(upstream_node, upstream_share)
```

**关键参数**：
- **传导率**：默认 30%（可配置）
- **最大传导深度**：5层
- **最小传导金额**：0.01元（低于此值停止传导）
- **循环引用检测**：使用路径集合防止无限递归

### 3. 难度补偿机制

如果任务有实际工时和预估工时数据：

```python
difficulty_factor = actual_hours / estimated_hours
# 如果 difficulty_factor = 1.5（超出50%工时）
# 则执行者保留率增加，传导率降低
```

## CSV格式要求

演示脚本支持飞书导出的任务管理表格，需包含以下列：

| 必需列          | 说明                          |
|----------------|------------------------------|
| 任务名称        | 节点标题                      |
| 父记录          | 引用关系（指向上游任务）       |
| 任务执行人      | 收益接收者                    |

| 可选列          | 说明                          |
|----------------|------------------------------|
| 任务管理人      | 额外收益分配者                |
| 创建日期        | 用于时间优先系数计算          |
| 截止日期        | 保留字段                      |
| 任务详细描述    | 保留字段                      |

**示例行**：

```csv
任务名称,父记录,任务执行人,创建日期
实现JWT认证,API框架搭建,张三,2025-01-01
API框架搭建,,李四,2024-12-15
```

→ "实现JWT认证"（张三）引用了"API框架搭建"（李四）

## 运行测试

```bash
# 运行所有测试
python -m unittest discover -s tests -p "test_*.py" -v

# 运行特定测试
python -m unittest tests.test_revenue_distribution -v
```

## 技术特点

- ✅ **精确金额计算**：使用 Python `Decimal` 类型，误差 < 0.01元
- ✅ **循环引用检测**：防止无限递归
- ✅ **幂等数据库迁移**：可重复执行 SQL 脚本
- ✅ **中文CSV支持**：`utf-8-sig` 编码，自动识别中文表头
- ✅ **自动补全缺失节点**：CSV中引用的父节点如不存在会自动创建

## 下一步计划

当前版本是**演示原型**，已实现核心算法。完整MVP还需要：

- [ ] REST API 服务（FastAPI）
- [ ] 可视化 Dashboard（引用网络图 + 收益分配流程图）
- [ ] 数据库持久化（PostgreSQL）
- [ ] 性能优化（1000节点 × 5层传导 < 1秒）
- [ ] 完整的防作弊机制

## 参考文档

- 完整PRD：[.claude/PRD_动态权重分配系统.md](.claude/PRD_动态权重分配系统.md)
- 算法详解：PRD 第2.5节
- 数据库设计：PRD 第3.2节
