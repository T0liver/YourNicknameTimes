# Data sources

Dates and times are converted to the configured timezone. The default is Europe/Budapest. Both date-only and date-time values are handled.

## CalDAV (Baïkal)

Calendar and tasks are the same CalDAV server. The dashboard lists every calendar and task list on that server, with the component types each one supports (`VEVENT`, `VTODO`), and the operator ticks which to include.

The host, username, and password are settings. A fresh install leaves the host empty. No personal server address is written into the code or the default config.

- Events are read with `search(expand=True)`, so a repeating event appears on the right days.
- Tasks read `SUMMARY`, `DESCRIPTION`, `DUE`, `PRIORITY`, `STATUS`, and `CATEGORIES`. Completed and cancelled tasks are ignored. A recurring task shows the current occurrence only.
- Auth is Basic or Digest. HTTPS is recommended.

Block placement for these records is in edition.md.

## RSS

No feed URL is written into the fetch code. Each feed has a URL, a name used as the publisher, a category (`interest` or `local`), a language, a weight, a max item count, and an enabled flag.

A fresh install starts with two feeds, stored as settings rows so they can be edited or removed:

| Name | URL | Category |
| --- | --- | --- |
| Telex | `https://telex.hu/rss` | local |
| Wired | `https://www.wired.com/feed/rss` | interest |

- Keep entries from the last 24 hours by published time.
- Deduplicate by URL, then by fuzzy title.
- Entries with no publish time are excluded unless that setting is turned off.
- OPML import and export both work.
- The pool sent to the model is capped at about 60 to 80 items. See llm.md.

The printed row is headline, publisher, and time. Code enforces a quota of about four interest items and about four local items. The model does not write the headline.

## Weather

Open-Meteo. Location coordinates and units are settings. Failure behavior is in edition.md: the text "Forecast unavailable", and no guessed numbers.

## Daily item

A rotation table maps each weekday to a type. The operator can change it. The default is xkcd on Monday, Wednesday, Friday, and Sunday, and sudoku on Tuesday, Thursday, and Saturday. The edition includes one item.

### xkcd

- Fetch from the xkcd JSON API.
- Choose a random comic that has not been used before. History is kept in the database.
- Skip interactive comics, and comics that are very tall or very wide.
- Convert the image to grayscale.
- Print the alt text as a caption. The alt text stays in English.
- Credit line: `xkcd.com, CC BY-NC 2.5`.
- If the fetch fails, print that day's puzzle instead.

### Sudoku

Generated in code with a verified unique solution. Difficulty depends on the weekday. Weekend editions use easy difficulty and a larger box, as in edition.md.

Mini crossword, Jumble, and word search are out of this version. They need a Hungarian word list with diacritics and a compatible license. A puzzle is not produced by a model unless code verifies it.

## Almanac and rates

These items do not need the model. Each has its own toggle. All of them start on.

| Item | Source | Rule |
| --- | --- | --- |
| Sunrise and sunset | Computed locally from coordinates and date | Works offline. |
| Moon phase | Computed locally | Works offline. Show the phase name and the illumination. |
| Name day | Static table vendored in the project | Hungarian calendar, from [froccsos/nevnapok-json](https://github.com/froccsos/nevnapok-json) (MIT). The list was compiled from the MEK page last updated in July 1997, so names added after that are absent. Print the day's `main` names. Works offline. On by default. Credit the dataset. |
| On this day | Wikipedia "on this day" feed | Language follows the paper language setting. Request `{lang}.wikipedia.org/api/rest_v1/feed/onthisday/selected/{mm}/{dd}`. If that language is unsupported or the day is empty, use the English feed and record the fallback on the run. Pick 1 to 3 short entries in code (for example the ones with the most notable pages), print them as written, and credit Wikipedia (CC BY-SA). |
| EUR/HUF, USD/HUF, CHF/HUF | Magyar Nemzeti Bank daily rates | Official MNB exchange-rate service, `GetCurrentExchangeRates`, for EUR, USD, and CHF, each quoted as HUF per 1 unit. Print the value with its rate date and the source name MNB. The bank publishes on working days, so a weekend or holiday shows the last published date. |

If an item cannot be fetched, it is omitted. No value is estimated.

Two densities:

- The normal edition uses a compact strip. Those details are the first things dropped on overflow.
- The fallback edition, and any edition built with the model off, expands the strip: more on-this-day entries and extra detail. That is what makes the no-model paper a fuller page of static information.
