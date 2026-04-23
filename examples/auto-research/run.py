from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from agentworld.apps.auto_research import resume_auto_research, run_auto_research


def main() -> None:
    args = parse_args()
    progress_sink = None if args.quiet else print_progress
    if args.resume_run:
        if args.goal or args.goal_file:
            raise SystemExit("Do not provide a new goal when using --resume-run.")
        result = resume_auto_research(
            run_root=args.resume_run,
            backend="claude-code",
            approval_mode=args.approval_mode,
            model=args.model,
            claude_command=args.claude_command,
            permission_mode=args.permission_mode,
            tools=args.tools,
            timeout_s=args.timeout,
            max_attempts=args.max_attempts,
            progress_sink=progress_sink,
        )
    else:
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
            progress_sink=progress_sink,
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
    parser.add_argument("--resume-run", type=Path, help="Resume an existing run root instead of starting a new run.")
    parser.add_argument("--claude-command", default="claude", help="Claude Code CLI command.")
    parser.add_argument("--model", help="Claude model name passed through to Claude Code.")
    parser.add_argument("--timeout", type=int, default=14400, help="Per-stage timeout in seconds.")
    parser.add_argument("--max-attempts", type=int, default=3)
    parser.add_argument("--quiet", action="store_true", help="Only print the final JSON result.")
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


def print_progress(event: dict[str, Any]) -> None:
    kind = str(event.get("kind") or "")
    if kind == "run_started":
        print(
            "\n[run] started"
            f"\n  run_root: {event.get('run_root')}"
            f"\n  backend: {event.get('backend')}"
            f"\n  approval: {event.get('approval_mode')}"
            f"\n  stages: {event.get('stage_count')}",
            flush=True,
        )
        return
    if kind == "run_resumed":
        print(f"\n[run] resumed: {event.get('run_root')}", flush=True)
        return
    if kind == "stages_selected":
        stages = ", ".join(str(item) for item in event.get("stages", []))
        print(f"[run] stages selected: {stages or '(none)'}", flush=True)
        return
    if kind == "stage_started":
        mode = "resume" if event.get("continue_session") else "start"
        print(
            f"\n[stage] {event.get('stage_title')} | attempt {event.get('attempt')} | {mode}",
            flush=True,
        )
        return
    if kind == "operator_started":
        print(f"[agent] running Claude Code | prompt: {event.get('prompt_path')}", flush=True)
        return
    if kind == "operator_finished":
        print(
            "[agent] finished"
            f" | success={event.get('success')}"
            f" | events={event.get('event_count')}"
            f" | session={event.get('session_ref')}",
            flush=True,
        )
        return
    if kind == "controller_event":
        _print_controller_event(event)
        return
    if kind == "stage_validated":
        print(f"[stage] validation passed: {event.get('stage_title')}", flush=True)
        return
    if kind == "stage_repair_started":
        print(f"[stage] repair started: {event.get('stage_title')}", flush=True)
        for error in list(event.get("errors", []))[:5]:
            print(f"  - {error}", flush=True)
        return
    if kind == "stage_validation_failed":
        print(f"[stage] validation failed: {event.get('stage_title')}", flush=True)
        for error in list(event.get("errors", []))[:5]:
            print(f"  - {error}", flush=True)
        return
    if kind == "stage_awaiting_review":
        print(
            f"[review] awaiting approval: {event.get('stage_title')}"
            f"\n  draft: {event.get('draft_path')}",
            flush=True,
        )
        return
    if kind == "stage_approved":
        print(
            f"[stage] approved: {event.get('stage_title')}"
            f"\n  final: {event.get('final_path')}",
            flush=True,
        )
        return
    if kind == "stage_refine_requested":
        print(f"[stage] refinement requested: {event.get('stage_title')}", flush=True)
        return
    if kind == "stage_aborted":
        print(f"[stage] aborted: {event.get('stage_title')} | {event.get('reason')}", flush=True)
        return
    if kind == "stage_failed":
        print(f"[stage] failed: {event.get('stage_title')} | {event.get('error')}", flush=True)
        return
    if kind == "run_failed":
        print(f"\n[run] failed at {event.get('failed_stage')}", flush=True)
        for error in list(event.get("errors", []))[:10]:
            print(f"  - {error}", flush=True)
        return
    if kind == "run_completed":
        print(f"\n[run] completed: {event.get('run_root')}", flush=True)
        return


def _print_controller_event(event: dict[str, Any]) -> None:
    event_kind = str(event.get("controller_event_kind") or "")
    payload = event.get("payload")
    if not isinstance(payload, dict):
        payload = {}
    if event_kind == "session_started":
        tools = payload.get("tools") or []
        print(
            "[claude] session started"
            f" | model={payload.get('model')}"
            f" | permission={payload.get('permission_mode')}"
            f" | tools={len(tools)}",
            flush=True,
        )
        return
    if event_kind == "tool_call":
        print(f"[claude] tool call: {payload.get('name')}", flush=True)
        return
    if event_kind == "tool_result":
        print(f"[claude] tool result: {payload.get('tool_use_id')}", flush=True)
        return
    if event_kind == "message_completed":
        text = _compact(str(payload.get("text") or ""))
        if text:
            print(f"[claude] {text}", flush=True)
        return
    if event_kind == "completed":
        duration = payload.get("duration_ms")
        suffix = f" | duration_ms={duration}" if duration is not None else ""
        print(f"[claude] completed{suffix}", flush=True)
        return
    if event_kind == "failed":
        print(f"[claude] failed: {payload.get('message')}", flush=True)
        return


def _compact(text: str, limit: int = 500) -> str:
    compacted = " ".join(text.split())
    if len(compacted) <= limit:
        return compacted
    return compacted[: limit - 3].rstrip() + "..."


if __name__ == "__main__":
    main()
