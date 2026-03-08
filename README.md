# 📈 Black Swan Hunter (V5.2 - The Full Alpha Edition)

> **核心哲学：由新闻驱动确定性，由量化驱动精确性，由风控驱动生存力。**

---

## 🏛️ 六级情报金字塔：全维度过滤架构

### **L1: 波动率自适应 (Volatility Adaptive)** 📡
- **触发**: Move > 3 × ATR(5m) 或 1m 实现波动率 4 倍偏离。

### **L2: 情报仲裁与公告核实 (Intelligence Arbiter)** 🗡️
- **Binance 公告**: 实时监控 `listing-sentinel` 查证下架、暂停、网络风险。
- **全球新闻**: 调用 `OpenNews` / `OpenTwitter` 查证 SEC 指控、黑客攻击、协议漏洞。
- **决策**: **基本面崩坏 = FADE**。拒绝接“死鱼”的飞刀。

### **L3: 结构性 Edge 确认 (The Blood Stream)** 🩸
- **Websocket 监听**: 接入 `!forceOrder@arr` 强平流。
- **OI Delta**: 监测持仓量下降 (> 2%)。
- **逻辑**: 价格跌 + OI 跌 + 爆仓激增 = **Leverage Flush (真·机会)**。

### **L4: MM 行为识别与熔断 (MM Lens & Circuit Breaker)** 🧨
- **逼空识别 (Short Squeeze)**: 暴涨时若 **Funding Rate < -0.1%**，判定为逼空陷阱。
- **动作**: **强制 FADE**。绝对禁止单边博弈逼空。

### **L5: 微结构确认 (Execution Confirmation)**
- **入场**: 等待 1m 线长下影、VWAP Reclaim (价格收回均线) 或衰竭 K 线确认。

---

## 🛡️ 风险控制与自动化执行 (Volatility-Based Ops)

- **止损 (Stop)**: **1.5 × ATR** (自适应波动止损)。
- **止盈 (Take Profit)**: 
  - **TP1 (38.2% Retrace)**: 锁定本金。
  - **TP2 (61.8% Retrace)**: 锁定核心利润。
  - **TP3 (VWAP Trailing)**: 趋势榨干。

---

## 🛠️ 指令集 (Institutional Command)

| 指令 | 说明 |
| :--- | :--- |
| `/hunt_v5 <symbol>` | 执行全维度分析：公告+新闻+代码+OI+爆仓流+MM。 |
| `/scan_v5` | 全场基于波动率和流动性的自适应扫描。 |
| `/liquid_stream` | 开启 Websocket 实时爆仓流监控。 |
| `/mm_check <symbol>` | 费率、持仓、订单簿深度全维度诊断。 |
