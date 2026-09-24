# M1 Starter Prompts (copy/paste)

## Agent C launch (dispatch now)

Attach:
- `docs/orchestration/prompts/agent-C-edition-engine.md`
- `docs/orchestration/dispatches/M1-C-LAYOUT-BOOTSTRAP-W1.md`

Prompt text:

```text
You are Agent C. Follow the attached role prompt and the attached dispatch contract exactly.

Execute only the scope in M1-C-LAYOUT-BOOTSTRAP-W1.
Provide progress updates at 30%, 70%, and 100%.
At 100%, return using the exact return format from the contract, including:
- changed files
- objective evidence
- failure-path checks
- known limitations
- next handoff notes

If blocked, stop and return blocked-state format exactly.
```

## Agent D launch (prepare now, send after C accepted)

Attach:
- `docs/orchestration/prompts/agent-D-render-print-cloud.md`
- `docs/orchestration/dispatches/M1-D-A4-RENDER-W2.md`

Prompt text:

```text
You are Agent D. Follow the attached role prompt and the attached dispatch contract exactly.

Execute only the scope in M1-D-A4-RENDER-W2.
Do not start until M1-C-LAYOUT-BOOTSTRAP is accepted and its outputs are attached.
Provide progress updates at 30%, 70%, and 100%.
At 100%, return using the exact return format from the contract, including:
- changed files
- objective evidence
- failure-path checks
- known limitations
- next handoff notes

If blocked, stop and return blocked-state format exactly.
```
