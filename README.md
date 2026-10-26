# Interaktiv verdenshistorie

An interactive world map for history teaching, 1814–2025. Drag the year rail (or press play) to see what happened each year, with power blocs and colonial rule coloured year by year. The rail shows one of two periods at a time, 1814–1913 or 1914–2025, so a single year stays easy to hit on a smartboard; playing runs on from one period into the next.

All UI text and event descriptions are in Danish.

Read-aloud plays pre-recorded MP3s (Google Cloud Text-to-Speech, voice `da-DK-Chirp3-HD-Charon`) from `audio/`. An event without a recording, for example one added or edited since the clips were last generated, is read by the browser's own Danish voice instead (Web Speech API). With "Oplæsning" on, playback waits for each year's reading to finish.

## Run locally

The page loads its data with `fetch`, so it needs a web server (opening `index.html` directly won't work):

```bash
python3 -m http.server 8000
```

Then open http://localhost:8000. Append `#1962` to jump to a year, or `#1962/cubakrise` (an event id from `events.json`) to open that event's card as well. The address updates as you browse, so any view can be shared as a link.

## Structure

| Path | What |
|---|---|
| `index.html` | The whole app (HTML, CSS, JS). D3 v7 is loaded from cdnjs. |
| `data/events.json` | Events: year, date, title, text, coordinates, category, countries involved. `until` marks ongoing conflicts/periods. |
| `data/status.json` | Colouring rules: map snapshot per year range, the 19th-century great powers and alliances (`c19`), WWI and WWII status, interwar regimes, Cold War blocs, colonial rule, Danish display names. All ranges are inclusive and describe the situation at the **end** of each year. A `names` range can carry a note about the map itself, shown under the name in the tooltip. |
| `data/campaigns.json` | Campaign arrows, from Napoleon's last campaign in 1815 to the Gulf War: year, side (a key of `SIDES` in index.html), Danish label and one or more polylines of [lon, lat] waypoints. The arrowhead sits on the last point. |
| `data/audio.json` | Voice name and the list of recorded clips in `audio/`. Written by `scripts/tts.py`. |
| `audio/` | One MP3 per event and per year, named by a hash of the voice and the text. |
| `data/borders_*.json` | Simplified border snapshots (1815, 1880, 1900, 1914, 1920, 1930, 1938, 1945, 1960, 1994, 2000). The 1815 map is used until 1864 (so the US conquests from Mexico in 1848 only show from 1865, but Schleswig and Holstein stay separate until the war of 1864), and the 1900 map takes its Africa from the 1914 map, because the source has no colonial partition of Africa. The 2000 map is used for 2000–2025, so East Timor, Kosovo, South Sudan and Crimea are not shown. |
| `scripts/` | Python scripts used to build the border files, the read-aloud clips, the Ukraine data and the Roman map data. |
| `rom/` | A separate page for the Roman state year by year, 509 BC–AD 476: a map of the Mediterranean world where the territory grows and shrinks each year, with the period's own events and campaign arrows. See [The Roman page](#the-roman-page). |
| `ukraine/` | A separate page for the Russia–Ukraine war, month by month from February 2022: a regional map with Russian-held and contested areas, the war's own events and campaign arrows. See [ukraine/data/README.md](ukraine/data/README.md). |

Country keys in `status.json` and `events.json` must match the `n` property in the border file used for that year (see `snapshots` in `status.json`).

## Rebuilding the border data

```bash
# 1914 before 1900: the 1900 map takes its Africa from the 1914 file.
for y in 1914 1920 1930 1938 1945 1960 1994 2000 1815 1880 1900; do
  curl -sSL -o /tmp/world_$y.geojson "https://raw.githubusercontent.com/aourednik/historical-basemaps/master/geojson/world_$y.geojson"
  MIN_AREA=0.03 python3 scripts/simplify.py /tmp/world_$y.geojson data/borders_$y.json
  python3 scripts/split.py data/borders_$y.json $y
done
```

`simplify.py` applies Douglas-Peucker simplification, rounds coordinates and fixes winding order for D3. `split.py` separates Greenland, Iceland and East Pakistan into their own features, so they can be coloured separately, and patches known source-data errors (the 1930 USSR label, the unnamed Switzerland in 1994/2000, the unnamed Netherlands in 1815). In the 19th-century maps it names the big unnamed inner-Africa polygon and other unnamed areas, draws large areas first so the kingdoms inside them stay visible, and replaces Africa in the 1900 map with the 1914 one.

Where a source map gives land to the wrong state, `split.py` copies that part into an overlay feature drawn on top, so it can be coloured and named on its own: Schleswig (1815–1914 maps), Alsace-Lorraine and Bessarabia, Tunisia in 1880, the Plovdiv region in 1900 and northern Alsace in 1815. It also swaps the mixed-up British and Italian Somaliland labels in the 1914 map. Errors it does not fix are named in the tooltip through a note in `names` (for example Belgium inside the Netherlands 1830–1864).

## The Roman page

`rom/index.html` is another cut-down copy of the main page. The rail runs from 509 BC to AD 476 (985 years, one column per decade, no year 0) and the map shows who held each part of the Mediterranean world at the end of each year.

The territory is not taken from snapshot maps. `scripts/rome_regions.py` divides the map into about 130 regions, each with a timeline of who held it, and a set of anchor points. The page draws the Voronoi cells of all anchors (d3-delaunay), colours each cell by its region's ruler that year and draws the sea from Natural Earth on top, so the coasts are exact and the borders between regions run halfway between neighbouring anchors. Anchor pairs along the Rhine, the Danube, the limes and Hadrian's Wall make those frontiers follow the line. Borders are therefore approximate; the timelines are what was fact-checked.

After editing the regions, rebuild the data (a second or two; Natural Earth is cached in `.cache/ne/`):

```bash
python3 scripts/rome.py
```

The events and arrows in `rom/data/events.json` and `campaigns.json` are written by hand. Years are integers, negative before Christ.

## The Ukraine war page

`ukraine/index.html` is a cut-down copy of the main page for one war. The slider steps through months instead of years. The map shows Ukraine and its neighbours at a regional scale, with oblasts, rivers and towns. Control areas come from [VIINA](https://github.com/zhukovyuri/VIINA), and the events are written by hand.

To update the control areas with the newest days, run this. It downloads about 240 MB to `.cache/` the first time and takes about 30 seconds:

```bash
python3 scripts/ukraine.py --refresh
```

New months appear on the rail automatically. Events and arrows for them are added by hand in `ukraine/data/events.json` and `campaigns.json`.

`ukraine/data/control.json` is derived from VIINA and is licensed under the Open Database License (ODbL), not the GPL.

## Regenerating the read-aloud clips

Run this after adding or editing events. It needs a Google Cloud API key with the Text-to-Speech API enabled, in `$GOOGLE_TTS_KEY` or `~/.config/google-tts/key`:

```bash
python3 scripts/tts.py --prune
```

The clips cover the main page and the Roman page (its events, and the year announcements for years that have events; "f.Kr." and "e.Kr." are read as "før/efter Kristus"). The Ukraine page uses the browser voice. Only clips whose text changed are generated again. `--prune` deletes the clips that no longer match any text, but only when every clip was generated. A full run is about 175,000 characters, which costs at most a few dollars. Set `TTS_VOICE` once to switch voice; that regenerates every clip, and later runs keep the voice stored in `data/audio.json`.

## Accuracy

Event texts and colouring rules were fact-checked in October 2026 (about 40 corrections applied). The 1814–1913 content (140 events, 29 arrows and the colouring tables) was fact-checked separately in the same month. Numbers such as casualty figures are estimates, so double-check them before using them in class.

Known limitations:
- Borders change in jumps between the snapshots. For example, Vietnam is one polygon from 1960 to 1975, and the 1880 map is used for 1865–1884.
- The 1815, 1880 and 1900 source maps contain many errors. The worst are fixed in `split.py`; the rest are named in the tooltip.
- Some territories are hidden inside larger polygons in the source data, such as Korea inside Japan in 1938 and Aden inside Yemen.

## Credits

Border data: [historical-basemaps](https://github.com/aourednik/historical-basemaps) by A. Ourednik, licensed GPL-3.0. The simplified files in `data/borders_*.json` are derived from it.

Roman page: coasts, rivers and lakes from [Natural Earth](https://www.naturalearthdata.com) (public domain); the regions and their timelines are this project's own.

Ukraine page: territorial control from VIINA (Zhukov and Ayers 2023, ODbL); basemap from [Natural Earth](https://www.naturalearthdata.com) (public domain).

## License

GPL-3.0, see [LICENSE](LICENSE). The border data is derived from GPL-3.0 licensed data, so the whole project uses the same license. The one exception is `ukraine/data/control.json`, which is licensed under the ODbL 1.0, as VIINA's licence requires.
