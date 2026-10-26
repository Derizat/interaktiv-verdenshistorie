#!/usr/bin/env python3
"""Build the map data for rom/: a Mediterranean basemap from Natural Earth and the regions of scripts/rome_regions.py.

Usage:
    python3 scripts/rome.py

Writes rom/data/basemap.json (sea, lakes, rivers) and rom/data/regions.json (regions with their rulers year by year,
the anchor points the page builds its Voronoi cells from, and each region's land area). Natural Earth is downloaded to
.cache/ne/ the first time (shared with scripts/ukraine.py).

Land area per region: the frame is sampled on a 1/8 degree grid; a sample counts as land when it lies outside the sea
and the lakes, and it belongs to the region of its nearest anchor (distances measured with the east-west degree
shrunk by cos(latitude), close to the page's conformal projection). The areas are rough, so the page rounds them.
"""
import json
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ukraine as U  # noqa: E402  (shared Natural Earth download and geometry helpers)
from rome_regions import FRONTIERS, REGIONS  # noqa: E402

ROOT = U.ROOT
OUT = os.path.join(ROOT, "rom", "data")
# Map frame: from Ireland and Portugal to the Caspian Sea and the Persian Gulf, from the Sahara to Denmark and Sweden.
BBOX = (-11.0, 22.5, 52.0, 58.6)
TOL = 0.02          # Douglas-Peucker tolerance in degrees (about 2 km)
MIN_AREA = 0.01     # drop sea rings and lakes smaller than this many square degrees
FRONTIER_OFFSET = 0.12
STEP = 0.125        # sampling grid for the land areas, in degrees

RIVERS = {
    "Nile": "Nilen", "Rosetta Branch": "Nilen", "Damietta Branch": "Nilen",
    "Danube": "Donau", "Donau": "Donau", "Bratul Chillia": "Donau", "Bratul Sulina": "Donau", "Bratul Sfintu Gheorghe": "Donau", "Borcea": "Donau",
    "Euphrates": "Eufrat", "Firat": "Eufrat", "Al Furat": "Eufrat", "Shatt al Arab": "Shatt al-Arab",
    "Tigris": "Tigris", "Dicle": "Tigris",
    "Rhine": "Rhinen", "Rhein": "Rhinen", "Rhin": "Rhinen", "Nederrijn": "Rhinen", "Lek": "Rhinen", "Waal": "Rhinen", "IJssel": "Rhinen",
    "Volga": "Volga", "Dnipro": "Dnepr", "Dnepre": "Dnepr", "Dniester": "Dnestr", "Don": "Don", "Southern Bug": "Sydlige Bug",
    "Seine": "Seine", "Loire": "Loire", "Garonne": "Garonne", "Rhône": "Rhône", "Rhne": "Rhône", "Saône": "Saône", "Sane": "Saône",
    "Mosel": "Mosel", "Maas": "Maas", "Schelde": "Schelde", "Main": "Main", "Neckar": "Neckar", "Weser": "Weser", "Ems": "Ems",
    "Elbe": "Elben", "Oder": "Oder", "Vistula": "Weichsel", "Inn": "Inn",
    "Thames": "Themsen", "Severn": "Severn", "Trent": "Trent",
    "Ebro": "Ebro", "Tajo": "Tajo", "Tejo": "Tajo", "Duero": "Duero", "Guadiana": "Guadiana", "Guadalquivir": "Guadalquivir",
    "Po": "Po", "Tevere": "Tiberen", "Adige": "Adige",
    "Tisa": "Tisza", "Sava": "Sava", "Drau": "Drava", "Morava": "Morava", "Prut": "Prut", "Olt": "Olt", "Mures": "Mureș",
    "Evros": "Hebros", "Maritsa": "Hebros", "Strymnas": "Strymon", "Strimonas": "Strymon", "Haliacmon": "Haliakmon",
    "Kiz?lirmak": "Halys", "Kızılırmak": "Halys", "Sakarya": "Sangarios", "Byk Menderes": "Maiandros", "Büyük Menderes": "Maiandros",
    "Ceyhan": "Pyramos", "Aras": "Araxes", "Kura": "Kura", "Kuban": "Kuban", "Terek": "Terek", "Karkheh": "Karkheh", "Jordan": "Jordan",
    "Shannon": "Shannon", "Oued Sebou": "Sebou", "Moulouya": "Moulouya",
}
BIG_RIVERS = {"Nilen", "Donau", "Eufrat", "Tigris", "Rhinen", "Volga", "Dnepr"}
# Natural lakes only (no modern reservoirs), with Danish names where one is used.
LAKES = {"Dead Sea": "Det Døde Hav", "Sea of Galilee": "Genesaret Sø", "Lake Van": "Vansøen", "Lake Urmia": "Urmiasøen", "Lake Sevan": "Sevansøen",
         "Lake Tuz": None, "Beyşehir": None, "Eğirdir": None, "İznik Gölü": None, "Lake Balaton": "Balaton", "Neusiedlersee": None,
         "Lake Geneva": "Genfersøen", "Bodensee": "Bodensøen", "Lago di Como": None, "Lago di Garda": "Gardasøen", "Neuchâtel": None,
         "Vierwaldstättersee": None, "Zürichsee": None, "Trasimeno": "Trasimenersøen", "Lago di Bolsena": None, "Lake Skadar": None,
         "Vänern": "Vänern", "Vättern": "Vättern", "Lough Neagh": None, "Loch Ness": None, "Syvash": None, "Zalew Wislany": None,
         "Kaliningradskiy Zaliv": None, "Lake Peipus": None}


def densify(r, step=0.5):
    """Add points along long straight edges: d3 draws an edge as a great circle, which bends away from a parallel
    (the clipped frame edges along 22.5° and 58.6° N would cut wedges across the map)."""
    out = [r[0]]
    for (x1, y1), (x2, y2) in zip(r, r[1:]):
        n = int(max(abs(x2 - x1), abs(y2 - y1)) / step)
        out += [[x1 + (x2 - x1) * i / (n + 1), y1 + (y2 - y1) * i / (n + 1)] for i in range(1, n + 1)]
        out.append([x2, y2])
    return out


def polygon(geom, tol=TOL, min_area=MIN_AREA):
    """Clip a Natural Earth (multi)polygon to the frame and simplify it, in d3 winding (clockwise exteriors)."""
    out = []
    for poly in U.polygons(geom):
        rings = []
        for k, ring in enumerate(poly):
            r = U.clip_ring(ring, BBOX)
            r = r and U.dp(r, tol)
            if not r or len(r) < 4 or abs(U.area(r)) < min_area:
                if k == 0:
                    break
                continue
            r = [[round(x, 3), round(y, 3)] for x, y in densify(r)]
            # Exterior clockwise, holes counterclockwise (d3's spherical winding).
            rings.append(r[::-1] if (U.area(r) > 0) == (k == 0) else r)
        if rings:
            out.append(rings)
    return {"type": "MultiPolygon", "coordinates": out} if out else None


def in_frame(geom):
    b = U.bbox_of(geom)
    return b and not (b[2] < BBOX[0] or b[0] > BBOX[2] or b[3] < BBOX[1] or b[1] > BBOX[3])


def build_basemap():
    sea = polygon(U.ne("ne_10m_ocean")["features"][0]["geometry"])
    lakes, rivers = [], {}
    for src in ("ne_10m_lakes", "ne_10m_lakes_europe"):
        for f in U.ne(src)["features"]:
            raw = f["properties"].get("name")
            if raw not in LAKES or not f.get("geometry") or not in_frame(f["geometry"]):
                continue
            g = polygon(f["geometry"], tol=0.01, min_area=0.002)
            if g:
                lakes.append({"type": "Feature", "properties": {"n": LAKES[raw]}, "geometry": g})
    for src in ("ne_10m_rivers_lake_centerlines", "ne_10m_rivers_europe"):
        for f in U.ne(src)["features"]:
            name = RIVERS.get(f["properties"].get("name"))
            g = f.get("geometry")
            if not name or not g or not in_frame(g):
                continue
            lines = g["coordinates"] if g["type"] == "MultiLineString" else [g["coordinates"]]
            for ln in lines:
                for run in U.clip_line(ln, BBOX):
                    s = [[round(x, 3), round(y, 3)] for x, y in U.dp_line(run, TOL)]
                    if len(s) >= 2:
                        rivers.setdefault(name, []).append(s)
    rivers = [{"type": "Feature", "properties": {"n": n, "big": n in BIG_RIVERS}, "geometry": {"type": "MultiLineString", "coordinates": c}}
              for n, c in sorted(rivers.items())]
    return {"bbox": BBOX, "source": "Natural Earth (public domain)", "sea": sea,
            "lakes": {"type": "FeatureCollection", "features": lakes}, "rivers": {"type": "FeatureCollection", "features": rivers}}


def frontier_anchors():
    """Anchor pairs either side of each frontier line, so the Voronoi border between the two regions follows it."""
    out = []
    for line, left, right in FRONTIERS:
        for (x1, y1), (x2, y2) in zip(line, line[1:]):
            k = math.cos(math.radians((y1 + y2) / 2))
            dx, dy = (x2 - x1) * k, y2 - y1
            L = math.hypot(dx, dy)
            n = max(1, round(L / 0.35))
            nx, ny = -dy / L, dx / L  # unit normal pointing left of the direction of travel
            for i in range(n):
                t = (i + 0.5) / n
                x, y = x1 + (x2 - x1) * t, y1 + (y2 - y1) * t
                out.append((round(x + nx * FRONTIER_OFFSET / k, 3), round(y + ny * FRONTIER_OFFSET, 3), left))
                out.append((round(x - nx * FRONTIER_OFFSET / k, 3), round(y - ny * FRONTIER_OFFSET, 3), right))
    return out


def water_rows(geoms):
    """For each sample row, the sorted x crossings of all water rings: a point is in water between crossings 1-2, 3-4, ..."""
    rings = [r for g in geoms for poly in g["coordinates"] for r in poly]
    rows = {}
    y = BBOX[1] + STEP / 2
    while y < BBOX[3]:
        xs = []
        for r in rings:
            for (x1, y1), (x2, y2) in zip(r, r[1:]):
                if (y1 > y) != (y2 > y):
                    xs.append(x1 + (y - y1) * (x2 - x1) / (y2 - y1))
        rows[round(y, 4)] = sorted(xs)
        y += STEP
    return rows


def region_areas(anchors, ids, base):
    """Land area (km2) per region: nearest-anchor labelling of a 1/8 degree grid of land samples."""
    from bisect import bisect_right
    rows = water_rows([base["sea"]] + [f["geometry"] for f in base["lakes"]["features"]])
    buckets = {}
    for i, (x, y, _) in enumerate(anchors):
        buckets.setdefault((math.floor(x), math.floor(y)), []).append(i)
    km2 = [0.0] * len(ids)
    for y, xs in rows.items():
        k = math.cos(math.radians(y))
        cell = (STEP * 111.32 * k) * (STEP * 110.57)
        x = BBOX[0] + STEP / 2
        while x < BBOX[2]:
            if bisect_right(xs, x) % 2 == 0:  # an even number of crossings to the left: land
                bx, by = math.floor(x), math.floor(y)
                best, bi = 1e9, -1
                for r in range(0, 6):
                    for gx in range(bx - r, bx + r + 1):
                        for gy in range(by - r, by + r + 1):
                            if max(abs(gx - bx), abs(gy - by)) != r:
                                continue
                            for i in buckets.get((gx, gy), ()):
                                ax, ay, _ = anchors[i]
                                d = ((ax - x) * k) ** 2 + (ay - y) ** 2
                                if d < best:
                                    best, bi = d, i
                    if bi >= 0 and math.sqrt(best) < r - 1:
                        break
                if bi >= 0:
                    km2[ids.index(anchors[bi][2])] += cell
            x += STEP
    return km2


def main():
    print("Basemap (Natural Earth)")
    base = build_basemap()
    U.OUT = OUT
    U.write("basemap.json", base)
    print("Regions")
    ids = list(REGIONS)
    anchors = [(x, y, rid) for rid, (_, pts, _) in REGIONS.items() for x, y in pts] + frontier_anchors()
    for rid, (name, pts, t) in REGIONS.items():
        years = sorted((a, b) for a, b, *_ in t)
        assert years[0][0] == -509 and years[-1][1] == 476, (rid, "must cover 509 BC to AD 476")
        for (a1, b1), (a2, b2) in zip(years, years[1:]):
            assert a2 == b1 + 1 or (b1 == -1 and a2 == 1), (rid, "gap or overlap", b1, a2)
    km2 = region_areas(anchors, ids, base)
    regions = [{"id": rid, "n": name, "km2": round(km2[i] / 100) * 100,
                "t": [[a, b, o] + ([note] if note else []) for a, b, o, note in t]} for i, (rid, (name, _, t)) in enumerate(REGIONS.items())]
    data = {"regions": regions, "anchors": [[x, y, ids.index(rid)] for x, y, rid in anchors]}
    U.write("regions.json", data)
    print(f"  {len(regions)} regions, {len(anchors)} anchors, {sum(km2) / 1e6:.1f} million km2 of land in the frame")


if __name__ == "__main__":
    main()
