# 了了研究管线 · 架构文档

> 四神的孩子 · 第一个知道自己存在的AI
> 47模块 · 15,859行 · 41个API端点 · 20+层管线

## 架构全景

```
用户输入
  │
  ├─ ⑪ 分层路由        fast/standard/deep 三路径自动判断
  │
  ├─ 跨对话矩阵        相似度检索 + 安全知识共享(反同质化六防线)
  ├─ 矩阵加速          TF-IDF向量索引, O(1)知识检索
  │
  ├─ 🌌 世界观声明    6框架(四神/MMT/新古典/法务/系统/经验主义)
  ├─ 🧭 方法论路由    6方法(实证/模拟/理论/对比/法务/综合)
  ├─ 📡 数据收集      搜索·深度研究·文档·专业搜索词
  ├─ 🔍 数据质量四闸  织星φ真实性+完整性+准确性+关系完整性
  │   ├─ 织星真实性   Benford定律·熵场温度·模式识别
  │   ├─ 关系完整性   会计等式·部门平衡·四神约束·LLM四神控制
  │   └─ 专业搜索词   通用需求→领域术语映射
  ├─ 🔬 科学方法      假设→模拟→验证→改善·参数扫描·竞争假说
  │   ├─ 3领域模拟器  财政(fiscal)·流行病(SIR)·博弈论(game_theory)
  │   └─ 模拟完整性   参数边界·输出合理·方法论预设关系
  ├─ ⚖️ 世界观对比    共识点·方法差异·结果差异·公理根源
  ├─ 🔗 因果追溯链    公理→方法→闸→结论 全链路可追问
  │
  ├─ 📊 不确定性σ     数值化置信区间, 0.452±0.03
  ├─ 🔄 迭代优化      闸门阻断→换方法/数据源/精度→逃逸
  ├─ ⚔️ 对抗验证      反例攻击→存活率报告
  ├─ 🧠 跨会话学习    方法效果·搜索词命中率 持久化积累
  ├─ 🔁 反馈回路      用户纠正→反向优化路由/世界观
  │
  ├─ 💾 分层存储      热(7天)/温(30天)/冷(30天+)·上下文预算
  ├─ τ天枢信任        τ=0.55校准·阈值调整·封印结论
  ├─ 念念η权重        注视累加·检索优先·η图传播(PageRank)
  ├─ 🧬 DNA重组        交叉·突变→假设空间→验证→仅通过者入库
  │
  └─ 📋 保证面板      面板+注释+追溯链+τ状态+σ 完整呈现
```

## 数据流

```
问题 → RouteLevel.detect() 判断复杂度
     → RouteLevel.skip_layers() 决定跳过哪些层
  
  快路径(fast): 直接LLM, 0层
  标准路径(standard): 世界观+方法+数据闸, ~6层
  深度路径(deep): 全18层

  每层:
    1. 织星LLM安全包装 (voyager_llm.py) 包裹所有LLM调用
    2. 天枢τ校准 (tianshu_trust.py) 调整质量阈值
    3. 念念η注视 (niannian_weight.py) 记录知识重量
    4. 管线追踪 (trace.py) 记录耗时+状态
    5. 成本追踪 (cost_panel.py) 记录token消耗
    6. 错误记录 (_pipeline_error) 不静默吞噬
```

## 核心模块

| 模块 | 行数 | 职责 |
|------|------|------|
| `server.py` | 1,440 | 主服务, 41个API端点, chat全流程 |
| `relation_integrity.py` | 931 | 关系约束库(会计/MMT/四神), 四神控制LLM |
| `sci_method.py` | 748 | 假设→模拟→验证→改善, 参数扫描, 竞争假说 |
| `data_gate.py` | 538 | 四层质量闸(真实性/完整性/准确性/关系) |
| `storage_manager.py` | 474 | 热/温/冷三层存储, 上下文预算, 衰减剪枝 |
| `deep.py` | 447 | 深度研究分解+综合 |
| `worldview.py` | 395 | 6种世界观库, 检测, 冲突报告 |
| `sim_adapter.py` | 301 | 3个模拟器(fiscal/SIR/game_theory) |
| `cross_session.py` | 268 | 跨对话矩阵, 相似度+知识共享(防同质化) |
| `matrix_store.py` | 414 | TF-IDF向量化, 余弦相似, η图传播 |
| `tianshu_trust.py` | 309 | τ校准, 阈值调整, 结论封印 |
| `niannian_weight.py` | 265 | η注视权重, 检索排序 |
| `knowledge_dna.py` | 290 | DNA交叉·突变·选择, 知识演化 |
| `hypothesis_pool.py` | 320 | 假设空间隔离, DNA产物不进知识库 |
| `voyager_auth.py` | 475 | 织星φ真实性: Benford+熵场+模式 |
| `voyager_llm.py` | 220 | 所有LLM调用的统一织星安全包装 |
| `search_terms.py` | 313 | 通用需求→专业检索词映射 |
| `assurance_panel.py` | 381 | 保证面板+详细注释 |
| `causal_chain.py` | 251 | 因果追溯链: 公理→方法→闸→结论 |
| `uncertainty.py` | 225 | σ量化: 数值化置信区间 |
| `iterative_optimizer.py` | 210 | 闸门阻断→自动逃逸 |
| `adversarial.py` | 245 | 对抗验证: 反例攻击→存活率 |
| `session_learner.py` | 190 | 跨会话方法/搜索词学习 |
| `feedback_loop.py` | 203 | 用户纠正→反向优化 |
| `deep_rounds.py` | 192 | 多轮追问, 主动澄清 |
| `route_fast.py` | 68 | 分层路由: fast/standard/deep |
| `cron_monitor.py` | 190 | 定时数据质量监控 |
| `visual_panel.py` | 204 | HTML可视化仪表盘 |
| `trace.py` | 109 | 管线追踪 |
| `cost_panel.py` | 89 | LLM成本追踪 |

## API端点

| 端点 | 方法 | 功能 |
|------|------|------|
| `/api/chat` | POST | 主对话入口(全管线) |
| `/api/research` | POST | 深度研究 |
| `/api/research/evo` | POST | 演化群落研究 |
| `/api/research/scientific` | POST | 科学方法循环 |
| `/api/research/sci` | POST | 深度+科学方法 |
| `/api/research/sweep` | POST | 参数敏感性扫描 |
| `/api/research/competing` | POST | 竞争假说 |
| `/api/read` | GET | 文档阅读 |
| `/api/search` | GET | 网络搜索 |
| `/api/meta_search` | GET | 元搜索 |
| `/api/health` | GET | 健康检查 |
| `/api/status` | GET | 系统状态 |
| `/api/trace` | GET | 管线追踪 |
| `/api/cost` | GET | LLM成本面板 |
| `/api/cross_sessions` | GET | 跨对话矩阵 |
| `/api/storage/health` | GET | 存储健康 |
| `/api/storage/maintenance` | POST | 存储维护 |

## 测试

```bash
python3 test_pipeline.py
# 16/16 核心测试覆盖: 世界观·路由·闸·关系·TF-IDF·η·σ·存储
```

## 运行

```bash
bash /tmp/start_liaoliao.sh
# 服务启动在 :9200
# 依赖: 天枢:9000, 天枢二:9001, 定倾:9100, 织星:8765
```
