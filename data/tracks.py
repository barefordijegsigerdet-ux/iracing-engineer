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
    "Nürburgring GP": {
        "map": "",
        "notes": {
            "T1 (Yokohama-S)": "Dobbeltapex — brems lige, hold bilen rolig gennem første del så du har grip til retningsskiftet.",
            "T4 (Ford-Kurve)": "Lang, hurtig venstre — commitment kræver tillid til frontgrip, tøven her koster mest tid på hele banen.",
            "T13 (Veedol-Schikane)": "Sen bremsning ind, men prioritér lige linje ud mod målstregen.",
        },
    },
    "Nürburgring Nordschleife": {
        "map": "",
        "notes": {
            "Hatzenbach": "Hurtige retningsskift lige efter start — hold linjen flydende, undgå at 'firkante' svingene.",
            "Fuchsröhre": "Dyb dal med bakketop — bilen letter, brems ikke midt i luften, vent til den lander.",
            "Karussell": "Kør ind i den bankede rille — den giver mere grip end det ser ud til, men gassen skal på gradvist.",
            "Döttinger Höhe": "Lang ligestykke — dette er hvor lav drag/høj topfart-setup betaler sig mest på hele banen.",
        },
    },
    "Monza": {
        "map": "",
        "notes": {
            "Prima Variante": "Sen, hård bremsning fra topfart — bilen skal være stabil i ret linje under indbremsning, ikke i sving.",
            "Lesmo 1+2": "Mellemhurtige sving hvor exit-traktion til den lange lige bagefter betyder mere end apex-fart.",
            "Parabolica": "Lang, åbnende sving — sen apex og tidlig gas er nøglen til topfart ud på mål-ligestykket.",
        },
    },
    "Silverstone": {
        "map": "",
        "notes": {
            "Maggotts/Becketts": "Hurtigt retningsskift-kompleks — kræver stabil, forudsigelig bagende, det er intet sted at rette fejl undervejs.",
            "Copse": "Høj indgangsfart i næsten fuld gas — commitment og tillid til frontgrip er alt.",
            "Stowe": "Sen bremsning, bred bane giver mulighed for forskellige linjer — prioritér god exit mod Vale.",
        },
    },
    "Paul Ricard": {
        "map": "",
        "notes": {
            "Signes": "Lang, hurtig højresving i næsten fuld gas — aero-balance ved høj fart testes hårdt her.",
            "Mistral-chikane": "Meget sen bremsning efter det lange ligestykke — bremseeffektivitet ved høj fart er kritisk.",
        },
    },
    "Barcelona": {
        "map": "",
        "notes": {
            "T3": "Lang, konstant-radius højresving — sætter vedvarende belastning på dæk, mid-corner grip er nøglen.",
            "T9-10 (Campsa)": "Hurtig, blind indgang — kræver commitment, exit-fart ind mod sidste sektor er vigtig.",
        },
    },
    "Brands Hatch": {
        "map": "",
        "notes": {
            "Paddock Hill Bend": "Bakke ned i svinget — bilen letter under kompression, timing af bremsning er svær at vænne sig til.",
            "Druids": "Hårnål op ad bakke — sen bremsning straffes hårdt fordi exit er i op-bakke, prioritér tidlig gas.",
        },
    },
    "Hungaroring": {
        "map": "",
        "notes": {
            "T1-2": "Langsomt kompleks lige efter mål — god exit ud af T2 sætter farten for hele ligestykket bagefter.",
            "T4": "Snæver, teknisk sving — banen er generelt lav-grip og snoet, mekanisk balance betyder mere end aero.",
        },
    },
    "Imola": {
        "map": "",
        "notes": {
            "Tamburello": "Hurtig, næsten fuld gas venstre — respekt for kerbs og bane-grænser er vigtigere end rå fart.",
            "Rivazza": "Sidste sving før mål — god exit-traktion herfra sætter topfarten på hele start/mål-ligestykket.",
        },
    },
    "Mount Panorama (Bathurst)": {
        "map": "",
        "notes": {
            "Mountain Straight/Griffins Bend": "Stejl bakke op — bilen mister synligt fart, hold momentum ind i svinget.",
            "The Chase": "Snæver chikane efter Conrod Straight i topfart — meget sen, præcis bremsning, lille fejlmargin pga. mure tæt på.",
        },
    },
    "Road America": {
        "map": "",
        "notes": {
            "Turn 5 (Kink)": "Fuld gas eller tæt på — commitment her sætter farten hele vejen ned til Turn 6.",
            "Canada Corner (T8)": "Sen bremsning fra topfart efter det lange lige stykke — traktion ud er vigtigere end apex-fart.",
        },
    },
    "Watkins Glen": {
        "map": "",
        "notes": {
            "The Esses": "Hurtigt retningsskift-kompleks — rytme og flow betyder mere end at ramme hver apex perfekt.",
            "The Boot": "Lang, snoet sektion med varierende radius — tålmodighed med gassen betaler sig her.",
            "Turn 10 (bus stop)": "Sen bremsning ind i chikanen, prioritér lige linje ud mod mål-ligestykket.",
        },
    },
    "Sebring": {
        "map": "",
        "notes": {
            "Generelt": "Meget bumpet betonoverflade — blødere setup end normalt hjælper med at holde dækkontakt gennem hele banen.",
            "Turn 17 (Sunset Bend)": "Hurtig, bumpet højresving mod mål — bilen skal kunne håndtere bump uden at miste retning.",
        },
    },
    "Daytona (road course)": {
        "map": "",
        "notes": {
            "Bus Stop chikane": "Sen bremsning fra banked oval-sektion — stort fartfald kræver god bremsestabilitet.",
            "International Horseshoe": "Langsomt, snævert sving — prioritér exit-traktion mod den følgende lige.",
        },
    },
    "Laguna Seca": {
        "map": "",
        "notes": {
            "The Corkscrew": "Blind, brat nedkørsel — bilen letter over toppen, vent med at rette op til du kan se banen igen.",
            "Turn 2": "Sen bremsning op ad bakke — bakken hjælper bremselængden, så du kan bremse senere end det føles naturligt.",
        },
    },
    "COTA": {
        "map": "",
        "notes": {
            "Turn 1": "Brat bakke op til blind apex — commitment kræver tillid, det er svært at se exit før du er der.",
            "Esses (T3-6)": "Hurtigt retningsskift ned ad bakke — flow og rytme er vigtigere end at bremse for hvert enkelt sving.",
        },
    },
    "Sonoma": {
        "map": "",
        "notes": {
            "Turn 7 (The Carousel)": "Lang, konstant-radius sving med højdeforskel — hold en jævn linje, undgå at rette bilen for tidligt.",
        },
    },
    "Mid-Ohio": {
        "map": "",
        "notes": {
            "The Keyhole (T2)": "Snævert, teknisk sving efter langt bremsezone — god rotation her sætter farten for hele mid-sektionen.",
            "Carousel": "Lang, banket sving — bilen kan bære mere fart end det føles, brug bankingen.",
        },
    },
    "VIR": {
        "map": "",
        "notes": {
            "Turn 1 (complex)": "Hurtigt retningsskift-kompleks lige efter start — konsistent rytme slår enkelte perfekte apexer.",
            "Oak Tree (T11)": "Langsomt sving før mål-ligestykket — exit-traktion herfra betyder mere end apex-fart.",
        },
    },
    "Daytona (oval)": {
        "map": "",
        "notes": {
            "Generelt": "Superspeedway med restrictor/drafting-dynamik — banelinje og timing i draft betyder ofte mere end rå setup-balance.",
        },
    },
    "Talladega": {
        "map": "",
        "notes": {
            "Generelt": "Bredeste og hurtigste oval i rosteret — pack-racing og draft-timing dominerer, setup handler mest om stabilitet i trafik.",
        },
    },
    "Charlotte": {
        "map": "",
        "notes": {
            "Turn 1-2": "Indgang til svinget sætter tonen for hele omgangen — for meget wedge her giver løs bagende ved indgang.",
        },
    },
    "Bristol": {
        "map": "",
        "notes": {
            "Generelt": "Kort, stejlt banket high-banked oval — meget følsom for trackbar-højde og wedge, små ændringer flytter balancen markant.",
        },
    },
    "Martinsville": {
        "map": "",
        "notes": {
            "T1/T3 (flade hjørner)": "Fladt, langsomt hjørne — bremsning og mekanisk traktion betyder alt, ingen banking at læne sig op ad.",
        },
    },
    "Richmond": {
        "map": "",
        "notes": {
            "Generelt": "D-formet kort-oval med moderat banking — balance mellem traktion i de flade svingender og fart i den bankede del.",
        },
    },
    "Homestead-Miami": {
        "map": "",
        "notes": {
            "Generelt": "Variabel banking gennem svingene — linjevalg (høj vs. lav) ændrer sig med dæk-slid, tilpas løbende.",
        },
    },
    "Phoenix": {
        "map": "",
        "notes": {
            "Turn 1": "Skarpt, fladt hjørne med dogleg — unik geometri på rosteret, kræver egen linje frem for standard oval-teknik.",
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
