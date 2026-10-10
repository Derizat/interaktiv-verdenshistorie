"""Simplify historical-basemaps GeoJSON for the browser: Douglas-Peucker per ring,
2-decimal coords, drop Antarctica and specks, fix winding for d3 (clockwise exteriors)."""
import json, sys, os, math

TOL = float(os.environ.get("TOL", "0.06"))
MIN_AREA = float(os.environ.get("MIN_AREA", "0.08"))

def dp(pts, tol):
    if len(pts) < 3:
        return pts
    keep = [False] * len(pts)
    keep[0] = keep[-1] = True
    stack = [(0, len(pts) - 1)]
    while stack:
        a, b = stack.pop()
        ax, ay = pts[a]; bx, by = pts[b]
        dx, dy = bx - ax, by - ay
        L = math.hypot(dx, dy)
        best, idx = -1.0, -1
        for i in range(a + 1, b):
            px, py = pts[i]
            d = abs(dy * px - dx * py + bx * ay - by * ax) / L if L else math.hypot(px - ax, py - ay)
            if d > best:
                best, idx = d, i
        if best > tol and idx > 0:
            keep[idx] = True
            stack.append((a, idx)); stack.append((idx, b))
    return [p for p, k in zip(pts, keep) if k]

def area(r):
    s = 0.0
    for i in range(len(r) - 1):
        s += r[i][0] * r[i + 1][1] - r[i + 1][0] * r[i][1]
    return s / 2

def ring(r):
    r = [(round(x, 2), round(y, 2)) for x, y in r]
    out = [r[0]]
    for p in r[1:]:
        if p != out[-1]:
            out.append(p)
    if out[0] != out[-1]:
        out.append(out[0])
    out = dp(out, TOL)
    if len(out) < 4:
        return None
    return out

def main(src, dst):
    g = json.load(open(src))
    feats = []
    for f in g["features"]:
        geom = f["geometry"]
        if not geom:
            continue
        polys = geom["coordinates"] if geom["type"] == "MultiPolygon" else [geom["coordinates"]]
        cand = []
        for poly in polys:
            if all(y < -60 for x, y in poly[0]):
                continue
            ext = ring(poly[0])
            if not ext:
                continue
            a = area(ext)
            cand.append((abs(a), ext, [ring(h) for h in poly[1:]]))
        if not cand:
            continue
        cand.sort(key=lambda c: -c[0])
        out = []
        for i, (a, ext, holes) in enumerate(cand):
            if i > 0 and a < MIN_AREA:
                continue
            if area(ext) > 0:
                ext = ext[::-1]
            rings = [[list(p) for p in ext]]
            for h in holes:
                if h and abs(area(h)) >= MIN_AREA:
                    if area(h) < 0:
                        h = h[::-1]
                    rings.append([list(p) for p in h])
            out.append(rings)
        p = f["properties"]
        name = p.get("NAME") or None
        if name in ("None", ""):
            name = None
        feats.append({"type": "Feature",
                      "properties": {"n": name, "s": p.get("SUBJECTO")},
                      "geometry": {"type": "MultiPolygon", "coordinates": out}})
    json.dump({"type": "FeatureCollection", "features": feats}, open(dst, "w"), separators=(",", ":"))

if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
