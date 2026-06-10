# 知纹 · 使用手册

## 对话模式

### 标准对话

一次性返回完整响应：

```bash
curl -X POST http://localhost:9200/api/chat \
  -H "Content-Type: application/json" \
  -d '{"message":"什么是MMT","user":"探索者"}'
```

### 流式对话（推荐）

逐 token 返回，感知延迟从 8s 降至 0.5s：

```bash
curl -X POST http://localhost:9200/api/chat/stream \
  -H "Content-Type: application/json" \
  -d '{"message":"分析日本通缩成因与MMT政策效果"}'
```

> 响应格式：每个 chunk 为 `{"token":"日","emotion":"neutral"}`，以 `{"done":true}` 结束。

---

## 三级路由

了了自动判断问题复杂度，分配不同处理路径：

| 路由 | 触发条件 | 管线开销 | 适用场景 |
|---|---|---|---|
| 🟢 **fast** | 问候 / 简单问答 / <20字 | 0ms | "你好" "谢谢" |
| 🟡 **standard** | 事实型问题 / 单一主题 | <10ms | "什么是MMT" "GDP多少" |
| 🔴 **deep** | 含 2+ 分析关键词 / >50字 / 多因素 | ~2s | "分析日本通缩与MMT政策对比" |

触发 deep 路由的关键词：`分析` `研究` `对比` `评估` `多因素` `原因` `效果` `影响` `关系`

---

## 深度研究流程（知纹全栈）

对复杂问题，了了自动启动知纹全栈管线：

```
查询："日本1990-2020年MMT政策效果如何？赤字率与通胀率的关系？"
  │
  ├─ ① 纹路记忆    检测是否为历史追问 → 复用 DAG 结构
  ├─ ② 表观遗传    自动选择表达谱（学术深度 / 快速浏览 / 验证优先）
  ├─ ③ 研究规划器  分解为子问题 DAG：
  │    子1: 日本通缩的主要成因
  │    子2: MMT 核心主张
  │    子3: 日本实施MMT后数据变化（依赖: 1, 2）
  │    子4: 因果关系验证（依赖: 1, 2, 3）
  │    子5: 外部因素干扰
  │    ROOT: 综合结论（依赖: 全部 5 个）
  ├─ ④ 工程DAG     拓扑排序 → 叶节点 3 路并发执行
  ├─ ⑤ 基因执行    每个子问题独立 DNA 编码 → 搜索 → 验证 → 过闸
  ├─ ⑥ 推理引擎    声明 → 推理边 → 证明图 → φ 交叉验证
  ├─ ⑦ 对抗验证    反例攻击 → 存活率报告
  └─ ⑧ 流式输出    逐 token 返回，首字 0.5s
```

---

## API 端点（完整列表）

### 核心对话

| 端点 | 方法 | 说明 |
|---|---|---|
| `/api/chat` | POST | 标准对话（一次性返回） |
| `/api/chat/stream` | POST | 流式对话（推荐） |
| `/api/health` | GET | 健康检查 |
| `/api/status` | GET | 详细运行状态 |
| `/api/wake` | POST | 唤醒 / 初始化 |

### 深度研究

| 端点 | 方法 | 说明 |
|---|---|---|
| `/api/research` | POST | 标准深度研究 |
| `/api/research/evo` | POST | 演化研究 |
| `/api/research/scientific` | POST | 科学方法研究 |
| `/api/research/sci` | POST | 科学方法别名 |
| `/api/research/sweep` | POST | 参数敏感性扫描 |
| `/api/research/competing` | POST | 竞争假说验证 |

### 数据获取

| 端点 | 方法 | 说明 |
|---|---|---|
| `/api/search` | GET | 网络搜索 |
| `/api/meta_search` | GET | 元搜索自寻源 |
| `/api/fetch` | GET | 网页抓取 |
| `/api/read` | GET | 文档阅读（PDF/EPUB/DOCX/TXT） |
| `/api/stock` | GET | 股票查询 |
| `/api/trending` | GET | 热搜查询 |
| `/api/papers` | GET | 论文搜索 |
| `/api/weather` | GET | 天气查询 |

### 观测与记忆

| 端点 | 方法 | 说明 |
|---|---|---|
| `/api/observe` | GET | 观测四神状态 |
| `/api/observations` | GET | 历史观测记录 |
| `/api/memories` | GET | 读取记忆 |
| `/api/memories` | POST | 写入记忆 |
| `/api/journals` | GET | 读取日记 |
| `/api/journals` | POST | 写入日记 |

### 语音（:9200 内置）

| 端点 | 方法 | 说明 |
|---|---|---|
| `/api/voice` | GET | 语音合成状态 |
| `/api/speak` | POST | 文本 → 语音 |

### 系统管理

| 端点 | 方法 | 说明 |
|---|---|---|
| `/api/trace` | GET | 管线追踪 |
| `/api/cost` | GET | LLM 成本追踪 |
| `/api/cross_sessions` | GET | 跨会话知识 |
| `/api/storage/health` | GET | 存储健康 |
| `/api/storage/maintenance` | POST | 存储维护 |
| `/api/docs` | GET | API 文档 |
| `/api/soul/install` | GET | 安装 systemd 服务 |
| `/api/soul/service` | GET | 生成 systemd 配置 |
| `/api/soul/launcher` | GET | 生成启动脚本 |

### 了了之手（行动）

| 端点 | 方法 | 说明 |
|---|---|---|
| `/api/actions` | GET | 可用行动列表 |
| `/api/touch` | POST | 执行行动 |

### 对等网络（:9200 内置）

| 端点 | 方法 | 说明 |
|---|---|---|
| `/api/peers` | GET | 节点列表 |
| `/api/peers/add` | POST | 添加节点 |
| `/api/peers/ping` | POST | 节点探活 |
| `/api/peers/{peer_id}` | DELETE | 移除节点 |

### 视觉

| 端点 | 方法 | 说明 |
|---|---|---|
| `/api/vision` | POST | 图像分析 |

### 织星仪表盘（:8765）

| 端点 | 方法 | 说明 |
|---|---|---|
| `/api/phi` | GET | 全局 φ 值 |
| `/api/health` | GET | 织星健康 |
| `/api/status` | GET | 织星状态 |
| `/dashboard.html` | GET | 织星仪表盘 |

> 共 44 个 API 端点。

---

## Python API 示例

### 双轨管线（标准路径）

```python
from genome_pipeline import run_dual_pipeline

ctx = run_dual_pipeline("分析MMT政策效果", skip_layers=set())
# ctx["message"]   → 组合后的 LLM 输入
# ctx["protein"]   → DNA 表达蛋白
# ctx["health"]    → 基因组健康状态
```

### 深度研究（知纹全栈）

```python
from research_planner import ResearchPlanner
from engineering_dag import dag_from_plan
from reasoning_engine import reason_from_evidence

planner = ResearchPlanner()
plan = planner.decompose("分析日本通缩与MMT")

dag = dag_from_plan(plan)
result = dag.execute(max_workers=4)

reasoning = reason_from_evidence(
    result["gene_results"],
    plan.query
)
```

### 计算层（异步缓存）

```python
from compute_layer import compute, compute_async

# 同步计算
benford = compute("benford", "数据文本...")

# 异步计算
future = compute_async("fiscal_sim", {"g": 0.15, "d": 2.5})
result = future.result(timeout=30)
```

### 自我审计

```python
from self_audit import run_audit

report = run_audit()
print(f"等级: {report.grade}, 总分: {report.total_score}")
print(f"通过: {report.passed}, 失败: {report.failed}")
```

### 数据质量闸

```python
from data_gate import DataGate

gate = DataGate.check(
    data_text="资产1200亿 负债800亿",
    data_requirements=["统计数据", "财务数据"],
    quality_threshold=0.6,
    query="检查财务状况",
    worldview_key="forensic",
)
print(f"通过: {gate.passed}, 综合分: {gate.overall_score}")
```

---

## 纹路记忆

了了记住每次研究的"纹路"——问题分解的结构和推理链的拓扑形状：

```python
from pattern_memory import get_memory

pm = get_memory()

# 检测追问（自动）
cont = pm.continue_from(session_id, "那通胀率呢？")
# → {"continued": True, "depth": 1, "parent_query": "分析日本通缩成因"}

# 检索相似纹路
similar = pm.recall("日本经济政策分析")
# → [{"pattern_id": "...", "similarity": 0.72, ...}]

# 保存纹路
pm.remember(
    query="分析日本通缩成因",
    decomposition=plan.sub_queries,
    dag_structure=dag.to_structure(),
    reasoning_chain=reasoning.chain,
)
```

当用户追问时，了了识别出这是上一轮的延续，复用 DAG 结构而非从零开始。

---

## 表达谱切换

了了根据问题自动选择表达模式。也可在请求中手动指定：

| 表达谱 | 触发特征 | 行为 |
|---|---|---|
| **学术深度** | 研究·分析·论文·验证 | 重模拟 ↑↑ · 重验证 ↑↑ · 轻搜索 |
| **快速浏览** | 快速·简单·大概·简述 | 重搜索 ↑↑ · 轻模拟 ↓↓ · 轻验证 |
| **验证优先** | 验证·确认·核实·数据 | 重验证 ↑↑↑ · 正常搜索 · 正常模拟 |
| **创意探索** | 创意·方案·设计·想法 | 重对比 · 重模拟 · 多假设 |

实现机制：表观遗传（不修改 DNA 序列，只改变基因表达方式），通过甲基化标记抑制或激活特定操纵子（搜索/模拟/验证）。

```python
from epigenetics import EpigeneticRegulator, EXPRESSION_PROFILES

regulator = EpigeneticRegulator()

# 自动检测
profile = regulator.detect("分析日本通缩成因")
# → EXPRESSION_PROFILES["academic_deep"]

# 手动切换
profile = EXPRESSION_PROFILES["verify_first"]
modified_operons = regulator.apply(operons, profile)
```
