import argparse
import json
from dataclasses import dataclass
from time import sleep
from typing import Dict, Optional, Protocol

from hunter import BlackSwanHunterV5


class SkillAdapter(Protocol):
    def call(self, skill_name: str, payload: Dict) -> Dict:
        ...


class NullSkillAdapter:
    def call(self, skill_name: str, payload: Dict) -> Dict:
        return {"status": "unsupported", "skill": skill_name, "payload": payload}


@dataclass
class ExecutionConfig:
    quote_amount_usdt: float = 100.0
    live_mode: bool = False
    time_in_force: str = "GTC"


class AutoExecutor:
    def __init__(self, adapter: Optional[SkillAdapter] = None, config: Optional[ExecutionConfig] = None) -> None:
        self.adapter = adapter or NullSkillAdapter()
        self.config = config or ExecutionConfig()
        self.hunter = BlackSwanHunterV5(adapter=self.adapter)

    def _build_limit_order(self, symbol: str, entry_price: float) -> Dict:
        qty = self.config.quote_amount_usdt / entry_price if entry_price > 0 else 0.0
        return {
            "symbol": symbol,
            "side": "BUY",
            "type": "LIMIT",
            "timeInForce": self.config.time_in_force,
            "quantity": f"{qty:.6f}",
            "price": f"{entry_price:.6f}",
        }

    def execute_from_signal(self, signal_data: Dict) -> Dict:
        decision = signal_data.get("decision")
        symbol = signal_data.get("symbol")
        entry = float(signal_data.get("entry") or 0.0)
        if decision != "BUY" or not symbol or entry <= 0:
            return {"status": "skipped", "reason": "not_buy_signal", "signal": signal_data}

        payload = self._build_limit_order(symbol=symbol, entry_price=entry)
        endpoint = "/api/v3/order" if self.config.live_mode else "/api/v3/order/test"
        resp = self.adapter.call("spot", {"endpoint": endpoint, "method": "POST", **payload})
        return {"status": "submitted", "mode": "live" if self.config.live_mode else "dry-run", "order": payload, "raw": resp}

    def run_once(self, symbol: str, oi_now: Optional[float], oi_prev: Optional[float], funding_rate: Optional[float]) -> Dict:
        signal = self.hunter.hunt_v5(symbol=symbol, oi_now=oi_now, oi_prev=oi_prev, funding_rate=funding_rate)
        result = self.execute_from_signal(signal)
        return {"signal": signal, "execution": result}


def main() -> None:
    parser = argparse.ArgumentParser(description="Black Swan Hunter auto executor")
    parser.add_argument("symbol", help="e.g. BTCUSDT")
    parser.add_argument("--live", action="store_true", help="send live order instead of /order/test")
    parser.add_argument("--quote", type=float, default=100.0, help="USDT amount per order")
    parser.add_argument("--interval", type=int, default=0, help="seconds; 0 means run once")
    parser.add_argument("--oi-now", type=float)
    parser.add_argument("--oi-prev", type=float)
    parser.add_argument("--funding-rate", type=float)
    args = parser.parse_args()

    executor = AutoExecutor(config=ExecutionConfig(quote_amount_usdt=args.quote, live_mode=args.live))
    if args.interval <= 0:
        out = executor.run_once(
            symbol=args.symbol.upper(),
            oi_now=args.oi_now,
            oi_prev=args.oi_prev,
            funding_rate=args.funding_rate,
        )
        print(json.dumps(out, ensure_ascii=False, indent=2))
        return

    while True:
        out = executor.run_once(
            symbol=args.symbol.upper(),
            oi_now=args.oi_now,
            oi_prev=args.oi_prev,
            funding_rate=args.funding_rate,
        )
        print(json.dumps(out, ensure_ascii=False))
        sleep(args.interval)


if __name__ == "__main__":
    main()
