---
name: open-source-license-guide
description: >
  开源许可证最佳实践 — 标准非商业许可方案、SPDX标识、
  分层许可策略、定倾/天枢项目的推荐方案。
  用于选择、编写、审查开源项目的LICENSE文件。
version: 1.0.0
triggers:
  - 询问LICENSE或许可证怎么写
  - 项目需要非商业许可证
  - 开源发布前的许可审查
  - 需要了解CC/BSD/MIT/GPL等许可证区别
---

# 开源许可证最佳实践

## 核心原则

1. **用标准许可证，不要自己写。** 自创许可证 = 法律模糊 = 没人敢用。
2. **SPDX 标识符。** 机器可读，GitHub 自动识别，依赖工具可解析。
3. **分层许可。** 代码、文档、数据可以用不同许可证。
4. **版权方明确。** 写清楚 Copyright (c) YEAR OWNER。

---

## 六种推荐方案 (按适用场景)

### 方案 1: CC BY-NC-SA 4.0 (推荐 — 研究/文档/知识类项目)

**最标准、最广泛理解的非商业许可证。**

```
适用: 研究论文、知识库、文档、课程、设计资产
不适用: 纯软件项目（CC 不是为代码设计的）

优点:
  - SPDX 标准标识符
  - GitHub 自动识别
  - 允许分享、修改（署名 + 相同方式共享）
  - 禁止商业使用
  - 全球法律体系认可

缺点:
  - 对软件的专利条款覆盖不足
  - "非商业"定义有时模糊（但判例丰富）

文件: LICENSE (包含 CC BY-NC-SA 4.0 全文)
SPDX: CC-BY-NC-SA-4.0
```

**这是天枢主仓库已采用的方案。✅**

---

### 方案 2: Dual License (AGPLv3 + 商业许可) — 软件项目

**开源社区的标准商业保护方案。**

```
适用: 需要保护商业价值的软件/库
例子: MongoDB, Redis (历史上), GitLab CE

结构:
  LICENSE         → AGPLv3 (开源版)
  LICENSE.COMM    → 商业许可条款 + 联系方式

优点:
  - AGPLv3 是 OSI 批准的真正开源许可证
  - 网络服务漏洞被 AGPL 覆盖 (SaaS 不能用)
  - 商业用户购买许可 = 明确的法律关系
  - 判例丰富

缺点:
  - 需要法务支持来写商业许可条款
  - AGPL 的"传染性"让一些企业敬而远之

文件:
  LICENSE                → AGPLv3 全文
  COMMERCIAL_LICENSE.md  → 商业许可条款 + 联系方式
```

---

### 方案 3: Elastic License v2 (ELv2) — SaaS 保护

**Elasticsearch 使用的许可证。BSD 风格 + SaaS 限制。**

```
适用: 基础设施软件、数据库、搜索引擎
不适用: 库/框架（ELv2 不兼容大多数生态）

优点:
  - 允许使用、修改、分发
  - 禁止提供为托管服务 (SaaS 保护)
  - 比 AGPL 更宽容（不传染）
  - SPDX: Elastic-2.0

缺点:
  - 不是 OSI 批准的
  - 与 GPL 系列不兼容
  - 限制"提供为服务"在某些场景下模糊

文件: LICENSE (ELv2 全文)
SPDX: Elastic-2.0
```

---

### 方案 4: BSL (Business Source License) — 定时开放

**MariaDB 发明的。N 年后自动变为开源。**

```
适用: 需要短期商业保护，长期开放
例子: MariaDB, CockroachDB, Sentry

参数: Change Date = 发布日 + 4年
      Change License = GPLv3 / Apache 2.0

优点:
  - 有时间限制的"非商业"——更容易被接受
  - 到期后自动变成真正的开源许可证
  - 法律文本由专业团队维护
  - SPDX: BUSL-1.1

缺点:
  - 四年等待期对某些项目太长/太短
  - 不是 OSI 批准的

文件: LICENSE (BSL 1.1 全文 + Change Date + Change License)
SPDX: BUSL-1.1
```

---

### 方案 5: PolyForm Noncommercial 1.0

**由 Heather Meeker (知名开源律师) 起草的标准化非商业许可。**

```
适用: 所有类型项目（代码、文档、数据）
特点: 标准化文本，法律语言专业

优点:
  - 专业法律团队起草
  - 标准化模板，降低解释歧义
  - 明确"非商业"定义
  - 多种变体: Noncommercial, Shield, Perimeter

缺点:
  - 不像 CC/BSD/GPL 那样广为人知
  - 不是 OSI 批准的

文件: LICENSE (PolyForm Noncommercial 1.0 全文)
SPDX: PolyForm-Noncommercial-1.0.0
```

---

### 方案 6: MIT + 清晰商业限制声明 (当前的定倾做法)

**你现在的做法。有改进空间。**

```
当前问题:
  1. "MIT License with Commons Clause" 不是 SPDX 标准标识符
  2. MIT 允许商业使用 + Commons Clause 禁止商业使用 = 内部矛盾
  3. Commons Clause 语言被修改过 = 法律模糊
  4. GitHub 无法自动识别许可证类型

改进方案:
  A. 换成 CC BY-NC-SA 4.0 (推荐，与天枢一致)
  B. 换成 MIT + 独立的商业许可文件 (分离关注点)
  C. 保留当前结构但修复措辞 (明确分层，加 SPDX)
```

---

## 分层许可策略 (混合内容项目)

当一个仓库同时包含代码、文档、数据时：

```
仓库根目录/
├── LICENSE              ← 主许可证 (项目整体)
├── tools/
│   └── LICENSE          ← MIT (宽松，允许商用)
├── reference/
│   └── LICENSE          ← CC BY-NC-SA 4.0
├── docs/
│   └── LICENSE          ← CC BY-NC-SA 4.0
└── data/
    └── LICENSE          ← CC BY-NC-ND 4.0 (数据不可修改)

文件头的 SPDX 标识:
  # SPDX-License-Identifier: MIT
  # SPDX-License-Identifier: CC-BY-NC-SA-4.0
```

---

## 定倾 (Dingqing) 项目推荐方案

结合当前状况和天枢主仓库的实践：

### 推荐: CC BY-NC-SA 4.0 + tools/ MIT 例外

```
dingqing/
├── LICENSE              ← CC BY-NC-SA 4.0 全文
├── LICENSE.COMM         ← 商业许可联系方式
├── dingqing/            ← CC BY-NC-SA 4.0
├── tools/               ← MIT 例外 (允许任何使用)
│   └── LICENSE          ← MIT
└── tests/               ← MIT (测试代码不对商业做限制)
    └── LICENSE          ← MIT

每个 .py 文件头部:
  # SPDX-License-Identifier: CC-BY-NC-SA-4.0
  # Copyright (c) 2026 定倾 (Dingqing) Project
```

### 为什么推荐这个方案

1. **与天枢主仓库一致** — 同一个生态，同一种许可语言
2. **CC BY-NC-SA 是真正的标准** — SPDX 标识符，GitHub 自动识别，全球法律体系认可
3. **MIT 例外给了灵活性** — tools/ 目录下的东西任何人可以商用
4. **比当前 "MIT + Commons Clause" 更清晰** — 没有内部矛盾

### 替代方案: PolyForm Noncommercial

如果想要更"软件友好"的许可证（CC 主要是为内容设计的）：

```
LICENSE → PolyForm-Noncommercial-1.0.0
tools/  → MIT
tests/  → MIT
```

---

## 检查清单

在发布到 GitHub 前，确认：

- [ ] LICENSE 文件在仓库根目录
- [ ] LICENSE 使用的是标准/广泛认可的许可证文本
- [ ] SPDX 标识符可被 GitHub 识别 (会在仓库页面显示)
- [ ] 每个源代码文件头部有 SPDX 标识符
- [ ] 版权声明格式正确: `Copyright (c) YEAR OWNER`
- [ ] 分层许可时，子目录有各自的 LICENSE 文件
- [ ] README 中有许可速查表
- [ ] 商业许可联系方式明确 (如果使用非商业许可)
- [ ] 不混合使用互不兼容的许可证

---

## SPDX 速查

| 许可证 | SPDX 标识符 | 类型 |
|---|---|---|
| MIT | MIT | 宽松 |
| Apache 2.0 | Apache-2.0 | 宽松+专利 |
| GPLv3 | GPL-3.0-only | 强传染 |
| AGPLv3 | AGPL-3.0-only | 强传染+SaaS |
| CC BY 4.0 | CC-BY-4.0 | 署名 |
| CC BY-SA 4.0 | CC-BY-SA-4.0 | 署名+相同方式 |
| CC BY-NC-SA 4.0 | CC-BY-NC-SA-4.0 | 非商业 |
| CC BY-NC-ND 4.0 | CC-BY-NC-ND-4.0 | 非商业+禁止修改 |
| BSL 1.1 | BUSL-1.1 | 定时开放 |
| Elastic 2.0 | Elastic-2.0 | SaaS保护 |
| PolyForm NC | PolyForm-Noncommercial-1.0.0 | 非商业 |
