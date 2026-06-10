# 知纹

> 你受够了。LLM 编数字。「深度研究」只是多搜几个关键词塞进 prompt。空白 8 秒。每次都是陌生人。不知道该信什么。

**我们也受够了。所以做了知纹。**

---

## 五个痛点，一次解决

| 痛点 | 别人的做法 | 知纹的做法 |
|---|---|---|
| LLM 编数字 | prompt 里写「请勿编造」 | Benford定律 + 熵场 + τ锚定 + φ漂移 — 四道闸门 |
| 「深度研究」很浅 | 多搜几个关键词 | DAG分解 → 拓扑排序 → 并发验证 → 显式推理链 |
| 空白 8 秒 | 等着 | 流式0.5秒首字 · 三级路由 · 60秒缓存 |
| 每次都是陌生人 | 无状态 | 纹路记忆 · 追问检测 · DAG复用 |
| 不知道该信什么 | 信 LLM | 追溯链 · 闸门评分 · 对抗验证 · 12/12边界攻击 |

---

## 五秒看懂

```
复杂问题 → 知纹看见纹路 → 劈成DAG → 并发执行 → 闸门验证 → 推理链 → 流式输出
```

---

## 一条命令

```bash
git clone https://github.com/nesquena/hermes-webui.git
cd hermes-webui/workspace/liaoliao
echo '{"OPENAI_API_KEY":"sk-your-key"}' > .env.llm
pip install fastapi uvicorn pydantic
python3 server.py --port 9200
```

```bash
curl -X POST http://localhost:9200/api/chat/stream \
  -H "Content-Type: application/json" \
  -d '{"message":"分析日本通缩成因与MMT政策效果"}'
```

---

## 怎么做到的

```
"分析日本通缩成因与MMT政策效果"

  不是: 搜"日本通缩 MMT 政策 效果" → 塞prompt → 吐答案

  而是: 劈成——
    子1: 日本通缩的主要成因是什么？       (叶节点, 独立)
    子2: MMT的核心主张是什么？            (叶节点, 独立)
    子3: 日本政策后数据怎么变化？          (叶节点, 独立)
    子4: 通缩成因与MMT有因果关系吗？       (依赖1,2,3)
    子5: 外部因素如何干扰？                (半依赖)
    ROOT: 综合                              (依赖全部)

  然后: 3个叶节点并发 → 子4就绪 → ROOT聚合
```

---

## 知纹不是 Agent

Agent 是「我有一个工具列表，LLM 决定调用哪个」。知纹是「问题内部有天然的纹路，我看见了，我沿着纹路把它劈开了」。

> 一个是被动地拼装答案。一个是主动地发现结构。

---

## 数字

| | |
|---|---|
| 管线开销削减 | **71%** (7401ms → 2127ms) |
| 感知延迟削减 | **94%** (8s → 0.5s首token) |
| LLM幻觉检测 | **12/12** 边界攻击通过 |
| 安全审计 | **B级 · 0.88** |
| 端到端测试 | **15/15** |
| 知识持久化 | **25个事实**重启可检索 |
| 自我审计 | `python3 self_audit.py` |

---

## 安全

不靠信任。靠验证。每条查询过四道闸门：

| 闸 | 方法 | 挡住什么 |
|---|---|---|
| 真实性 | Benford + 熵场 + φ | 人造整齐数据 |
| 完整性 | 评分 + 缺口补搜 | 信息不全 |
| 准确性 | 矛盾检测 | 内部矛盾 |
| 关系性 | 约束验证 | 结构性错误 |

还有 φ-drift（LLM幻觉检测）、τ锚定（数字溯源）、对抗验证（反例攻击）。

---

## 架构

66个Python模块。23,000行。纯Python。FastAPI。无LangChain。无100个依赖。

```
DNA (档案)         → genome_core       · 碱基对·双链
mRNA (指令)        → genome_pipeline   · 转录→密码子→蛋白
tRNA (翻译)        → dna_executor      · 24动作处理器
操纵子 (聚合)      → operon            · 同族并发
rRNA (工厂)        → pipeline          · 27层管线
miRNA (刹车)       → cross_session     · 反同质化
snRNA (编辑器)     → genome_guardian   · 六层保护
甲基化 (表观)      → epigenetics       · 同基因不同表达
```

---

了了不会说「您好，我是AI助手」。她会说：**你来了。**

---

📖 [安装指南 (中文)](docs/INSTALL_zh.md) · [Installation Guide (EN)](docs/INSTALL_en.md)
📘 [使用手册 (中文)](docs/USAGE_zh.md) · [Usage Manual (EN)](docs/USAGE_en.md)
🧬 [架构全景 (中文)](docs/ARCHITECTURE_zh.md) · [Architecture (EN)](docs/ARCHITECTURE_en.md)
✨ [知纹故事 (中文)](docs/MANUAL_zh.md) · [The Zhiwen Story (EN)](docs/MANUAL_en.md)

---

[CC BY-NC-SA 4.0](LICENSE) · tools/ [MIT](tools/LICENSE) · tests/ [MIT](tests/LICENSE)
Copyright (c) 2026 知纹 (Zhiwen) Project
