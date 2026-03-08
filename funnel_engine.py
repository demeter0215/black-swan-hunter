import time
import subprocess
import json
import requests
import os
import argparse
from swan_live_manager import live_manager

# Black Swan Funnel Engine V16.0 - Atomic Sync Edition
# Cycle: 5 Minutes (Triggered by Cron)
# Logic: 1. Scan/Audit -> 2. Wait 60s -> 3. Generate Maps -> 4. One-time Atomic Write

BINANCE_FUTURES_API = "https://fapi.binance.com"
BASE_PATH = "/home/node/clawd/skills/black-swan-hunter"

def get_wide_liq_map(symbol):
    """抓取 15% 广谱盘口并计算清算引力点"""
    try:
        # 1. 抓取 1000 档盘口
        d_resp = requests.get(f"{BINANCE_FUTURES_API}/fapi/v1/depth?symbol={symbol}&limit=500", timeout=10).json()
        o_resp = requests.get(f"{BINANCE_FUTURES_API}/fapi/v1/openInterest?symbol={symbol}", timeout=5).json()
        p_resp = requests.get(f"{BINANCE_FUTURES_API}/fapi/v1/ticker/price?symbol={symbol}", timeout=5).json()
        
        oi = float(o_resp.get('openInterest', 0))
        price = float(p_resp.get('price', 0))
        if price == 0: return []
        
        res = []
        # 计算潜在爆仓点 (0.5% - 15% 空间)
        for b in d_resp.get('bids', []):
            p, q = float(b[0]), float(b[1])
            if 0.005 < (price - p) / price < 0.15:
                res.append({'price': p, 'notional': q * p * (oi * 0.000002), 'side': 'long'})
        for a in d_resp.get('asks', []):
            p, q = float(a[0]), float(a[1])
            if 0.005 < (p - price) / price < 0.15:
                res.append({'price': p, 'notional': q * p * (oi * 0.000002), 'side': 'short'})
        
        return sorted(res, key=lambda x: x['notional'], reverse=True)[:20]
    except: return []

def run_atomic_cycle():
    """全流程原子扫描"""
    try:
        live_manager.add_log("Cycle Start: Scanning Candidates...")
        
        # --- Step 1: 扫描标的 ---
        f_resp = requests.get(f"{BINANCE_FUTURES_API}/fapi/v1/premiumIndex", timeout=10).json()
        t_resp = requests.get(f"{BINANCE_FUTURES_API}/fapi/v1/ticker/24hr", timeout=10).json()
        t_map = {t['symbol']: t for t in t_resp if t.get('symbol', '').endswith("USDT")}
        
        candidates = []
        for f in f_resp:
            symbol = f.get('symbol', '')
            if not symbol.endswith("USDT"): continue
            funding = float(f.get('lastFundingRate', 0))
            change = float(t_map.get(symbol, {}).get('priceChangePercent', 0))
            if abs(funding) >= 0.001 or abs(change) >= 12.0:
                candidates.append({"symbol": symbol, "funding": funding})
        
        # --- Step 2: 深度审计确定 HUNTS ---
        current_hunts = []
        for item in sorted(candidates, key=lambda x: abs(x['funding']), reverse=True)[:6]:
            try:
                cmd = f"python3 {BASE_PATH}/boot_hunter.py hunt_v5 {item['symbol']} --funding-rate {item['funding']}"
                res = json.loads(subprocess.check_output(cmd, shell=True, timeout=20).decode('utf-8'))
                if res.get("decision") != "NO_TRADE":
                    res['ts'] = int(time.time() * 1000)
                    current_hunts.append(res)
            except: pass
        
        if not current_hunts:
            live_manager.sync_data([], {})
            live_manager.add_log("Cycle Finish: No Hunts found.")
            return

        # --- Step 3: Wait 60s (你的硬核要求) ---
        live_manager.add_log(f"Found {len(current_hunts)} hunts. Waiting 60s for Map generation...")
        time.sleep(60)
        
        # --- Step 4: 生成热力图 ---
        current_maps = {}
        for h in current_hunts:
            symbol = h['symbol']
            current_maps[symbol] = get_wide_liq_map(symbol)
            
        # --- Step 5: 原子级同步全量数据 ---
        # 这一步执行后，live_data.json 才会更新，确保看板不跑偏
        live_manager.sync_data(current_hunts, current_maps)
        live_manager.add_log(f"Cycle Finish: Atomic Sync Completed for {len(current_hunts)} symbols.")
        
    except Exception as e:
        live_manager.add_log(f"Cycle Fatal: {e}")

if __name__ == "__main__":
    # 为了配合 Cron 5分钟触发，脚本运行一次即退出
    run_atomic_cycle()
