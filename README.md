# Interaktiv verdenshistorie

An interactive world map for history teaching, 1939–2000. Drag the year rail (or press play) to see what happened each year, with power blocs and colonial rule coloured year by year.

All UI text and event descriptions are in Danish.

## Run locally

The page loads its data with `fetch`, so it needs a web server (opening `index.html` directly won't work):

```bash
python3 -m http.server 8000
```

Then open http://localhost:8000. Append `#1962` to jump to a year.

## Structure

| Path | What |
|---|---|
| `index.html` | The whole app (HTML, CSS, JS). D3 v7 is loaded from cdnjs. |
| `data/events.json` | Events: year, date, title, text, coordinates, category, countries involved. `until` marks ongoing conflicts/periods. |
| `data/status.json` | Colouring rules: map snapshot per year range, WWII status, Cold War blocs, colonial rule, Danish display names. All ranges are inclusive and describe the situation at the **end** of each year. |
| `data/borders_*.json` | Simplified border snapshots (1938, 1945, 1960, 1994, 2000). |
| `scripts/` | Python scripts used to build the border files. |

Country keys in `status.json` and `events.json` must match the `n` property in the border file used for that year (see `snapshots` in `status.json`).

## Rebuilding the border data

```bash
for y in 1938 1945 1960 1994 2000; do
  curl -sSL -o /tmp/world_$y.geojson "https://raw.githubusercontent.com/aourednik/historical-basemaps/master/geojson/world_$y.geojson"
  MIN_AREA=0.03 python3 scripts/simplify.py /tmp/world_$y.geojson data/borders_$y.json
  python3 scripts/split.py data/borders_$y.json $y
done
```

`simplify.py` applies Douglas-Peucker simplification, rounds coordinates and fixes winding order for D3. `split.py` separates Greenland, Iceland and East Pakistan into their own features, so they can be coloured separately.

## Accuracy

Event texts and colouring rules were fact-checked in October 2026 (about 40 corrections applied). Numbers such as casualty figures are estimates, so double-check them before using them in class.

Known limitations:
- Borders change in jumps between the five snapshots. For example, Vietnam is one polygon from 1960 to 1975.
- Some territories are hidden inside larger polygons in the source data, such as Korea inside Japan in 1938 and Aden inside Yemen.

## Credits

Border data: [historical-basemaps](https://github.com/aourednik/historical-basemaps) by A. Ourednik, licensed GPL-3.0. The simplified files in `data/borders_*.json` are derived from it.

## License

GPL-3.0, see [LICENSE](LICENSE). The border data is derived from GPL-3.0 licensed data, so the whole project uses the same license.
