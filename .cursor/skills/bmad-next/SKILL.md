---
name: bmad-next
description: >
  Answers "what next", "I have an idea", or "I have a thing" with the next BMad
  skill only. Use when the user asks what to do next, brings an idea, or brings
  something already made.
---

# Next step

Reply in this shape and stop. Do not add a method overview.

```
Next: `<skill>`
Agent: `<skill>` or none
Give it: one line
Then:
1. `<skill>` — when
```

`Agent` is `none` unless the user asked for a person to think with. When they did, name that phase's agent skill.

Read the project before choosing. Run:

`uv run _bmad/scripts/resolve_config.py --project-root . --key core.output_folder --key core.active_initiative`

Then list the folders in the active initiative and at the root of the output folder.

Use the smallest path:

- One obvious edit, such as a typo, formatting, or config change, needs no skill. Set `Next` to `none`.
- One real change is `bmad-build`.
- A larger intent the user can already explain is `bmad-spec`, then `bmad-ticket`, then `bmad-build` once per story.
- A larger idea that is not written down yet uses one of `bmad-forge-idea`, `bmad-prfaq`, `bmad-product-brief`, `bmad-prd`, `bmad-ux`, or `bmad-architecture`.
- After a planning skill, the usual next step is `bmad-spec`.

`Give it` is one line naming the input to hand the next skill. `Then` lists only the later skills on that same path, each with when it runs.
