def get_track_data(track):
    track_db = {
        "Zandvoort": {
            "map": "https://www.iracing.com/wp-content/uploads/2020/06/zandvoort-map.png",
            "notes": {
                "T1 (Tarzan)": "Brems sent, fokuser på trail-braking for at rotere bilen til en sen apex.",
                "T3 (Hugenholtz)": "Hold den høje linje i bankingen for at få maksimal fart ud på langsiden."
            }
        },
        "Spa": {
            "map": "https://www.iracing.com/wp-content/uploads/2020/06/spa-map.png",
            "notes": {
                "Eau Rouge": "Hold den fladt, men vær præcis med din 'turn-in'.",
                "Pouhon": "Vigtigt med høj minimumshastighed. Slip gassen let, men brems minimalt."
            }
        }
    }
    return track_db.get(track, {"map": "", "notes": {"Info": "Vælg en bane for at se noter."}})
