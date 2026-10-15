- source_plan: `_bmad-output/initiative-your-nickname-times/epic-morning-edition/story-serve-the-dashboard-and-status-plan.md`
  summary: An empty OpenRouter key marks the edition degraded in `meta.mode` and leaves `/status` ok.
  evidence: `apply_model` returns before it sets `sources.model`. `/status` turns the model check yellow only when that field is `failed`.
