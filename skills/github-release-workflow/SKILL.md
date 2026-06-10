---
name: github-release-workflow
description: >
  GitHub发布前自动检查流水线: 验证代码更新, 文档更新, 许可合规,
  雷军式文档重写, 中英双语, 一键推送。推送任何项目到GitHub前加载。
version: 1.0.0
triggers:
  - 准备发布或推送项目到GitHub
  - 需要检查代码和文档是否最新
  - 开源项目发布前的合规检查
  - 需要写或重写GitHub README和文档
  - 发布到github或推送github或开源发布
---

# GitHub 发布工作流

## 推送前检查清单

### ① 代码是否最新
```bash
git status --short        # 未提交改动
git fetch && git log HEAD..origin/master --oneline  # 是否落后远程
```
- [ ] 无未提交改动
- [ ] 已同步远程最新
- [ ] 本地运行测试通过 (`python3 self_audit.py`)

### ② 文档是否更新

必须存在的文件:
- [ ] `README.md` — 项目首页 (雷军体·痛点驱动)
- [ ] `LICENSE` — 标准许可证文件 (SPDX标识符)
- [ ] `docs/INSTALL.zh.md` + `docs/INSTALL.en.md`
- [ ] `docs/USAGE.zh.md` + `docs/USAGE.en.md`
- [ ] `docs/ARCHITECTURE.zh.md` + `docs/ARCHITECTURE.en.md`
- [ ] `docs/MANUAL.zh.md` + `docs/MANUAL.en.md`
- [ ] `.gitignore` — 排除密钥/缓存/数据库

### ③ 许可合规检查

- [ ] LICENSE 使用标准 SPDX 标识符 (非自创)
- [ ] 非商业项目推荐: CC BY-NC-SA 4.0 或 PolyForm Noncommercial
- [ ] 商业友好推荐: MIT / Apache 2.0 / BSD
- [ ] 分层许可: 主体 + tools/MIT + tests/MIT
- [ ] 核心源文件头部有 SPDX 标识
- [ ] README 中有许可速查表
- [ ] 商业许可联系方式明确 (如有非商业限制)

### ④ 文档质量检查

- [ ] 开头直击痛点 (开发者普遍踩过的坑)
- [ ] 清晰说明设计初衷和核心能力
- [ ] 明确写出使用后规避的风险、降低的成本
- [ ] 不是功能罗列 — 是痛点→方案叙事
- [ ] 有具体数据支撑
- [ ] 排版清爽: 表格+代码块+分层展示
- [ ] 中英双语版本内容一致

---

## 雷军式文档写作模板

### README 结构
```
# 项目名
> 一句话痛点共鸣。我们也受够了。所以做了XX。

## 五个痛点，一次解决
| 痛点 | 别人的做法 | 我们的做法 |
|---|---|---|

## 一条命令
(一键安装)

## XX做什么
(具体流程)

## 安全
(如有)

## 文档链接
(中英双语表格)
```

### 写作铁律
1. 开头=痛点 — 不说「XX是一个...」, 说「你受够了...」
2. 对比呈现 — 表格对比「别人 vs 我们」
3. 数字说话 — 每个声称后面跟数据
4. 一条命令 — 读者不需要读文档就能跑起来
5. 不解释技术 — 不需要懂架构就能用

### 禁止
- 「首先/其次/最后」结构
- 功能列表罗列
- 技术术语堆砌
- 「支持多种...」式空泛描述
- 长段落文字 (>5行)

---

## 中英双语规范

### 文件命名
```
README.md            → 根 README (双语摘要)
README.zh.md         → 中文完整版
README.en.md         → 英文完整版
docs/INSTALL.zh.md   → 中文安装指南
docs/INSTALL.en.md   → 英文安装指南
```

### 翻译原则
- 英文版不是逐字翻译·保持叙事力量
- 痛点共鸣用英语自然表达
- 代码示例和命令保持一致

---

## 执行流程

```
1. 检查代码    → git status / git log / self_audit
2. 检查文档    → 必选文件清单
3. 检查许可    → SPDX·分层·联系方式
4. 重写文档    → 雷军体模板·中英双语
5. 生成文件    → 按命名规范写入
6. Git提交     → 规范commit message
7. 推送到GitHub → 验证远端
```

## Commit Message 规范

```
类型: 简短描述

LICENSE: SPDX标识符
文档: 列出更新的文件
```

示例:
```
docs: Lei Jun-style + CC BY-NC-SA 4.0 + SPDX

LICENSE: CC BY-NC-SA 4.0 (core) + MIT (tools/)
README: 中英双语 · 五痛点 · 一条命令
MANUAL/INSTALL/USAGE/ARCH: 中英双语
```
