# 当前 LICENSE vs 推荐方案对比

## 当前: "MIT License with Commons Clause"

```diff
- 问题 1: 不是 SPDX 标准标识符 (GitHub 无法自动识别)
- 问题 2: MIT 允许商业使用 + Commons Clause 禁止 = 内部矛盾
- 问题 3: Commons Clause 语言被修改 (法律模糊)
- 问题 4: 没有明确的分层许可 (全部文件同一个模糊许可证)
```

## 推荐 A: CC BY-NC-SA 4.0 + MIT 例外

```diff
+ SPDX: CC-BY-NC-SA-4.0 (GitHub 自动识别 ✅)
+ 全球法律体系认可 · 判例丰富
+ 与天枢主仓库一致 (同一生态)
+ MIT 例外给了 tools/ 灵活性

- "非商业"定义有时模糊 (但有 CC 官方 FAQ 解释)
- CC 不是为纯代码设计的 (但对研究/文档/库类项目完全适用)
```

## 推荐 B: PolyForm Noncommercial 1.0

```diff
+ 专业律师团队起草 (更精确的法律语言)
+ 专门为软件设计
+ SPDX: PolyForm-Noncommercial-1.0.0

- 不如 CC 广为人知
- 与天枢主仓库不一致
```

## 推荐 C: 保留当前结构但修复

```diff
改为:
  LICENSE           → "All Rights Reserved" (保留所有权利) + 明确授权条款
  LICENSE.MIT        → MIT (给 tools/ 用)

这样:
+ 没有 MIT + 非商业的内部矛盾
+ 授权条款可以写得更清晰

- 不是 SPDX 标准
- GitHub 无法自动识别
```

## 最佳选择

**对于定倾项目: 推荐 A (CC BY-NC-SA 4.0 + MIT 例外)**

理由:
1. 天枢主仓库已经用 CC BY-NC-SA 4.0 — 同一生态保持一致
2. CC 是 Creative Commons 的标准文本 — 全球认可
3. 定倾是研究性质的 Python 包 — CC 完全适用
4. tools/ 的 MIT 例外保留了灵活性
