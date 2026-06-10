# 知纹 Zhiwen

> 你受够了。LLM 编数字。「深度研究」只是多搜几个关键词。空白 8 秒。每次都是陌生人。不知道该信什么。**我们也受够了。所以做了知纹。**

> You're tired. LLMs hallucinate. "Deep research" is shallow. 8 seconds of silence. Every query a stranger. Never knowing what to trust. **We were too. So we built Zhiwen.**

---

## 一键安装 · One Command

```bash
curl -fsSL https://raw.githubusercontent.com/RealBeingHHH/zhiwen/master/setup.sh | bash
```

或者手动：

```bash
git clone https://github.com/RealBeingHHH/zhiwen.git && cd zhiwen
pip install -r requirements.txt
echo '{"OPENAI_API_KEY":"sk-your-key"}' > .env.llm
python3 server.py --port 9200
```

```bash
curl -X POST http://localhost:9200/api/chat/stream \
  -H "Content-Type: application/json" \
  -d '{"message":"分析日本通缩成因与MMT政策效果"}'
```

---

## 五个痛点 · Five Pain Points

| 痛点 | 别人的做法 | 知纹 |
|---|---|---|
| LLM 编数字 | prompt 写「请勿编造」 | Benford + 熵场 + τ锚定 + φ漂移 — 四道闸门 |
| 「深度研究」很浅 | 多搜几个关键词 | DAG分解 → 拓扑排序 → 并发验证 → 显式推理链 |
| 空白 8 秒 | 等着 | 流式0.5s首字 · 三级路由 · 60s缓存 |
| 每次都是陌生人 | 无状态 | 纹路记忆 · 追问检测 · DAG复用 |
| 不知道该信什么 | 信 LLM | 追溯链 · 闸门评分 · 对抗验证 · 12/12边界攻击 |

---

## 知纹做什么

```
"分析日本通缩成因与MMT政策效果"

  不是: 搜关键词 → 塞prompt → 吐答案

  而是: 劈成5个原子问题 →
    子1: 日本通缩的主要成因？        (叶节点·独立)
    子2: MMT的核心主张？             (叶节点·独立)
    子3: 日本政策后数据变化？         (叶节点·独立)
    子4: 通缩与MMT有因果关系？        (依赖1,2,3)
    ROOT: 综合结论                    (依赖全部)

  3个叶节点并发 → 子4就绪触发 → ROOT聚合
```

---

## 安全 · Safety

| 闸 | 方法 | 挡住什么 |
|---|---|---|
| 真实性 | Benford + 熵场 + φ | 人造数据 |
| 完整性 | 评分 + 补搜 | 信息不全 |
| 准确性 | 矛盾检测 + 关系验证 | 内部矛盾 |
| 幻觉 | φ-drift + τ锚定 + 对抗 | LLM编造 |

`python3 self_audit.py` — 12/12通过 · B级

---

## 文档 · Docs

| 中文 | English |
|---|---|
| [📖 安装指南](docs/INSTALL_zh.md) | [📖 Installation](docs/INSTALL_en.md) |
| [📘 使用手册](docs/USAGE_zh.md) | [📘 Usage Manual](docs/USAGE_en.md) |
| [🧬 架构全景](docs/ARCHITECTURE_zh.md) | [🧬 Architecture](docs/ARCHITECTURE_en.md) |
| [✨ 知纹故事](docs/MANUAL_zh.md) | [✨ The Zhiwen Story](docs/MANUAL_en.md) |

---

[CC BY-NC-SA 4.0](LICENSE) · tools/ [MIT](tools/LICENSE)
Copyright (c) 2026 知纹 (Zhiwen) Project
