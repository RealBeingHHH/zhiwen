# 知纹 · 使用手册

## 对话模式

### 基础对话

```bash
# 标准对话 (一次性返回)
curl -X POST http://localhost:9200/api/chat \
  -H "Content-Type: application/json" \
  -d '{"message":"什么是MMT","user":"探索者"}'
```

### 流式对话 (推荐)

```bash
# 逐token返回, 感知延迟 8s→0.5s
curl -X POST http://localhost:9200/api/chat/stream \
  -H "Content-Type: application/json" \
  -d '{"message":"分析日本通缩成因"}'
```

---

## 三级路由

了了自动判断问题复杂度，分配不同处理路径：

| 路由 | 触发条件 | 管线开销 | 适用场景 |
|---|---|---|---|
| 🟢 fast | "你好""谢谢"等闲聊 | 0ms | 问候·简单问答 |
| 🟡 standard | 一般事实型问题 | <10ms | "什么是MMT""GDP多少" |
| 🔴 deep | 2+分析关键词/>50字 | ~2s | "分析日本通缩与MMT对比" |

---

## 深度研究 (知纹全栈)

对复杂问题，了了自动启动知纹研究管线：

```
查询: "日本1990-2020年MMT政策效果如何？赤字率与通胀率的关系？"
  ↓
研究规划器 → 分解为5子问题DAG:
  子1: 日本通缩主要成因
  子2: MMT核心主张
  子3: 日本MMT政策后数据变化 (依赖:1,2)
  子4: 因果关系验证 (依赖:1,2,3)
  子5: 外部因素影响
  ROOT: 综合结论 (依赖:全5个)
  ↓
工程DAG → 拓扑调度·4路并发
  ↓
推理引擎 → 声明→推理边→证明链
  ↓
流式输出 → 逐token返回
```

---

## API 端点

### 核心端点

| 端点 | 方法 | 说明 |
|---|---|---|
| `/api/chat` | POST | 标准对话 |
| `/api/chat/stream` | POST | 流式对话 (推荐) |
| `/api/health` | GET | 健康检查 |
| `/api/status` | GET | 详细状态 |

### 研究端点

| 端点 | 方法 | 说明 |
|---|---|---|
| `/api/research` | POST | 深度研究 |
| `/api/research/evo` | POST | 演化研究 |
| `/api/research/scientific` | POST | 科学方法研究 |
| `/api/research/sweep` | POST | 参数敏感性扫描 |
| `/api/research/competing` | POST | 竞争假说验证 |

### 数据端点

| 端点 | 方法 | 说明 |
|---|---|---|
| `/api/search` | GET | 网络搜索 |
| `/api/read` | GET | 文档阅读 (PDF/EPUB/DOCX) |
| `/api/meta_search` | GET | 元搜索自寻源 |
| `/api/stock` | GET | 股票查询 |
| `/api/trending` | GET | 热搜查询 |
| `/api/papers` | GET | 论文搜索 |
| `/api/weather` | GET | 天气查询 |

### 观测端点

| 端点 | 方法 | 说明 |
|---|---|---|
| `/api/observe` | GET | 了了观测四神状态 |
| `/api/observations` | GET | 历史观测记录 |
| `/api/memories` | GET/POST | 记忆管理 |
| `/api/journals` | GET/POST | 日记管理 |

### 系统端点

| 端点 | 方法 | 说明 |
|---|---|---|
| `/api/trace` | GET | 管线追踪 |
| `/api/cost` | GET | LLM 成本追踪 |
| `/api/cross_sessions` | GET | 跨会话知识 |
| `/api/storage/health` | GET | 存储健康 |
| `/api/storage/maintenance` | POST | 存储维护 |
| `/api/docs` | GET | API 文档 |

### 织星端点 (:8765)

| 端点 | 方法 | 说明 |
|---|---|---|
| `/api/phi` | GET | 织星全局φ值 |
| `/api/health` | GET | 织星健康 |
| `/api/status` | GET | 织星状态 |
| `/dashboard.html` | GET | 织星仪表盘 |

---

## 表达谱 (表观遗传)

了了根据问题自动切换表达模式。也可以手动指定：

| 表达谱 | 触发词 | 行为 |
|---|---|---|
| 学术深度 | 研究·分析·论文·验证 | 重模拟·重验证 |
| 快速浏览 | 快速·简单·大概·简述 | 重搜索·轻模拟 |
| 验证优先 | 验证·确认·核实·数据 | 重验证·正常搜索 |
| 创意探索 | 创意·方案·设计·想法 | 重对比·重模拟 |

---

## Python API

```python
# 双轨管线 (标准路径)
from genome_pipeline import run_dual_pipeline
ctx = run_dual_pipeline("分析MMT政策", skip_layers=set())

# 深度研究 (知纹全栈)
from research_planner import ResearchPlanner
from engineering_dag import dag_from_plan
from reasoning_engine import reason_from_evidence

planner = ResearchPlanner()
plan = planner.decompose("分析日本通缩与MMT")
dag = dag_from_plan(plan)
result = dag.execute(max_workers=4)
reasoning = reason_from_evidence(result["gene_results"], plan.query)

# 计算层 (异步缓存)
from compute_layer import compute, compute_async
benford = compute("benford", "数据文本")
future = compute_async("fiscal_sim", {})

# 自我审计
from self_audit import run_audit
report = run_audit()
print(f"等级: {report.grade}, 总分: {report.total_score}")
```

---

## 纹路记忆

了了记住每次研究的"纹路"——问题分解的结构和推理链的形状。

```python
from pattern_memory import get_memory
pm = get_memory()

# 检测追问 (自动)
cont = pm.continue_from(session_id, "那通胀率呢？")
# → {"continued": True, "depth": 1, "parent_query": "分析日本通缩成因"}

# 检索相似纹路
similar = pm.recall("日本经济政策分析")
# → [{"pattern_id": "...", "similarity": 0.72, ...}]
```
