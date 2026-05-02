def get_porsche_advice(problem):
    advice_map = {
        "Understyring (Indgang)": {
            "Løsning": "Flyt Brake Bias bagud (lavere %). Dette hjælper bilen med at rotere under opbremsning.",
            "Setup": "Sænk Brake Pressure eller blødgør forfjedre (Front Springs)."
        },
        "Understyring (Mid-corner)": {
            "Løsning": "Bilen mangler 'front grip'. Øg din vinge (Rear Wing) for stabilitet, men tjek om du kan sænke forhøjden.",
            "Setup": "Øg Front Anti-Roll Bar (ARB) blødhed eller øg Rear ARB stivhed."
        },
        "Overstyring (Exit)": {
            "Løsning": "Du mister bagenden, når du går på gassen. Vær mere progressiv med speederen.",
            "Setup": "Blødgør Rear Anti-Roll Bar (ARB) eller øg Rear Wing vinkel."
        },
        "Bilen er nervøs over curbs": {
            "Løsning": "Dine dæmpere er for stive til denne bane.",
            "Setup": "Sænk 'Bump Stiffness' på dine dæmpere eller øg dæktrykket en smule."
        },
        "Blokering af forhjul": {
            "Løsning": "Du bremser for hårdt eller har for meget vægt foran.",
            "Setup": "Flyt Brake Bias fremad (+) eller sænk det maksimale bremsetryk i indstillingerne."
        }
    }
    return advice_map.get(problem, {"Løsning": "Ingen specifik data fundet.", "Setup": "Kontakt din chief engineer."})
