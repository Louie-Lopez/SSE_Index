# 【CLI】从分片快照 + 各节点 prompt_md 覆盖生成当日 8 个节点 JSON；不覆盖 HumanInput 占位正文。
# 默认：**本地推理**（GOT_LOCAL_INFER 子进程 + stdin）；``--synth-fallback`` 为离线模版（snapshot_synth_v1）。
# 调用方：``python -m src.got_mvp.generate_agent_outputs``；或由 ``run_mvp --generate-agent-first`` 链式调用。
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from .support.agent_local_infer import generate_all_via_local_infer
from .support.agent_snapshot_generator import (
    generate_all_node_payloads,
    load_node_prompt_texts,
    read_snapshot_meta_json,
    write_node_jsons,
)
from .support.local_infer_runner import LocalInferRunner
from .support.node_output_json import ensure_human_input_stub, load_optional_human_input
from .support.snapshot_loader import (
    read_snapshot_inputs,
    resolved_agent_outputs_dir,
    resolved_snapshot_date,
    resolved_snapshot_dir,
)


def resolve_backend(*, infer_local: bool, synth_fallback: bool) -> str:
    if infer_local and synth_fallback:
        raise ValueError("--infer-local 与 --synth-fallback 互斥。")
    if synth_fallback:
        return "synth"
    has_infer = bool(os.getenv("GOT_LOCAL_INFER", "").strip())
    if infer_local:
        if not has_infer:
            raise ValueError("--infer-local 需要已设置环境变量 GOT_LOCAL_INFER（子进程 argv，提示词走 stdin）。")
        return "infer"
    if has_infer:
        return "infer"
    raise ValueError(
        "生成 8 节点须使用本地推理：请设置环境变量 GOT_LOCAL_INFER（示例：claude -p -），"
        "或显式传入 --infer-local（仍会要求 GOT_LOCAL_INFER）；"
        "离线/CI 仅可改用 --synth-fallback。"
    )


def run_generate_agent_outputs(
    agent_parent: str,
    snapshot_date: str = "",
    *,
    print_summary: bool = False,
    infer_local: bool = False,
    synth_fallback: bool = False,
) -> str:
    """
    进程内入口：设置 GOT_SNAPSHOT_DATE（若传入）、读快照与各节点 .md、覆盖写入 8 个节点 JSON。
    默认 backend：已设置 GOT_LOCAL_INFER → ``infer``；否则须 ``--synth-fallback``。
    返回当日运行目录绝对路径字符串。
    """
    if snapshot_date.strip():
        os.environ["GOT_SNAPSHOT_DATE"] = snapshot_date.strip()

    ap = agent_parent.strip()
    if not ap:
        raise ValueError("agent_parent 为空：请传入 Agent 输出父目录。")

    day = resolved_snapshot_date()
    run_dir = resolved_agent_outputs_dir(ap)
    Path(run_dir).mkdir(parents=True, exist_ok=True)
    ensure_human_input_stub(run_dir)

    snapshot = read_snapshot_inputs()
    meta = read_snapshot_meta_json(resolved_snapshot_dir())
    if meta.get("snapshot_date") and meta["snapshot_date"] != day:
        raise ValueError(
            f"meta.json snapshot_date={meta.get('snapshot_date')!r} 与当前解析日 {day!r} 不一致。"
        )

    prompts = load_node_prompt_texts()
    human = load_optional_human_input(run_dir)
    backend = resolve_backend(infer_local=infer_local, synth_fallback=synth_fallback)

    if backend == "infer":
        runner = LocalInferRunner.from_env()
        payloads = generate_all_via_local_infer(
            snapshot,
            snapshot_meta=meta,
            prompt_texts=prompts,
            snapshot_date=day,
            human_input=human,
            runner=runner,
        )
    else:
        payloads = generate_all_node_payloads(
            snapshot,
            snapshot_meta=meta,
            prompt_texts=prompts,
            snapshot_date=day,
            human_input=human,
        )

    write_node_jsons(run_dir, payloads)

    if print_summary:
        brief = {
            k: {
                "confidence": v.get("confidence"),
                "engine": (v.get("_generator") or {}).get("engine"),
            }
            for k, v in payloads.items()
        }
        print(json.dumps({"agent_outputs_dir": run_dir, "backend": backend, "nodes": brief}, ensure_ascii=False, indent=2))
    return run_dir


def main() -> None:
    parser = argparse.ArgumentParser(
        description="读取 snapshot_{YYYY-MM-DD}/ 与 prompt_md/节点/*.md，覆盖写入 agent_outputs/YYYY-MM-DD/ 下 8 个节点 JSON。"
    )
    parser.add_argument(
        "--snapshot-date",
        default="",
        metavar="YYYY-MM-DD",
        help="与分片快照目录名一致；默认环境变量 GOT_SNAPSHOT_DATE 或当天",
    )
    parser.add_argument(
        "--agent-dir",
        default=os.getenv("GOT_AGENT_OUTPUT_DIR", ""),
        help="Agent JSON 父目录，写入 父目录/YYYY-MM-DD/*.json",
    )
    parser.add_argument(
        "--print-summary",
        action="store_true",
        help="向 stdout 打印各节点 stem 与 confidence（UTF-8）。",
    )
    parser.add_argument(
        "--infer-local",
        action="store_true",
        help="强制走本地推理（仍须设置 GOT_LOCAL_INFER）；与 --synth-fallback 互斥。",
    )
    parser.add_argument(
        "--synth-fallback",
        action="store_true",
        help="使用 snapshot_synth_v1 模版生成（离线/CI）；与真实 prompt 驱动推理无关。",
    )
    args = parser.parse_args()

    agent_parent = (args.agent_dir or "").strip()
    if not agent_parent:
        raise SystemExit(
            "请指定 --agent-dir（Agent 输出父目录）或设置 GOT_AGENT_OUTPUT_DIR。"
        )

    try:
        run_generate_agent_outputs(
            agent_parent,
            args.snapshot_date,
            print_summary=args.print_summary,
            infer_local=args.infer_local,
            synth_fallback=args.synth_fallback,
        )
    except ValueError as e:
        raise SystemExit(str(e)) from e


if __name__ == "__main__":
    main()
