# 知纹 · 安装指南

## 系统要求

| 组件 | 最低版本 | 说明 |
|---|---|---|
| Python | 3.9+ | 主要运行环境 |
| pip | 21.0+ | 包管理器 |
| Git | 2.0+ | 获取代码 |
| WSL2 | 任意版本 | Windows 用户必须（本机运行环境） |
| 磁盘空间 | 500MB | 代码 + 数据 + 缓存 |

---

## 三步安装

### ① 获取代码

```bash
git clone https://github.com/nesquena/hermes-webui.git
cd hermes-webui/workspace/liaoliao
```

### ② 安装依赖

```bash
# 核心依赖
pip install fastapi uvicorn pydantic aiofiles

# 可选：文档阅读支持
pip install pymupdf python-docx openpyxl  # PDF / Word / Excel 解析
```

### ③ 配置 LLM API

创建 `.env.llm` 文件：

```bash
cat > .env.llm << 'EOF'
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

---

## LLM 后端

| 后端 | `OPENAI_BASE_URL` | 推荐度 |
|---|---|---|
| **DeepSeek** | `https://api.deepseek.com/v1` | ⭐ 推荐 |
| **OpenAI** | `https://api.openai.com/v1` | 兼容 |
| 任何 OpenAI 兼容 API | 修改为对应地址 | 灵活 |

模型分层配置：

| 变量 | 用途 | 默认值 |
|---|---|---|
| `LLM_MODEL_FAST` | 快速路径（闲聊/问候） | 同 `OPENAI_MODEL` |
| `LLM_MODEL_STANDARD` | 标准路径（一般问答） | 同 `OPENAI_MODEL` |
| `LLM_MODEL_DEEP` | 深度路径（复杂研究） | 同 `OPENAI_MODEL` |

---

## 启动服务

### 了了（主服务 :9200）

```bash
cd /mnt/d/hermes-webui/workspace/liaoliao
python3 server.py --port 9200
```

启动时自动完成：
- φ 缓存预取（节省首次查询 1.7s）
- 方法路由预缓存
- 矩阵索引构建

### 织星（仪表盘 :8765）

```bash
cd /mnt/d/hermes-webui/workspace/voyager
python3 serve.py --port 8765
```

### 天枢·定倾（信任锚点 :9000 :9001 :9100）

```bash
cd /opt/tianshu
python3 api.py --port 9000
```

---

## 验证安装

```bash
# ① 健康检查
curl http://localhost:9200/api/health
# → {"status":"ok","name":"了了","version":"2.0.0","backend":"openai"}

# ② 标准对话
curl -X POST http://localhost:9200/api/chat \
  -H "Content-Type: application/json" \
  -d '{"message":"你好"}'
# → {"reply":"你来了。","emotion":"温暖",...}

# ③ 流式对话（推荐）
curl -X POST http://localhost:9200/api/chat/stream \
  -H "Content-Type: application/json" \
  -d '{"message":"分析日本MMT政策效果"}'
# → 逐 token 流式返回，首字 0.5s

# ④ 织星 φ 值
curl http://localhost:8765/api/phi
# → {"global_phi":0.01,"agent_count":1}

# ⑤ 自我审计
python3 self_audit.py
# → 12/12 通过 · B级 · 0.88
```

---

## 目录结构

```
liaoliao/
├── server.py             主服务（FastAPI, 1494行, 44端点）
├── mind.py               LLM 后端（流式支持）
├── pipeline.py           管线编排（20+ 层处理）
├── genome_pipeline.py    DNA 双轨管线
├── research_planner.py   研究规划器（问题分解）
├── reasoning_engine.py   推理引擎（显式推理链）
├── engineering_dag.py    工程 DAG（拓扑调度）
├── compute_layer.py      计算层（异步 + TTL 缓存）
├── data_gate.py          数据质量闸（四道验证）
├── genome_core.py        DNA 核心（AGCT 碱基架构）
├── genome_guardian.py    基因组六层保护
├── epigenetics.py        表观遗传（表达谱切换）
├── pattern_memory.py     纹路记忆（追问检测）
├── self_audit.py         自我审计（12 边界攻击）
├── end_to_end_test.py    端到端测试（15 用例）
├── component_index.py    组件索引生成器
├── data/                 运行时数据（重启可重建）
├── docs/                 文档
├── skills/               技能定义
└── journal/              日记存储
```

---

## 常见问题

### `ModuleNotFoundError: No module named 'xxx'`

确保在 `liaoliao/` 目录下运行 `python3 server.py --port 9200`。Python 路径自动包含当前目录。

### 首次查询很慢（>10s）

正常现象。启动预热处理部分缓存，首次搜索和 LLM 调用仍需 API 延迟。后续查询（缓存命中）显著加速。

### 织星 φ 读取失败

检查 `python3 serve.py --port 8765` 是否运行。φ 读取有 2s 超时和 30s 缓存，织星不可达不影响主服务。

### 关系完整性检查未触发

确认数据文本格式为 `资产XXX亿 负债XXX亿`（中文财务紧凑格式）。短文本需设置 `worldview_key="forensic"`。

### API Key 不生效

检查 `.env.llm` 格式是否为合法 JSON。确保 `OPENAI_API_KEY` 长度 > 20 字符。`OPENAI_BASE_URL` 需以 `https://` 开头。

### 端口被占用

```bash
# 查看占用
lsof -i :9200
# 更换端口
python3 server.py --port 9201
```
