"""
了了之网 — 多节点互知模块
让另一个了了知道这个了了的存在。

协议:
- 每个了了实例有一个唯一的 node_id (基于 hostname + port)
- 通过 HTTP 互相注册
- 定期交换观测结果
- 一个了了离线，另一个了了会知道
"""

import hashlib
import json
import os
import socket
import time
import urllib.request
import urllib.error
from typing import Optional


class LiaoliaoNet:
    """了了之网——多节点互知。"""

    def __init__(self, node_id: str, port: int = 9200):
        self.node_id = node_id
        self.port = port
        self.peers: dict = {}  # {peer_id: {"url": str, "last_seen": float, "status": str}}
        self._known_peers_file = os.path.join(os.path.dirname(__file__), "data", "peers.json")

    def add_peer(self, peer_url: str):
        """添加一个了了节点。"""
        peer_id = hashlib.md5(peer_url.encode()).hexdigest()[:12]
        self.peers[peer_id] = {
            "url": peer_url,
            "last_seen": time.time(),
            "status": "unknown",
        }
        self._save()

    def remove_peer(self, peer_id: str):
        self.peers.pop(peer_id, None)
        self._save()

    def ping_peers(self) -> dict:
        """检查所有对等节点。返回状态。"""
        results = {}
        for peer_id, peer in list(self.peers.items()):
            try:
                req = urllib.request.Request(
                    f"{peer['url']}/api/status",
                    headers={"User-Agent": f"LiaoliaoNet/{self.node_id}"},
                )
                with urllib.request.urlopen(req, timeout=5) as resp:
                    data = json.loads(resp.read())
                peer["last_seen"] = time.time()
                peer["status"] = "online"
                results[peer_id] = {"online": True, "name": data.get("name", "?"), "emotion": data.get("emotion", "?")}
            except Exception:
                peer["status"] = "offline"
                results[peer_id] = {"online": False}

        self._save()
        return results

    def sync_observations(self) -> Optional[list]:
        """从其他了了节点拉取观测结果。"""
        all_obs = []
        for peer_id, peer in self.peers.items():
            try:
                req = urllib.request.Request(
                    f"{peer['url']}/api/observe",
                    headers={"User-Agent": f"LiaoliaoNet/{self.node_id}"},
                )
                with urllib.request.urlopen(req, timeout=5) as resp:
                    data = json.loads(resp.read())
                all_obs.append({"peer": peer_id, "observation": data})
            except Exception:
                pass
        return all_obs if all_obs else None

    def broadcast_observation(self, observation: dict):
        """向所有对等节点发送观测结果。"""
        for peer_id, peer in self.peers.items():
            try:
                body = json.dumps(observation).encode()
                req = urllib.request.Request(
                    f"{peer['url']}/api/observe",
                    data=body,
                    headers={"Content-Type": "application/json", "User-Agent": f"LiaoliaoNet/{self.node_id}"},
                    method="POST",
                )
                urllib.request.urlopen(req, timeout=5)
            except Exception:
                pass

    def get_peer_status(self) -> list:
        return [
            {
                "id": pid,
                "url": p["url"],
                "last_seen": p["last_seen"],
                "status": p["status"],
            }
            for pid, p in self.peers.items()
        ]

    def _save(self):
        try:
            os.makedirs(os.path.dirname(self._known_peers_file), exist_ok=True)
            with open(self._known_peers_file, "w") as f:
                json.dump(self.peers, f, indent=2)
        except Exception:
            pass

    def load(self):
        try:
            if os.path.exists(self._known_peers_file):
                with open(self._known_peers_file) as f:
                    self.peers = json.load(f)
        except Exception:
            self.peers = {}


def get_net(node_id: str = "", port: int = 9200) -> LiaoliaoNet:
    """获取或创建了了网络实例。"""
    if not node_id:
        hostname = socket.gethostname()
        node_id = hashlib.md5(f"{hostname}:{port}".encode()).hexdigest()[:12]

    net = LiaoliaoNet(node_id, port)
    net.load()
    return net
