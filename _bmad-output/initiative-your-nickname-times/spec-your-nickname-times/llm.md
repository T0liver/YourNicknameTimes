# Language model

The model is reached through OpenRouter. The account is a funded key with 1,000 requests per day. Sending task text to free providers is an accepted tradeoff, because those providers may log prompts. A titles-only switch still exists.

## Modes

1. **On** (default). The full paper, including the two calls below.
2. **Degraded.** The model is on, and a call failed. That block uses its deterministic fallback. The run can finish as `done_degraded`.
3. **Off.** A global switch. The paper is always built with the deterministic rules. No model call is made.

Deterministic behavior:

- News: recency, plus per-feed weight, plus an interest keyword score, with the same quotas as a model pick.
- Prep for tomorrow: the plain list of tomorrow's items, with descriptions.
- Almanac and rates expand to fill space. See data-sources.md.

On a weekend with the mood set to `light`, and with the model off, hobby-category weights are raised instead of asking a picker. See edition.md.

## Calls

Two calls per edition, plus retries.

1. **News picker.** Input is a numbered list of titles and short snippets, plus the edition mood (`normal` or `light`). The list is capped at about 60 to 80 items. Output is JSON: `{"picks": [{"id": 12, "category": "interest"}]}`. Only IDs come back. The script prints the original headline, publisher, and time. Quotas are enforced in code after the model answers.
2. **Planner.** Input is tomorrow's tasks and events. Output is JSON with one note per item. Each note is at most 120 characters. A longer note is rejected.

## When a call fails

- Validate against a JSON schema. Unknown IDs are dropped. Notes over the character budget are rejected.
- One retry, with a stricter prompt. Then the deterministic fallback for that block.
- Default model: `openrouter/free`. The operator can pin a specific `:free` model or a paid model.
- The router may choose a different model on each call. The run report records the model that answered.
- Each call has a timeout. A daily request counter is shown on the dashboard so the 1,000-request limit is visible.

## Privacy

- The setting "send task descriptions to the model" defaults to on. Turning it off sends titles only.
- The exact prompt and response of every call are stored with the edition, so the operator can see what left the Pi.

## Copy rules

Planner text is Hungarian when the paper language is Hungarian. Quality from free models varies, which is one reason the picker returns only IDs.

The note is plain and literal.

- It does not personify the calendar or the tasks.
- It does not use an "X is not Y, it is Z" construction.
- It has no closing kicker.
- It gives no advice beyond the task's own text.
- It states no fact that is not in the item.
- Each planner note is at most 120 characters. That is about three lines in a span-2 column.

In the light weekend mood the tone may be a little warmer. The rules above still apply. The weekend wording also skips jokes, personification, and clever reversals.
