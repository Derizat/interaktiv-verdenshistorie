#!/usr/bin/env python3
"""Build the map data for ukraine/: monthly control areas from VIINA and a regional basemap from Natural Earth.

Usage:
    python3 scripts/ukraine.py            # download what is missing, rebuild ukraine/data/control.json and basemap.json
    python3 scripts/ukraine.py --refresh  # also download the current year's VIINA file again, for the newest days

Downloads are cached in .cache/ (not committed): about 185 MB from VIINA and 90 MB from Natural Earth.

Control: VIINA (Zhukov and Ayers, https://github.com/zhukovyuri/VIINA) gives a daily status (UA, RU or CONTESTED) for 33,141
populated places from several sources, and a tessellation with one cell per place. For the last available day of
each month, the cells with status RU and CONTESTED are merged into areas. Adjacent cells share their edges exactly,
so merging is edge cancellation: an edge shared by two selected cells disappears, and the edges left over form the
outlines.

The status compares the same two sources for the whole war: Wikipedia's crowd-sourced maps and DeepStateMap (in
February and March 2022, before DeepStateMap's history starts, Wikipedia and ISW). RU or UA only when both agree,
otherwise CONTESTED (they disagree, or one of them reports fighting). So red means "both sources agree Russia holds
it", and the hatched band shows the uncertainty along the front.

Why not VIINA's own "status" column or all three sources: the column is a majority vote that also counts "boost"
(Wikipedia plus VIINA's event reports), so Wikipedia gets two votes, and ISW is missing from VIINA from July 2026.
Either way the result changes when a source drops out: with the majority vote about 300 places tipped to RU on
1 July 2026, and with all three sources about 190 contested places turned red, although neither Wikipedia nor
DeepStateMap had changed. Two sources that cover the whole period keep month-to-month changes real.
"""
import datetime
import io
import json
import math
import os
import sys
import urllib.request
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE = os.path.join(ROOT, ".cache")
OUT = os.path.join(ROOT, "ukraine", "data")
VIINA = "https://media.githubusercontent.com/media/zhukovyuri/VIINA/main/Data/"
NE = "https://raw.githubusercontent.com/nvkelso/natural-earth-vector/master/geojson/"
FIRST_YEAR = 2022
PREWAR = "20220223"
# Map frame: Ukraine with the Russian border regions, Belarus' south, Moldova and the Black Sea coast.
BBOX = (21.0, 43.4, 41.8, 53.8)
TOL_CONTROL = 0.006   # Douglas-Peucker tolerance in degrees (about 500 m)
TOL_BASE = 0.008
MIN_AREA = 0.0008     # drop rings smaller than this many square degrees (about 6 km2)


def fetch(url, path, refresh=False):
    if os.path.exists(path) and not refresh:
        return path
    os.makedirs(os.path.dirname(path), exist_ok=True)
    print("  downloading", url)
    tmp = path + ".part"
    with urllib.request.urlopen(url, timeout=300) as r, open(tmp, "wb") as f:
        while chunk := r.read(1 << 20):
            f.write(chunk)
    os.replace(tmp, path)
    return path


# ---------- geometry helpers ----------

def area(r):
    return sum(r[i][0] * r[i + 1][1] - r[i + 1][0] * r[i][1] for i in range(len(r) - 1)) / 2


def dp(pts, tol):
    """Douglas-Peucker on a closed ring (first point == last point)."""
    if len(pts) < 4:
        return pts
    keep = [False] * len(pts)
    keep[0] = keep[-1] = True
    # A closed ring has no baseline; split it at the point farthest from the start first.
    far = max(range(1, len(pts) - 1), key=lambda i: (pts[i][0] - pts[0][0]) ** 2 + (pts[i][1] - pts[0][1]) ** 2)
    keep[far] = True
    stack = [(0, far), (far, len(pts) - 1)]
    while stack:
        a, b = stack.pop()
        ax, ay = pts[a]
        bx, by = pts[b]
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
            stack += [(a, idx), (idx, b)]
    return [p for p, k in zip(pts, keep) if k]


def dp_line(pts, tol):
    if len(pts) < 3:
        return pts
    ring = dp(pts + [pts[0]], tol)[:-1] if pts[0] != pts[-1] else dp(pts, tol)
    return ring if len(ring) >= 2 else [pts[0], pts[-1]]


def tidy(r, tol, digits=3):
    """Simplify and round a closed ring; None when it collapses."""
    r = dp(r, tol)
    out = []
    for x, y in r:
        p = [round(x, digits), round(y, digits)]
        if not out or p != out[-1]:
            out.append(p)
    if out and out[0] != out[-1]:
        out.append(out[0])
    return out if len(out) >= 4 and abs(area(out)) >= MIN_AREA else None


def inside(pt, ring):
    x, y = pt
    c = False
    for (x1, y1), (x2, y2) in zip(ring, ring[1:]):
        if (y1 > y) != (y2 > y) and x < (x2 - x1) * (y - y1) / (y2 - y1) + x1:
            c = not c
    return c


def to_d3(rings, tol):
    """Rings of mixed orientation (counterclockwise outlines, clockwise holes) -> MultiPolygon in d3 winding:
    clockwise exteriors, counterclockwise holes, each hole under the outline that contains it."""
    outers, holes = [], []
    for r in rings:
        t = tidy(r, tol)
        if not t:
            continue
        (outers if area(t) > 0 else holes).append(t)
    polys = [[o[::-1]] for o in sorted(outers, key=lambda o: abs(area(o)))]
    for h in holes:
        for p in polys:  # smallest containing outline first
            if inside(h[0], p[0]):
                p.append(h[::-1])
                break
    return polys


def clip_ring(ring, box):
    """Sutherland-Hodgman clip of a closed ring to an axis-aligned box."""
    x0, y0, x1, y1 = box
    pts = ring[:-1]
    for edge in range(4):
        if not pts:
            return None
        out = []
        def ins(p):
            return (p[0] >= x0, p[1] >= y0, p[0] <= x1, p[1] <= y1)[edge]
        def cut(p, q):
            if edge in (0, 2):
                x = x0 if edge == 0 else x1
                t = (x - p[0]) / (q[0] - p[0])
                return [x, p[1] + t * (q[1] - p[1])]
            y = y0 if edge == 1 else y1
            t = (y - p[1]) / (q[1] - p[1])
            return [p[0] + t * (q[0] - p[0]), y]
        for i, q in enumerate(pts):
            p = pts[i - 1]
            if ins(q):
                if not ins(p):
                    out.append(cut(p, q))
                out.append(q)
            elif ins(p):
                out.append(cut(p, q))
        pts = out
    return pts + [pts[0]] if len(pts) >= 3 else None


def clip_line(line, box):
    """Keep the runs of a polyline whose points lie inside the box (rivers only need to be roughly cut)."""
    x0, y0, x1, y1 = box
    runs, cur = [], []
    for p in line:
        if x0 <= p[0] <= x1 and y0 <= p[1] <= y1:
            cur.append(p)
        elif cur:
            runs.append(cur)
            cur = []
    if cur:
        runs.append(cur)
    return [r for r in runs if len(r) >= 2]


def polygons(geom):
    if not geom:
        return []
    return geom["coordinates"] if geom["type"] == "MultiPolygon" else [geom["coordinates"]] if geom["type"] == "Polygon" else []


def base_polygon(geom, box=BBOX):
    """Clip a Natural Earth (multi)polygon to the map frame and simplify it, in d3 winding."""
    out = []
    for poly in polygons(geom):
        ext = clip_ring(poly[0], box)
        ext = ext and tidy(ext, TOL_BASE)
        if not ext:
            continue
        if area(ext) > 0:
            ext = ext[::-1]
        rings = [ext]
        for h in poly[1:]:
            h = clip_ring(h, box)
            h = h and tidy(h, TOL_BASE)
            if h:
                rings.append(h if area(h) > 0 else h[::-1])
        out.append(rings)
    return {"type": "MultiPolygon", "coordinates": out} if out else None


# ---------- control areas ----------

def merge_cells(cells):
    """Outline of the union of tessellation cells (lists of counterclockwise rings), by edge cancellation."""
    edges = set()
    for ring in cells:
        for a, b in zip(ring, ring[1:]):
            if a == b:
                continue
            if (b, a) in edges:
                edges.remove((b, a))
            else:
                edges.add((a, b))
    nxt = {}
    for a, b in edges:
        nxt.setdefault(a, []).append(b)
    rings = []
    while nxt:
        start = next(iter(nxt))
        ring, cur = [start], start
        while True:
            outs = nxt.get(cur)
            if not outs:
                break
            b = outs.pop()
            if not outs:
                del nxt[cur]
            ring.append(b)
            cur = b
            if cur == start:
                break
        if len(ring) >= 4 and ring[0] == ring[-1]:
            rings.append([list(p) for p in ring])
    return rings


def vote(wiki, dsm, isw):
    """The status Wikipedia and DeepStateMap (before April 2022: Wikipedia and ISW) agree on, else CONTESTED."""
    pair = [s for s in ((wiki, dsm) if dsm else (wiki, isw)) if s]
    if not pair:
        return "UA"
    return pair[0] if all(v == pair[0] for v in pair) else "CONTESTED"


def read_control(years, refresh):
    """Status per place for the prewar day and for the last available day of every month.
    Returns ({month: {gid: status}}, {month: last date}, {gid: status} on PREWAR)."""
    frames, last_day, prewar = {}, {}, {}
    this_year = datetime.date.today().year
    for y in years:
        path = fetch(VIINA + f"control_latest_{y}.zip", os.path.join(CACHE, "viina", f"control_{y}.zip"), refresh and y == this_year)
        with zipfile.ZipFile(path) as z:
            name = next(n for n in z.namelist() if n.endswith(".csv"))
            with io.TextIOWrapper(z.open(name), encoding="utf-8") as f:
                head = f.readline().rstrip("\n").split(",")
                gi, di = head.index("geonameid"), head.index("date")
                wi, dsi, ii = head.index("status_wiki"), head.index("status_dsm"), head.index("status_isw")
                # Rows are grouped by place and sorted by date, so the last row of a (place, month) run is that month's status.
                cur = None
                for line in f:
                    row = line.split(",")
                    gid, date = row[gi], row[di]
                    status = vote(row[wi], row[dsi], row[ii])
                    if date == PREWAR and status in ("RU", "CONTESTED"):
                        prewar[gid] = status
                    month = date[:6]
                    key = (gid, month)
                    if key != cur:
                        if cur and cur_status in ("RU", "CONTESTED"):
                            frames.setdefault(cur[1], {})[cur[0]] = cur_status
                        cur = key
                    cur_status = status
                    if date > last_day.get(month, ""):
                        last_day[month] = date
                if cur and cur_status in ("RU", "CONTESTED"):
                    frames.setdefault(cur[1], {})[cur[0]] = cur_status
        print(f"  VIINA {y}: read, last day {max(d for m, d in last_day.items() if m.startswith(str(y)))}")
    return frames, last_day, prewar


def build_control(refresh):
    tess = json.load(open(fetch("https://raw.githubusercontent.com/zhukovyuri/VIINA/main/Data/gn_UA_tess.geojson",
                                os.path.join(CACHE, "viina", "gn_UA_tess.geojson"))))
    cells = {}
    for f in tess["features"]:
        gid = str(int(f["properties"]["geonameid"]))
        cells[gid] = [[(round(x, 6), round(y, 6)) for x, y in poly[0]] for poly in f["geometry"]["coordinates"]]
    years = range(FIRST_YEAR, datetime.date.today().year + 1)
    frames, last_day, prewar = read_control(years, refresh)

    def areas(status_by_gid, want):
        sel = [ring for gid, st in status_by_gid.items() if st == want for ring in cells.get(gid, [])]
        return to_d3(merge_cells(sel), TOL_CONTROL) if sel else []

    out = {"source": "VIINA (Zhukov and Ayers); RU where its Wikipedia and DeepStateMap columns (Feb-Mar 2022: Wikipedia and ISW) agree, contested where they differ",
           "license": "ODbL-1.0", "prewar": {"date": PREWAR, "ru": areas(prewar, "RU")}, "months": []}
    for month in sorted(last_day):
        st = frames.get(month, {})
        out["months"].append({"m": f"{month[:4]}-{month[4:]}", "date": last_day[month], "ru": areas(st, "RU"), "contested": areas(st, "CONTESTED")})
    return out


# ---------- basemap ----------

COUNTRIES = {"UKR": "Ukraine", "RUS": "Rusland", "BLR": "Hviderusland", "POL": "Polen", "SVK": "Slovakiet", "HUN": "Ungarn",
             "ROU": "Rumænien", "MDA": "Moldova", "BGR": "Bulgarien", "SRB": "Serbien", "LTU": "Litauen", "GEO": "Georgien", "TUR": "Tyrkiet"}
OBLASTS = {"Cherkasy": "Tjerkasy", "Chernihiv": "Tjernihiv", "Chernivtsi": "Tjernivtsi", "Dnipropetrovs'k": "Dnipropetrovsk",
           "Donets'k": "Donetsk", "Ivano-Frankivs'k": "Ivano-Frankivsk", "Kharkiv": "Kharkiv", "Kherson": "Kherson",
           "Khmel'nyts'kyy": "Khmelnytskyj", "Kiev": "Kyiv (oblast)", "Kiev City": "Kyiv", "Kirovohrad": "Kirovohrad",
           "L'viv": "Lviv", "Luhans'k": "Luhansk", "Mykolayiv": "Mykolajiv", "Odessa": "Odesa", "Poltava": "Poltava",
           "Rivne": "Rivne", "Sumy": "Sumy", "Ternopil'": "Ternopil", "Transcarpathia": "Transkarpatien", "Vinnytsya": "Vinnytsja",
           "Volyn": "Volyn", "Zaporizhzhya": "Zaporizjzja", "Zhytomyr": "Zjytomyr", "Crimea": "Krim", "Sevastopol": "Sevastopol"}
# Russian border regions, drawn for the Kursk incursion and the shelling of Belgorod.
RU_REGIONS = {"Bryansk": "Brjansk", "Kursk": "Kursk", "Belgorod": "Belgorod", "Voronezh": "Voronezj", "Rostov": "Rostov"}
RIVERS = {"Dnipro": "Dnipro", "Desna": "Desna", "Pripyat": "Pripjat", "Prypyat": "Pripjat", "Donets": "Donets", "Seversky Donets": "Donets",
          "Southern Bug": "Sydlige Bug", "Dniester": "Dnjestr", "Prut": "Prut", "Danube": "Donau", "Bratul Chillia": "Donau",
          "Don": "Don", "Oskol": "Oskil", "Seym": "Sejm", "Zakhidnyy Buh": "Vestlige Bug", "Bug": "Vestlige Bug"}
LAKES = {"Kakhovka Reservoir": "Kakhovka-reservoiret", "Kremenchuk Reservoir": "Krementjuk-reservoiret",
         "Kiev Reservoir": "Kyiv-reservoiret", "Syvash": "Sivasj"}


def bbox_of(geom):
    xs, ys = [], []
    def walk(c):
        if c and isinstance(c[0], (int, float)):
            xs.append(c[0]); ys.append(c[1])
        else:
            for x in c or []:
                walk(x)
    walk(geom["coordinates"])
    return (min(xs), min(ys), max(xs), max(ys)) if xs else None


def hits(geom):
    b = geom and bbox_of(geom)
    return b and not (b[2] < BBOX[0] or b[0] > BBOX[2] or b[3] < BBOX[1] or b[1] > BBOX[3])


def ne(name):
    return json.load(open(fetch(NE + name + ".geojson", os.path.join(CACHE, "ne", name + ".geojson"))))


def build_basemap():
    feats = {"countries": [], "regions": [], "rivers": [], "lakes": []}
    # Ukraine's point of view: Crimea belongs to Ukraine.
    for f in ne("ne_10m_admin_0_countries_ukr")["features"]:
        a3 = f["properties"]["ADM0_A3"]
        if a3 in COUNTRIES and hits(f["geometry"]):
            g = base_polygon(f["geometry"])
            if g:
                feats["countries"].append({"type": "Feature", "properties": {"id": a3, "n": COUNTRIES[a3]}, "geometry": g})
    for f in ne("ne_10m_admin_1_states_provinces")["features"]:
        p = f["properties"]
        name, a3 = p["name"], p["adm0_a3"]
        if a3 == "UKR" or name in ("Crimea", "Sevastopol"):
            label, country = OBLASTS.get(name), "UKR"
        elif a3 == "RUS" and name in RU_REGIONS:
            label, country = RU_REGIONS[name], "RUS"
        else:
            continue
        g = base_polygon(f["geometry"])
        if g and label:
            feats["regions"].append({"type": "Feature", "properties": {"n": label, "c": country,
                                     "l": [round(p["longitude"], 2), round(p["latitude"], 2)]}, "geometry": g})
    for src in ("ne_10m_rivers_lake_centerlines", "ne_10m_rivers_europe"):
        for f in ne(src)["features"]:
            name = RIVERS.get(f["properties"].get("name"))
            g = f["geometry"]
            if not name or not hits(g):
                continue
            lines = g["coordinates"] if g["type"] == "MultiLineString" else [g["coordinates"]]
            out = []
            for ln in lines:
                for run in clip_line(ln, BBOX):
                    s = [[round(x, 3), round(y, 3)] for x, y in dp_line(run, TOL_BASE)]
                    if len(s) >= 2:
                        out.append(s)
            if out:
                feats["rivers"].append({"type": "Feature", "properties": {"n": name, "r": f["properties"].get("scalerank")},
                                        "geometry": {"type": "MultiLineString", "coordinates": out}})
    for src in ("ne_10m_lakes", "ne_10m_lakes_europe"):
        for f in ne(src)["features"]:
            if not hits(f["geometry"]):
                continue
            g = base_polygon(f["geometry"])
            if g:
                raw = f["properties"].get("name")
                feats["lakes"].append({"type": "Feature", "properties": {"n": LAKES.get(raw), "id": "kakhovka" if raw == "Kakhovka Reservoir" else None},
                                       "geometry": g})
    return {"bbox": BBOX, "source": "Natural Earth (public domain), Ukrainian point of view",
            **{k: {"type": "FeatureCollection", "features": v} for k, v in feats.items()}}


def write(name, data):
    os.makedirs(OUT, exist_ok=True)
    path = os.path.join(OUT, name)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, separators=(",", ":"))
    print(f"  wrote {os.path.relpath(path, ROOT)} ({os.path.getsize(path) // 1024} KB)")


def main():
    refresh = "--refresh" in sys.argv[1:]
    print("Basemap (Natural Earth)")
    write("basemap.json", build_basemap())
    print("Control areas (VIINA)")
    control = build_control(refresh)
    write("control.json", control)
    m = control["months"]
    print(f"  {len(m)} months, {m[0]['m']} to {m[-1]['m']} (last day {m[-1]['date']})")


if __name__ == "__main__":
    main()
