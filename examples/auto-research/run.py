from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from agentworld.apps.auto_research import run_auto_research


def main() -> None:
    args = parse_args()
    goal = resolve_goal(args)
    result = run_auto_research(
        goal=goal,
        runs_dir=args.runs_dir,
        run_id=args.run_id,
        backend="claude-code",
        approval_mode=args.approval_mode,
        model=args.model,
        claude_command=args.claude_command,
        permission_mode=args.permission_mode,
        tools=args.tools,
        timeout_s=args.timeout,
        max_attempts=args.max_attempts,
    )
    print(json.dumps(
        {
            "success": result.success,
            "run_root": str(result.workspace.run_root),
            "approved_stages": list(result.approved_stages),
            "failed_stage": result.failed_stage,
            "errors": list(result.errors),
        },
        indent=2,
        ensure_ascii=True,
    ))
    if not result.success:
        raise SystemExit(1)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run a real AutoR-style workflow on AgentWorld.")
    parser.add_argument("goal", nargs="?", help="Research goal. Use --goal-file for a longer brief.")
    parser.add_argument("--goal-file", type=Path, help="Path to a markdown or text research brief.")
    parser.add_argument("--runs-dir", type=Path, default=Path(__file__).resolve().parent / "runs")
    parser.add_argument("--run-id", help="Optional run id. Defaults to a timestamp.")
    parser.add_argument("--claude-command", default="claude", help="Claude Code CLI command.")
    parser.add_argument("--model", help="Claude model name passed through to Claude Code.")
    parser.add_argument("--timeout", type=int, default=14400, help="Per-stage timeout in seconds.")
    parser.add_argument("--max-attempts", type=int, default=3)
    parser.add_argument(
        "--permission-mode",
        default="default",
        choices=["acceptEdits", "bypassPermissions", "default", "dontAsk", "plan", "auto"],
    )
    parser.add_argument(
        "--tools",
        nargs="*",
        default=["Read", "Write", "Edit", "Bash", "Grep", "Glob"],
        help="Claude Code tools allowed for each stage.",
    )
    parser.add_argument(
        "--approval-mode",
        choices=["manual", "validation-only"],
        default="manual",
        help="manual asks for human approval at every stage; validation-only approves after validation passes.",
    )
    return parser.parse_args()


def resolve_goal(args: argparse.Namespace) -> str:
    if args.goal_file:
        return args.goal_file.read_text(encoding="utf-8").strip()
    if args.goal:
        return args.goal.strip()
    raise SystemExit("Provide a research goal or --goal-file.")


if __name__ == "__main__":
    main()
