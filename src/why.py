"""ZizkaDB Why: explain why an AI agent did what it did, in the job summary and PR."""

from __future__ import annotations

import re
import sys
import urllib.error

import zizkadb_ci as z

MARKER = "<!-- zizkadb-why-action -->"
FAILURE = re.compile(r"error|fail|exception|denied|reject|timeout|crash|abort", re.I)
LABEL_KEYS = ("tool", "name", "text", "message", "content", "query", "input",
              "output", "result", "status", "error", "reason")


def is_failure(event: dict) -> bool:
    if FAILURE.search(event.get("event") or ""):
        return True
    data = event.get("data") or {}
    if any(k in data for k in ("error", "exception", "traceback")):
        return True
    return str(data.get("status", "")).lower() in ("error", "failed", "failure")


def label(event: dict, show_data: bool) -> str:
    name = f"`{event.get('event')}`"
    if not show_data:
        return name
    data = event.get("data") or {}
    for key in LABEL_KEYS:
        if data.get(key) not in (None, "", [], {}):
            return f"{name} · {key}: “{z.short(data[key])}”"
    return name


def pick_focus(events: list[dict], max_chains: int) -> list[dict]:
    """Failures first (newest first); otherwise the last step of each session."""
    failures = [e for e in events if is_failure(e)]
    if failures:
        return failures[:max_chains]
    seen, focus = set(), []
    for e in events:  # newest first
        key = e.get("session_id") or "_"
        if key not in seen:
            seen.add(key)
            focus.append(e)
    return focus[:max_chains]


def render_chain(why: dict, anchor: dict, show_data: bool) -> str:
    chain = why.get("chain") or []
    failed = is_failure(anchor)
    head = "❌" if failed else "🔎"
    lines = [f"#### {head} Why did **{anchor.get('agent')}** do {label(anchor, False)}?\n"]
    for i, step in enumerate(chain, 1):
        mark = " ← **this step**" if step.get("event_id") == anchor.get("event_id") else ""
        lines.append(f"{i}. {label(step, show_data)} <sub>`{step['event_id'][:8]}`</sub>{mark}")
    if chain and len(chain) > 1:
        root = chain[0]
        lines.append(f"\n**Root cause:** {label(root, show_data)}, "
                     f"{len(chain) - 1} step{'s' if len(chain) > 2 else ''} before.")
    if why.get("orphan"):
        lines.append("\n> The chain points to a parent step that was never recorded (or was deleted).")
    elif len(chain) <= 1 or not why.get("chain_complete", True):
        lines.append(
            f"\n> This step has no recorded cause. Pass `parent_id` when you log each step "
            f"to see the full chain: [how]({z.CONNECT_URL})")
    if why.get("depth_truncated"):
        lines.append("\n> Chain shortened to the 25 most recent steps.")
    return "\n".join(lines) + "\n"


def empty_state() -> str:
    return (
        "### ZizkaDB Why: no agent steps were recorded\n\n"
        "Your command ran, but your agent did not log to ZizkaDB. "
        "`ZIZKADB_HOST` and `ZIZKADB_API_KEY` are already set in its environment; "
        "add a few lines and run again:\n\n"
        "```python\n"
        "from zizkadb import ZizkaDB   # pip install zizkadb-sdk\n"
        "async with ZizkaDB() as db:  # uses ZIZKADB_HOST and ZIZKADB_API_KEY\n"
        "    ask = await db.log(agent=\"my-agent\", event=\"user_message\", data={\"text\": question})\n"
        "    await db.log(agent=\"my-agent\", event=\"tool_call\", data={\"tool\": \"search\"}, parent_id=ask.event_id)\n"
        "```\n\n"
        f"LangChain, CrewAI, LangGraph, LiveKit, TypeScript and MCP: [connect your agent]({z.CONNECT_URL}).\n\n"
        "**What you will see here once it logs:**\n\n"
        "1. `user_message` · text: “Refund order 42”\n"
        "2. `tool_call` · tool: “lookup_order”\n"
        "3. `tool_result` · status: “delivered”\n"
        "4. `tool_call` · tool: “refund” ← **this step**\n\n"
        "**Root cause:** `user_message` · text: “Refund order 42”, 3 steps before.\n"
    )


def main() -> int:
    command = z.env("INPUT_RUN")
    host = z.env("INPUT_HOST")
    key = z.env("INPUT_API_KEY")
    max_chains = int(z.env("INPUT_MAX_CHAINS", "5") or 5)
    show_data = z.truthy("INPUT_SHOW_DATA")
    artifact = z.env("INPUT_ARTIFACT_NAME", "zizkadb-history")

    started = z.now_iso()
    if not host:
        if not command:
            raise SystemExit("Set `run` (the command that runs your agent), or `host` for an existing ZizkaDB.")
        host = z.start_local(z.env("INPUT_IMAGE", "ghcr.io/zizka-ai-sl/zizkadb:latest"))
        key = z.LOCAL_KEY
        since = None
    else:
        if not key:
            raise SystemExit("`api-key` is required with `host`.")
        since = started  # only this run's events on a shared instance
    zenv = {"ZIZKADB_HOST": host, "ZIZKADB_API_KEY": key}
    z.export_env(zenv)

    exit_code, output = (z.run_command(command, zenv) if command else (0, ""))
    api = z.Api(host, key)

    try:
        agents = [a["agent"] for a in api.agents()]
        wanted = [a.strip() for a in z.env("INPUT_AGENTS").split(",") if a.strip()]
        if wanted:
            agents = [a for a in agents if a in wanted]
        per_agent = {a: api.events(a, after=since) for a in agents}
    except (urllib.error.URLError, OSError) as e:
        z.write_summary(f"### ZizkaDB Why\n\nCould not read from ZizkaDB at `{host}`: {e}\n\n{z.FOOTER}")
        return exit_code or 1

    events_total = sum(len(v) for v in per_agent.values())
    body: list[str] = []
    chains = 0
    if events_total == 0:
        body.append(empty_state())
    else:
        failed_any = any(is_failure(e) for evs in per_agent.values() for e in evs)
        title = "Why your agent failed" if failed_any else "What your agent did, and why"
        body.append(f"### ZizkaDB Why: {title}\n")
        body.append(f"{events_total} steps recorded from {len(per_agent)} agent"
                    f"{'s' if len(per_agent) != 1 else ''} in this run.\n")
        for agent, events in per_agent.items():
            for anchor in pick_focus(events, max_chains - chains):
                try:
                    body.append(render_chain(api.why(anchor["event_id"]), anchor, show_data))
                    chains += 1
                except urllib.error.HTTPError as e:
                    body.append(f"> Could not load the chain for `{anchor['event_id']}` (HTTP {e.code}).\n")
            if chains >= max_chains:
                break
        if any(per_agent.values()):
            z.save_history(api, [a for a, evs in per_agent.items() if evs], "zizkadb-history")
            body.append(z.open_locally_markdown(artifact))

    if z.agent_limit_hit(output):
        body.append(z.agent_limit_markdown())
    body.append(z.FOOTER)
    report = "\n".join(body)

    z.write_summary(report)
    status = z.upsert_pr_comment(MARKER, report) if z.truthy("INPUT_COMMENT") else "disabled"
    z.log(f"PR comment: {status}")
    z.set_output("events", str(events_total))
    z.set_output("chains", str(chains))
    z.set_output("command-exit-code", str(exit_code))
    z.set_output("history-dir", "zizkadb-history" if events_total else "")
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
