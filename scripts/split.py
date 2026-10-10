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
}

# Source-data fixes: the 1930 basemap labels the whole USSR "White Russia".
RENAMES = {"1930": {"White Russia": "USSR"}}
# The 1994 and 2000 basemaps leave Switzerland unnamed and name a tiny sliver instead:
# name the unnamed feature containing the point and drop the sliver.
NAME_BY_POINT = {"1994": {"Switzerland": (7.45, 46.95)}, "2000": {"Switzerland": (7.45, 46.95)}}

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

def main(path, snap):
    g = json.load(open(path))
    for old, new in RENAMES.get(snap, {}).items():
        for f in g["features"]:
            if f["properties"]["n"] == old:
                f["properties"]["n"] = new
                print(snap, f"renamed {old} -> {new}")
    for name, (x, y) in NAME_BY_POINT.get(snap, {}).items():
        g["features"] = [f for f in g["features"] if not (f["properties"]["n"] == name and sum(ring_area(p[0]) for p in f["geometry"]["coordinates"]) < 0.05)]
        for f in g["features"]:
            if f["properties"]["n"] is None and any(contains(p[0], x, y) for p in f["geometry"]["coordinates"]):
                f["properties"]["n"] = name
                print(snap, f"named unnamed feature -> {name}")
                break
    for src, new, test in RULES.get(snap, []):
        for f in list(g["features"]):
            if f["properties"]["n"] != src:
                continue
            keep, moved = [], []
            for poly in f["geometry"]["coordinates"]:
                (moved if test(*centroid(poly[0])) else keep).append(poly)
            if moved:
                f["geometry"]["coordinates"] = keep
                g["features"].append({"type": "Feature", "properties": {"n": new, "s": None},
                                      "geometry": {"type": "MultiPolygon", "coordinates": moved}})
                print(snap, f"split {len(moved)} polygons {src} -> {new}")
    json.dump(g, open(path, "w"), separators=(",", ":"))

if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
