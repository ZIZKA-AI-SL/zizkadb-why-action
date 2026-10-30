# ZizkaDB Why: explain AI agent failures in your PR

> Part of **[ZizkaDB](https://github.com/ZIZKA-AI-SL/ZizkaDB)**, the open-source causal database for AI agents.

[![OpenSSF Baseline](https://www.bestpractices.dev/projects/16048/baseline)](https://www.bestpractices.dev/projects/16048)
[![ZizkaDB](https://img.shields.io/github/stars/ZIZKA-AI-SL/ZizkaDB?label=ZizkaDB&style=flat)](https://github.com/ZIZKA-AI-SL/ZizkaDB)

Your agent test failed. Logs show *what* happened; this action shows **why**: the chain of steps that led to the failure, from the agent's final action back to the user message or tool result that caused it. It appears in the job summary and as a comment on the pull request.

```
❌ Why did refund-agent do tool_error?

1. user_message · text: "Refund order 42"
2. tool_call    · tool: "lookup_order"
3. tool_result  · status: "delivered"
4. tool_call    · tool: "refund"
5. tool_error   · error: "refund denied: order already delivered"   ← this step

Root cause: user_message · text: "Refund order 42", 4 steps before.
```

## Quick start

```yaml
permissions:
  contents: read
  pull-requests: write   # for the PR comment

jobs:
  agent-tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: "3.12" }
      - run: pip install -r requirements.txt zizkadb-sdk
      - uses: ZIZKA-AI-SL/zizkadb-why-action@v1
        with:
          run: pytest tests/agent
```

That is all. The action:

1. **Starts ZizkaDB inside the runner** (the open-source single container). No account, no API key, no secrets. **Your data never leaves the runner** and is deleted with the job.
2. **Runs your command** with `ZIZKADB_HOST` and `ZIZKADB_API_KEY` set, so the ZizkaDB SDK in your agent logs there automatically.
3. **Explains** failed steps (or, when nothing failed, the last step of each session) as causal chains, in the **job summary** and a **PR comment** that it updates on every push.
4. **Saves the history** as the `zizkadb-history` artifact, so you can open the exact run in the ZizkaDB dashboard on your machine.
5. **Fails the step** with your command's exit code, after the report is written.

## Make your agent log

If your agent does not log to ZizkaDB yet, the report tells you and shows the lines to add:

```python
from zizkadb import ZizkaDB   # pip install zizkadb-sdk

async with ZizkaDB() as db:  # uses ZIZKADB_HOST and ZIZKADB_API_KEY
    ask = await db.log(agent="my-agent", event="user_message", data={"text": question})
    await db.log(agent="my-agent", event="tool_call", data={"tool": "search"}, parent_id=ask.event_id)
```

`parent_id` is what links a step to its cause. LangChain, CrewAI, LangGraph, LiveKit, TypeScript and MCP: **[connect your agent](https://github.com/ZIZKA-AI-SL/ZizkaDB/blob/main/CONNECT.md)**.

## Inputs

| Input | Default | Description |
|-------|---------|-------------|
| `run` | | Command that runs your agent or its tests. Required unless `host` is set. |
| `host` | | Use an existing ZizkaDB instead of a local one, e.g. your self-hosted server. |
| `api-key` | | API key for `host`; pass it from a secret. |
| `agents` | all | Comma-separated agent names to report on. |
| `max-chains` | `5` | Most causal chains to show. |
| `show-data` | `true` | Show a short excerpt of each step's data. Set `false` if prompts are sensitive: PR comments and job summaries in public repos are public. |
| `comment` | `true` | Post and update a PR comment (needs `pull-requests: write`; fork PRs get the job summary only). |
| `image` | `ghcr.io/zizka-ai-sl/zizkadb:latest` | ZizkaDB image for the local instance; pin a version for reproducible runs. |
| `artifact-name` | `zizkadb-history` | Name of the uploaded history artifact. |
| `github-token` | `${{ github.token }}` | Token used for the PR comment. |

## Outputs

| Output | Description |
|--------|-------------|
| `events` | Agent steps recorded in this run |
| `chains` | Causal chains reported |
| `command-exit-code` | Exit code of `run` |

Later steps in the job also get `ZIZKADB_HOST` and `ZIZKADB_API_KEY`.

## Good to know

- **One agent per run.** The local instance is open-source ZizkaDB, which records one agent per install. If your tests log a second agent name, it is refused and the report says so. For many agents, fleets and agent-to-agent recording, see [ZizkaDB Cloud](https://db.zizka.ai).
- **Telemetry.** The ZizkaDB SDK in your agent sends an anonymous install count; set `ZIZKADB_TELEMETRY: "false"` in the job's `env` to turn it off. [Details](https://github.com/ZIZKA-AI-SL/ZizkaDB/blob/main/docs/telemetry.md).
- **Proving the history is intact** for audits: [ZizkaDB Audit](https://github.com/ZIZKA-AI-SL/zizkadb-audit-action).

## Beyond CI

ZizkaDB also runs on your machine and servers: causal `why()`, time travel with `at()`, memory for the next prompt, search, and a tamper-evident audit log, on Postgres.

**[⭐ Star ZizkaDB on GitHub](https://github.com/ZIZKA-AI-SL/ZizkaDB)** · [Run it locally in 60 seconds](https://github.com/ZIZKA-AI-SL/ZizkaDB#quickstart-60-seconds) · [Docs](https://db.zizka.ai/docs)

---

MIT licensed. Security issues: founder@zizka.ai ([policy](https://github.com/ZIZKA-AI-SL/ZizkaDB/blob/main/SECURITY.md)).
