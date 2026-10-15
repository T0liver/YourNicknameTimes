- source_plan: `_bmad-output/initiative-your-nickname-times/epic-morning-edition/story-serve-the-dashboard-and-status-plan.md`
  summary: An empty OpenRouter key marks the edition degraded in `meta.mode` and leaves `/status` ok.
  evidence: `apply_model` returns before it sets `sources.model`. `/status` turns the model check yellow only when that field is `failed`.

- source_plan: `_bmad-output/initiative-your-nickname-times/epic-morning-edition/story-harden-lan-access-plan.md`
  summary: A failed settings read on `/status` can skip the bearer check if a second read then succeeds.
  evidence: `_status_denied` treats any exception as not denied. `build_report` returns the down shell when the database is still unreadable, so the usual JSON shows up only when the second read works. A test that fails the first read and lets the second succeed would settle it.
