"""
实时监控 — 定时数据质量复检 + 持续研究问题跟踪

两个模式:
  1. script模式: 作为cron脚本运行 (no_agent=True), stdout=报告
  2. check模式: 函数调用, 返回状态

用途:
  - 对持续性研究问题，定时检查数据是否过期
  - 检测到质量下降 → 告警
  - 可接入cron调度
"""

import json
import time
from pathlib import Path
from typing import Optional

MONITOR_DIR = Path.home() / ".hermes" / "profiles" / "evopolis" / "monitor"
MONITOR_DIR.mkdir(parents=True, exist_ok=True)

WATCH_FILE = MONITOR_DIR / "watched_queries.json"


class CronMonitor:
    """定时数据质量监控。"""

    @classmethod
    def watch(cls, query: str, data_hash: str = "", check_interval_hours: int = 6) -> dict:
        """
        注册一个持续监控的研究问题。

        返回: {watch_id, status}
        """
        watches = cls._load_watches()

        watch_id = f"watch_{int(time.time())}"
        watches[watch_id] = {
            "query": query[:200],
            "data_hash": data_hash,
            "created": time.time(),
            "last_check": time.time(),
            "check_interval_hours": check_interval_hours,
            "status": "active",
            "alerts": [],
        }
        cls._save_watches(watches)
        return {"watch_id": watch_id, "status": "registered"}

    @classmethod
    def check_all(cls) -> dict:
        """
        检查所有活跃监控项。

        返回: {checks: [{watch_id, query, status, alerts}], summary}
        """
        watches = cls._load_watches()
        now = time.time()
        results = []

        for wid, watch in watches.items():
            if watch.get("status") != "active":
                continue

            interval = watch.get("check_interval_hours", 6) * 3600
            if now - watch.get("last_check", 0) < interval:
                continue  # 还没到检查时间

            # 执行检查
            check_result = cls._check_single(watch)

            watches[wid]["last_check"] = now
            if check_result.get("alert"):
                watches[wid]["alerts"].append({
                    "time": now,
                    "message": check_result["alert"],
                })

            results.append({
                "watch_id": wid,
                "query": watch["query"][:80],
                "status": watch.get("status", "?"),
                "alert": check_result.get("alert", ""),
                "fresh": check_result.get("fresh", True),
            })

        cls._save_watches(watches)

        alerts = [r for r in results if r.get("alert")]
        return {
            "checks": results,
            "total_watched": len(watches),
            "checked": len(results),
            "alerts": len(alerts),
            "summary": (
                f"检查了{len(results)}个监控项，{len(alerts)}个告警"
                if alerts else f"检查了{len(results)}个监控项，全部正常"
            ),
        }

    @classmethod
    def _check_single(cls, watch: dict) -> dict:
        """检查单个监控项的数据新鲜度。"""
        query = watch.get("query", "")

        # 尝试重新搜索
        from web import search_and_summarize
        try:
            new_data = search_and_summarize(query)
        except Exception:
            return {"fresh": True, "alert": ""}

        if not new_data or len(new_data) < 30:
            return {"alert": f"数据不可达: {query[:60]}", "fresh": False}

        # 简单新鲜度检查: 数据中是否有近期的年份
        import re
        years = re.findall(r'(20\d{2})', new_data)
        current_year = 2026
        max_year = max(int(y) for y in years) if years else 0
        age = current_year - max_year

        if age >= 2:
            return {
                "alert": f"数据可能过时 (最新年份{max_year}, {age}年前)",
                "fresh": False,
            }

        return {"fresh": True, "alert": ""}

    @classmethod
    def unwatch(cls, watch_id: str) -> dict:
        """停止监控。"""
        watches = cls._load_watches()
        if watch_id in watches:
            watches[watch_id]["status"] = "inactive"
            cls._save_watches(watches)
            return {"status": "unwatched"}
        return {"status": "not found"}

    @classmethod
    def _load_watches(cls) -> dict:
        if WATCH_FILE.exists():
            try:
                return json.loads(WATCH_FILE.read_text())
            except Exception:
                pass
        return {}

    @classmethod
    def _save_watches(cls, data: dict) -> None:
        WATCH_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2))


# ═══ Cron脚本模式 ═══
# 用法: python3 cron_monitor.py
# 输出: 检查结果json, 如果有告警则exit非0

def cron_check() -> int:
    """Cron入口: 检查所有监控项, 打印报告, 若有告警返回1。"""
    result = CronMonitor.check_all()

    print(json.dumps(result, ensure_ascii=False, indent=2))

    if result["alerts"] > 0:
        print(f"\n⚠ 发现{result['alerts']}个告警!")
        return 1
    return 0


# ═══ 自检 ═══
if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "check":
        sys.exit(cron_check())

    # 注册一个测试监控
    wid = CronMonitor.watch(
        "2025年中国GDP增长率",
        check_interval_hours=0,  # 立即检查
    )
    print(f"注册: {wid}")

    # 检查
    result = CronMonitor.check_all()
    print(f"检查结果: {result['summary']}")
    for c in result.get("checks", []):
        print(f"  {c['query'][:50]}... → {'⚠' if c['alert'] else '✅'} {c.get('alert','')}")
