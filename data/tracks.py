"""
Bane-database. Indeholder KUN verificerede bane-kort — ingen
sving-for-sving-tekstnoter, fordi de tidligere var skrevet ud fra generel
viden uden opslag/verificering ("gætværk"). Al banespecifik coaching skal
i stedet komme fra faktisk telemetri (se metrics/delta-funktionerne i
app.py og data/cars.py), ikke fra hardkodede tekstbeskrivelser.

Om "map"-feltet: bruger Wikimedia Commons' stabile Special:FilePath-URL
(https://commons.wikimedia.org/wiki/Special:FilePath/<filnavn>), som altid
peger på den nyeste version af filen uanset intern hash. Kortene er
CC BY-SA-licenserede baneskitser (ikke iRacing's egne), og filnavnet er
verificeret via opslag før det blev sat ind her — se map_coverage_report()
for hvilke baner der mangler et verificeret kort endnu.
"""

TRACK_ROSTER = {
    "Road (Europa)": [
        "Spa-Francorchamps", "Zandvoort", "Nürburgring GP", "Nürburgring Nordschleife",
        "Monza", "Silverstone", "Paul Ricard", "Barcelona", "Brands Hatch",
        "Navarra", "Hungaroring", "Imola", "Mount Panorama (Bathurst)",
    ],
    "Road (Nordamerika)": [
        "Road America", "Watkins Glen", "Sebring", "Daytona (road course)",
        "Laguna Seca", "COTA", "Sonoma", "Mid-Ohio", "VIR",
    ],
    "Oval": [
        "Daytona (oval)", "Talladega", "Charlotte", "Bristol", "Martinsville",
        "Richmond", "Homestead-Miami", "Phoenix",
    ],
}

_WIKI = "https://commons.wikimedia.org/wiki/Special:FilePath/"

# Kun baner med et verificeret Commons-filnavn har en post her.
TRACK_DB = {
    "Zandvoort":                 {"map": _WIKI + "Zandvoort.svg"},
    "Spa-Francorchamps":         {"map": _WIKI + "Spa-Francorchamps of Belgium.svg"},
    "Nürburgring GP":            {"map": _WIKI + "Nürburgring - Grand-Prix-Strecke.svg"},
    "Nürburgring Nordschleife":  {"map": _WIKI + "Nordschleife.svg"},
}


def list_categories() -> list[str]:
    return list(TRACK_ROSTER.keys())


def get_track_data(track: str) -> dict:
    return TRACK_DB.get(track, {"map": ""})


def coverage_report() -> dict[str, list[str]]:
    """Baner i TRACK_ROSTER der slet ikke har en post (heller ikke kort) endnu."""
    have = set(TRACK_DB.keys())
    missing = {}
    for cat, tracks in TRACK_ROSTER.items():
        gap = [t for t in tracks if t not in have]
        if gap:
            missing[cat] = gap
    return missing


def map_coverage_report() -> list[str]:
    """Alle baner i rosteret der endnu ikke har et verificeret kort."""
    have_map = {name for name, data in TRACK_DB.items() if data.get("map")}
    return [t for cat in TRACK_ROSTER.values() for t in cat if t not in have_map]
