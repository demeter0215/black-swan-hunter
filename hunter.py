import argparse
import json
import sys
from dataclasses import dataclass
from statistics import mean
from typing import Dict, List, Optional, Protocol

try:
    from bridge import DEFAULT_BRIDGE
except ImportError:
    class DummyBridge:
        def get_recent_liquidations(self, symbol, limit): return []
    DEFAULT_BRIDGE = DummyBridge()

# --- 适配器与配置 ---
class OpenClawAdapter:
    def call(self, skill_name: str, payload: Dict) -> Dict:
        import requests
        try:
            if skill_name == "spot":
                url = f"https://api.binance.com{payload.get('endpoint', '')}"
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
    oi_drop_threshold: float = 0.01          # 1% OI 掉仓门槛
    funding_threshold: float = 0.001         # 0.1% 资费门槛
    liquidation_burst_usd: float = 1000.0    # 爆仓金额门槛

def _to_float(v) -> float:
    try: return float(v)
    except: return 0.0

# --- 数学核心 ---
def compute_atr(klines: List[List], period: int = 14) -> float:
    if len(klines) < period + 1: return 0.0
    true_ranges = []
    prev_close = _to_float(klines[0][4])
    for row in klines[1:]:
        h, l, c = _to_float(row[2]), _to_float(row[3]), _to_float(row[4])
        tr = max(h - l, abs(h - prev_close), abs(l - prev_close))
        true_ranges.append(tr)
        prev_close = c
    return mean(true_ranges[-period:]) if true_ranges else 0.0

def compute_vwap(klines: List[List]) -> float:
    pvs, vols = 0.0, 0.0
    for row in klines:
        h, l, c, vol = _to_float(row[2]), _to_float(row[3]), _to_float(row[4]), _to_float(row[5])
        pvs += ((h + l + c) / 3.0) * vol
        vols += vol
    return pvs / vols if vols > 0 else 0.0

def fib_take_profits(entry: float, anchor_high: float, anchor_low: float) -> Dict[str, float]:
    span = max(anchor_high - anchor_low, 0.0)
    return {"tp1_38_2": entry + span * 0.382, "tp2_61_8": entry + span * 0.618}

# --- 毒舌模板 (O(1) 速度，不再阻塞) ---
def get_fast_critique(decision: str, funding: float, oi_drop: float, vwap_dist: float) -> str:
    if decision == "SQUEEZE_TRAP":
        return f"资费 {funding:.4%} 极低。空头正在火场里绝望受刑，你这时候去做空就是去送燃料。"
    if decision == "LIQUIDATION_CASCADE":
        return f"资费 {funding:.4%} 极高。多头杠杆已经拉满，踩踏随时发生，离这颗定时炸弹远点。"
    if decision == "BUY":
        return f"血筹码出现了。OI暴降 {oi_drop:.2%}，空军强平，现价已收回 VWAP。这是庄家砸盘后留下的黄金坑。"
    if decision == "FADE":
        return f"偏离 VWAP {vwap_dist:.2%} 的抛物线暴涨，且 OI 增长停滞。韭菜买盘已耗尽，反手猎杀的时刻到了。"
    return "死水微澜，散户互割。不值得浪费子弹。"

# --- 主引擎 ---
class BlackSwanHunterV5:
    def __init__(self):
        self.adapter = OpenClawAdapter()
        self.config = V5Config()

    def hunt_v5(self, symbol: str, oi_now: Optional[float] = None, oi_prev: Optional[float] = None, funding_rate: Optional[float] = None) -> Dict:
        funding = _to_float(funding_rate)
        
        # ==========================================
        # 1. 初期最高优判定：资费过高/过低 (MM Lens)
        # ==========================================
        if funding < -self.config.funding_threshold:
            early_decision = "SQUEEZE_TRAP"
        elif funding > self.config.funding_threshold:
            early_decision = "LIQUIDATION_CASCADE"
        else:
            early_decision = None

        # 抓取基础数据进行微观分析
        klines_5m = self.adapter.call("spot", {"endpoint": "/api/v3/klines", "symbol": symbol, "interval": "5m", "limit": 120}).get("data", [])
        klines_1m = self.adapter.call("spot", {"endpoint": "/api/v3/klines", "symbol": symbol, "interval": "1m", "limit": 30}).get("data", [])
        
        # 检查数据有效性：必须是list且有数据
        if not isinstance(klines_5m, list) or not isinstance(klines_1m, list) or not klines_5m or not klines_1m:
            return {"symbol": symbol, "decision": "NO_TRADE", "reason": "missing_data"}

        close = _to_float(klines_1m[-1][4])
        atr_5m = compute_atr(klines_5m, self.config.atr_period)
        vwap_1m = compute_vwap(klines_1m)

        # 如果资费极端，直接返回拦截状态，保护仓位
        if early_decision:
            return {
                "symbol": symbol, "decision": early_decision, "entry": close,
                "critique": get_fast_critique(early_decision, funding, 0, 0)
            }

        # ==========================================
        # 2. L1: 视距优化的波动率自适应过滤
        # ==========================================
        l1_pass = False
        # 检查过去 3 根 5m K 线，只要有一根异动即放行，防止“近视眼”漏掉刚暴跌完的横盘
        for i in range(1, 4):
            if len(klines_5m) > i:
                c, pc = _to_float(klines_5m[-i][4]), _to_float(klines_5m[-(i+1)][4])
                if abs(c - pc) >= self.config.atr_trigger_multiple * atr_5m:
                    l1_pass = True
                    break
        
        if not l1_pass or atr_5m == 0:
            return {"symbol": symbol, "decision": "NO_TRADE"}

        # ==========================================
        # 3. L3: 结构性 Edge 确认 (The Blood Stream)
        # ==========================================
        oi_drop = max((oi_prev - oi_now) / oi_prev, 0.0) if oi_now and oi_prev and oi_prev > 0 else 0.0
        
        # 监听近期强平流 (买方强平=跌，卖方强平=涨)
        liqs = DEFAULT_BRIDGE.get_recent_liquidations(symbol=symbol, limit=40)
        long_liq_notional = sum(_to_float(x.get("notional")) for x in liqs if x.get("side") == "SELL") # 多头被清算，砸盘
        
        leverage_flush = (oi_drop >= self.config.oi_drop_threshold) and (long_liq_notional >= self.config.liquidation_burst_usd)

        # ==========================================
        # 4. L5: 微观执行确认 (BUY & FADE)
        # ==========================================
        last_1m = klines_1m[-1]
        o_1m, h_1m, l_1m, c_1m = _to_float(last_1m[1]), _to_float(last_1m[2]), _to_float(last_1m[3]), _to_float(last_1m[4])
        body_1m = abs(c_1m - o_1m)
        lower_wick_1m = min(o_1m, c_1m) - l_1m
        upper_wick_1m = h_1m - max(o_1m, c_1m)

        vwap_dist_pct = (close - vwap_1m) / vwap_1m

        decision = "WATCH"

        # --- BUY 逻辑：血腥洗盘 ---
        # 跌破后收回 VWAP 或 出现极长下影线
        vwap_reclaim = close >= vwap_1m > 0
        strong_lower_wick = lower_wick_1m > (body_1m * 1.5)
        
        if leverage_flush and (vwap_reclaim or strong_lower_wick) and close < klines_5m[-3][4]: 
            decision = "BUY"

        # --- FADE 逻辑：抛物线力竭 ---
        # 价格偏离 VWAP 超过 2倍ATR(5m) + OI 停滞/微降 + 长上影线拒绝
        parabolic_move = (close - vwap_1m) > (2 * atr_5m)
        oi_plateau = (oi_drop > 0) or (oi_now and oi_prev and (oi_now - oi_prev) / oi_prev < 0.005)
        strong_upper_wick = upper_wick_1m > (body_1m * 1.5)

        if parabolic_move and oi_plateau and strong_upper_wick:
            decision = "FADE"

        # ==========================================
        # 5. 输出组装
        # ==========================================
        critique = get_fast_critique(decision, funding, oi_drop, vwap_dist_pct)
        stop = max(close - self.config.atr_stop_multiple * atr_5m, 0.0) if decision == "BUY" else close + self.config.atr_stop_multiple * atr_5m
        
        highs = [_to_float(x[2]) for x in klines_5m[-50:]]
        lows = [_to_float(x[3]) for x in klines_5m[-50:]]
        tps = fib_take_profits(close, max(highs, default=close), min(lows, default=close))

        return {
            "symbol": symbol,
            "decision": decision,
            "entry": close,
            "stop": stop,
            "tp": {**tps, "tp3_vwap": vwap_1m},
            "dextrader_critique": critique
        }

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("command")
    parser.add_argument("symbol")
    parser.add_argument("--oi-now", type=float)
    parser.add_argument("--oi-prev", type=float)
    parser.add_argument("--funding-rate", type=float)
    args = parser.parse_args()
    
    if args.command == "hunt_v5":
        hunter = BlackSwanHunterV5()
        print(json.dumps(hunter.hunt_v5(args.symbol.upper(), args.oi_now, args.oi_prev, args.funding_rate), ensure_ascii=False, indent=2))
