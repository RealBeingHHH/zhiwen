"""
分层路由器 — 不是所有问题都需要18层

🟢 快路径: "你好" → 直接LLM (0层)
🟡 标准路径: "GDP是多少" → 世界观+方法+数据闸 (6层)
🔴 深度路径: "最优赤字率" → 全18层

自动判断复杂度，分配合适的层数。
"""

class RouteLevel:
    FAST = "fast"       # 跳过所有验证, 直接LLM
    STANDARD = "standard"  # 世界观+数据闸
    DEEP = "deep"       # 全18层

    # 快速路径触发词 — 纯闲聊/简单问答
    FAST_PATTERNS = [
        "你好", "在吗", "谢谢", "再见", "晚安", "早安",
        "哈哈", "嗯", "哦", "好的", "OK", "行",
    ]

    # 深度路径触发 — 复杂研究问题
    DEEP_KEYWORDS = [
        "最优", "最佳", "改善", "优化", "方案", "策略",
        "对比", "比较", "分析", "评价", "推荐",
        "模拟", "仿真", "演化", "假设", "验证",
        "造假", "操纵", "不可信", "可信吗",
    ]

    @classmethod
    def detect(cls, query: str) -> str:
        """自动判断路由级别。"""
        msg = query.strip()

        # 极短 + 纯闲聊 → 快速
        if len(msg) < 6 and any(kw in msg for kw in cls.FAST_PATTERNS):
            return cls.FAST

        # 短查询但有实质内容 → 标准 (不是闲聊)
        if len(msg) < 6:
            return cls.STANDARD

        # 包含深度触发词 → 深度
        deep_count = sum(1 for k in cls.DEEP_KEYWORDS if k in msg)
        if deep_count >= 2 or len(msg) > 50:
            return cls.DEEP

        # 默认 → 标准
        return cls.STANDARD

    @classmethod
    def skip_layers(cls, level: str) -> set:
        """返回需要跳过的层名。"""
        if level == cls.FAST:
            return {"worldview", "method", "data_gate", "contrast", "sci_method",
                    "causal_chain", "uncertainty", "iterative", "adversarial"}
        if level == cls.STANDARD:
            return {"contrast", "sci_method", "iterative", "adversarial"}
        return set()  # 深度: 不跳任何层


def detect_route(query: str) -> str:
    return RouteLevel.detect(query)


# ═══ 自检 ═══
if __name__ == "__main__":
    for q in ["你好", "GDP是多少", "对比MMT和新古典哪个更优", "再见"]:
        level = RouteLevel.detect(q)
        skip = RouteLevel.skip_layers(level)
        print(f"{level:10s} | {q:30s} | 跳过{len(skip)}层")
