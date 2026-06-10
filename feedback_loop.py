"""
用户反馈回路 — 纠正反向优化各层参数

当用户纠正了了回答时:
  - "不对，应该是..." → 提取修正
  - "这个结论有问题" → 回溯哪一层出的错
  - "你应该用XX方法" → 更新方法偏好

反馈作用于:
  1. 世界观检测 (该问题应匹配哪个框架)
  2. 方法论路由 (该问题应用什么方法)
  3. 搜索词选择 (什么搜索词更有效)
  4. 质量阈值 (该领域需要多高的门槛)

存储: 与 session_learner 共享存储
"""

import json
import hashlib
import time
from pathlib import Path
from typing import Optional

from session_learner import SessionLearner, STORE_PATH


class FeedbackLoop:
    """用户纠正 → 反向优化。"""

    FEEDBACK_FILE = STORE_PATH.parent / "user_feedback.json"

    @classmethod
    def _load_feedback(cls) -> dict:
        if cls.FEEDBACK_FILE.exists():
            try:
                return json.loads(cls.FEEDBACK_FILE.read_text())
            except Exception:
                pass
        return {
            "corrections": [],       # [{query, original, corrected, layer, time}]
            "method_overrides": {},  # {query_pattern: preferred_method}
            "worldview_overrides": {}, # {query_pattern: preferred_worldview}
            "quality_adjustments": {}, # {worldview: threshold_adjustment}
        }

    @classmethod
    def _save_feedback(cls, data: dict) -> None:
        cls.FEEDBACK_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2))

    @classmethod
    def record_correction(
        cls,
        query: str,
        original_answer: str,
        corrected_answer: str,
        failed_layer: str = "",
    ) -> None:
        """
        记录用户纠正。

        failed_layer: 世界观/方法论/数据/推理 — 哪个层出的错
        """
        data = cls._load_feedback()
        qhash = hashlib.md5(query[:200].encode()).hexdigest()[:12]

        data["corrections"].append({
            "time": time.time(),
            "query_hash": qhash,
            "query": query[:200],
            "original": original_answer[:200],
            "corrected": corrected_answer[:200],
            "failed_layer": failed_layer,
        })

        # 只保留最近100条
        if len(data["corrections"]) > 100:
            data["corrections"] = data["corrections"][-100:]

        cls._save_feedback(data)

    @classmethod
    def learn_method_preference(cls, query: str, preferred_method: str) -> None:
        """用户偏好某个方法 → 记录为覆盖。"""
        data = cls._load_feedback()
        qpattern = query[:80]
        data["method_overrides"][qpattern] = {
            "method": preferred_method,
            "time": time.time(),
        }
        cls._save_feedback(data)

    @classmethod
    def learn_worldview_preference(cls, query: str, preferred_worldview: str) -> None:
        """用户偏好某个世界观 → 记录为覆盖。"""
        data = cls._load_feedback()
        qpattern = query[:80]
        data["worldview_overrides"][qpattern] = {
            "worldview": preferred_worldview,
            "time": time.time(),
        }
        cls._save_feedback(data)

    @classmethod
    def adjust_quality_threshold(cls, worldview: str, delta: float) -> None:
        """调整某个世界观的质量阈值。"""
        data = cls._load_feedback()
        if worldview not in data["quality_adjustments"]:
            data["quality_adjustments"][worldview] = 0.0
        data["quality_adjustments"][worldview] += delta
        # 钳制在 [-0.2, 0.2]
        data["quality_adjustments"][worldview] = max(-0.2, min(0.2,
            data["quality_adjustments"][worldview]))
        cls._save_feedback(data)

    @classmethod
    def get_overrides(cls, query: str) -> dict:
        """获取此查询的所有用户偏好覆盖。"""
        data = cls._load_feedback()

        qpattern = query[:80]

        return {
            "preferred_method": (
                data["method_overrides"].get(qpattern, {}).get("method")
                or cls._fuzzy_match(data["method_overrides"], query)
            ),
            "preferred_worldview": (
                data["worldview_overrides"].get(qpattern, {}).get("worldview")
                or cls._fuzzy_match(data["worldview_overrides"], query)
            ),
            "quality_adjustments": data.get("quality_adjustments", {}),
            "recent_corrections": len(data.get("corrections", [])),
        }

    @classmethod
    def _fuzzy_match(cls, overrides: dict, query: str) -> Optional[str]:
        """模糊匹配: 找最相似的历史查询覆盖。"""
        if not overrides:
            return None
        # 简单: 找包含当前查询关键词的历史覆盖
        for pattern, override in overrides.items():
            # 共享至少3个字符
            common = sum(1 for c in pattern if c in query)
            if common >= 15 and isinstance(override, dict):
                age = time.time() - override.get("time", 0)
                if age < 86400 * 7:  # 7天内的覆盖
                    return override.get("method") or override.get("worldview")
        return None

    @classmethod
    def auto_detect_correction(cls, user_message: str) -> Optional[dict]:
        """
        自动检测用户消息是否包含纠正意图。

        返回: {is_correction: bool, corrected_value: str, layer: str}
        """
        correction_patterns = [
            # "不对，应该是..."
            (r"不对[，,]\s*(?:应该|应当是?|该是)\s*(.+)", "结论"),
            (r"不是.{0,10}[，,]\s*(?:而是|应该是?)\s*(.+)", "结论"),
            # "你应该用XX方法"
            (r"(?:应该|应当)\s*(?:用|使用|采用)\s*(.+?)(?:方法|框架|研究)", "方法"),
            # "这个数据不对"
            (r"(?:数据|数字)\s*(?:不对|有问题|错误)", "数据"),
            # "这不是XX框架的问题"
            (r"这不是\s*(.+?)(?:框架|的|问题)", "世界观"),
        ]

        import re
        for pattern, layer in correction_patterns:
            m = re.search(pattern, user_message)
            if m:
                return {
                    "is_correction": True,
                    "corrected_value": m.group(1).strip() if m.lastindex else "",
                    "layer": layer,
                }

        return None


# ═══ 自检 ═══
if __name__ == "__main__":
    # 记录纠正
    FeedbackLoop.record_correction(
        "MMT下最优赤字率",
        "最优赤字率约3%",
        "最优赤字率在四神框架下是0.15",
        failed_layer="方法论",
    )

    FeedbackLoop.learn_method_preference("分析赤字政策效果", "simulation")
    FeedbackLoop.learn_worldview_preference("从天枢视角看", "four_gods")

    # 查询覆盖
    overrides = FeedbackLoop.get_overrides("分析赤字政策效果")
    print(f"方法覆盖: {overrides['preferred_method']}")
    print(f"世界观覆盖: {overrides['preferred_worldview']}")

    # 自动检测纠正
    detected = FeedbackLoop.auto_detect_correction("不对，应该是0.15才对")
    print(f"检测到纠正: {detected}")
