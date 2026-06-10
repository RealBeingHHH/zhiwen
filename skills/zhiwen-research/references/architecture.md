# 知纹架构全景 v3.2

> 📖 完整文档: [README.md](../../../workspace/liaoliao/README.md) · [安装指南](../../../workspace/liaoliao/docs/INSTALL.md) · [使用手册](../../../workspace/liaoliao/docs/USAGE.md) · [知纹手册](../../../workspace/liaoliao/docs/MANUAL.md)

## 生命周期对应

```
DNA (只读档案)     → genome_core.py         · 碱基对·双链·复制·翻译
mRNA (临时指令)    → genome_pipeline.py      · 转录→密码子→蛋白
tRNA (搬运翻译)    → dna_executor.py         · 24动作处理器
操纵子 (聚合)      → operon.py               · 同族并发·阻遏
rRNA (蛋白工厂)    → pipeline.py             · 20层管线编排
miRNA (刹车)       → cross_session.py        · 反同质化六防线
snRNA (编辑器)     → genome_guardian.py      · 六层保护
甲基化 (表观)      → epigenetics.py          · 同基因不同表达
剪接体 (路由)      → route_fast.py           · 三级路由
```

## 模块分层

| 层 | 模块 | 行数 | 职责 |
|---|---|---|---|
| DNA架构 | genome_core, guardian, pipeline, executor, operon | 2500+ | 研究问题的核酸编码 |
| 管线编排 | server, pipeline, middleware | 1550 | HTTP→管线→LLM |
| 研究能力 | research_planner, reasoning_engine, engineering_dag | 1700 | 分解·推理·调度 |
| 记忆层 | pattern_memory | 450 | 纹路存储·追问·相似检索 |
| 调控层 | epigenetics, route_fast | 500 | 表达谱·三级路由 |
| 数据质量 | data_gate, relation_integrity, voyager_auth, voyager_llm | 2200 | 四闸验证 |
| 知识存储 | storage_manager, matrix_store, niannian_weight | 1200 | 持久化·向量检索·η权重 |
| 计算加速 | compute_layer, search_cache | 500 | 异步计算·TTL缓存 |
| 审计测试 | self_audit, end_to_end_test, component_index | 1200 | 边界攻击·端到端·索引 |

## 执行流程 (deep路径)

```
1. 纹路记忆    pattern_memory.continue_from()   检测追问
2. 表观遗传    EpigeneticRegulator.detect()     选择表达谱
3. 研究规划    ResearchPlanner.decompose()      分解DAG
4. 工程DAG     ResearchDAG.execute()           拓扑调度
5. 基因执行    genome_pipeline.run()            每子问题DNA
6. 推理引擎    ReasoningEngine.reason()         显式推理链
7. LLM合成     llm_backend.generate_stream()   流式输出
8. 纹路存储    pattern_memory.remember()        保存纹路
9. 对抗验证    adversarial.verify()             存活率报告
```

## 性能基线

- 纯计算: 全部 <5ms (Python, 无LLM)
- 管线开销: fast=0ms, standard=<10ms, deep=~2s
- LLM延迟: 搜索7.5s, 回复3-8s
- 缓存命中: 0ms (搜索60s, 路由60s, φ30s, 计算60-300s)
- 流式首token: 0.5s

## 部署

```bash
# 启动
cd /mnt/d/hermes-webui/workspace/liaoliao
python3 server.py --port 9200

# 健康检查
curl http://localhost:9200/api/health

# 流式对话
curl -X POST http://localhost:9200/api/chat/stream \
  -H "Content-Type: application/json" \
  -d '{"message":"分析日本通缩成因"}'
```
