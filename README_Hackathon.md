# Black Swan Hunter V5.2 - Binance Hackathon Edition

> **"Hunt the blood, map the gravity."**
> 一款基于 AI 注入与庄家视野的次世代 DEX 永续合约监控工具。

## 🌟 核心杀手锏

### 1. 庄家视野 (Liquidation Heatmap)
不同于市面上滞后的“爆仓统计”，本项目通过实时抓取 **Binance L2 盘口深度** 与 **Open Interest (OI)**，利用动态加权算法预判价格上下 15% 的“潜在清算引力区”。让猎手在天鹅起飞前就看到导火索。

### 2. AI 灵魂注入 (Dynamic AI Critique)
彻底告别死板的模板化提醒。系统集成 LLM 接口，根据费率、波动率、OI 变动等核心指标，生成**毒舌、专业且冷酷**的行情点评，为冰冷的交易数据赋予生命。

### 3. 跨端同步黑科技 (Mirror-Handshake Protocol)
针对云端 Agent 与本地 Dashboard 的同步延迟难题，首创“镜像双文件”握手协议。通过影子文件与信号灯机制，实现 100% 数据一致性，彻底消除文件锁竞争导致的同步冲突。

---

## 🚀 系统架构

系统采用 **“前后期分离，物理对齐”** 架构：
- **云端大脑 (Agent)**: 负责全场扫描、费率审计、清算地图建模。
- **本地看板 (Dashboard)**: 基于 Streamlit 开发，通过网盘挂载实现数据实时可视化。

---

## 🛠️ 快速开始 (可复制性说明)

### 1. 环境准备
```bash
git clone https://github.com/your-repo/black-swan-hunter.git
cd black-swan-hunter
pip install -r requirements.txt
```

### 2. 配置脱敏
将 `.env.example` 重命名为 `.env` 并填入：
- `BINANCE_API_KEY`: 你的 API Key
- `LLM_MODEL_ENDPOINT`: OpenClaw 兼容的模型接口
- `DINGTALK_TOKEN`: 钉钉报警推送 Token

### 3. 运行逻辑
- **全场扫描**: `python funnel_engine.py --mode scan` (建议 Cron 5min)
- **实时看板**: `streamlit run dashboard/blackswarndashboard.py`

---

## 📈 交易状态判定
- **SQUEEZE_TRAP**: 费率极低，空头正在火场受刑。
- **LIQUIDATION_CASCADE**: 费率极高，多头踩踏预警。
- **BUY the Blood**: 结构化洗盘结束，VWAP 收回信号。
- **FADE the Bubble**: 抛物线力竭，反手猎杀时刻。

---

**Built for the sharpest traders.** 
*Black Swan Hunter - 永远领先市场一秒。*
