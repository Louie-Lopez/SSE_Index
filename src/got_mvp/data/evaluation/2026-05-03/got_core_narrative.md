# GoT 核心叙事（归并 · 决策 · 批判）

- **snapshot_date**: 2026-05-03
- **run_id**: got-mvp-20260505130212-95041395

---

## AggregateEvidence（归并）

## 时间尺度
- **宏观**：月度。**- **SSE**：独立 **SSEIndex.json**（近10交易日至 04-30 收盘段落）。**- **标题窗**：meta 2026-04-30—2026-05-03，且 policy 混入旧稿 => **降噪**。

## 共识
上证 **台阶上行**；国内 PMI+松货币+分红情绪；美方 **通胀黏性 + 鹰派 chatter**。**外溢**：抬波动多于单向打穿在岸短线趋势。

## 冲突（结构化）
**A**：联储/地缘 => 贴现率摩擦 vs **B**：在岸宽货币与指数动能。**严重度**：**中**。**维度**：外溢liquidity <-> 内需+指数。

## 权重
SSE + CN.US EDB **主盘**；新闻 **远低于**硬数据。**缺失**：core_CPI_cn、MLF、Markit PMI 等。**反证**：4050±区间放量破位或信用事件 => 偏多共识作废。

### 分源复述（单行）sse.summary
近10个交易日上证由4050一带震荡上行至4112上方，短线偏多、波动温和抬升。

---

## DecisionNode（决策）

## 倾向
上证综指 **短线（约一周）偏多**。

## 尺度
SSE 十日抬升为主导近证；月为背景；资讯噪声封顶置信。

## 置信
宽货币+PMI+台阶指数 vs **外溢波动** => **confidence 中等**。

## 驱动（分源）
SSEIndex close path；CN shibor+PMI；US CPI+联储 chatter（波动）；Micro 分红。

## 人类采纳
HumanInput `human_note` **空** -> **无额外偏好**。

## 证伪上证 **4050-ish**以下放量台阶破坏；国内外信用黑天鹅。

## 风险
evaluation keyword 误判；missing macro fields。

---

## CriticNode（批判）

## 人类Decision 一致性
已对 **空 HumanInput** 显性处理。**Aggregate** 已对 MacroNews.old 混入与 SSE **分文件**。**Pass**。

## residual
可加「逐条剔除非窗 policy 行」作下一版 cleanliness。

**need_revision** false：无强制逻辑断裂。

## （格式边界）只审查本条消息给定材料。**
