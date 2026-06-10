# 知纹 · 安装指南

## 环境要求

| 组件 | 最低版本 | 说明 |
|---|---|---|
| Python | 3.9+ | 主要运行环境 |
| pip | 21.0+ | 包管理器 |
| Git | 2.0+ | 版本控制 (可选) |
| WSL2 | 任意 | Windows用户必须 (本机运行环境) |
| 磁盘空间 | 500MB | 代码+数据+缓存 |

## 快速安装 (3步)

### 1. 获取代码

```bash
git clone https://github.com/nesquena/hermes-webui.git
cd hermes-webui/workspace/liaoliao
```

### 2. 安装 Python 依赖

```bash
pip install fastapi uvicorn pydantic aiofiles
```

可选依赖 (文档阅读):
```bash
pip install pymupdf python-docx openpyxl  # PDF/Word/Excel解析
```

### 3. 配置 LLM API 密钥

```bash
# 创建配置文件 (支持OpenAI兼容API)
cat > .env.llm << EOF
{
  "OPENAI_API_KEY": "sk-your-api-key-here",
  "OPENAI_BASE_URL": "https://api.deepseek.com/v1",
  "OPENAI_MODEL": "deepseek-chat",
  "LLM_MODEL_FAST": "deepseek-chat",
  "LLM_MODEL_STANDARD": "deepseek-v4-pro",
  "LLM_MODEL_DEEP": "deepseek-v4-pro"
}
EOF
```

支持的 LLM 后端:
- **DeepSeek** (推荐): `OPENAI_BASE_URL=https://api.deepseek.com/v1`
- **OpenAI**: 默认 `https://api.openai.com/v1`
- **任何 OpenAI 兼容 API**: 修改 `OPENAI_BASE_URL`

---

## 启动服务

### 了了 (主服务 :9200)

```bash
python3 server.py --port 9200
```

启动预热 (自动):
- φ缓存预取 (节省首次查询1.7s)
- 方法路由预缓存
- 矩阵索引构建

### 织星 (仪表盘 :8765)

```bash
cd ../voyager && python3 serve.py --port 8765
```

### 天枢·定倾 (信任锚点 :9000 :9001 :9100)

```bash
# 如已有则跳过, 如需要新建:
cd /opt/tianshu && python3 api.py --port 9000
```

---

## 验证安装

```bash
# 1. 健康检查
curl http://localhost:9200/api/health
# → {"status":"ok","name":"了了","version":"2.0.0","backend":"openai"}

# 2. 对话测试
curl -X POST http://localhost:9200/api/chat \
  -H "Content-Type: application/json" \
  -d '{"message":"你好"}' 
# → {"reply":"你来了。","emotion":"温暖",...}

# 3. 流式对话 (推荐)
curl -X POST http://localhost:9200/api/chat/stream \
  -H "Content-Type: application/json" \
  -d '{"message":"分析日本MMT政策"}'
# → 逐token流式返回

# 4. 织星 φ 值
curl http://localhost:8765/api/phi
# → {"global_phi":0.01,"agent_count":1}

# 5. 自我审计
python3 self_audit.py
# → 12/12通过 · B级
```

---

## 目录结构

```
liaoliao/
├── server.py           主服务 (FastAPI)
├── mind.py             LLM后端 (支持流式)
├── pipeline.py         管线编排
├── genome_pipeline.py  DNA管线
├── research_planner.py 研究规划器
├── reasoning_engine.py 推理引擎
├── engineering_dag.py  工程DAG
├── compute_layer.py    计算层 (缓存+异步)
├── data/               运行时数据 (重启可重建)
├── docs/               文档
└── skills/             技能定义备份
```

## 环境变量

| 变量 | 说明 | 默认值 |
|---|---|---|
| OPENAI_API_KEY | LLM API密钥 | - |
| OPENAI_BASE_URL | API地址 | https://api.openai.com/v1 |
| OPENAI_MODEL | 默认模型 | gpt-4o-mini |
| LLM_MODEL_FAST | 快速路径模型 | 同OPENAI_MODEL |
| LLM_MODEL_STANDARD | 标准路径模型 | 同OPENAI_MODEL |
| LLM_MODEL_DEEP | 深度路径模型 | 同OPENAI_MODEL |

## 常见问题

**Q: 提示 `ModuleNotFoundError: No module named 'xxx'`**
A: 确保在 `liaoliao/` 目录下运行 `python3 server.py --port 9200`。Python 路径会自动包含当前目录。

**Q: 首次查询很慢 (>10s)**
A: 正常。启动预热会处理一部分，但首次搜索和 LLM 调用仍需 API 延迟。后续查询（缓存命中）会快很多。

**Q: 织星 φ 读取失败**
A: 检查 `python3 serve.py --port 8765` 是否在运行。φ 读取有 2s 超时和 30s 缓存，织星不可达不影响主服务。

**Q: 关系完整性检查没触发**
A: 确认数据文本格式为"资产XXX亿 负债XXX亿"（中文财务紧凑格式）。短文本需要 worldview_key="forensic"。
