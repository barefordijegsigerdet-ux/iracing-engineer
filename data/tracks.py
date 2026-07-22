"""
Bane-database. Samme princip som data/cars.py: struktureret og let at
udvide. TRACK_ROSTER er den fulde liste vi gerne vil dække til sidst;
TRACK_DB har kun de baner der har detaljerede noter indtil videre.
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

TRACK_DB = {
    "Zandvoort": {
        "map": "https://www.iracing.com/wp-content/uploads/2020/06/zandvoort-map.png",
        "notes": {
            "T1 (Tarzan)": "Brems sent, fokuser på trail-braking for at rotere bilen til en sen apex.",
            "T3 (Hugenholtz)": "Hold den høje linje i bankingen for at få maksimal fart ud på langsiden.",
        },
    },
    "Spa-Francorchamps": {
        "map": "https://www.iracing.com/wp-content/uploads/2020/06/spa-map.png",
        "notes": {
            "Eau Rouge": "Hold den fladt, men vær præcis med din 'turn-in'.",
            "Pouhon": "Vigtigt med høj minimumshastighed. Slip gassen let, men brems minimalt.",
            "La Source": "Sen bremsning, men prioritér god exit til Kemmel frem for hurtig indgang.",
            "Bus Stop": "Rytmen (retning-vægt-retning) betyder mere end topfart gennem chikanen.",
        },
    },
    "Navarra": {
        "map": "",
        "notes": {
            "Sektor 1 (langsomme sving)": "Fokuser på exit-hastighed frem for apex-hastighed — korte lige stykker straffer dårlig traktion hårdt.",
        },
    },
}


def list_categories() -> list[str]:
    return list(TRACK_ROSTER.keys())


def get_track_data(track: str) -> dict:
    return TRACK_DB.get(track, {"map": "", "notes": {"Info": "Vælg en bane for at se noter."}})


def coverage_report() -> dict[str, list[str]]:
    have = set(TRACK_DB.keys())
    missing = {}
    for cat, tracks in TRACK_ROSTER.items():
        gap = [t for t in tracks if t not in have]
        if gap:
            missing[cat] = gap
    return missing
