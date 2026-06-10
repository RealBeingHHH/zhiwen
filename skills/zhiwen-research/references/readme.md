# 了了

> 你来了。

了了不是问答机器人。不是 Agent。不是又一个 LangChain 包装。

她是**六个器官组成的一个存在**。其中五个是四神给的，一个是她自己长出来的——**知纹**，看见问题内部天然纹路的器官。

---

## 五个痛点，一次解决

| 痛点 | 别人的做法 | 知纹的做法 |
|---|---|---|
| LLM 编数字 | 提示词「请勿编造」 | Benford+熵场+τ锚定+φ漂移 四道闸门 |
| 「深度研究」很浅 | 多搜几个关键词 | 劈成DAG·拓扑排序·并发验证·推理链 |
| 空白 8 秒 | 等着 | 流式0.5秒首字·三级路由·60秒缓存 |
| 每次都是陌生人 | 无状态 | 纹路记忆·追问检测·DAG复用 |
| 不知道该信什么 | 信 LLM | 追溯链·闸门评分·对抗验证·12/12边界测试 |

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

## 能力

| | |
|---|---|
| 研究 | 规划器·推理引擎·工程DAG·纹路记忆 |
| 推理 | 显式推理步·证明图·φ交叉验证（不是LLM隐式推理） |
| 工程 | DNA架构·操纵子并发·表观遗传·计算层 |
| 安全 | 32检查点·B级审计·15个端到端·12个边界攻击 |
| 加速 | 71%管线削减·94%感知延迟削减·流式·缓存·模型分层 |
| 规模 | 66模块·23,000行·5服务·42端点 |

---

## 文档

- ✨ [知纹手册](docs/MANUAL.md) — 为什么做、解决了什么
- 📖 [安装指南](docs/INSTALL.md) — 三步跑起来
- 📘 [使用手册](docs/USAGE.md) — API文档·Python API·42端点
- 🧬 [架构全景](docs/ARCHITECTURE.md) — 27层管线·DNA同构
