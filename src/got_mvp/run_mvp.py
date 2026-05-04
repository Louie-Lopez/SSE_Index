# 【CLI】解析参数，调用 graph.run_graph 与 evaluation，向 stdout 打印汇总 JSON；支持 ``--decision-only`` / ``GOT_DECISION_ONLY``。
# 调用方：人工 ``python -m src.got_mvp.run_mvp``。
from __future__ import annotations

import argparse
import json
import os

from .evaluation import evaluate_run, format_logs
from .generate_agent_outputs import run_generate_agent_outputs
from .graph import run_graph


def main() -> None:
    parser = argparse.ArgumentParser(
        description="GoT MVP：从 Agent 目录读 JSON；首次运行会在该目录自动生成 HumanInput_{D}.json 占位（不覆盖已有）。"
    )
    parser.add_argument(
        "--snapshot-date",
        default="",
        metavar="YYYY-MM-DD",
        help="快照输入（snapshot_inputs）与 Agent 子目录使用此日期；默认当天（GOT_SNAPSHOT_DATE）",
    )
    parser.add_argument(
        "--agent-dir",
        default=os.getenv("GOT_AGENT_OUTPUT_DIR", ""),
        help="Agent JSON 父目录，实际读取 父目录/YYYY-MM-DD/（日期与 --snapshot-date 或 GOT_SNAPSHOT_DATE 一致）；环境变量 GOT_AGENT_OUTPUT_DIR",
    )
    parser.add_argument(
        "--decision-only",
        action="store_true",
        help="仅重跑决策链读盘与 evaluation：保持五路与归并等 JSON 不变，先更新 HumanInput_{D}.json 与/或 DecisionNode.json；不经过 LangGraph 批判回流",
    )
    parser.add_argument(
        "--generate-agent-first",
        action="store_true",
        help="在跑图前执行 generate_agent_outputs：按当日快照与各节点 .md 覆盖写入 8 个节点 JSON（不覆盖 HumanInput 已有文件正文）。",
    )
    parser.add_argument(
        "--infer-local",
        action="store_true",
        help="与 --generate-agent-first 联用：强制本地推理（须 GOT_LOCAL_INFER）；与 --synth-fallback 互斥。",
    )
    parser.add_argument(
        "--synth-fallback",
        action="store_true",
        help="与 --generate-agent-first 联用：使用 snapshot_synth_v1 离线模版，不要求本地 CLI。",
    )
    args = parser.parse_args()
    if args.snapshot_date.strip():
        os.environ["GOT_SNAPSHOT_DATE"] = args.snapshot_date.strip()

    decision_only = args.decision_only or os.getenv("GOT_DECISION_ONLY", "").strip().lower() in (
        "1",
        "true",
        "yes",
        "on",
    )

    agent_dir = (args.agent_dir or "").strip()
    if not agent_dir:
        raise SystemExit(
            "请指定 Agent 输出父目录: python -m src.got_mvp.run_mvp --agent-dir 父目录\n"
            "（读取 父目录/YYYY-MM-DD/ 下各节点 JSON）或设置 GOT_AGENT_OUTPUT_DIR。"
        )

    if args.generate_agent_first:
        if decision_only:
            raise SystemExit("--generate-agent-first 与 --decision-only 互斥。")
        if args.infer_local and args.synth_fallback:
            raise SystemExit("--infer-local 与 --synth-fallback 互斥。")
        try:
            run_generate_agent_outputs(
                agent_dir,
                args.snapshot_date,
                print_summary=False,
                infer_local=args.infer_local,
                synth_fallback=args.synth_fallback,
            )
        except ValueError as e:
            raise SystemExit(str(e)) from e

    state = run_graph(agent_outputs_dir=agent_dir, decision_only=decision_only)
    report = evaluate_run(state)
    output = {
        "final_output": state["final_output"],
        "aggregate": state["aggregate"],
        "human_input_for_decision": state.get("human_input_for_decision"),
        "critic": state["critic"],
        "evaluation": report,
        "observability": {
            "agent_outputs_dir": state.get("agent_outputs_dir"),
            "decision_only": decision_only,
            "evaluation_output_path": report.get("evaluation_output_path"),
            "elapsed_ms": state["meta"]["elapsed_ms"],
            "token_estimates": state["meta"]["token_estimates"],
            "prompt_versions": state["meta"]["prompt_versions"],
            "logs": format_logs(state),
        },
    }
    print(json.dumps(output, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
