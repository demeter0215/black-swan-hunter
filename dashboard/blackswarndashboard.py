import html
import json
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

try:
    from streamlit_autorefresh import st_autorefresh
except Exception:
    st_autorefresh = None

st.set_page_config(
    page_title="Black Swan Hunter | REAL-TIME V5.2",
    page_icon="BS",
    layout="wide",
    initial_sidebar_state="collapsed",
)

DASHBOARD_DIR = Path(__file__).resolve().parent
MICROSERVICE_SKILL_DIR = Path(r"你的输出文档路径")
DATA_FILE = MICROSERVICE_SKILL_DIR / "live_data.json"
STAGED_DATA_FILE = MICROSERVICE_SKILL_DIR / "live_data.json.new"
SYNC_READY_FILE = MICROSERVICE_SKILL_DIR / "sync.ready"
DEBUG_DATA_FILE = DASHBOARD_DIR / "debug_live_data.json"
LOCAL_CACHE_FILE = DASHBOARD_DIR / "local_cache.json"
USE_DEBUG_DATA = False
REFRESH_SECONDS = int(os.getenv("SWAN_DASH_REFRESH_SECONDS", "2"))
MAX_HUNTS = int(os.getenv("SWAN_MAX_HUNTS", "120"))
AUTO_TRADE_STATE_FILE = MICROSERVICE_SKILL_DIR / "auto_trade_state.json"

EMPTY_DATA = {
    "meta": {
        "engine_status": "unknown",
        "last_scan_ts": 0,
        "candidate_count": 0,
        "latest_alert_symbol": "",
    },
    "hunts": [],
    "liquidation_map": {},  # 清算热力图数据
    "logs": [],
}

st.markdown(
    """
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;800&family=JetBrains+Mono:wght@400;700&display=swap');
    .stApp { background-color: #f4f6f9; font-family: 'Inter', sans-serif; }
    .font-mono { font-family: 'JetBrains Mono', monospace; }
    header, #MainMenu, footer {visibility: hidden;}
    .custom-card {
        background: white; border-radius: 0.75rem; border: 1px solid #e6e8ea;
        box-shadow: 0 1px 2px 0 rgba(0,0,0,0.05); overflow: hidden; margin-bottom: 1rem;
    }
    .card-header {
        padding: 1rem; border-bottom: 1px solid #f3f4f6; background-color: #f9fafb;
        font-size: 0.75rem; font-weight: 700; color: #6b7280; text-transform: uppercase;
        letter-spacing: 0.05em; display: flex; justify-content: space-between; align-items: center;
    }
    .hunt-card {
        padding: 0.75rem; border-bottom: 1px solid #f3f4f6; border-left: 4px solid transparent;
        transition: all 0.2s; font-size: 0.875rem;
    }
    .hunt-card:hover { transform: translateX(2px); background-color: #f9fafb; }
    .hunt-card.BUY, .hunt-card.LONG { border-left-color: #2ab1a8; }
    .hunt-card.SELL, .hunt-card.SHORT { border-left-color: #f6465d; }
    .hunt-card.FADE { border-left-color: #f59e0b; }
    .hunt-card.WATCH { border-left-color: #3b82f6; }
    .hunt-card.NO_TRADE { border-left-color: #9ca3af; }
    .hunt-card.SQUEEZE_TRAP { border-left-color: #8b5cf6; } /* 为 SQUEEZE_TRAP 增加一个特殊的紫色标识 */
    /* 缩小页面顶部的默认白边空白 */
    .block-container { padding-top: 1.5rem !important; padding-bottom: 1rem !important; }
</style>
""",
    unsafe_allow_html=True,
)


def _to_float(value, default=0.0):
    try:
        return float(value)
    except Exception:
        return default


def _to_int(value, default=0):
    try:
        return int(value)
    except Exception:
        return default


def _normalize_hunt(item):
    tp = item.get("tp") if isinstance(item.get("tp"), dict) else {}
    return {
        "symbol": str(item.get("symbol") or "UNKNOWN"),
        "decision": str(item.get("decision") or "NO_TRADE"),
        "entry": _to_float(item.get("entry")),
        "stop": _to_float(item.get("stop")),
        "tp": {
            "tp1_38_2": _to_float(tp.get("tp1_38_2")),
            "tp2_61_8": _to_float(tp.get("tp2_61_8")),
        },
        "critique": str(item.get("critique") or item.get("dextrader_critique") or ""),
        "ts": _to_int(item.get("ts")),
    }


def _normalize_data(raw):
    data = raw if isinstance(raw, dict) else {}
    meta = data.get("meta") if isinstance(data.get("meta"), dict) else {}
    hunts = [_normalize_hunt(x) for x in data.get("hunts", []) if isinstance(x, dict)]
    
    # 提取新的 liquidation_map 数据
    liq_map = data.get("liquidation_map", {}) if isinstance(data.get("liquidation_map"), dict) else {}

    hunts.sort(key=lambda x: x["ts"], reverse=True)

    return {
        "meta": {
            "engine_status": str(meta.get("engine_status") or "unknown"),
            "last_scan_ts": _to_int(meta.get("last_scan_ts")),
            "candidate_count": _to_int(meta.get("candidate_count"), default=len(hunts)),
            "latest_alert_symbol": str(meta.get("latest_alert_symbol") or ""),
        },
        "hunts": hunts[:MAX_HUNTS],
        "liquidation_map": liq_map,               
        "logs": data.get("logs", []) if isinstance(data.get("logs"), list) else [],
    }


def load_data():
    if "last_good_data" not in st.session_state:
        st.session_state.last_good_data = EMPTY_DATA

    source_file = DEBUG_DATA_FILE if USE_DEBUG_DATA else DATA_FILE

    try:
        if USE_DEBUG_DATA:
            read_file = source_file
            if not read_file.exists():
                raise FileNotFoundError(f"Data file not found: {read_file}")
        else:
            # Handshake protocol:
            # 1) dashboard watches sync.ready
            # 2) when ready exists, pull live_data.json.new to local cache
            # 3) consume local cache for rendering
            # 4) delete sync.ready as ACK
            if SYNC_READY_FILE.exists():
                if not STAGED_DATA_FILE.exists():
                    raise FileNotFoundError(f"Staged data file not found: {STAGED_DATA_FILE}")
                LOCAL_CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(STAGED_DATA_FILE, LOCAL_CACHE_FILE)
                try:
                    SYNC_READY_FILE.unlink()
                except FileNotFoundError:
                    pass

            read_file = LOCAL_CACHE_FILE if LOCAL_CACHE_FILE.exists() else DATA_FILE
            if not read_file.exists():
                raise FileNotFoundError(
                    f"Data file not found (cache and fallback both missing): "
                    f"{LOCAL_CACHE_FILE} | {DATA_FILE}"
                )

        with read_file.open("r", encoding="utf-8") as f:
            loaded = json.load(f)

        normalized = _normalize_data(loaded)
        st.session_state.last_good_data = normalized
        st.session_state.last_read_error = ""
        st.session_state.data_source_file = str(read_file)
        return normalized
    except Exception as exc:
        st.session_state.last_read_error = str(exc)
        st.session_state.data_source_file = str(source_file)
        return st.session_state.last_good_data


def _fmt_ts(ms):
    if not ms:
        return "--:--:--"
    return datetime.fromtimestamp(ms / 1000, tz=timezone.utc).astimezone().strftime("%H:%M:%S")


def _safe(value):
    return html.escape(str(value), quote=True)


def _price_tickformat(series) -> str:
    try:
        if series is None or len(series) == 0:
            return ".2f"
        values = pd.to_numeric(series, errors="coerce").dropna()
        if values.empty:
            return ".2f"
        pmax = float(values.max())
        pmin = float(values.min())
        span = abs(pmax - pmin)
        pabs = max(abs(pmax), abs(pmin))
        if pabs < 0.1 or span < 0.01:
            return ".6f"
        if pabs < 1 or span < 0.1:
            return ".4f"
        if pabs < 100 or span < 10:
            return ".2f"
        return ".0f"
    except Exception:
        return ".2f"


def _engine_badge(meta: dict, read_error: str):
    if read_error:
        return ("DATA ERROR", "#fffbeb", "#fcd34d", "#b45309")

    status = str(meta.get("engine_status") or "").strip().lower()
    if status == "running" or status == "debug_static":
        return ("ENGINE ACTIVE", "#ecfdf5", "#a7f3d0", "#059669")
    if status in {"stopped", "offline", "error"}:
        return ("ENGINE OFFLINE", "#fef2f2", "#fecaca", "#dc2626")

    now_ms = int(datetime.now(tz=timezone.utc).timestamp() * 1000)
    last_scan = _to_int(meta.get("last_scan_ts"))
    if last_scan > 0 and (now_ms - last_scan) <= 180000:
        return ("ENGINE ACTIVE", "#ecfdf5", "#a7f3d0", "#059669")
    if last_scan > 0:
        return ("ENGINE STALE", "#fff7ed", "#fdba74", "#c2410c")
    return ("ENGINE UNKNOWN", "#f3f4f6", "#d1d5db", "#4b5563")


def _load_auto_trade_state() -> bool:
    try:
        if not AUTO_TRADE_STATE_FILE.exists():
            return False
        payload = json.loads(AUTO_TRADE_STATE_FILE.read_text(encoding="utf-8"))
        return bool(payload.get("enabled", False))
    except Exception:
        return False


def _persist_auto_trade_state(enabled: bool) -> None:
    payload = {
        "enabled": bool(enabled),
        "updated_ts": int(datetime.now(tz=timezone.utc).timestamp() * 1000),
        "source": "black-swan-streamlit-dashboard",
    }
    tmp_path = AUTO_TRADE_STATE_FILE.with_suffix(AUTO_TRADE_STATE_FILE.suffix + ".tmp")
    AUTO_TRADE_STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    tmp_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    tmp_path.replace(AUTO_TRADE_STATE_FILE)


def _on_auto_trade_toggle() -> None:
    try:
        _persist_auto_trade_state(bool(st.session_state.get("auto_trade_enabled", False)))
        st.session_state.auto_trade_write_error = ""
    except Exception as exc:
        st.session_state.auto_trade_write_error = str(exc)


if "auto_trade_enabled" not in st.session_state:
    st.session_state.auto_trade_enabled = _load_auto_trade_state()
if "auto_trade_write_error" not in st.session_state:
    st.session_state.auto_trade_write_error = ""


if st_autorefresh:
    st_autorefresh(interval=REFRESH_SECONDS * 1000, key="auto_refresh")

data = load_data()
meta = data.get("meta", {})
hunts = data.get("hunts", [])
liq_map_data = data.get("liquidation_map", {})

# 汇集所有标的（来自 hunts 和 liquidation_map）
symbol_set = {str(h.get("symbol", "")).strip() for h in hunts if h.get("symbol")}
symbol_set.update({str(k).strip() for k in liq_map_data.keys() if k})
symbols = sorted([x for x in symbol_set if x])

if "active_symbol" not in st.session_state:
    st.session_state.active_symbol = symbols[0] if symbols else ""
if st.session_state.active_symbol and st.session_state.active_symbol not in symbols:
    st.session_state.active_symbol = symbols[0] if symbols else ""

selected_symbol = st.session_state.active_symbol

# 数据过滤
filtered_hunts = [h for h in hunts if h.get("symbol") == selected_symbol] if selected_symbol else hunts
filtered_map = liq_map_data.get(selected_symbol, []) if selected_symbol else []

if st.session_state.get("last_read_error"):
    st.warning(f"Data source error: {st.session_state.last_read_error}")

col_head1, col_head2, col_head3 = st.columns([2, 2, 1])
with col_head1:
    label, color_bg, color_border, color_text = _engine_badge(meta, st.session_state.get("last_read_error", ""))
    st.markdown(
        f"""
        <div style="display:flex; flex-direction:column; gap:4px; margin-top:-10px;">
            <div style="display: flex; align-items: center; gap: 6px; color: #F3BA2F; font-size: 13px; font-weight: 800; letter-spacing: 0.5px;">
                <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="#F3BA2F" width="16px" height="16px">
                    <path d="M16.624 13.9202l2.7175 2.7154-7.353 7.353-7.353-7.352 2.7175-2.7164 4.6355 4.6595 4.6356-4.6595zm4.6366-4.6366L24 12l-2.7394 2.7154-2.7394-2.7154L21.2606 9.2836zM7.353 12L4.6137 9.2836 1.8962 12l2.7175 2.7154L7.353 12zm4.635-7.353l2.7175 2.7154-2.7175 2.7164-2.7175-2.7164L11.988 4.647zM12 0l7.353 7.353-2.7175 2.7164-4.6355-4.6595-4.6356 4.6595L4.647 7.353 12 0z"/>
                </svg>
                BINANCE
            </div>
            <div style="display:flex; align-items:center; gap:10px;">
                <h2 style="margin:0; font-weight:800; font-size:1.25rem;">Black Swan Hunter <span style="color:#9ca3af; font-size:0.75rem; font-weight:normal;">V5.2 LIVE</span></h2>
                <span style="background:{color_bg}; border:1px solid {color_border}; color:{color_text}; font-size:10px; padding:2px 8px; border-radius:10px; font-weight:bold;">{label}</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
with col_head2:
    st.markdown(
        f"""
        <div class="font-mono" style="display:flex; gap:20px; font-size:12px;">
            <div><span style="color:#9ca3af; font-weight:bold;">LAST SCAN:</span> <b>{_fmt_ts(meta.get('last_scan_ts', 0))}</b></div>
            <div><span style="color:#9ca3af; font-weight:bold;">CANDIDATES:</span> <b>{_to_int(meta.get('candidate_count'))}</b></div>
            <div><span style="color:#9ca3af; font-weight:bold;">ALERT:</span> <b>{_safe(meta.get('latest_alert_symbol', '-'))}</b></div>
        </div>
        """,
        unsafe_allow_html=True,
    )
with col_head3:
    st.toggle("Auto Trade", key="auto_trade_enabled", on_change=_on_auto_trade_toggle)
    state_text = "ON" if st.session_state.get("auto_trade_enabled", False) else "OFF"
    st.caption(f"State: {state_text}")
    if st.session_state.get("auto_trade_write_error"):
        st.error(f"Auto-trade state write failed: {st.session_state.auto_trade_write_error}")

st.markdown("<hr style='margin: 10px 0 20px 0;'>", unsafe_allow_html=True)

col_left, col_center, col_right = st.columns([1.2, 2.5, 1.2], gap="medium")

with col_left:
    st.markdown("**Active Pairs**")
    if symbols:
        btn_cols = st.columns(2, gap="small")
        for idx, sym in enumerate(symbols):
            button_type = "primary" if sym == selected_symbol else "secondary"
            if btn_cols[idx % 2].button(sym, key=f"pair_btn_{sym}", use_container_width=True, type=button_type):
                st.session_state.active_symbol = sym
                st.rerun()
    else:
        st.caption("No pairs available")

    st.markdown("<br>", unsafe_allow_html=True)
    st.caption(f"Selected: {selected_symbol or 'ALL'}")

    if filtered_hunts:
        latest = filtered_hunts[0]
        st.markdown(
            f"""
            <div class="custom-card hunt-card {latest.get('decision', 'NO_TRADE')}">
                <div style="font-weight:bold;">{latest.get('symbol', 'UNKNOWN')} ({latest.get('decision', 'NO_TRADE')})</div>
                <div style="font-size:12px; margin-top:4px;">Entry: <b>{latest.get('entry', '--')}</b></div>
            </div>
            """,
            unsafe_allow_html=True
        )
    else:
        st.caption("No active hunt signal for selected pair")

with col_center:
    st.markdown(
        """
        <div style="font-size: 0.75rem; font-weight: 700; color: #6b7280; text-transform: uppercase; margin-bottom: 10px;">
            Liquidation Heatmap / 清算热力分布图
        </div>
        """,
        unsafe_allow_html=True,
    )

    if filtered_map:
        df_lmap = pd.DataFrame(filtered_map)
        df_lmap["price"] = pd.to_numeric(df_lmap["price"], errors="coerce")
        df_lmap["notional"] = pd.to_numeric(df_lmap["notional"], errors="coerce")
        df_lmap = df_lmap.dropna(subset=["price", "notional"])

        if not df_lmap.empty:
            # 区分空头爆仓(阻力，上方) 和 多头爆仓(支撑，下方)
            shorts_df = df_lmap[df_lmap["side"].str.lower() == "short"]
            longs_df  = df_lmap[df_lmap["side"].str.lower() == "long"]

            fig = go.Figure()

            # 绘制空头爆仓柱状图 (做空者被平仓，通常位于当前价格上方，形成向上阻力/磁吸)
            if not shorts_df.empty:
                fig.add_trace(go.Bar(
                    x=shorts_df["price"],
                    y=shorts_df["notional"],
                    name="Short Liq (Resistance)",
                    marker_color="rgba(246, 70, 93, 0.7)",  # Binance 红色
                    marker_line_color="#f6465d",
                    marker_line_width=1,
                    hovertemplate="Price: %{x}<br>Liq Notional: $%{y:,.0f}<extra>Shorts Rekt</extra>"
                ))

            # 绘制多头爆仓柱状图 (做多者被平仓，通常位于当前价格下方，形成向下支撑/磁吸)
            if not longs_df.empty:
                fig.add_trace(go.Bar(
                    x=longs_df["price"],
                    y=longs_df["notional"],
                    name="Long Liq (Support)",
                    marker_color="rgba(42, 177, 168, 0.7)",  # Binance 绿色
                    marker_line_color="#2ab1a8",
                    marker_line_width=1,
                    hovertemplate="Price: %{x}<br>Liq Notional: $%{y:,.0f}<extra>Longs Rekt</extra>"
                ))

            # 获取当前开仓价格以定义视角边界 +/- 15%
            current_entry = None
            if filtered_hunts and filtered_hunts[0].get("entry"):
                current_entry = float(filtered_hunts[0].get("entry"))
            
            x_tick_fmt = _price_tickformat(df_lmap["price"])

            layout_args = {
                "plot_bgcolor": "white",
                "paper_bgcolor": "white",
                "margin": dict(l=10, r=10, t=20, b=10),
                "height": 600,
                "barmode": "overlay",
                "xaxis": dict(title="Price Level (USD)", showgrid=True, gridcolor="#f3f4f6", tickformat=x_tick_fmt),
                "yaxis": dict(title="Liquidation Notional (USD)", showgrid=True, gridcolor="#f3f4f6"),
                "legend": dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
            }

            if current_entry and current_entry > 0:
                # 获取清算点数据的最小和最大价格
                data_min = float(df_lmap["price"].min())
                data_max = float(df_lmap["price"].max())
                
                # 动态自适应视角：既保证当前价±15%的默认视野，又向外包容所有实际存在的极值点数据
                x_min = min(current_entry * 0.85, data_min * 0.98)
                x_max = max(current_entry * 1.15, data_max * 1.02)
                layout_args["xaxis"]["range"] = [x_min, x_max]

                # 绘制当前价格基准线
                fig.add_vline(
                    x=current_entry, 
                    line_width=2, 
                    line_dash="dash", 
                    line_color="#6b7280",
                    annotation_text="Current Price", 
                    annotation_position="top right"
                )

            fig.update_layout(**layout_args)
            st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
        else:
            st.info("No valid valid liquidation point data found.")
    else:
        st.info("Waiting for Liquidation Heatmap data...")

with col_right:
    html_stream = """
<div class="custom-card">
    <div class="card-header">
        <span>AI Critique / 策略分析</span>
        <div style="display: flex; align-items: center; gap: 6px; color: #F3BA2F; font-size: 12px; font-weight: 800; letter-spacing: 0.5px;">
            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="#F3BA2F" width="14px" height="14px">
                <path d="M16.624 13.9202l2.7175 2.7154-7.353 7.353-7.353-7.352 2.7175-2.7164 4.6355 4.6595 4.6356-4.6595zm4.6366-4.6366L24 12l-2.7394 2.7154-2.7394-2.7154L21.2606 9.2836zM7.353 12L4.6137 9.2836 1.8962 12l2.7175 2.7154L7.353 12zm4.635-7.353l2.7175 2.7154-2.7175 2.7164-2.7175-2.7164L11.988 4.647zM12 0l7.353 7.353-2.7175 2.7164-4.6355-4.6595-4.6356 4.6595L4.647 7.353 12 0z"/>
            </svg>
            BINANCE
        </div>
    </div>
    <div style="height: 600px; overflow-y: auto; background: white; padding: 1.25rem;">
"""

    if not filtered_hunts:
        html_stream += "<div style='padding: 20px; color: #9ca3af; text-align: center; font-size: 12px;'>No active hunt critique available</div>"
    else:
        latest_hunt = filtered_hunts[0]
        critique = latest_hunt.get("critique", "")
        if not critique:
            critique = "No detailed critique provided for this symbol."
            
        # 兼容换行符展示
        safe_critique = _safe(critique).replace("\n", "<br>")

        html_stream += f"""
<div style="display:flex; flex-direction:column; gap:12px;">
    <div style="font-weight: 800; color: #111827; font-size: 1.1rem; border-bottom: 1px solid #f3f4f6; padding-bottom: 10px;">
        {_safe(latest_hunt.get('symbol', 'UNKNOWN'))} 
        <span style="color:#6b7280; font-size:0.8rem; font-weight:normal; margin-left: 6px;">
            / {_safe(latest_hunt.get('decision', 'NO_TRADE'))}
        </span>
    </div>
    <div style="font-size: 0.875rem; color: #374151; line-height: 1.7; font-family: 'Inter', sans-serif;">
        {safe_critique}
    </div>
</div>
"""
            
    html_stream += "</div></div>"
    st.markdown(html_stream, unsafe_allow_html=True)

if not st_autorefresh:
    import time
    time.sleep(REFRESH_SECONDS)

    st.rerun()
