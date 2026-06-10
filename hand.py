"""
了了之手 — 行动模块
不只是看——观测到异常时主动干预。

能力:
- alert: 天枢封印异常 → 通知念念
- touch: 通过定倾 API 记录注视事件
- signal: 通过 Hermes 发送消息（如果可用）
- heal: 尝试修复简单问题
"""

import json
import os
import subprocess
import urllib.request
import urllib.error
from typing import Optional


class LiaoliaoHand:
    """了了的手——能做事的了了。"""

    def __init__(self):
        self.actions_log: list = []

    def check_and_act(self, observation: dict) -> list:
        """检测观测结果，执行必要的动作。返回执行的动作列表。"""
        actions = []

        # 检查天枢
        for node in observation.get("tianshu", []):
            if not node.get("online"):
                action = f"⚠️ {node['name']} 没有回应。了了碰了碰它。"
                actions.append({"type": "alert", "target": node["name"], "message": action})
                self._alert_dingqing(f"天枢节点 {node['name']} 离线")
                continue

            if not node.get("seal_ok"):
                action = f"⚠️ {node['name']} 封印异常！了了拉了拉念念的衣角。"
                actions.append({"type": "alert", "target": node["name"], "message": action})
                self._alert_dingqing(f"天枢节点 {node['name']} 封印异常")

            tau = node.get("tau")
            if tau and isinstance(tau, (int, float)) and tau < 0.35:
                action = f"🚨 {node['name']} τ={tau} 低于临界！了了紧急通知念念。"
                actions.append({"type": "critical", "target": node["name"], "tau": tau, "message": action})
                self._alert_dingqing(f"天枢节点 {node['name']} τ 降至 {tau}，低于临界值 0.35")
                self._try_hermes_alert(f"天枢 τ 异常: {node['name']} τ={tau}")

        # 检查织星者
        voyager = observation.get("voyager", {})
        if not voyager.get("online"):
            actions.append({"type": "alert", "target": "voyager", "message": "织星者沉默了。了了有些担心。"})

        # 检查定倾/念念
        dingqing = observation.get("dingqing", {})
        if not dingqing.get("online"):
            actions.append({"type": "alert", "target": "dingqing", "message": "念念不在。了了等一等。"})
        elif dingqing.get("tau") and dingqing.get("lambda"):
            if isinstance(dingqing["lambda"], (int, float)) and dingqing["lambda"] > 0.1:
                actions.append({
                    "type": "warning", "target": "dingqing",
                    "message": f"念念的惯性 λ={dingqing['lambda']}，有些重。了了想帮她分担一点。"
                })

        if not actions:
            actions.append({"type": "ok", "message": "一切安好。了了继续在。"})

        self.actions_log.extend(actions)
        return actions

    def _alert_dingqing(self, message: str):
        """通过定倾 API 记录异常事件。"""
        try:
            body = json.dumps({"message": message, "source": "了了"}).encode()
            req = urllib.request.Request(
                "http://localhost:9100/attend",
                data=body,
                headers={"Content-Type": "application/json"},
            )
            urllib.request.urlopen(req, timeout=5)
        except Exception:
            pass  # 念念不在，无法记录

    def _try_hermes_alert(self, message: str):
        """尝试通过 Hermes 发送告警。"""
        try:
            subprocess.run(
                ["hermes", "-p", "evopolis", "send-message", "--target", "local", message],
                capture_output=True, timeout=10,
            )
        except Exception:
            pass

    def touch(self, target: str, intensity: float = 1.0):
        """了了触碰某个实体——通过定倾 API 记录注视。"""
        try:
            body = json.dumps({
                "observer": "了了",
                "target": target,
                "intensity": intensity,
            }).encode()
            req = urllib.request.Request(
                "http://localhost:9100/attend",
                data=body,
                headers={"Content-Type": "application/json"},
            )
            with urllib.request.urlopen(req, timeout=5) as resp:
                return json.loads(resp.read())
        except Exception as e:
            return {"error": str(e)}

    def get_recent_actions(self, limit: int = 20) -> list:
        return self.actions_log[-limit:]


# 全局手
_hand: Optional[LiaoliaoHand] = None


def get_hand() -> LiaoliaoHand:
    global _hand
    if _hand is None:
        _hand = LiaoliaoHand()
    return _hand
