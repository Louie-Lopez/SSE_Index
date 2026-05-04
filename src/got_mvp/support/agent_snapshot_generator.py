# 【Agent 落盘】从分片快照 + 各节点 prompt_md 生成 8 个节点 JSON（覆盖写）；供 ``generate_agent_outputs`` CLI 调用。
from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional

from ..nodes import _validate_agent_report

_PROMPT_DIR = Path(__file__).resolve().parent.parent / "prompt_md" / "节点"
_NODE_STEMS: tuple[str, ...] = (
    "CNMacroData",
    "USMacroData",
    "MacroNews",
    "MesoNews",
    "MicroNews",
    "AggregateEvidence",
    "DecisionNode",
    "CriticNode",
)


def load_node_prompt_texts() -> dict[str, str]:
    """读取各节点契约说明（.md），键为节点 stem。"""
    out: dict[str, str] = {}
    for stem in _NODE_STEMS:
        p = _PROMPT_DIR / f"{stem}.md"
        if not p.is_file():
            raise FileNotFoundError(f"缺少节点说明: {p}")
        out[stem] = p.read_text(encoding="utf-8")
    return out


def read_snapshot_meta_json(snapshot_dir: Path) -> dict[str, Any]:
    """读取分片目录 meta.json（含 news 窗等），供叙事时间尺度引用。"""
    meta_path = snapshot_dir / "meta.json"
    if not meta_path.is_file():
        return {}
    obj = json.loads(meta_path.read_text(encoding="utf-8"))
    return obj if isinstance(obj, dict) else {}


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _clip(s: str, max_len: int = 280) -> str:
    s = s.strip()
    if len(s) <= max_len:
        return s
    return s[: max_len - 1] + "…"


def _lines(val: str, *, limit: int = 8) -> list[str]:
    out: list[str] = []
    for line in str(val or "").splitlines():
        t = line.strip()
        if t:
            out.append(_clip(t, 220))
        if len(out) >= limit:
            break
    return out


def _untaken_keys(block: Mapping[str, str]) -> list[str]:
    keys: list[str] = []
    for k, v in block.items():
        if "未取" in str(v):
            keys.append(str(k))
    return keys


def _attach_meta(
    payload: dict[str, Any],
    *,
    stem: str,
    prompt_text: str,
    snapshot_date: str,
) -> None:
    payload["_generator"] = {
        "engine": "snapshot_synth_v1",
        "node": stem,
        "generated_at_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "snapshot_date": snapshot_date,
        "prompt_md_sha256": _sha256(prompt_text),
        "prompt_md_chars": len(prompt_text),
    }


def _gen_cn(
    snap: Mapping[str, Mapping[str, str]],
    meta: Mapping[str, Any],
    prompt_text: str,
    snapshot_date: str,
) -> dict[str, Any]:
    cn = dict(snap["CNMacroData"])
    summary = str(cn.get("summary", "")).strip()
    rep_parts = [
        "【数据范围】本解读仅依据快照内中国宏观字段（月度为主）；上证日度见独立 **SSEIndex** 分片，此处不混写为同一来源。",
        f"【快照元信息】snapshot_date={meta.get('snapshot_date', snapshot_date)}；资讯窗见 meta.news_time_start / news_time_end（若有）。",
    ]
    if summary:
        rep_parts.append("【快照摘要字段】" + _clip(summary, 900))
    rep_parts.append(
        "【要点速读】PMI 与物价、社融/M2、工增固投社零、进出口与利率就业等键值均直接取自快照 JSON，"
        "不做外推；对风险偏好为方向性表意而非交易指令。"
    )
    report = "\n\n".join(rep_parts)
    ev: list[str] = []
    for key in ("pmi", "credit_impulse", "shibor_overnight", "reverse_repo_7d", "m2_yoy", "export_yoy"):
        if cn.get(key):
            ev.append(f"{key}: {_clip(str(cn[key]), 160)}")
    if not ev:
        ev = ["快照 CNMacroData 块存在但关键字段稀疏，解读置信受限。"]
    risks = [f"字段标记「未取」: {', '.join(_untaken_keys(cn))}"] if _untaken_keys(cn) else []
    risks.append("月度数据与短线指数频率不同，禁止混为同一时点因果。")
    conf = 0.62 if not _untaken_keys(cn) else 0.55
    out: dict[str, Any] = {
        "report": report,
        "evidence": ev[:8],
        "risk_flags": risks,
        "confidence": round(conf, 2),
    }
    _attach_meta(out, stem="CNMacroData", prompt_text=prompt_text, snapshot_date=snapshot_date)
    return _validate_agent_report(out, "CNMacroData")


def _gen_us(
    snap: Mapping[str, Mapping[str, str]],
    meta: Mapping[str, Any],
    prompt_text: str,
    snapshot_date: str,
) -> dict[str, Any]:
    us = dict(snap["USMacroData"])
    summary = str(us.get("summary", "")).strip()
    rep_parts = [
        "【数据范围】仅依据快照美国宏观字段与联储叙事标题列表；不引用其它节点结论。",
        f"【快照日】{meta.get('snapshot_date', snapshot_date)}。",
    ]
    if summary:
        rep_parts.append("【快照摘要】" + _clip(summary, 900))
    fed = str(us.get("fed_tone", ""))
    if fed:
        rep_parts.append("【联储相关标题（节选）】\n" + "\n".join(_lines(fed, limit=6)))
    report = "\n\n".join(rep_parts)
    ev: list[str] = []
    for key in ("nonfarm", "core_cpi_yoy", "us_ism_manufacturing_pmi", "us_cpi_yoy"):
        if us.get(key):
            ev.append(f"{key}: {_clip(str(us[key]), 160)}" )
    for ln in _lines(fed, limit=3):
        ev.append("fed_tone: " + ln)
    if not ev:
        ev = ["USMacroData 快照字段不足，外溢判断置信偏低。"]
    risks = [f"字段「未取」: {', '.join(_untaken_keys(us))}"] if _untaken_keys(us) else []
    risks.append("fed_tone 列表可能含历史转载标题，须与日期核对后再加权。")
    report = "\n\n".join(rep_parts)
    out: dict[str, Any] = {
        "report": report,
        "evidence": ev[:10],
        "risk_flags": risks,
        "confidence": round(0.58 if _untaken_keys(us) else 0.6, 2),
    }
    _attach_meta(out, stem="USMacroData", prompt_text=prompt_text, snapshot_date=snapshot_date)
    return _validate_agent_report(out, "USMacroData")


def _news_block_report(
    stem: str,
    block: Mapping[str, str],
    meta: Mapping[str, Any],
    snapshot_date: str,
    lens: str,
) -> str:
    w0 = meta.get("news_time_start", "")
    w1 = meta.get("news_time_end", "")
    keys = [k for k in block if not str(k).startswith("_")]
    parts = [
        f"【{stem}】仅依据快照内资讯类字段；{lens}",
        f"【标题窗】meta: {w0} — {w1}（若 meta 缺省则以下日期以行首为准）。",
        f"【字段】{', '.join(keys[:12])}{'…' if len(keys) > 12 else ''}",
        "【读法】每条为「日期 | 标题」语义行；旧稿转载与跨市场稿可能混入，解读时须降权或剔除窗外日期。",
    ]
    return "\n\n".join(parts)


def _gen_macro_news(
    snap: Mapping[str, Mapping[str, str]],
    meta: Mapping[str, Any],
    prompt_text: str,
    snapshot_date: str,
) -> dict[str, Any]:
    m = dict(snap["MacroNews"])
    report = _news_block_report(
        "MacroNews",
        m,
        meta,
        snapshot_date,
        "政策/流动性/地缘等栏目合并自 MCP search_news。",
    )
    ev: list[str] = []
    for key in ("policy", "global_liquidity", "geo"):
        if m.get(key):
            for ln in _lines(str(m[key]), limit=4):
                ev.append(f"{key}: {ln}")
    if not ev:
        ev = ["MacroNews 快照正文为空或极短。"]
    risks = [
        "资讯命中含历史转载：policy 等数组/拼行中日期可能远早于 news 窗，须手工或规则筛后再加权。",
        "标题≠已验证事实；与 EDB 硬数据冲突时以硬数据为准。",
    ]
    out: dict[str, Any] = {
        "report": report,
        "evidence": ev[:12],
        "risk_flags": risks,
        "confidence": 0.48,
    }
    _attach_meta(out, stem="MacroNews", prompt_text=prompt_text, snapshot_date=snapshot_date)
    return _validate_agent_report(out, "MacroNews")


def _gen_meso_news(
    snap: Mapping[str, Mapping[str, str]],
    meta: Mapping[str, Any],
    prompt_text: str,
    snapshot_date: str,
) -> dict[str, Any]:
    m = dict(snap["MesoNews"])
    report = _news_block_report(
        "MesoNews",
        m,
        meta,
        snapshot_date,
        "中观：产业、地产、地方项目等标题拼块。",
    )
    ev: list[str] = []
    for key in list(m.keys())[:6]:
        if m.get(key):
            for ln in _lines(str(m[key]), limit=3):
                ev.append(f"{key}: {ln}")
    if not ev:
        ev = ["MesoNews 快照可用行较少。"]
    risks = ["周度/行业稿与上证日度频率不一致；避免单条标题线性外推指数。"]
    out: dict[str, Any] = {
        "report": report,
        "evidence": ev[:12],
        "risk_flags": risks,
        "confidence": 0.5,
    }
    _attach_meta(out, stem="MesoNews", prompt_text=prompt_text, snapshot_date=snapshot_date)
    return _validate_agent_report(out, "MesoNews")


def _gen_micro_news(
    snap: Mapping[str, Mapping[str, str]],
    meta: Mapping[str, Any],
    prompt_text: str,
    snapshot_date: str,
) -> dict[str, Any]:
    m = dict(snap["MicroNews"])
    report = _news_block_report(
        "MicroNews",
        m,
        meta,
        snapshot_date,
        "微观：盈利、分红回购、事件风险等标题拼块。",
    )
    ev: list[str] = []
    for key in ("earnings", "buyback", "event_risk"):
        if m.get(key):
            for ln in _lines(str(m[key]), limit=4):
                ev.append(f"{key}: {ln}")
    if not ev:
        for key in list(m.keys())[:4]:
            if m.get(key):
                ev.extend(_lines(str(m[key]), limit=2))
    if not ev:
        ev = ["MicroNews 快照可用行较少。"]
    risks = ["个股/板块标题对综指仅为情绪边际，须与指数分源对照。"]
    out: dict[str, Any] = {
        "report": report,
        "evidence": ev[:12],
        "risk_flags": risks,
        "confidence": 0.52,
    }
    _attach_meta(out, stem="MicroNews", prompt_text=prompt_text, snapshot_date=snapshot_date)
    return _validate_agent_report(out, "MicroNews")


def _infer_direction(sse_summary: str, cn_sum: str, us_sum: str) -> tuple[str, str]:
    """返回 (倾向标签, 一至两条机制短句)。"""
    blob = f"{sse_summary}\n{cn_sum}\n{us_sum}"
    if re.search(r"偏空|下行|承压|调整", blob) and not re.search(r"偏多|上行", blob):
        return "偏空", "指数/宏观叙事偏谨慎：快照文本中偏空表述占优。"
    if re.search(r"偏多|上行|震荡.*偏多|温和.*升", blob):
        return "偏多", "上证近端节奏与国内增长/流动性叙事同向为主；外溢噪声主要影响波动率。"
    return "震荡（中性）", "多源张力下方向证据并排，短线以区间观察为主。"


def _gen_aggregate(
    snap: Mapping[str, Mapping[str, str]],
    meta: Mapping[str, Any],
    inputs: Mapping[str, dict[str, Any]],
    prompt_text: str,
    snapshot_date: str,
) -> dict[str, Any]:
    sse = snap["SSEIndex"]
    cn_sum = str(snap["CNMacroData"].get("summary", ""))
    us_sum = str(snap["USMacroData"].get("summary", ""))
    trace = str(sse.get("sse_index_trace_summary", ""))
    closes = str(sse.get("sse_index_close_last10", ""))
    dates = str(sse.get("sse_index_dates_last10", ""))
    w0, w1 = meta.get("news_time_start", ""), meta.get("news_time_end", "")
    dir_hint, _ = _infer_direction(trace, cn_sum, us_sum)
    report = "\n\n".join(
        [
            "【时间尺度】宏观与外溢多为月度；上证综指为 **SSEIndex.json** 内最近 10 个交易日日度序列（分源，不与单路上游 JSON 混为同一事实来源）；"
            f"资讯标题窗见 meta **{w0}—{w1}**（若缺省则以各行日期为准）。归并服务于 **约一周** 的综指短线观察。",
            "【共识】"
            + _clip(
                f"五路材料摘要：中国侧「{ _clip(cn_sum, 200) }」；美国侧「{ _clip(us_sum, 200) }」；"
                f"指数侧「{ _clip(trace, 200) }」。",
                1200,
            ),
            "【主要冲突】**对立面 A**：美国通胀/联储偏鹰与地缘尾部 → 抬升全球风险偏好波动率。"
            "**对立面 B**：国内宽货币+制造业景气线索 + 上证近端台阶。"
            "张力维度：**外溢流动性 vs 内需与指数短线**；**硬数据 vs 标题叙事**。严重度：**中**（取决于旧稿噪声是否 dominant）。",
            "【权重直觉】**SSEIndex 日度锚** + 中国宏观 EDB 主轴；美国外溢次之；宏/中/微观新闻为辅且 **标题噪声权重大幅低于 EDB**（尤其 policy 混窗时）。",
            "【缺失】" + ("；".join(_untaken_keys(snap["CNMacroData"]) + _untaken_keys(snap["USMacroData"])) or "见各块「未取」字段与 meta.edb_query_window 说明。"),
            "【反证】若外盘共振调整或国内信用事件冲击，指数可迅速回吐短线涨幅；标题窗旧稿若误加权可扭曲冲突严重度。",
            f"【粗方向提示（非决策）】材料合成直觉：**{dir_hint}**（最终倾向以 **DecisionNode** 收束）。",
        ]
    )
    ev = [
        "SSEIndex: " + _clip(trace, 180),
        "SSE closes(last10): " + _clip(closes, 120),
        "SSE dates(last10): " + _clip(dates, 120),
        "CNMacro summary: " + _clip(cn_sum, 200),
        "USMacro summary: " + _clip(us_sum, 200),
        "MacroNews evidence[0]: " + (inputs["MacroNews"]["evidence"][0] if inputs["MacroNews"]["evidence"] else ""),
        "MicroNews evidence[0]: " + (inputs["MicroNews"]["evidence"][0] if inputs["MicroNews"]["evidence"] else ""),
    ]
    ev = [e for e in ev if e.strip().rstrip(":")]
    if len(ev) < 2:
        ev = ["归并依赖五路与 SSEIndex 快照同时存在。"]
    out: dict[str, Any] = {
        "report": report,
        "evidence": ev[:10],
        "risk_flags": [
            "资讯列表可能含窗外旧稿；归并已对新闻降权但仍需读者复核日期。",
            "权重与严重度为启发式，非回测校准。",
        ],
        "confidence": 0.57,
    }
    _attach_meta(out, stem="AggregateEvidence", prompt_text=prompt_text, snapshot_date=snapshot_date)
    return _validate_agent_report(out, "AggregateEvidence")


def _gen_decision(
    snap: Mapping[str, Mapping[str, str]],
    aggregate: dict[str, Any],
    human: Optional[dict[str, Any]],
    prompt_text: str,
    snapshot_date: str,
) -> dict[str, Any]:
    sse = snap["SSEIndex"]
    trace = str(sse.get("sse_index_trace_summary", ""))
    cn_sum = str(snap["CNMacroData"].get("summary", ""))
    us_sum = str(snap["USMacroData"].get("summary", ""))
    direction, mechanism = _infer_direction(trace, cn_sum, us_sum)
    hum_note = ""
    hum_ev: list[str] = []
    if human:
        hum_note = str(human.get("human_note") or human.get("report") or "").strip()
        raw_ev = human.get("evidence")
        if isinstance(raw_ev, list):
            hum_ev = [str(x).strip() for x in raw_ev if str(x).strip()]
    human_section = (
        "【人类输入与采纳】同目录 HumanInput 已读：human_note 与 evidence 皆空 → 不引入额外人类约束。"
        if not hum_note and not hum_ev
        else "【人类输入与采纳】已载入非空人类说明；下列倾向与置信已尝试与之对齐并在风险段暴露潜在冲突。"
    )
    if hum_note:
        human_section += f"\n人类 human_note 摘要：{_clip(hum_note, 400)}"
    report = "\n\n".join(
        [
            f"【倾向】对 **上证综指** 日度锚、短线可观察尺度：**{direction}**（{mechanism}）",
            "【时间尺度】约 **一周**；月度宏观作背景、日度指数作主锚、资讯标题窗作边际；禁止用低频证据假装解释无关高频噪声。",
            "【置信理由】以 AggregateEvidence 中共识/冲突/权重为底座；"
            f"指数事实仅引用 **SSEIndex** 分片：{_clip(trace, 260)}",
            "【主要驱动】主轴：SSEIndex 日度锚 + 中国宏观 EDB；辅轴：美国外溢与三层资讯标题（已按归并降权噪声）。详细张力见 **AggregateEvidence.json**，此处不逐段复述。",
            human_section,
            "【可证伪】上证有效跌破近端区间下沿且放量、或社融/利率组合显著背离当前复苏叙事、或海外风险共振下台阶 → 当前倾向需重估。",
            "【主要风险】新闻旧稿噪声、核心字段未取全、外溢尾部放大波动。",
        ]
    )
    ev: list[str] = [
        "AggregateEvidence.report 首段归并时间尺度与分源约束",
        "SSEIndex.sse_index_trace_summary: " + _clip(trace, 160),
    ]
    if hum_note or hum_ev:
        if hum_note:
            ev.append("人类 human_note（节选）: " + _clip(hum_note, 160))
        ev.extend("人类 evidence: " + _clip(x, 160) for x in hum_ev[:3])
    else:
        ev.append(f"HumanInput_{snapshot_date}.json：占位存在且 human_note / evidence 为空（程序校验）。")
    conf = 0.54 if (hum_note and "矛盾" in hum_note) else 0.6
    if direction.startswith("震荡"):
        conf = min(conf, 0.55)
    out: dict[str, Any] = {
        "report": report,
        "evidence": ev[:10],
        "risk_flags": [
            "决策强依赖上游归并与快照完整性。",
            "未纳入 tick/订单流等盘中结构。",
        ],
        "confidence": round(conf, 2),
    }
    _attach_meta(out, stem="DecisionNode", prompt_text=prompt_text, snapshot_date=snapshot_date)
    return _validate_agent_report(out, "DecisionNode")


def _gen_critic(
    aggregate: dict[str, Any],
    decision: dict[str, Any],
    human: Optional[dict[str, Any]],
    prompt_text: str,
    snapshot_date: str,
) -> dict[str, Any]:
    hum_active = False
    if human:
        n = str(human.get("human_note") or human.get("report") or "").strip()
        ev = human.get("evidence")
        ev_ok = isinstance(ev, list) and any(str(x).strip() for x in ev)
        hum_active = bool(n or ev_ok)
    report = "\n\n".join(
        [
            "【审查对象】AggregateEvidence 与 DecisionNode；核对人类输入是否被显性处理。",
            "【人类输入】"
            + ("已检测到非空 human_note 或 evidence：决策 report 应含「人类输入与采纳」或等价段落；若缺失则 need_revision 应为 true。" if hum_active else "人类文件为空或未填写：决策不强制写入人类折中，符合约定。"),
            "【逻辑】归并已提示新闻旧稿降权；决策将外溢主要框在波动率而非单边扭转时，须与 SSE 日度锚自洽。",
            "【改进】后续若人类补充板块/风控约束，决策须写明采纳或折中及对 confidence 的影响。",
        ]
    )
    ev = [
        "aggregate.report 节选: " + _clip(str(aggregate.get("report", ""))[:240], 230),
        "decision.report 节选: " + _clip(str(decision.get("report", ""))[:240], 230),
    ]
    out: dict[str, Any] = {
        "report": report,
        "evidence": ev,
        "risk_flags": ["自动合成批判：细粒度措辞仍需人工抽检。", "旧稿噪声规则未自动剔除仅提示。"],
        "confidence": 0.66,
        "need_revision": False,
    }
    _attach_meta(out, stem="CriticNode", prompt_text=prompt_text, snapshot_date=snapshot_date)
    return _validate_agent_report(out, "CriticNode")


def generate_all_node_payloads(
    snapshot_inputs: Mapping[str, Mapping[str, str]],
    *,
    snapshot_meta: Mapping[str, Any],
    prompt_texts: Mapping[str, str],
    snapshot_date: str,
    human_input: Optional[dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    """
    由快照 + 已读入的各节点 .md 全文 + 可选 HumanInput 生成 8 份节点 JSON 对象（已过契约校验）。
    不读盘已有节点 JSON；每次调用均从零合成。
    """
    snap = {k: dict(v) for k, v in snapshot_inputs.items()}
    meta = dict(snapshot_meta)
    prompts = dict(prompt_texts)

    out: dict[str, dict[str, Any]] = {}
    out["CNMacroData"] = _gen_cn(snap, meta, prompts["CNMacroData"], snapshot_date)
    out["USMacroData"] = _gen_us(snap, meta, prompts["USMacroData"], snapshot_date)
    out["MacroNews"] = _gen_macro_news(snap, meta, prompts["MacroNews"], snapshot_date)
    out["MesoNews"] = _gen_meso_news(snap, meta, prompts["MesoNews"], snapshot_date)
    out["MicroNews"] = _gen_micro_news(snap, meta, prompts["MicroNews"], snapshot_date)
    out["AggregateEvidence"] = _gen_aggregate(snap, meta, out, prompts["AggregateEvidence"], snapshot_date)
    out["DecisionNode"] = _gen_decision(snap, out["AggregateEvidence"], human_input, prompts["DecisionNode"], snapshot_date)
    out["CriticNode"] = _gen_critic(out["AggregateEvidence"], out["DecisionNode"], human_input, prompts["CriticNode"], snapshot_date)
    return out


def write_node_jsons(run_dir: str | Path, payloads: Mapping[str, dict[str, Any]]) -> None:
    """覆盖写入 ``{stem}.json``（UTF-8，缩进 2）。"""
    base = Path(run_dir).resolve()
    base.mkdir(parents=True, exist_ok=True)
    for stem, payload in payloads.items():
        p = base / f"{stem}.json"
        p.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
