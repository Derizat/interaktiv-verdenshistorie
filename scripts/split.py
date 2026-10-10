"""Split composite features so they can be coloured separately (Greenland/Iceland out of Denmark, East Pakistan out of Pakistan)."""
import json, sys

RULES = {
    "1938": [("Denmark", "Greenland", lambda x, y: x < -11 and x > -75 and y > 58 and not (-25.5 < x < -12)),
             ("Denmark", "Iceland", lambda x, y: -25.5 < x < -12 and 62.5 < y < 67.5)],
    "1945": [("Denmark", "Greenland", lambda x, y: x < -11 and x > -75 and y > 58 and not (-25.5 < x < -12))],
    "1960": [("Pakistan", "East Pakistan", lambda x, y: x > 85)],
}

def centroid(ring):
    xs = [p[0] for p in ring]; ys = [p[1] for p in ring]
    return sum(xs) / len(xs), sum(ys) / len(ys)

def main(path, snap):
    g = json.load(open(path))
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
