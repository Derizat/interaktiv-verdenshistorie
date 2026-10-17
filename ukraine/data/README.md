# Data for the Ukraine war page

| File | What | Licence |
|---|---|---|
| `events.json` | Event cards: `m` is the month shown ("2022-03"), `until` the last month of an ongoing item, plus date, title, text, lat/lon, category (`cat`, a key of `CATS` in `../index.html`) and `dk` for a Danish angle. | GPL-3.0, like the rest of the repo |
| `campaigns.json` | Arrows: `m`/`until` (months shown), `side` (`russia` or `ukraine`), label and polylines of [lon, lat]. The arrowhead sits on the last point. Arrows are drawn by hand to show direction, not exact routes. | GPL-3.0 |
| `places.json` | Towns with Danish spellings; `r` is the rank (1–2 always shown, 3–4 when zoomed in), `ru` marks towns in Russia, `side: "l"` puts the label on the left. | GPL-3.0 |
| `control.json` | Russian-held and contested areas at the end of every month, and on 23 February 2022 (`prewar`). Built by `scripts/ukraine.py`. | **ODbL 1.0** (see below) |
| `basemap.json` | Countries, oblasts, rivers and lakes for the map frame, from Natural Earth (Ukrainian point of view, so Crimea is Ukrainian). Built by `scripts/ukraine.py`. | Public domain |

## control.json and the ODbL

`control.json` is a derived database from VIINA:

> Contains information from VIINA, which is made available here under the Open Database License (ODbL).
> Zhukov, Yuri and Natalie Ayers (2023). "VIINA 2.0: Violent Incident Information from News Articles on the 2022 Russian Invasion of Ukraine." Cambridge, MA: Harvard University. https://github.com/zhukovyuri/VIINA, accessed 17 October 2026.

As required by the ODbL, `control.json` is itself offered under the [Open Database License 1.0](https://opendatacommons.org/licenses/odbl/1-0/), and so is any database adapted from it.

How it is made: VIINA gives a daily status (UA, RU or CONTESTED) for 33,141 populated places from four sources: Wikipedia's crowd-sourced maps, DeepStateMap, ISW and VIINA's own news-event reports ("boost"). This build compares Wikipedia and DeepStateMap for the whole war (Wikipedia and ISW in February–March 2022, before DeepStateMap's history starts), because ISW is missing from VIINA from July 2026 and a source dropping out would show up as a fake change on the map. A place counts as Russian or Ukrainian only when both sources agree; otherwise it counts as contested. The cells of VIINA's tessellation (one per place) are merged into areas for the last available day of each month. See `scripts/ukraine.py` for the details, including why VIINA's own majority-vote column is not used.

Update with:

```bash
python3 scripts/ukraine.py --refresh
```
