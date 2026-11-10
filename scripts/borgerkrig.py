#!/usr/bin/env python3
"""Build the data for the American Civil War page (borgerkrig/): a basemap from Natural Earth and, for every month
from November 1860 to June 1865, the area the Confederacy held at the end of the month and the contested areas.

There is no dataset of front lines for this war, so the areas are drawn from the secession dates of the states and a
list of zones (convex polygons) with the months they were held: Union-held parts of the Confederacy are cut out of it,
Confederate incursions into Union states are added, and contested zones are drawn hatched. The result is approximate:
fronts were fluid, and guerrilla war went on behind them.

    python3 scripts/borgerkrig.py
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ukraine import ROOT, CACHE, NE, fetch, area, tidy, to_d3, clip_ring, clip_line, dp_line, polygons  # noqa: E402

OUT = os.path.join(ROOT, "borgerkrig", "data")
BBOX = (-107.5, 24.0, -66.5, 45.2)
TOL = 0.03

FIRST, LAST = "1860-11", "1865-06"


def months():
    y, m = map(int, FIRST.split("-"))
    out = []
    while f"{y}-{m:02d}" <= LAST:
        out.append(f"{y}-{m:02d}")
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)
    return out


# Months each state belonged to the Confederacy (inclusive, status at the end of the month). The end is the month
# before the last Confederate forces there surrendered: Lee on 9 April 1865 (Virginia), Johnston on 26 April (the
# Carolinas, Georgia, Florida), Taylor on 4 May (Alabama, Mississippi), Kirby Smith on 2 June (west of the Mississippi).
SECEDED = {
    "South Carolina": ("1860-12", "1865-03"), "Mississippi": ("1861-01", "1865-04"), "Florida": ("1861-01", "1865-03"),
    "Alabama": ("1861-01", "1865-04"), "Georgia": ("1861-01", "1865-03"), "Louisiana": ("1861-01", "1865-05"),
    "Texas": ("1861-02", "1865-05"), "Virginia": ("1861-04", "1865-03"), "West Virginia": ("1861-04", "1861-06"),
    "Arkansas": ("1861-05", "1865-05"), "North Carolina": ("1861-05", "1865-03"), "Tennessee": ("1861-05", "1865-03"),
}


def box(x0, y0, x1, y1):
    return [[x0, y0], [x1, y0], [x1, y1], [x0, y1]]


def corridor(points, w):
    """Rectangles of half-width w (degrees) along a polyline of (lon, lat) points, each counterclockwise."""
    out = []
    for (ax, ay), (bx, by) in zip(points, points[1:]):
        dx, dy = bx - ax, by - ay
        n = (dx * dx + dy * dy) ** 0.5
        nx, ny = -dy / n * w, dx / n * w
        out.append([[ax - nx, ay - ny], [bx - nx, by - ny], [bx + nx, by + ny], [ax + nx, ay + ny]])
    return out


MISSISSIPPI = [(-90.05, 35.15), (-90.59, 34.53), (-91.2, 33.75), (-91.06, 33.4), (-91.17, 32.8), (-90.88, 32.35),
               (-91.4, 31.56), (-91.27, 30.69), (-91.19, 30.45)]
MARCH_TO_THE_SEA = [(-84.39, 33.75), (-83.23, 33.08), (-81.95, 32.8), (-81.09, 32.08)]

# (kind, first month, last month, zones, states the zone applies to or None for all)
# union: held by the Union inside the Confederacy; csa: held by the Confederacy outside it; contested: drawn hatched.
ZONES = [
    # Virginia
    ("union", "1861-05", "1865-06", [box(-77.35, 38.75, -77.03, 38.95)], None),          # Alexandria and Arlington
    ("union", "1861-05", "1861-06", [box(-81.8, 39.0, -79.45, 40.65)], None),            # north-western Virginia: Wheeling, Grafton, Philippi
    ("union", "1861-05", "1865-06", [box(-76.45, 36.95, -76.25, 37.1)], None),           # Fort Monroe and Hampton
    ("union", "1861-11", "1865-06", [box(-76.1, 37.0, -75.2, 38.05)], None),             # Virginia's Eastern Shore
    ("union", "1862-03", "1862-07", [box(-78.1, 38.45, -76.9, 39.0)], None),             # northern Virginia after Manassas
    ("union", "1862-11", "1863-06", [box(-77.6, 38.32, -76.9, 38.95)], None),            # north of the Rappahannock, Falmouth
    ("union", "1863-07", "1865-06", [box(-78.3, 38.35, -76.9, 39.0)], None),             # north of the Rapidan
    ("union", "1862-05", "1865-06", [box(-76.75, 36.55, -75.9, 37.15)], None),           # Norfolk and Suffolk
    ("union", "1862-05", "1862-07", [box(-77.3, 37.0, -76.3, 37.6)], None),              # McClellan on the Peninsula
    ("union", "1862-08", "1865-06", [box(-76.9, 37.0, -76.3, 37.35)], None),             # Yorktown and Williamsburg
    ("union", "1864-06", "1865-06", [box(-77.35, 37.1, -76.8, 37.45)], None),            # siege lines at Petersburg
    ("union", "1862-03", "1862-04", [box(-78.6, 38.95, -77.7, 39.45)], None),            # Banks in the lower Shenandoah Valley
    ("union", "1862-06", "1862-08", [box(-78.6, 38.95, -77.7, 39.45)], None),
    ("union", "1862-12", "1863-05", [box(-78.6, 38.95, -77.7, 39.45)], None),            # Milroy at Winchester
    ("union", "1864-10", "1865-06", [box(-78.6, 38.95, -77.7, 39.45)], None),            # the lower Shenandoah Valley
    ("contested", "1861-07", "1865-03", [box(-81.6, 37.2, -79.6, 38.6)], ["West Virginia"]),
    # North Carolina
    ("union", "1862-03", "1865-06", [box(-77.2, 34.6, -75.4, 36.6)], None),              # the coast and the sounds
    ("union", "1865-02", "1865-06", [box(-78.3, 33.8, -77.6, 34.5)], None),              # Wilmington
    ("union", "1865-03", "1865-06", [box(-79.6, 34.6, -77.6, 35.5)], None),              # Fayetteville and Goldsboro
    # South Carolina
    ("union", "1861-11", "1865-06", [box(-81.0, 32.0, -80.35, 32.6)], None),             # Port Royal and Beaufort
    ("union", "1865-02", "1865-06", [box(-81.4, 32.0, -79.7, 34.2)], None),              # Sherman, Columbia, Charleston
    ("union", "1865-03", "1865-06", [box(-81.2, 34.2, -79.6, 35.0)], None),
    # Georgia
    ("union", "1863-11", "1864-04", [box(-85.6, 34.75, -85.0, 35.0)], None),             # below Chattanooga, after Missionary Ridge
    ("union", "1864-05", "1864-06", [box(-85.6, 34.0, -84.5, 35.0)], None),              # the Atlanta campaign
    ("union", "1864-07", "1864-08", [box(-85.6, 33.75, -84.2, 35.0)], None),
    ("union", "1864-09", "1864-10", [box(-85.6, 33.55, -84.15, 35.0)], None),            # Atlanta taken
    ("contested", "1864-11", "1864-11", corridor(MARCH_TO_THE_SEA[:3], 0.45), None),     # the march to the sea
    ("contested", "1864-12", "1864-12", corridor(MARCH_TO_THE_SEA, 0.45), None),
    ("union", "1864-12", "1865-06", [box(-81.3, 31.9, -80.85, 32.25)], None),            # Savannah
    # Florida
    ("union", "1861-01", "1865-06", [box(-82.0, 24.4, -80.2, 25.3)], None),              # Key West
    ("union", "1862-05", "1865-06", [box(-87.45, 30.3, -87.0, 30.55)], None),            # Pensacola
    ("union", "1862-03", "1865-06", [box(-81.6, 29.85, -81.25, 30.75)], None),           # Fernandina and St. Augustine
    ("union", "1864-02", "1865-06", [box(-81.75, 30.1, -81.6, 30.5)], None),             # Jacksonville, held from February 1864
    # Alabama and Mississippi
    ("contested", "1862-04", "1865-03", [box(-88.2, 34.4, -85.5, 35.0)], ["Alabama"]),   # the Tennessee valley
    ("union", "1865-04", "1865-06", [box(-88.3, 30.2, -87.8, 30.9), box(-87.2, 32.2, -86.1, 32.6)], None),  # Mobile, Selma, Montgomery
    ("union", "1862-05", "1864-01", [box(-88.7, 34.75, -88.3, 35.0)], None),             # Corinth
    # Louisiana and the Mississippi
    ("union", "1862-04", "1865-06", [box(-90.3, 29.6, -89.6, 30.1)], None),              # New Orleans
    ("union", "1862-05", "1865-06", [box(-90.5, 28.9, -89.0, 30.2)], None),              # around New Orleans
    ("union", "1862-05", "1862-07", [box(-91.35, 30.2, -90.95, 30.6)], None),            # Baton Rouge, given up in August 1862
    ("union", "1862-12", "1865-06", [box(-91.35, 30.2, -90.95, 30.6)], None),            # and retaken in December
    ("union", "1862-10", "1865-06", [box(-91.35, 28.9, -90.5, 30.2)], None),             # the Lafourche district, taken in October 1862
    ("contested", "1862-05", "1865-05", [box(-90.95, 30.2, -89.6, 30.6)], ["Louisiana"]),  # the north shore of Lake Pontchartrain
    ("contested", "1864-03", "1864-04", [box(-93.2, 30.9, -91.6, 31.8)], ["Louisiana"]),  # the Red River campaign
    ("union", "1862-06", "1865-06", corridor(MISSISSIPPI[:1] + [(-90.05, 35.0)], 0.25), None),  # Memphis
    ("union", "1862-07", "1865-06", corridor(MISSISSIPPI[:2], 0.25), None),              # down to Helena
    ("contested", "1863-05", "1863-06", [box(-91.3, 32.15, -90.6, 32.55)], None),        # the siege of Vicksburg
    ("union", "1863-07", "1865-06", corridor(MISSISSIPPI, 0.25), None),                  # the whole river
    # Arkansas
    ("contested", "1862-03", "1863-08", [box(-94.65, 35.4, -92.5, 36.5)], ["Arkansas"]),
    ("union", "1862-07", "1865-06", [box(-91.1, 34.3, -90.5, 34.8)], None),              # Helena
    ("union", "1863-09", "1865-06", [box(-94.65, 34.6, -89.6, 36.5)], None),             # Little Rock and the north
    # Tennessee
    ("union", "1862-02", "1862-02", [box(-88.3, 35.95, -86.4, 36.7)], None),             # Forts Henry and Donelson, Nashville
    ("union", "1862-03", "1862-05", [box(-88.3, 35.5, -86.0, 36.7)], None),
    ("union", "1862-04", "1862-05", [box(-88.6, 35.0, -88.0, 35.9), box(-89.8, 36.2, -89.3, 36.6)], None),  # Shiloh, Island No. 10
    ("union", "1862-06", "1862-08", [box(-90.4, 35.0, -86.2, 36.7)], None),
    ("union", "1862-09", "1862-12", [box(-90.4, 35.0, -88.0, 36.7), box(-88.0, 35.95, -86.4, 36.7)], None),
    ("union", "1863-01", "1863-06", [box(-90.4, 35.0, -88.0, 36.7), box(-88.0, 35.75, -86.2, 36.7)], None),
    ("union", "1863-07", "1863-08", [box(-90.4, 35.0, -85.6, 36.7)], None),              # after Tullahoma
    ("union", "1863-09", "1865-06", [box(-90.4, 35.0, -84.3, 36.7), box(-84.3, 35.6, -83.4, 36.7)], None),  # Knoxville and Chattanooga
    ("contested", "1863-11", "1864-03", [box(-84.3, 35.5, -81.6, 36.7)], ["Tennessee"]), # Longstreet at Knoxville
    ("contested", "1864-11", "1864-12", [box(-88.0, 35.0, -86.5, 36.0)], ["Tennessee"]), # Hood's Tennessee campaign
    # Texas
    ("union", "1863-11", "1864-06", [box(-97.7, 25.8, -97.1, 26.3)], None),              # Brownsville
    ("union", "1862-08", "1865-06", [box(-106.65, 31.4, -106.0, 32.0)], None),           # El Paso and Fort Bliss, retaken by the California Column
    ("union", "1862-10", "1862-12", [box(-95.0, 29.15, -94.7, 29.4)], None),             # Galveston, until 1 January 1863
    # Confederate incursions and allies outside the Confederacy
    ("csa", "1861-09", "1862-01", [box(-89.6, 36.45, -83.6, 37.05)], ["Kentucky"]),       # Columbus to Bowling Green
    ("csa", "1862-09", "1862-09", [box(-85.9, 37.25, -83.6, 38.45)], ["Kentucky"]),       # Bragg and Kirby Smith
    ("csa", "1863-06", "1863-06", [box(-78.3, 39.45, -77.6, 39.75), box(-78.3, 39.73, -76.6, 40.25)], ["Maryland", "Pennsylvania"]),  # Lee before Gettysburg
    ("csa", "1861-08", "1863-06", [box(-100.0, 33.5, -94.4, 37.1)], ["Oklahoma"]),        # the Indian Territory nations
    ("csa", "1863-07", "1865-05", [box(-100.0, 33.5, -94.4, 35.4)], ["Oklahoma"]),
    ("csa", "1861-08", "1862-06", [box(-114.9, 31.3, -103.0, 34.0)], ["New Mexico", "Arizona"]),  # Confederate Arizona
    ("csa", "1862-03", "1862-03", [box(-107.2, 34.0, -105.3, 35.8)], ["New Mexico"]),     # Albuquerque and Santa Fe
    ("contested", "1861-08", "1862-02", [box(-94.65, 36.5, -92.4, 38.2)], ["Missouri"]),  # Wilson's Creek
    ("contested", "1861-09", "1861-09", [box(-94.6, 38.2, -93.2, 39.3)], ["Missouri"]),   # Lexington
    ("contested", "1864-09", "1864-10", [box(-94.6, 37.0, -90.5, 39.0)], ["Missouri"]),   # Price's raid
]


# ---------- clipping by convex zones ----------

def halfplanes(zone):
    """Inside of a counterclockwise convex polygon as half-planes nx*x + ny*y <= c."""
    out = []
    for (ax, ay), (bx, by) in zip(zone, zone[1:] + zone[:1]):
        nx, ny = by - ay, ax - bx
        out.append((nx, ny, nx * ax + ny * ay))
    return out


def clip_hp(ring, nx, ny, c):
    pts, out = ring[:-1], []
    for i, q in enumerate(pts):
        p = pts[i - 1]
        fp, fq = nx * p[0] + ny * p[1] - c, nx * q[0] + ny * q[1] - c
        if (fq <= 0) != (fp <= 0):
            t = fp / (fp - fq)
            out.append([p[0] + t * (q[0] - p[0]), p[1] + t * (q[1] - p[1])])
        if fq <= 0:
            out.append(q)
    return out + [out[0]] if len(out) >= 3 and abs(area(out + [out[0]])) > 1e-5 else None


def intersect(ring, zone):
    for hp in halfplanes(zone):
        ring = ring and clip_hp(ring, *hp)
    return ring


def subtract(ring, zone):
    """ring minus a convex zone, as disjoint pieces."""
    pieces = []
    for nx, ny, c in halfplanes(zone):
        out = clip_hp(ring, -nx, -ny, -c)
        if out:
            pieces.append(out)
        ring = clip_hp(ring, nx, ny, c)
        if not ring:
            break
    return pieces


# ---------- data ----------

def ne(name):
    return json.load(open(fetch(NE + name + ".geojson", os.path.join(CACHE, "ne", name + ".geojson"))))


def hits(geom):
    xs = [x for poly in polygons(geom) for x, _ in poly[0]]
    ys = [y for poly in polygons(geom) for _, y in poly[0]]
    return xs and not (max(xs) < BBOX[0] or min(xs) > BBOX[2] or max(ys) < BBOX[1] or min(ys) > BBOX[3])


def outlines(geom, tol=TOL):
    """Simplified counterclockwise outer rings of a (multi)polygon inside the map frame."""
    out = []
    for poly in polygons(geom):
        r = clip_ring(poly[0], BBOX)
        r = r and tidy(r, tol)
        if r:
            out.append(r if area(r) > 0 else r[::-1])
    return out


STATE_NAMES = {"District of Columbia": "Washington D.C.", "Oklahoma": "Indianerterritoriet"}
COUNTRIES = {"USA": "USA", "CAN": "Britisk Nordamerika (Canada)", "MEX": "Mexico", "CUB": "Cuba (spansk)", "BHS": "Bahamas (britisk)"}
RIVERS = {"Mississippi": "Mississippi", "Ohio": "Ohio", "Tennessee": "Tennessee", "Cumberland": "Cumberland", "Potomac": "Potomac",
          "James": "James", "Missouri": "Missouri", "Arkansas": "Arkansas", "Red": "Red River", "Rio Grande": "Rio Grande",
          "Savannah": "Savannah", "Chattahoochee": "Chattahoochee", "Alabama": "Alabama", "Tombigbee": "Tombigbee",
          "Susquehanna": "Susquehanna", "Kanawha": "Kanawha", "Roanoke": "Roanoke", "Cape Fear": "Cape Fear", "Santee": "Santee",
          "Pearl": "Pearl", "White": "White River", "Canadian": "Canadian", "Brazos": "Brazos", "Pecos": "Pecos", "Holston": "Holston",
          "Kentucky": "Kentucky", "Wabash": "Wabash", "Illinois": "Illinois", "Delaware": "Delaware", "Hudson": "Hudson"}


def build():
    states = {}
    regions = []
    for f in ne("ne_10m_admin_1_states_provinces")["features"]:
        p = f["properties"]
        if p["adm0_a3"] != "USA" or not f["geometry"] or not hits(f["geometry"]):
            continue
        rings = outlines(f["geometry"])
        if not rings:
            continue
        states[p["name"]] = rings
        regions.append({"type": "Feature", "properties": {"n": STATE_NAMES.get(p["name"], p["name"]), "id": p["name"],
                                                          "l": [round(p["longitude"], 2), round(p["latitude"], 2)]},
                        "geometry": {"type": "MultiPolygon", "coordinates": [[r[::-1]] for r in rings]}})
    countries = []
    for f in ne("ne_10m_admin_0_countries")["features"]:
        a3 = f["properties"]["ADM0_A3"]
        if a3 in COUNTRIES and hits(f["geometry"]):
            rings = outlines(f["geometry"], 0.03)
            if rings:
                countries.append({"type": "Feature", "properties": {"id": a3, "n": COUNTRIES[a3]},
                                  "geometry": {"type": "MultiPolygon", "coordinates": [[r[::-1]] for r in rings]}})
    rivers = []
    for f in ne("ne_10m_rivers_lake_centerlines")["features"]:
        name = RIVERS.get(f["properties"].get("name"))
        g = f["geometry"]
        if not name or not g:
            continue
        lines = g["coordinates"] if g["type"] == "MultiLineString" else [g["coordinates"]]
        out = [[[round(x, 3), round(y, 3)] for x, y in dp_line(run, TOL)] for ln in lines for run in clip_line(ln, BBOX)]
        out = [s for s in out if len(s) >= 2]
        if out:
            rivers.append({"type": "Feature", "properties": {"n": name, "r": f["properties"].get("scalerank")},
                           "geometry": {"type": "MultiLineString", "coordinates": out}})
    lakes = []
    for f in ne("ne_10m_lakes")["features"]:
        if f["geometry"] and hits(f["geometry"]) and (f["properties"].get("scalerank") or 9) <= 3:
            rings = outlines(f["geometry"])
            if rings:
                lakes.append({"type": "Feature", "properties": {"n": None, "id": None},
                              "geometry": {"type": "MultiPolygon", "coordinates": [[r[::-1]] for r in rings]}})
    base = {"bbox": BBOX, "source": "Natural Earth (public domain); today's state borders",
            **{k: {"type": "FeatureCollection", "features": v} for k, v in
               (("countries", countries), ("regions", regions), ("rivers", rivers), ("lakes", lakes))}}

    out = {"source": "Drawn for this page from secession dates and the zones in scripts/borgerkrig.py (approximate)",
           "license": "GPL-3.0", "prewar": {"date": "18601106", "ru": []}, "months": []}
    for m in months():
        held = []
        for name, (a, b) in SECEDED.items():
            if a <= m <= b:
                held += [list(r) for r in states[name]]
        csa, contested = [], []
        for kind, a, b, zones, only in ZONES:
            if not a <= m <= b:
                continue
            if kind == "union":
                for z in zones:
                    held = [piece for r in held for piece in subtract(r, z)]
            else:
                target = csa if kind == "csa" else contested
                for z in zones:
                    if only:
                        target += [r for s in only for ring in states.get(s, []) for r in [intersect(ring, z)] if r]
                    else:
                        target.append(z + [z[0]])
        y, mo = map(int, m.split("-"))
        last = [31, 29 if y % 4 == 0 else 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31][mo - 1]
        out["months"].append({"m": m, "date": f"{y}{mo:02d}{last}", "ru": densify(to_d3(held + csa, TOL)), "contested": densify(to_d3(contested, TOL))})
    return base, out


def densify(polys, step=1.0):
    """Extra points on long edges, so that d3 draws them as the straight lines they are in longitude and latitude
    (it draws edges as great circles, which can turn a thin sliver inside out)."""
    out = []
    for poly in polys:
        rings = []
        for r in poly:
            pts = [r[0]]
            for (ax, ay), (bx, by) in zip(r, r[1:]):
                n = int(max(abs(bx - ax), abs(by - ay)) / step)
                pts += [[ax + (bx - ax) * i / (n + 1), ay + (by - ay) * i / (n + 1)] for i in range(1, n + 1)]
                pts.append([bx, by])
            rings.append([[round(x, 2), round(y, 2)] for x, y in pts])
        out.append(rings)
    return out


def write(name, data):
    os.makedirs(OUT, exist_ok=True)
    path = os.path.join(OUT, name)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, separators=(",", ":"))
    print(f"  wrote {os.path.relpath(path, ROOT)} ({os.path.getsize(path) // 1024} KB)")


def main():
    base, control = build()
    write("basemap.json", base)
    write("control.json", control)
    print(f"  {len(control['months'])} months, {control['months'][0]['m']} to {control['months'][-1]['m']}")


if __name__ == "__main__":
    main()
