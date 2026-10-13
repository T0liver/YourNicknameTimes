# Edition

The morning paper is one A4 page. Dates, weekdays, and labels follow the paper language. A Hungarian dateline looks like `2026. szeptember 21., hétfő`. Typographic quotes follow the paper language. In Hungarian they are `„ ”`.

## Masthead

- Nameplate: `{Nickname} Times`, in the kit's masthead style. Until a nickname is saved, the text is "Your Nickname Times".
- Motto: an optional small line under the nameplate. Empty by default. When it is empty, the line collapses and leaves no gap.
- Dateline: `Vol. N · date · weekday · city · AS OF hh:mm`.
  - `Vol. N` is the edition counter stored in the database.
  - `AS OF` is the time data collection began, not the print time.
- Weekend edition, when that switch is on: a small sun icon beside the dateline and a short greeting line. Both are editable. The icon can be switched off. The icon is a static asset, not generated art.

## Blocks

| Block | Source | What it shows |
| --- | --- | --- |
| News | RSS | About 8 rows: headline, publisher, time. Last 24 hours. Split between interest and local by quota. No model-written prose. |
| Today | CalDAV | Events (time, title, place) and tasks due today (title, short description). Undated open tasks go on a separate "anytime" line. |
| This week | CalDAV | The next 7 days, grouped by day: events and due tasks. |
| Weather | Open-Meteo | Today high and low, a short summary, and a 3-4 day outlook. On failure the block says "Forecast unavailable" and prints no guessed numbers. |
| Prep for tomorrow | CalDAV, and the model when it is on | Tomorrow's events and tasks. With the model: one short preparation note per item, grounded only in that item's text. Without the model: the plain list. |
| Due this week | CalDAV | Open tasks due in the next 7 days, excluding today and tomorrow. |
| Overdue | CalDAV | Open tasks due before today, oldest first, each with "N days overdue". |
| Daily item | code or xkcd | One comic or one puzzle. See data-sources.md. |
| Almanac and rates | local computation or APIs | Sunrise and sunset, moon phase, name day, on this day, and EUR/HUF, USD/HUF, CHF/HUF. See data-sources.md. |

An empty block collapses and its neighbors widen. The page does not print "None" in a box.

## Weekend edition

When the weekend switch is on, Saturday and Sunday use a lighter edition.

- Schedule: its own start time, default 08:00.
- News mood: the picker prefers upbeat, hobby, and human-interest items over conflict, crime, or disaster headlines. A local item that is directly relevant is still allowed. A setting chooses `light` or `neutral`. Without the model, hobby-category weights are raised instead.
- Notes: planner notes are a little friendlier and stay plain. The copy rules in llm.md still apply.
- Daily item: easy sudoku, in a larger box.
- Small touches: the sun icon and a short greeting, both editable, icon optional. The greeting defaults to "Yippie, weekend! You earned it!".
- Tasks: a compressed band, so the lighter material has more room.

The weekday edition uses none of these.

## Layout

Turn `The-Firstname-Times-Setup-Kit-v17.3/layout/template.html` into one Jinja2 template. Keep that kit's `edition.css`, the table-based grid, and WeasyPrint. Fonts (Chomsky, Libre Franklin, Newsreader) load from the kit's `fonts/` folder. Those three faces are under the SIL Open Font License 1.1, so the app may ship them under that license. The rest of the kit stays local and gitignored. WeasyPrint is the only renderer.

The kit's own page is US Letter and four pages. This app is one A4 page. The kit measures US Letter as 8.5 in wide, 0.32 in margins, 7.86 in of content. A4 is 8.27 in wide. Keeping the 0.32 in margins leaves 7.63 in of content.

- 6 columns of about 1.197 in, with 0.09 in gutters.
- Span-4 is about 5.06 in. Span-2 is about 2.48 in.
- `@page { size: A4; margin: 0 }`. A4 is about 0.69 in taller than Letter.

The source gives these measures as the proposed grid. Milestone 1 checks them by rendering.

### Glyphs and hyphenation

- Hungarian `ő` and `ű` render in every font on the page, especially the Chomsky nameplate, because a nickname may contain them. A missing glyph uses a fallback font for that character, or the dashboard warns.
- `lang="hu"` hyphenation in WeasyPrint is tested on real headlines.
- Quotes follow the paper language, as above.

## Overflow

Render, then count pages. If there is more than one page, drop the lowest-priority item and render again. Body type is not shrunk. Drop order, first to last:

1. Almanac details.
2. Extra week rows.
3. Extra news rows.
4. Descriptions.
5. Second-tier prep notes.

Every drop is written to the run report. If the PDF still cannot be built, or still exceeds one page, the run fails and nothing prints.

## Two PDFs

Each edition writes two PDFs from the same content snapshot, so they cannot drift apart.

- `print.pdf` is the full edition.
- `cloud.pdf` is trimmed unless the cloud level is set to full. The trimmed copy omits task descriptions, event locations, attendees, and prep notes.
