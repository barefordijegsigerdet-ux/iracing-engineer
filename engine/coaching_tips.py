def get_track_data(track):
    track_db = {
        "Zandvoort": {
            "map": "https://www.iracing.com/wp-content/uploads/2020/06/zandvoort-map.png",
            "notes": {
                "T1 (Tarzan)": "Brems sent, slip bremsen gradvist for at få næsen ind.",
                "T3 (Hugenholtz)": "Hold dig højt i bankingen for at få et bedre 'launch' ud."
            }
        },
        "Spa-Francorchamps": {
            "map": "https://www.iracing.com/wp-content/uploads/2020/06/spa-map.png",
            "notes": {
                "Eau Rouge": "Hold den fladt, men vær forsigtig med din 'entry' vinkel.",
                "Bruxelles": "Langt sving, fokusér på tålmodighed på gassen."
            }
        },
        "Monza": {
            "map": "https://www.iracing.com/wp-content/uploads/2020/06/monza-map.png",
            "notes": {
                "Variante del Rettifilo": "Skær curberne aggressivt, men pas på balancen.",
                "Parabolica": "Åbn svinget tidligt for at maksimere topfart på langsiden."
            }
        }
    }
    return track_db.get(track, {"map": "", "notes": {"Info": "Bane-data kommer snart."}})
