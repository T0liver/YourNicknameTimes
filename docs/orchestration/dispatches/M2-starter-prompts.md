# M2 Starter Prompts (copy/paste)

## Agent B launch (dispatch now)

Attach:
- `docs/orchestration/prompts/agent-B-data-integration.md`
- `docs/orchestration/dispatches/M2-B-FULL-SOURCES-W3.md`

Prompt text:

```text
You are Agent B. Follow the attached role prompt and the attached dispatch contract exactly.

Execute only the scope in M2-B-FULL-SOURCES-W3.
Provide progress updates at 30%, 70%, and 100%.
At 100%, return using the exact return format from the contract, including:
- changed files
- objective evidence
- failure-path checks
- known limitations
- next handoff notes

If blocked, stop and return blocked-state format exactly.
```

## Agent C launch (prepare now, send after B accepted)

Attach:
- `docs/orchestration/prompts/agent-C-edition-engine.md`
- `docs/orchestration/dispatches/M2-C-DETERMINISTIC-EDITION-W3.md`

Prompt text:

```text
You are Agent C. Follow the attached role prompt and the attached dispatch contract exactly.

Execute only the scope in M2-C-DETERMINISTIC-EDITION-W3.
Do not start until M2-B-FULL-SOURCES is accepted and its outputs are attached.
Provide progress updates at 30%, 70%, and 100%.
At 100%, return using the exact return format from the contract, including:
- changed files
- objective evidence
- failure-path checks
- known limitations
- next handoff notes

If blocked, stop and return blocked-state format exactly.
```
