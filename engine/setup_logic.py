def get_vehicle_advice(vehicle, problem):
    # Setup-database for forskellige biltyper
    setup_db = {
        "Porsche 911 Cup (992)": {
            "Understyring (Indgang)": "Flyt Brake Bias bagud. Porsche Cup har ingen ABS, så trail-braking er kritisk for rotation.",
            "Overstyring (Exit)": "Blødgør Rear ARB. Pas på med at 'tromle' gassen for hurtigt pga. motoren bagtil.",
            "Nervøs på curbs": "Blødgør fjedre og øg dæktrykket en smule."
        },
        "GT3 Class (General)": {
            "Understyring (Indgang)": "Øg din Brake Bias (fremad) hvis du låser baghjulene, eller øg vingen.",
            "Overstyring (Exit)": "Sænk din Traction Control (TC) indstilling eller øg vinge-vinklen.",
            "Bundskrab (Bottoming)": "Øg din Ride Height eller gør fjedrene stivere."
        },
        "Formula 4 / Super Formula": {
            "Understyring (Høj fart)": "Øg Front Wing eller sænk Rear Wing for bedre aero-balance.",
            "Overstyring (Høj fart)": "Øg Rear Wing vinklen med 1-2 grader.",
            "Hjulspin": "Gør din differentiale-indstilling mere 'locked'."
        }
    }
    
    car_data = setup_db.get(vehicle, setup_db["GT3 Class (General)"])
    return car_data.get(problem, "Ingen specifik løsning fundet for dette problem.")
