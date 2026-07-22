"""
Bil- og klasse-database til Setup Rådgiveren.

VIGTIGT om tallene herunder:
Dette er INGEN nøjagtig kopi af iRacing's slider-min/max (dem kan kun ses
inde i garagen for den enkelte bil, og de ændrer sig ved BOP/patches).
Det er ingeniørmæssigt fornuftige REFERENCE-intervaller pr. bilklasse,
brugt til at sanity-checke AI'ens forslag ("foreslår den noget urimeligt?")
— ikke som facit. Værdier bør altid krydstjekkes i garagen i spillet.

Struktur: CAR_DB[klasse][bilnavn] = {
    "drivetrain": kort beskrivelse af layout/hjælpemidler,
    "params": {parameter: {"range": (min, max), "unit": "...", "note": "..."}},
    "notes": generel karakteristik/tuning-filosofi for bilen,
}

For at tilføje en bil: kopiér en eksisterende post i samme klasse og
justér tallene. Kør scripts/print_missing_cars.py (se bunden af filen)
for at se hvilke biler i CLASS_ROSTER der stadig mangler en post.
"""

# Fuld bil-liste pr. klasse i iRacing (til at vise "mangler stadig" — ikke
# alle har en detaljeret CAR_DB-post endnu, se DÆKNING nederst i filen).
CLASS_ROSTER = {
    "GT3": [
        "Porsche 911 GT3 R (992)", "McLaren 720S GT3 EVO", "Ferrari 296 GT3",
        "Audi R8 LMS EVO II GT3", "BMW M4 GT3", "Mercedes-AMG GT3 EVO",
        "Chevrolet Corvette Z06 GT3.R", "Ford Mustang GT3", "Aston Martin Vantage GT3 EVO",
        "Lamborghini Huracán GT3 EVO2",
    ],
    "GT4": [
        "Porsche 718 Cayman GT4 Clubsport MR", "BMW M4 GT4",
        "Chevrolet Camaro GT4.R", "Ford Mustang GT4", "McLaren 570S GT4",
        "Aston Martin Vantage GT4",
    ],
    "GTP/Hypercar": [
        "Porsche 963 GTP", "Cadillac V-Series.R GTP", "BMW M Hybrid V8",
        "Acura ARX-06 GTP",
    ],
    "LMP2": ["Oreca 07 LMP2"],
    "LMP3": ["Ligier JS P320"],
    "Formula": [
        "iRacing Formula 4", "Formula Vee", "Dallara F3", "Super Formula SF23",
        "iRacing Indycar (Dallara IR18)", "iRacing Formula B",
    ],
    "TCR": ["Audi RS3 LMS TCR", "Honda Civic Type R TCR", "Hyundai Elantra N TCR"],
    "Porsche Cup": ["Porsche 911 Cup (992.2)"],
    "Oval": [
        "NASCAR Cup Next Gen", "NASCAR Xfinity Next Gen", "NASCAR Truck",
        "Late Model Stock", "Legends Ford '34 Coupe", "Super Late Model",
    ],
}

CAR_DB = {
    "Porsche Cup": {
        "Porsche 911 Cup (992.2)": {
            "drivetrain": "RWD, bagmotor, INGEN ABS/TC — trail-braking teknik er kritisk",
            "params": {
                "spring_f":       {"range": (110, 190), "unit": "lb/in", "note": "Front fjeder"},
                "spring_r":       {"range": (140, 240), "unit": "lb/in", "note": "Bag fjeder — typisk stivere end front pga. bagmotor"},
                "arb_f":          {"range": (1, 24), "unit": "trin (blødt→hårdt)"},
                "arb_r":          {"range": (1, 24), "unit": "trin (blødt→hårdt)"},
                "camber_f":       {"range": (-4.8, -2.5), "unit": "°"},
                "camber_r":       {"range": (-3.2, -1.5), "unit": "°", "note": "Ofte mindre negativ end front"},
                "toe_f":          {"range": (-0.15, 0.15), "unit": "° pr. hjul"},
                "toe_r":          {"range": (-0.10, 0.30), "unit": "° pr. hjul", "note": "Let toe-in bagpå for stabilitet"},
                "ride_height_f":  {"range": (55, 80), "unit": "mm"},
                "ride_height_r":  {"range": (60, 85), "unit": "mm"},
                "brake_bias":     {"range": (54, 63), "unit": "% front"},
                "tire_pressure":  {"range": (25, 32), "unit": "psi (kold)"},
            },
            "notes": "Ingen elektroniske hjælpemidler. Front stivere end bag giver mere turn-in men mindre traktion ud af sving.",
        },
    },
    "GT3": {
        "Porsche 911 GT3 R (992)": {
            "drivetrain": "RWD, bagmotor, ABS + TC justerbar",
            "params": {
                "spring_f":       {"range": (130, 220), "unit": "N/mm"},
                "spring_r":       {"range": (110, 200), "unit": "N/mm", "note": "Ofte blødere end front for at holde bagenden bevægelig"},
                "arb_f":          {"range": (1, 10), "unit": "trin"},
                "arb_r":          {"range": (1, 10), "unit": "trin"},
                "camber_f":       {"range": (-4.5, -2.8), "unit": "°"},
                "camber_r":       {"range": (-3.5, -1.8), "unit": "°"},
                "toe_f":          {"range": (-0.10, 0.10), "unit": "° pr. hjul"},
                "toe_r":          {"range": (-0.05, 0.20), "unit": "° pr. hjul"},
                "ride_height_f":  {"range": (55, 75), "unit": "mm"},
                "ride_height_r":  {"range": (60, 80), "unit": "mm"},
                "brake_bias":     {"range": (52, 60), "unit": "% front"},
                "wing_r":         {"range": (1, 10), "unit": "trin"},
                "tire_pressure":  {"range": (25, 31), "unit": "psi (kold)"},
            },
            "notes": "Iboende understeer pga. bagmotor-layout, især i mellemhurtige sving. Blødere front-ARB eller mere front-spring hjælper turn-in.",
        },
        "McLaren 720S GT3 EVO": {
            "drivetrain": "RWD, midtmotor, ABS + TC justerbar",
            "params": {
                "spring_f":       {"range": (140, 230), "unit": "N/mm"},
                "spring_r":       {"range": (140, 230), "unit": "N/mm"},
                "arb_f":          {"range": (1, 10), "unit": "trin"},
                "arb_r":          {"range": (1, 10), "unit": "trin"},
                "camber_f":       {"range": (-4.2, -2.5), "unit": "°"},
                "camber_r":       {"range": (-3.0, -1.5), "unit": "°"},
                "toe_f":          {"range": (-0.10, 0.10), "unit": "° pr. hjul"},
                "toe_r":          {"range": (-0.05, 0.20), "unit": "° pr. hjul"},
                "ride_height_f":  {"range": (50, 70), "unit": "mm"},
                "ride_height_r":  {"range": (55, 75), "unit": "mm"},
                "brake_bias":     {"range": (53, 61), "unit": "% front"},
                "wing_r":         {"range": (1, 10), "unit": "trin"},
                "tire_pressure":  {"range": (25, 31), "unit": "psi (kold)"},
            },
            "notes": "Midtmotor giver mere neutral balance end Porsche GT3 R — nemmere at trimme, men mindre tolerance for forkert brake bias.",
        },
    },
    "GT4": {
        "Porsche 718 Cayman GT4 Clubsport MR": {
            "drivetrain": "RWD, midtmotor, ABS (ofte fast), ingen TC",
            "params": {
                "spring_f":       {"range": (100, 180), "unit": "N/mm"},
                "spring_r":       {"range": (100, 180), "unit": "N/mm"},
                "arb_f":          {"range": (1, 6), "unit": "trin"},
                "arb_r":          {"range": (1, 6), "unit": "trin"},
                "camber_f":       {"range": (-4.0, -2.0), "unit": "°"},
                "camber_r":       {"range": (-2.8, -1.2), "unit": "°"},
                "ride_height_f":  {"range": (60, 85), "unit": "mm"},
                "ride_height_r":  {"range": (65, 90), "unit": "mm"},
                "brake_bias":     {"range": (54, 62), "unit": "% front"},
                "tire_pressure":  {"range": (26, 32), "unit": "psi (kold)"},
            },
            "notes": "Lavere downforce end GT3 — mekanisk grip og køretøjsplacering betyder mere end aero-trim.",
        },
    },
    "GTP/Hypercar": {
        "Porsche 963 GTP": {
            "drivetrain": "Hybrid AWD (elmotor front under acceleration), ABS + TC",
            "params": {
                "spring_f":       {"range": (150, 260), "unit": "N/mm"},
                "spring_r":       {"range": (150, 260), "unit": "N/mm"},
                "ride_height_f":  {"range": (35, 55), "unit": "mm", "note": "Meget lav pga. ground-effect aero"},
                "ride_height_r":  {"range": (45, 70), "unit": "mm"},
                "brake_bias":     {"range": (52, 62), "unit": "% front"},
                "tire_pressure":  {"range": (24, 30), "unit": "psi (kold)"},
            },
            "notes": "Ground-effect underbund gør ride height ekstremt følsom — små ændringer flytter aero-balance markant.",
        },
    },
    "LMP2": {
        "Oreca 07 LMP2": {
            "drivetrain": "RWD, ground-effect aero, ABS + TC (spec-reglementeret)",
            "params": {
                "spring_f":       {"range": (140, 240), "unit": "N/mm"},
                "spring_r":       {"range": (140, 240), "unit": "N/mm"},
                "ride_height_f":  {"range": (30, 50), "unit": "mm"},
                "ride_height_r":  {"range": (45, 70), "unit": "mm"},
                "brake_bias":     {"range": (52, 62), "unit": "% front"},
                "tire_pressure":  {"range": (24, 30), "unit": "psi (kold)"},
            },
            "notes": "Spec-bil — setup-frihed er begrænset af reglementet, meget handler om ride height og aero-balance.",
        },
    },
    "LMP3": {
        "Ligier JS P320": {
            "drivetrain": "RWD, prototype-aero, ingen TC",
            "params": {
                "spring_f":       {"range": (120, 200), "unit": "N/mm"},
                "spring_r":       {"range": (120, 200), "unit": "N/mm"},
                "ride_height_f":  {"range": (35, 60), "unit": "mm"},
                "ride_height_r":  {"range": (50, 75), "unit": "mm"},
                "brake_bias":     {"range": (54, 64), "unit": "% front"},
                "tire_pressure":  {"range": (24, 30), "unit": "psi (kold)"},
            },
            "notes": "Let bil med prototype-aero — respekterer bumps dårligt hvis for stiv, mister aero-effekt hvis for blød.",
        },
    },
    "Formula": {
        "iRacing Formula 4": {
            "drivetrain": "RWD, open-wheel, ingen ABS/TC",
            "params": {
                "spring_f":       {"range": (90, 160), "unit": "N/mm"},
                "spring_r":       {"range": (90, 160), "unit": "N/mm"},
                "arb_f":          {"range": (1, 8), "unit": "trin"},
                "arb_r":          {"range": (1, 8), "unit": "trin"},
                "camber_f":       {"range": (-4.0, -2.0), "unit": "°"},
                "camber_r":       {"range": (-3.0, -1.0), "unit": "°"},
                "toe_f":          {"range": (-0.10, 0.10), "unit": "° pr. hjul"},
                "ride_height_f":  {"range": (20, 40), "unit": "mm"},
                "ride_height_r":  {"range": (30, 55), "unit": "mm"},
                "brake_bias":     {"range": (52, 62), "unit": "% front"},
                "tire_pressure":  {"range": (20, 26), "unit": "psi (kold)"},
            },
            "notes": "Ingen driver aids — vægtoverførsel via setup (ARB/spring balance) er alt. Lav ride height, aero er stadig moderat.",
        },
    },
    "TCR": {
        "Audi RS3 LMS TCR": {
            "drivetrain": "FWD, mekanisk diff (LSD), ABS",
            "params": {
                "spring_f":       {"range": (90, 160), "unit": "N/mm"},
                "spring_r":       {"range": (80, 150), "unit": "N/mm"},
                "arb_f":          {"range": (1, 6), "unit": "trin"},
                "arb_r":          {"range": (1, 6), "unit": "trin"},
                "camber_f":       {"range": (-3.5, -1.5), "unit": "°"},
                "camber_r":       {"range": (-2.5, -0.8), "unit": "°"},
                "ride_height_f":  {"range": (65, 95), "unit": "mm"},
                "ride_height_r":  {"range": (70, 100), "unit": "mm"},
                "brake_bias":     {"range": (58, 68), "unit": "% front", "note": "FWD trækker bias markant fremad ift. RWD-biler"},
                "tire_pressure":  {"range": (26, 32), "unit": "psi (kold)"},
            },
            "notes": "FWD med LSD — power-understeer ud af langsomme sving er hovedudfordringen, diff-lock-indstilling er nøgleparameteren.",
        },
    },
    "Oval": {
        "NASCAR Cup Next Gen": {
            "drivetrain": "RWD, symmetrisk chassis, ingen ABS/TC",
            "params": {
                "spring_f":       {"range": (700, 1400), "unit": "lb/in", "note": "Markant stivere end road course-biler"},
                "spring_r":       {"range": (150, 350), "unit": "lb/in"},
                "camber_lf":      {"range": (-4.0, 0.0), "unit": "°", "note": "Asymmetrisk — venstre/højre sat forskelligt pga. konstant venstresving"},
                "camber_rf":      {"range": (-1.0, 3.0), "unit": "°"},
                "wedge_crossweight": {"range": (48, 54), "unit": "% cross"},
                "trackbar_height":{"range": (5, 15), "unit": "tommer"},
                "tire_pressure":  {"range": (18, 30), "unit": "psi (kold, LF ofte lavest)"},
            },
            "notes": "Ovalt setup er asymmetrisk (venstre ≠ højre) modsat road course. Wedge/cross-weight er den primære balance-parameter, ikke ARB.",
        },
    },
}


def list_classes() -> list[str]:
    return list(CAR_DB.keys())


def list_cars(car_class: str) -> list[str]:
    return list(CAR_DB.get(car_class, {}).keys())


def get_car_params(car_class: str, car_name: str) -> dict | None:
    return CAR_DB.get(car_class, {}).get(car_name)


def params_as_text(car_class: str, car_name: str) -> str:
    """Formaterer parameter-intervallerne som tekst til AI-prompten, så
    forslag kan sanity-checkes mod fornuftige grænser for netop denne bil."""
    car = get_car_params(car_class, car_name)
    if not car:
        return ""
    lines = [f"=== Reference-intervaller for {car_name} ({car_class}) ===",
             f"Drivetrain: {car['drivetrain']}"]
    for key, p in car["params"].items():
        lo, hi = p["range"]
        note = f" — {p['note']}" if p.get("note") else ""
        lines.append(f"{key}: {lo}–{hi} {p['unit']}{note}")
    lines.append(f"Karakteristik: {car['notes']}")
    lines.append("(Reference-intervaller til sanity-check, ikke eksakte spilgrænser — bekræft i garagen.)")
    return "\n".join(lines)


def coverage_report() -> dict[str, list[str]]:
    """Viser hvilke biler i CLASS_ROSTER der endnu ikke har en CAR_DB-post —
    brug denne til at prioritere hvilke biler der skal tilføjes næste gang."""
    missing = {}
    for cls, cars in CLASS_ROSTER.items():
        have = set(CAR_DB.get(cls, {}).keys())
        gap = [c for c in cars if c not in have]
        if gap:
            missing[cls] = gap
    return missing
