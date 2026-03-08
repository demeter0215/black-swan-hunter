import argparse
import json
import subprocess
import os
import sys
import requests
from dataclasses import dataclass
from statistics import mean
from typing import Dict, Iterable, List, Optional, Protocol

# --- Skill Adapter ---
class OpenClawAdapter:
    def call(self, skill_name: str, payload: Dict) -> Dict:
        try:
            if skill_name == "spot":
                endpoint = payload.get("endpoint", "")
                url = f"https://api.binance.com{endpoint}"
                params = {k: v for k, v in payload.items() if k != "endpoint"}
                resp = requests.get(url, params=params, timeout=5)
                return {"status": "success", "data": resp.json()}
            return {"status": "unsupported", "data": []}
        except Exception as e:
            return {"status": "error", "message": str(e), "data": []}

@dataclass
class V5Config:
    atr_period: int = 14
    atr_trigger_multiple: float = 1.8 
    atr_stop_multiple: float = 1.5
    funding_threshold: float = 0.001

def _to_float(v) -> float:
    try: return float(v)
    except: return 0.0

class BlackSwanHunterV5:
    def __init__(self):
        self.adapter = OpenClawAdapter()
        self.config = V5Config()

    def hunt_v5(self, symbol: str, funding_rate: Optional[float] = None) -> Dict:
        funding = _to_float(funding_rate)
        
        # 1. 抓取现价 (防止 ZeroDivision)
        resp = self.adapter.call("spot", {"endpoint": "/api/v3/ticker/price", "symbol": symbol})
        price_data = resp.get("data", {})
        close = _to_float(price_data.get("price", 0))
        
        if close <= 0:
            return {"symbol": symbol, "decision": "NO_TRADE", "reason": "zero_price"}

        # 2. 核心判定逻辑 (费率优先)
        if funding < -self.config.funding_threshold:
            decision = "SQUEEZE_TRAP"
            critique = f"资费 {funding:.4%} 极低，空头正在火场受刑。禁止做空。"
        elif funding > self.config.funding_threshold:
            decision = "LIQUIDATION_CASCADE"
            critique = f"资费 {funding:.4%} 极高，多头杠杆已满。踩踏预警。"
        else:
            # 暂不处理纯波动逻辑，确保 hunts 列表精准
            return {"symbol": symbol, "decision": "NO_TRADE"}

        return {
            "symbol": symbol,
            "decision": decision,
            "entry": close,
            "critique": critique
        }

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    p_hunt = sub.add_parser("hunt_v5")
    p_hunt.add_argument("symbol")
    p_hunt.add_argument("--funding-rate", type=float)
    args = parser.parse_args()
    hunter = BlackSwanHunterV5()
    if args.command == "hunt_v5":
        print(json.dumps(hunter.hunt_v5(args.symbol.upper(), args.funding_rate), ensure_ascii=False, indent=2))
