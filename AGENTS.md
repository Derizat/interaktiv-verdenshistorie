# Notes for coding agents

Claude Code reads this file through `CLAUDE.md`; Codex reads it directly. The [README](README.md) describes the pages, the data files and how to rebuild them, so read it first. This file adds the rules that are easy to get wrong.

## The project

- A Danish world-history atlas for pupils aged 13–16. It has four pages: `index.html` (the world 1814–2025), `rom/` (the Roman state, 509 BC–AD 476), `borgerkrig/` (the American Civil War by month) and `ukraine/` (the Russia–Ukraine war by month).
- The pages are static and load D3 v7 from cdnjs. There is no build step and no package manager.
- GitHub Pages serves `main`, so a push to `main` is live at https://derizat.github.io/interaktiv-verdenshistorie/ within a minute or two.
- Two people work on the repo in parallel, one with Claude Code and one with Codex. Fetch and check `origin/main` before committing, and never rewrite pushed history.
- UI and event texts are in Danish. Code, comments, commit messages and docs are in English.

## Run and check

- Serve the repo root, because the pages load their JSON with `fetch`: run `python3 -m http.server 8000` and open http://localhost:8000/#1962/cubakrise.
- There is no test suite. After a change, step through the affected years in the browser, open their events and watch the console.
- Leave the GoatCounter snippet as it is.
- After editing `events.json` or `status.json`, check two things:
  - Every name in an event's `countries` exists on the border map used in its year, or in an `aliases` group.
  - The ranges of a key never overlap.

## Data rules (main map)

- `status.json` ranges are `[from, to, value, note?]`, inclusive, and describe the situation on 31 December of each year in the range.
- A note must be true at the end of every year in its range; split the range when it isn't.
- Keys are the `n` names in the border file that `snapshots` assigns to the year.
- `blocStatus` in `index.html` decides which table colours a polygon in each period (`c19`, `ww1`, `interwar`, `ww2`, `cold`, `modern`, `colonies`, `*RulerAlign`).
  - A key with no row in the period's table falls back to the other tables (see `blocStatus`) and finally to neutral, so a missing row fails silently.
- In `names`, the 4th element is a note about the map itself, such as "Kortet medtager fejlagtigt X, som …" or "Kortet mangler …". It is shown under the name in the tooltip.
  - A key with no `names` row falls back to `da` and then to the raw English key.
- The tooltip already starts a colony's note with its label (for example "Britisk koloni"), so don't repeat the label in `colonies` or `*RulerAlign` notes.
- Each event has these fields:
  - `lat`/`lon` is where the event happened, or the launch site when it happened off the map.
  - `countries` covers the whole state when the card is about the state, including the separate polygons some maps draw for parts of it (Tibet, Xinjiang, the Soviet republics).
  - `dk: true` marks an event whose text has a Danish angle.
- Write texts for 13–16-year-olds:
  - Use plain Danish and no unsupported superlatives.
  - Mark estimates with "omkring", "anslået" or "ifølge …".
  - Check figures against Wikipedia, lex.dk or Den Store Danske.
- Fix large errors in the source maps in `scripts/split.py` with renames, overlays or copies from another snapshot (see the README). Name smaller ones in a `names` note.
- `split.py` patches the built border files in place and is not idempotent. Rebuild a border file from its source as the README shows, rather than running the script twice.

## Roman, Civil War and Ukraine pages

- The Roman territory comes from `scripts/rome_regions.py`; rebuild it with `python3 scripts/rome.py`. Years are integers, negative before Christ, and there is no year 0.
- The Civil War areas are drawn from the secession months and the zones in `scripts/borgerkrig.py`; rebuild them with `python3 scripts/borgerkrig.py`.
- For the Ukraine page, see `ukraine/data/README.md`.

## Read-aloud clips

- After changing an event's title, date or text on the main or Roman page, run `python3 scripts/tts.py --prune`.
  - Commit `audio/` and `data/audio.json` together with the change.
  - A clip is named by a hash of the voice and the text; an event without a clip falls back to the browser voice.
- The Google API key lives in `~/.config/google-tts/key` (or `$GOOGLE_TTS_KEY`). Never print, log, paste or commit it.

## Licences

- The project is GPL-3.0, because the border data is derived from historical-basemaps (GPL-3.0).
- `ukraine/data/control.json` is ODbL (VIINA).
- Keep the credits in the README and on the pages up to date when adding data.
