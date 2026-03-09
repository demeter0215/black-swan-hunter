import time
import subprocess
import json
import requests
import os
import argparse
import sys
from swan_live_manager import live_manager

# Force unbuffered output
sys.stdout = os.fdopen(sys.stdout.fileno(), 'w', buffering=1)
sys.stderr = os.fdopen(sys.stderr.fileno(), 'w', buffering=1)

# Black Swan Funnel Engine V16.0 - Atomic Sync Edition
# Cycle: 5 Minutes (Triggered by Cron)
# Logic: 1. Scan/Audit -> 2. Wait 60s -> 3. Generate Maps -> 4. One-time Atomic Write

BINANCE_FUTURES_API = "https://fapi.binance.com"
BASE_PATH = "/home/node/clawd/skills/black-swan-hunter"
ALERT_HISTORY_FILE = f"{BASE_PATH}/alert_history.json"

def load_alert_history():
    """加载已推送信号历史"""
    try:
        if os.path.exists(ALERT_HISTORY_FILE):
            with open(ALERT_HISTORY_FILE, "r") as f:
                return json.load(f)
    except: pass
    return {"alerts": [], "last_updated": 0}

def save_alert_history(history):
    """保存信号历史"""
    with open(ALERT_HISTORY_FILE, "w") as f:
        json.dump(history, f)

def is_new_signal(symbol, decision, history):
    """检查是否是新信号"""
    for alert in history.get("alerts", []):
        if alert["symbol"] == symbol and alert["decision"] == decision:
            return False
    return True

def mark_as_alerted(symbol, decision, history):
    """标记为已推送"""
    history["alerts"].append({
        "symbol": symbol,
        "decision": decision,
        "ts": int(time.time() * 1000)
    })
    # 只保留最近 100 条记录
    if len(history["alerts"]) > 100:
        history["alerts"] = history["alerts"][-100:]
    history["last_updated"] = int(time.time() * 1000)

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
        print("[BSH] Cycle Start: Scanning Candidates...")
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
            print("[BSH] No Hunts found, finishing...")
            live_manager.sync_data([], {})
            live_manager.add_log("Cycle Finish: No Hunts found.")
            return

        # --- Step 3: Wait 30s ---
        print(f"[BSH] Found {len(current_hunts)} hunts. Waiting 30s for Map generation...", flush=True)
        live_manager.add_log(f"Found {len(current_hunts)} hunts. Waiting 30s for Map generation...")
        time.sleep(30)
        
        # --- Step 4: 生成热力图 ---
        print(f"[BSH] Starting map generation for {len(current_hunts)} hunts...", flush=True)
        current_maps = {}
        for h in current_hunts:
            symbol = h['symbol']
            print(f"[BSH] Generating map for {symbol}...", flush=True)
            current_maps[symbol] = get_wide_liq_map(symbol)
            print(f"[BSH] Map done for {symbol}", flush=True)

        # --- Step 5: Wait 30s for LLM Critique ---
        print(f"[BSH] Maps generated. Waiting 30s before generating LLM critiques...", flush=True)
        live_manager.add_log(f"Maps generated. Waiting 30s before LLM critiques...")
        time.sleep(30)

        # --- Step 6: 异步/高速 LLM 锐评模块 ---
        print(f"[BSH] Generating LLM critiques for {len(current_hunts)} hunts...", flush=True)
        for h in current_hunts:
            symbol = h.get("symbol")
            decision = h.get("decision")
            metrics = h.get("metrics", {})
            prompt = f"""你是一个冷酷、毒舌、专业的顶级 DEX Perpetual 交易员。
现在的行情判决如下：
- 币种: {symbol}
- 决策: {decision}
- 资金费率: {metrics.get('funding', 0):.4%}
- 24h涨跌: {metrics.get('change', 0):.2%}
- RSI(5m): {metrics.get('rsi', 50):.1f}

逻辑参考：
1. BUY: 血腥洗盘，多头爆仓，VWAP回收，买入血筹码。
2. SQUEEZE_TRAP: 费率极低，空头陷阱，正在逼空，坚决不空。
3. LIQUIDATION_CASCADE: 费率极高，多头踩踏预警，定时炸弹。
4. FADE: 抛物线力竭。有单逃命，没单反手反向猎杀。

要求：
1. 语气：尖酸刻薄、专业、不留情面。
2. 长度：1-2句话。
3. 不要废话，直接扎心。"""
            
            # 使用固定 sessionKey 复用会话，防止 session 爆炸
            try:
                resp = requests.post(
                    "http://127.0.0.1:18789/v1/chat/completions",
                    headers={"Authorization": "Bearer YOUR_GATEWAY_TOKEN", "Content-Type": "application/json"},
                    json={
                        "model": "minimax-cn/MiniMax-M2.5", # 使用你的默认高速模型
                        "messages": [{"role": "user", "content": prompt}],
                        "temperature": 0.7,
                        "user": "bsh-critique-engine" # 强制指定用户标识以复用会话
                    },
                    timeout=15
                )
                if resp.status_code == 200:
                    ai_text = resp.json()['choices'][0]['message']['content'].strip()
                    h['dextrader_critique'] = ai_text  # 覆盖预设的模板点评
                    h['critique'] = ai_text
            except Exception as e:
                print(f"[BSH] LLM Critique failed for {symbol}: {e}")
                pass # 失败则保留 hunter.py 生成的 get_fast_critique 模板

        # --- Step 7: 原子级同步全量数据 ---
        # 这一步执行后，live_data.json 才会更新，确保看板不跑偏
        print(f"[BSH] Syncing {len(current_hunts)} hunts to live_data.json...")
        live_manager.sync_data(current_hunts, current_maps)
        
        # --- Step 8: 实时信号推送 (去重逻辑) ---
        alert_history = load_alert_history()
        new_alerts = []
        
        for hunt in current_hunts:
            decision = hunt.get("decision", "NO_TRADE")
            if decision != "NO_TRADE":
                symbol = hunt.get("symbol")
                entry = hunt.get("entry")
                critique = hunt.get("critique", "No critique available.")
                
                # 检查是否是新信号
                if not is_new_signal(symbol, decision, alert_history):
                    print(f"[BSH] Skip (already alerted): {symbol} - {decision}")
                    continue
                
                # 新信号，推送
                alert_msg = (
                    f"⚠️ **黑天鹅 V5 新预警**\n"
                    f"------------------------\n"
                    f"标的: {symbol}\n"
                    f"决策: **{decision}**\n"
                    f"参考价: {entry}\n"
                    f"点评: {critique}\n"
                    f"------------------------\n"
                    f"时间: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime())} (CST)"
                )
                # 钉钉推送 (使用正确的 session ID)
                try:
                    subprocess.run(["openclaw", "message", "send", "--channel", "dingtalk-connector", "--target", "YOUR_DINGTALK_SESSION_ID", "--message", alert_msg], capture_output=True)
                    mark_as_alerted(symbol, decision, alert_history)
                    new_alerts.append(f"{symbol} - {decision}")
                    print(f"[BSH] Alert sent: {symbol} - {decision}")
                except: pass
        
        # 保存更新后的历史
        save_alert_history(alert_history)

        print(f"[BSH] Cycle Finish: Atomic Sync and Alerts Completed for {len(current_hunts)} symbols.")
        live_manager.add_log(f"Cycle Finish: Atomic Sync and Alerts Completed for {len(current_hunts)} symbols.")
        
    except Exception as e:
        live_manager.add_log(f"Cycle Fatal: {e}")

if __name__ == "__main__":
    # 为了配合 Cron 5分钟触发，脚本运行一次即退出
    run_atomic_cycle()
