def get_vehicle_advice(vehicle, problem):
    setup_db = {
        "Porsche 911 Cup (992)": {
            "Understyring (Indgang)": "Flyt Brake Bias bagud. Porsche Cup har ingen ABS, så trail-braking er kritisk for rotation.",
            "Overstyring (Exit)": "Blødgør Rear ARB eller vær mere progressiv med gassen pga. hækmotoren.",
            "Nervøs på curbs": "Blødgør fjedre og tjek om din ride height er for lav."
        },
        "GT3 Class": {
            "Understyring (Indgang)": "Øg Brake Bias fremad hvis bagenden er ustabil, ellers blødgør forfjedre.",
            "Overstyring (Exit)": "Øg TC (Traction Control) eller øg din vinge-vinkel.",
            "Bundskrab (Bottoming)": "Øg Ride Height eller gør fjedrene stivere."
        }
    }
    car_data = setup_db.get(vehicle, setup_db["GT3 Class"])
    return car_data.get(problem, "Ingen specifik løsning fundet. Prøv AI-analysen for detaljer.")
