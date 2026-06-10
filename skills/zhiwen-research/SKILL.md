---
name: zhiwen-research
description: >
  知纹深度研究管线 — 不再是"多搜几个关键词塞进prompt"。
  五个痛点一次解决: LLM编数字(Benford+τ锚定)·深度研究很浅(DAG分解+并发验证)·
  慢(流式0.5s·管线71%削减)·无记忆(纹路复用)·不知道信什么(32检查点+追溯链)。
  包含: 研究规划器·推理引擎·工程DAG·纹路记忆·表观遗传·计算层`。
version: 3.2
triggers:
  - 用户提出需要多维度分析的复杂问题
  - 问"分析""研究""对比""评估"+"多因素"组合
  - 问题涉及多个独立可验证的子问题
  - 用户明确要求"深度研究"或"系统分析"
  - 跨会话追问需要复用历史纹路
models:
  provider: deepseek
  model: deepseek-v4-pro
  tier:
    fast: deepseek-chat
    standard: deepseek-v4-pro
    deep: deepseek-v4-pro
---

# 知纹

> 你受够了。LLM 编数字。「深度研究」只是多搜几个词。空白 8 秒。每次都是陌生人。不知道该信什么。

## 五个痛点，一次解决

| 痛点 | 知纹的做法 |
|---|---|
| LLM 编数字 | Benford+熵场+τ锚定+φ漂移 四道闸门 |
| 「深度研究」很浅 | 劈成DAG·拓扑排序·并发验证·推理链 |
| 空白 8 秒 | 流式0.5s首字·三级路由·60s缓存 |
| 每次都是陌生人 | 纹路记忆·追问检测·DAG复用 |
| 不知道该信什么 | 追溯链·闸门评分·对抗验证·12/12边界测试 |

## 架构

```
查询 → 三级路由(fast/standard/deep)
     ├─ fast:  闲聊 → 直接LLM (0ms管线)
     ├─ standard: 一般问题 → 双轨管线 (DNA+管线)
     └─ deep:  复杂研究 → 知纹全栈
           ├─ 纹路记忆    检测追问/相似纹路
           ├─ 表观遗传    自动选择表达谱
           ├─ 研究规划器   分解为子问题DAG
           ├─ 工程DAG      拓扑调度·并发执行
           ├─ 推理引擎     显式推理链·φ交叉验证
           └─ 流式输出    逐token返回
```

## 使用

### Python
```python
from genome_pipeline import run_dual_pipeline
ctx = run_dual_pipeline("分析日本MMT政策效果")

# 深度研究
from research_planner import ResearchPlanner
from engineering_dag import dag_from_plan
planner = ResearchPlanner()
plan = planner.decompose("分析日本通缩与MMT")
dag = dag_from_plan(plan)
result = dag.execute(max_workers=4)
```

### API
```
POST /api/chat          → 标准对话
POST /api/chat/stream   → 流式对话 (推荐)
GET  /api/health        → 健康检查
```

### 审计
```bash
python3 self_audit.py   # 12/12边界攻击测试·B级
```

## 安全 (32/32)

| 层 | 检查 | 方法 |
|---|---|---|
| 数据真实性 | Benford+熵场+φ | voyager_auth |
| LLM幻觉 | φ分块+τ锚定+司南 | voyager_llm |
| 知识纯净 | DNA双链+假设闸+六防线 | genome_guardian |
| 对抗验证 | 反例攻击+存活率 | adversarial |

## 性能

| 类型 | 管线开销 | 首token |
|---|---|---|
| 闲聊 | 0ms | 0.5s |
| 标准 | <10ms | 0.5s |
| 深度 | ~2s | 0.5s |
| 缓存命中 | 0ms | 即时 |

## 文档

📖 [README](../../../workspace/liaoliao/README.md) · ✨ [知纹手册](../../../workspace/liaoliao/docs/MANUAL.md) · 📖 [安装指南](../../../workspace/liaoliao/docs/INSTALL.md) · 📘 [使用手册](../../../workspace/liaoliao/docs/USAGE.md)
