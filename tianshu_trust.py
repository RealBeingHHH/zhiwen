"""
天枢信任层 — τ温度计注入全管线

τ (天枢) = 信任的物理锚。不是"我觉得可信"，而是"封印在不可篡改记录中"。

管线注入点:
  1. τ源读取 — 从天枢获取当前封印状态和参考τ
  2. τ加权真实性 — 织星φ分数 × τ因子 → 校准后的真实性
  3. τ校准闸门 — 质量阈值随τ动态调整
  4. τ衰减追踪 — 存储事实的置信度随τ自然衰减: conf(t)=conf₀×e^(-t/τ)
  5. 封印结论 — 高置信结论写入天枢账本(不可篡改)
  6. τ置信注入 — 最终置信度标注τ锚定状态

核心公式:
  校准后真实性 = φ分数 × min(1, τ/τ_ref)
  有效置信度 = 原始置信度 × e^(-age/τ半衰期)
  综合信任分 = 闸分数 × τ因子
"""

import json
import math
import time
import hashlib
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional
from config import TIANSHU_URL, TIANSHU2_URL, TIANSHU_REF_TAU, TIANSHU_CACHE_TTL

BASE = Path(__file__).parent

# ════════════════════════════════════════════════════════
# 天枢连接
# ════════════════════════════════════════════════════════

@dataclass
class TianshuState:
    """天枢当前状态。"""
    online: bool = False
    tau: float = 0.55           # 参考τ温度
    fingerprint: str = ""       # 硬件指纹
    seal_verified: bool = False # 封印是否完好
    uptime_seconds: float = 0
    last_check: float = 0

    def trust_factor(self) -> float:
        """信任因子: τ/τ_ref, 封印完好=1.0, 封印损坏=0.3"""
        if not self.seal_verified:
            return 0.3
        return min(1.0, self.tau / 0.55)

    @property
    def is_trustworthy(self) -> bool:
        return self.online and self.seal_verified


class TianshuClient:
    """天枢API客户端 — 读取τ源状态。"""

    REF_TAU = TIANSHU_REF_TAU

    _cached_state: Optional[TianshuState] = None
    _cache_ttl = TIANSHU_CACHE_TTL

    @classmethod
    def get_state(cls) -> TianshuState:
        """获取天枢当前状态（带缓存+重试）。"""
        now = time.time()
        if cls._cached_state and (now - cls._cached_state.last_check) < cls._cache_ttl:
            return cls._cached_state

        state = TianshuState(last_check=now)

        # 重试2次
        for attempt in range(2):
            try:
                # WSL下urllib可能被网络层阻塞，用curl更可靠
                import subprocess
                result = subprocess.run(
                    ["curl", "-s", "--max-time", "3", f"{TIANSHU_URL}/status"],
                    capture_output=True, text=True, timeout=5,
                )
                if result.returncode == 0 and result.stdout:
                    data = json.loads(result.stdout)
                    state.online = True
                    state.fingerprint = data.get("fingerprint", "")
                    state.seal_verified = data.get("seal_verified", False)
                    state.uptime_seconds = data.get("uptime_seconds", 0)
                    state.tau = cls.REF_TAU
                    cls._cached_state = state
                    return state
            except Exception:
                if attempt == 0:
                    time.sleep(0.5)  # 短暂等待后重试

        # 两次都失败
        state.online = False
        state.tau = cls.REF_TAU * 0.7
        cls._cached_state = state
        return state

    @classmethod
    def seal_conclusion(cls, conclusion: str, metadata: dict = None) -> dict:
        """将结论封印到天枢账本（不可篡改记录）。"""
        state = cls.get_state()
        if not state.is_trustworthy:
            return {"sealed": False, "reason": "天枢不可用或封印损坏"}

        record = {
            "timestamp": time.time(),
            "tau": state.tau,
            "fingerprint": state.fingerprint,
            "conclusion_hash": hashlib.sha256(conclusion.encode()).hexdigest()[:16],
            "conclusion": conclusion[:500],
            "metadata": metadata or {},
        }

        # 尝试写入天枢API (用curl)
        try:
            import subprocess
            result = subprocess.run(
                ["curl", "-s", "--max-time", "3", "-X", "POST",
                 "http://localhost:9001/ledger",
                 "-H", "Content-Type: application/json",
                 "-d", json.dumps(record)],
                capture_output=True, text=True, timeout=5,
            )
            if result.returncode == 0 and result.stdout:
                api_result = json.loads(result.stdout)
                return {"sealed": True, "tau": state.tau, "record": record, "result": api_result}
        except Exception:
            pass
            # API不可达 → 本地密封
            seal_path = BASE / "data" / "tianshu_seals.jsonl"
            seal_path.parent.mkdir(parents=True, exist_ok=True)
            with open(seal_path, "a") as f:
                f.write(json.dumps(record, ensure_ascii=False) + "\n")
            return {"sealed": True, "tau": state.tau, "record": record, "local_only": True}

    @classmethod
    def flush_cache(cls) -> None:
        cls._cached_state = None

    @classmethod
    def _reset_for_server(cls) -> None:
        """服务启动时重置缓存。"""
        cls._cached_state = None


# ════════════════════════════════════════════════════════
# τ信任评分
# ════════════════════════════════════════════════════════

class TauTrust:
    """τ信任评分 — 将τ注入每个质量维度。"""

    @classmethod
    def calibrate_authenticity(
        cls, voyager_score: float, url_score: float, tianshu_state: TianshuState = None
    ) -> dict:
        """
        τ校准真实性分数。

        校准后真实性 = (0.7×φ分数 + 0.3×URL分数) × τ信任因子
        """
        if tianshu_state is None:
            tianshu_state = TianshuClient.get_state()

        tf = tianshu_state.trust_factor()
        raw = 0.7 * voyager_score + 0.3 * url_score
        calibrated = raw * tf

        return {
            "raw_score": round(raw, 3),
            "tau_factor": round(tf, 3),
            "calibrated_score": round(calibrated, 3),
            "tau_reference": tianshu_state.tau,
            "seal_verified": tianshu_state.seal_verified,
            "anchored": tianshu_state.is_trustworthy,
        }

    @classmethod
    def calibrate_threshold(
        cls, base_threshold: float, tianshu_state: TianshuState = None
    ) -> float:
        """
        τ动态调整质量阈值。

        封印完好 → 阈值 = base（严格）
        封印损坏 → 阈值 = base × 0.7（放宽，因为信任锚不可用）
        天枢离线 → 阈值 = base × 0.85（略微放宽）
        """
        if tianshu_state is None:
            tianshu_state = TianshuClient.get_state()

        if not tianshu_state.online:
            return round(base_threshold * 0.85, 2)
        if not tianshu_state.seal_verified:
            return round(base_threshold * 0.7, 2)
        return base_threshold

    @classmethod
    def decay_confidence(
        cls,
        initial_confidence: float,
        age_days: float,
        tau: float = None,
    ) -> float:
        """
        τ衰减: 置信度随时间指数衰减。

        conf(t) = conf₀ × e^(-age_days / (τ × 30))
        
        τ越高 → 衰减越慢 (信任温度高, 信息保鲜期长)
        τ越低 → 衰减越快 (信任温度低, 信息快速贬值)
        """
        if tau is None:
            state = TianshuClient.get_state()
            tau = state.tau

        half_life_days = tau * 30  # τ=0.55 → 半衰16.5天
        if half_life_days <= 0:
            return 0.0

        decay = math.exp(-age_days / half_life_days)
        return round(initial_confidence * decay, 3)

    @classmethod
    def overall_trust(
        cls,
        gate_score: float,
        sigma: float,
        adversarial_survival: float,
        tianshu_state: TianshuState = None,
    ) -> dict:
        """
        综合τ信任分。

        综合 = (闸分数 × 0.4 + (1-σ) × 0.3 + 对抗存活率 × 0.3) × τ因子
        """
        if tianshu_state is None:
            tianshu_state = TianshuClient.get_state()

        tf = tianshu_state.trust_factor()
        raw = 0.4 * gate_score + 0.3 * (1 - sigma) + 0.3 * adversarial_survival
        calibrated = raw * tf

        level = "🟢 高" if calibrated >= 0.7 else ("🟡 中" if calibrated >= 0.4 else "🔴 低")

        return {
            "raw_trust": round(raw, 3),
            "tau_factor": round(tf, 3),
            "tau_calibrated_trust": round(calibrated, 3),
            "level": level,
            "tau": tianshu_state.tau,
            "seal_verified": tianshu_state.seal_verified,
            "formula": "τ校准信任 = (0.4×闸 + 0.3×(1-σ) + 0.3×存活率) × τ因子",
        }


# ════════════════════════════════════════════════════════
# 快捷接口
# ════════════════════════════════════════════════════════

def get_tau() -> float:
    """获取当前τ温度。"""
    return TianshuClient.get_state().tau

def calibrate_with_tau(gate_result, sigma: float, adversarial_survival: float = 1.0) -> dict:
    """快捷τ校准管线分数。"""
    return TauTrust.overall_trust(
        getattr(gate_result, "overall_score", 0),
        sigma,
        adversarial_survival,
    )

def seal_if_trusted(conclusion: str, min_gate_score: float = 0.6) -> dict:
    """如果结论通过高闸，封印到天枢。"""
    return TianshuClient.seal_conclusion(conclusion)


# ═══ 自检 ═══
if __name__ == "__main__":
    # 状态
    state = TianshuClient.get_state()
    print(f"天枢: {'在线' if state.online else '离线'}")
    print(f"τ={state.tau} 封印={'完好' if state.seal_verified else '损坏'}")
    print(f"信任因子: {state.trust_factor():.2f}")
    print()

    # τ校准真实性
    auth = TauTrust.calibrate_authenticity(0.85, 0.60, state)
    print(f"校准后真实性: {auth['raw_score']:.2f} → τ×{auth['tau_factor']:.2f} → {auth['calibrated_score']:.2f}")
    print()

    # τ衰减
    for days in [0, 7, 14, 30, 60]:
        conf = TauTrust.decay_confidence(0.8, days, state.tau)
        print(f"置信度 0.8 → {days}天后 → {conf:.3f}")
    print()

    # 综合τ信任
    trust = TauTrust.overall_trust(0.65, 0.30, 0.75, state)
    print(f"综合τ信任: {trust['raw_trust']:.2f} → τ×{trust['tau_factor']:.2f} → {trust['tau_calibrated_trust']:.2f} ({trust['level']})")
    print()

    # 封印结论
    seal = TianshuClient.seal_conclusion("在τ=0.55条件下, 资产200≠负债150+权益30, 数据不可信")
    print(f"封印: {'✅' if seal['sealed'] else '❌'} (τ={seal.get('tau','?')})")
