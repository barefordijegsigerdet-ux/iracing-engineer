def get_track_notes(track):
    tracks = {
        "Zandvoort": {
            "Sving 1 (Tarzan)": "Brems sent og trail-brake dybt ind i svinget. Fokusér på en sen apex for at få fart med ned mod Sving 2.",
            "Sving 3 (Hugenholtz)": "Dette er et banked sving. Kør højt i indgangen og 'dyk' ned for at bruge bankingen til at rotere bilen.",
            "Sektor 1 Generelt": "Her tabes mest tid (jf. Jonas vs Leeroy). Fokusér på at minimere rat-korrektioner midt i svinget.",
            "Sving 7 (Scheivlak)": "Højfartssving. Kræver tillid til bilens downforce. Hold en stabil gasfod gennem hele svinget."
        }
    }
    return tracks.get(track, {"Generelt": "Hold bilen på asfalten og kig fremad!"})
