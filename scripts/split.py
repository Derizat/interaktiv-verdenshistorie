"""Split composite features so they can be coloured separately (Greenland/Iceland out of Denmark, East Pakistan out of Pakistan)."""
import json, sys

RULES = {
    "1938": [("Denmark", "Greenland", lambda x, y: x < -11 and x > -75 and y > 58 and not (-25.5 < x < -12)),
             ("Denmark", "Iceland", lambda x, y: -25.5 < x < -12 and 62.5 < y < 67.5)],
    "1945": [("Denmark", "Greenland", lambda x, y: x < -11 and x > -75 and y > 58 and not (-25.5 < x < -12))],
    "1914": [("Denmark", "Greenland", lambda x, y: x < -11 and x > -75 and y > 58 and not (-25.5 < x < -12))],
    "1920": [("Denmark", "Greenland", lambda x, y: x < -11 and x > -75 and y > 58 and not (-25.5 < x < -12))],
    "1930": [("Denmark", "Greenland", lambda x, y: x < -11 and x > -75 and y > 58 and not (-25.5 < x < -12))],
    "1960": [("Pakistan", "East Pakistan", lambda x, y: x > 85)],
    "1815": [("Denmark", "Greenland", lambda x, y: x < -11 and x > -75 and y > 58 and not (-25.5 < x < -12)),
             ("Denmark", "Iceland", lambda x, y: -25.5 < x < -12 and 62.5 < y < 67.5),
             # The source still draws the Austrian Netherlands (Austrian until 1795); in 1815 it joined the Netherlands.
             ("Austrian Empire", "United Kingdom of the Netherlands", lambda x, y: 2.4 < x < 6.4 and 49.4 < y < 51.5),
             # The eastern Cape is mislabelled "Dutch East Indies" in the source.
             ("Dutch East Indies", "Cape Colony", lambda x, y: x < 40)],
    # Alaska's islands are drawn twice, in the USA and (on top) in Russia; Alaska was American from 1867.
    "1880": [("Russian Empire", "United States of America", lambda x, y: -172.1 < x < -129 and y > 50)],
    # Ottoman Libya lies under the 1914 "Libya" taken in from the 1914 map; drop the Ottoman copy.
    "1900": [("Ottoman Empire", None, lambda x, y: 9 < x < 25.5 and 19 < y < 33.5)],
}

# Source-data fixes: the 1930 basemap labels the whole USSR "White Russia".
RENAMES = {"1930": {"White Russia": "USSR"}}
# The 1914 basemap swaps British and Italian Somaliland (Mogadishu lies in "British Somaliland"); the 1900 map takes
# its Africa from the 1914 file, so it is fixed too.
SWAPS = {"1914": [("British Somaliland", "Italian Somaliland")]}
# The 1994 and 2000 basemaps leave Switzerland unnamed and name a tiny sliver instead:
# name the unnamed feature containing the point and drop the sliver.
NAME_BY_POINT = {"1994": {"Switzerland": (7.45, 46.95)}, "2000": {"Switzerland": (7.45, 46.95)},
                 # Unnamed northern Arabian desert in the 1920 and 1930 basemaps.
                 "1920": {"Nordarabien": (40.9, 29.4)}, "1930": {"Nordarabien": (40.9, 29.4)}}
# Unnamed leftovers drawn on top of a named country: drop them.
DROP_UNNAMED_AT = {"1938": [(40.9, 29.4)], "1994": [(121.0, 23.7)]}
# The 19th-century basemaps cover inner Africa with one big unnamed polygon. Name it, and draw the largest
# features first in these maps, so that it (and other large areas) lies under the kingdoms drawn inside it.
NAME_BY_POINT.update({"1815": {"Indre Afrika": (22.0, -2.0), "United Kingdom of the Netherlands": (5.3, 52.1)},
                      "1880": {"Indre Afrika": (22.0, -2.0)}})
SORT_BY_AREA = {"1815", "1880", "1900"}
# Unnamed features that plainly belong to a named one: name them (nothing is dropped, unlike NAME_BY_POINT).
NAME_UNNAMED_AT = {
    "1815": [("Denmark", (14.9, 55.12)), ("Sweden–Norway", (18.5, 57.5)), ("Faroe Islands", (-6.95, 62.05)),
             ("Tasmania", (146.6, -42.0)), ("Taiwan", (120.95, 23.7)), ("Dutch East Indies", (110.4, -7.4)),
             ("Dutch East Indies", (120.2, -2.0)), ("Dutch East Indies", (114.0, -2.5)), ("Dutch East Indies", (102.0, -1.0)),
             ("Sydarabien", (41.25, 18.9)), ("Nordarabien", (36.85, 29.44)), ("Madagascar", (43.47, -22.65)), ("Sakhalin", (141.67, 46.48)),
             ("Australian aboriginal hunter-gatherers", (129.07, -30.11)), ("Russian Empire", (-171.77, 63.43)), ("Russian Empire", (-167.37, 60.16)),
             ("Russian Empire", (-164.9, 54.52))],
    "1880": [("Faroe Islands", (-6.95, 62.05)), ("Tasmania", (146.6, -42.0)), ("Vestafrikanske riger og folk", (-16.07, 12.21)),
             ("Russian Empire", (48.26, 68.88))],
    "1900": [("Faroe Islands", (-6.95, 62.05)), ("Tasmania", (146.6, -42.0)), ("Taiwan", (120.95, 23.7))],
    "1914": [("Faroe Islands", (-6.95, 62.05))],
}
# Unnamed features whose source lists their ruler (SUBJECTO) as one of these: use that as the name.
NAME_FROM_SOURCE = {"1815": {"Dutch East Indies"}}
# The 1815 map draws Goa about 60 km too far south-east.
SHIFT = {"1815": {"Goa": (-0.42, 0.78)}}

# Overlays: territory the source map gives to the wrong state. The part of the source feature inside the region
# (convex pieces, counter-clockwise) is copied into a new feature drawn on top, so it can be coloured and named on
# its own. Coordinates are [lon, lat].
def _bands(line, east):
    """Convex bands east of a north-to-south border line, up to longitude `east`."""
    return [[line[k + 1], (east, line[k + 1][1]), (east, line[k][1]), line[k]] for k in range(len(line) - 1)]
def _kongeaa(x):
    return 55.25 + (x - 8.4) * (0.20 / 1.3)
# Schleswig south of Kongeåen (the 1864 border, which left Ribe Danish), plus Als; Ærø and Funen stay Danish.
SCHLESWIG = [[(7.8, 53.8), (9.7, 53.8), (9.7, _kongeaa(9.7)), (7.8, _kongeaa(7.8))],
             [(9.7, 53.8), (10.15, 53.8), (10.15, 55.10), (9.7, 55.10)]]
# Alsace-Lorraine: east of the 1871 border (Luxembourg, west of Metz, the Seille, Avricourt, the Vosges crest, east of Belfort).
ALSACE_LORRAINE = _bands([(5.94, 49.75), (6.02, 49.0), (6.60, 48.75), (7.15, 48.50), (6.85, 47.82), (7.10, 47.40)], 9.0)
# Bessarabia: east of the Prut, down to the Chilia arm of the Danube (Izmail).
BESSARABIA = _bands([(26.15, 48.80), (26.55, 48.40), (26.95, 48.15), (27.85, 47.15), (28.15, 46.45), (28.10, 45.45), (28.20, 45.28)], 31.5)
# Northern Alsace west of the Rhine, which the 1815 map gives to Baden.
WEST_OF_RHINE = [[(5.5, 47.5), (7.57, 47.5), (7.58, 48.03), (5.5, 48.03)], [(5.5, 48.03), (7.58, 48.03), (7.80, 48.57), (5.5, 48.57)],
                 [(5.5, 48.57), (7.80, 48.57), (8.23, 48.98), (5.5, 48.98)]]
TUNISIA = [[(7.4, 30.5), (11.55, 30.5), (11.55, 37.6), (7.4, 37.6)]]
PLOVDIV = [[(23.9, 41.8), (26.3, 41.8), (26.3, 42.65), (23.9, 42.65)]]
OVERLAYS = {
    "1815": [("Denmark", "North Schleswig", SCHLESWIG), ("Ottoman Empire", "Bessarabia", BESSARABIA), ("Baden", "France", WEST_OF_RHINE)],
    "1880": [("Denmark", "Schleswig", SCHLESWIG), ("France", "Alsace-Lorraine", ALSACE_LORRAINE), ("Romania", "Bessarabia", BESSARABIA),
             ("Ottoman Empire", "Tunisia", TUNISIA)],
    "1900": [("Denmark", "Schleswig", SCHLESWIG), ("France", "Alsace-Lorraine", ALSACE_LORRAINE), ("Romania", "Bessarabia", BESSARABIA),
             ("Ottoman Empire", "Bulgaria", PLOVDIV)],
    "1914": [("Denmark", "Schleswig", SCHLESWIG), ("France", "Alsace-Lorraine", ALSACE_LORRAINE), ("Romania", "Bessarabia", BESSARABIA)],
}
MIN_PIECE = 0.004

def clip_convex(ring, clip):
    """Sutherland-Hodgman: the part of a closed ring inside a convex, counter-clockwise polygon, or None."""
    out = ring[:-1] if ring[0] == ring[-1] else list(ring)
    for i in range(len(clip)):
        (ax, ay), (bx, by) = clip[i], clip[(i + 1) % len(clip)]
        inside = lambda p: (bx - ax) * (p[1] - ay) - (by - ay) * (p[0] - ax) >= 0
        def cut(p, q):
            den = (p[0] - q[0]) * (ay - by) - (p[1] - q[1]) * (ax - bx)
            t = ((p[0] - ax) * (ay - by) - (p[1] - ay) * (ax - bx)) / den
            return [p[0] + t * (q[0] - p[0]), p[1] + t * (q[1] - p[1])]
        src, out = out, []
        for j in range(len(src)):
            p, q = src[j - 1], src[j]
            if inside(q):
                if not inside(p):
                    out.append(cut(p, q))
                out.append(q)
            elif inside(p):
                out.append(cut(p, q))
        if not out:
            return None
    pts = []
    for x, y in out:
        pt = [round(x, 2), round(y, 2)]
        if not pts or pt != pts[-1]:
            pts.append(pt)
    if len(pts) < 3:
        return None
    pts.append(pts[0])
    return pts if ring_area(pts) >= MIN_PIECE else None
# The 1900 basemap has no colonial partition of Africa; take Africa from the 1914 map instead (the colonies
# table in status.json says who held each territory in which years).
AFRICA_FROM = {"1900": "1914"}
AFRICA = [(-18, 30), (-10, 36), (-5, 36.1), (10, 38), (12, 37.5), (20, 33), (32.5, 31.5), (34.3, 31.3), (35, 29.5),
          (33, 28), (37, 22), (43.5, 12.5), (51.5, 12), (51, 10), (42, -1), (51, -10), (51, -26), (36, -26), (33, -35),
          (17, -35), (11, -17), (8, -1), (5, 4), (-8, 4), (-17, 14), (-18, 22), (-18, 30)]

def contains(ring, x, y):
    inside = False
    for i in range(len(ring) - 1):
        x1, y1 = ring[i]; x2, y2 = ring[i + 1]
        if (y1 > y) != (y2 > y) and x < (x2 - x1) * (y - y1) / (y2 - y1) + x1:
            inside = not inside
    return inside

def ring_area(r):
    return abs(sum(r[i][0] * r[i + 1][1] - r[i + 1][0] * r[i][1] for i in range(len(r) - 1)) / 2)

def centroid(ring):
    xs = [p[0] for p in ring]; ys = [p[1] for p in ring]
    return sum(xs) / len(xs), sum(ys) / len(ys)

def area_of(f):
    return sum(ring_area(p[0]) for p in f["geometry"]["coordinates"])

def in_africa(f):
    big = max(f["geometry"]["coordinates"], key=lambda p: ring_area(p[0]))
    return contains(AFRICA, *centroid(big[0]))

def main(path, snap):
    g = json.load(open(path))
    # The 1815 basemap names the Netherlands with blanks only; treat blank names as missing.
    for f in g["features"]:
        if isinstance(f["properties"]["n"], str) and not f["properties"]["n"].strip():
            f["properties"]["n"] = None
    if snap in AFRICA_FROM:
        other = json.load(open(path.replace(f"borders_{snap}", f"borders_{AFRICA_FROM[snap]}")))
        before = len(g["features"])
        g["features"] = [f for f in g["features"] if not in_africa(f)]
        africa = [f for f in other["features"] if in_africa(f)]
        g["features"] += africa
        print(snap, f"replaced {before - len(g['features']) + len(africa)} African features with {len(africa)} from {AFRICA_FROM[snap]}")
    for old, new in RENAMES.get(snap, {}).items():
        for f in g["features"]:
            if f["properties"]["n"] == old:
                f["properties"]["n"] = new
                print(snap, f"renamed {old} -> {new}")
    for a, b in SWAPS.get(snap, []):
        for f in g["features"]:
            if f["properties"]["n"] in (a, b):
                f["properties"]["n"] = b if f["properties"]["n"] == a else a
        print(snap, f"swapped {a} <-> {b}")
    for name, (x, y) in NAME_BY_POINT.get(snap, {}).items():
        g["features"] = [f for f in g["features"] if not (f["properties"]["n"] == name and sum(ring_area(p[0]) for p in f["geometry"]["coordinates"]) < 0.05)]
        for f in g["features"]:
            if f["properties"]["n"] is None and any(contains(p[0], x, y) for p in f["geometry"]["coordinates"]):
                f["properties"]["n"] = name
                print(snap, f"named unnamed feature -> {name}")
                break
    for name, (x, y) in NAME_UNNAMED_AT.get(snap, []):
        for f in g["features"]:
            if f["properties"]["n"] is None and any(contains(p[0], x, y) for p in f["geometry"]["coordinates"]):
                f["properties"]["n"] = name
                print(snap, f"named unnamed feature at {x},{y} -> {name}")
    for f in g["features"]:
        if f["properties"]["n"] is None and f["properties"].get("s") in NAME_FROM_SOURCE.get(snap, ()):
            f["properties"]["n"] = f["properties"]["s"]
            print(snap, f"named unnamed feature after its ruler -> {f['properties']['s']}")
    for name, (dx, dy) in SHIFT.get(snap, {}).items():
        for f in g["features"]:
            if f["properties"]["n"] == name:
                f["geometry"]["coordinates"] = [[[[round(x + dx, 2), round(y + dy, 2)] for x, y in r] for r in p] for p in f["geometry"]["coordinates"]]
                print(snap, f"shifted {name} by {dx},{dy}")
    for x, y in DROP_UNNAMED_AT.get(snap, []):
        before = len(g["features"])
        g["features"] = [f for f in g["features"] if not (f["properties"]["n"] is None and any(contains(p[0], x, y) for p in f["geometry"]["coordinates"]))]
        if len(g["features"]) < before:
            print(snap, f"dropped {before - len(g['features'])} unnamed feature(s) at {x},{y}")
    for src, new, test in RULES.get(snap, []):
        for f in list(g["features"]):
            if f["properties"]["n"] != src:
                continue
            keep, moved = [], []
            for poly in f["geometry"]["coordinates"]:
                (moved if test(*centroid(poly[0])) else keep).append(poly)
            if moved:
                f["geometry"]["coordinates"] = keep
                if new:
                    g["features"].append({"type": "Feature", "properties": {"n": new, "s": None},
                                          "geometry": {"type": "MultiPolygon", "coordinates": moved}})
                print(snap, f"split {len(moved)} polygons {src} -> {new or 'dropped'}")
    g["features"] = [f for f in g["features"] if f["geometry"]["coordinates"]]
    if snap in SORT_BY_AREA:
        g["features"].sort(key=area_of, reverse=True)
    # Overlays go last, so they are drawn on top of the feature they are cut from.
    for src, new, regions in OVERLAYS.get(snap, []):
        pieces = [piece for f in g["features"] if f["properties"]["n"] == src
                  for poly in f["geometry"]["coordinates"] for region in regions
                  for piece in [clip_convex(poly[0], region)] if piece]
        if pieces:
            g["features"].append({"type": "Feature", "properties": {"n": new, "s": src, "o": 1},
                                  "geometry": {"type": "MultiPolygon", "coordinates": [[pc] for pc in pieces]}})
            print(snap, f"overlay {new}: {len(pieces)} pieces cut from {src}")
        else:
            print(snap, f"WARNING overlay {new}: nothing inside the region of {src}")
    json.dump(g, open(path, "w"), separators=(",", ":"))

if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
