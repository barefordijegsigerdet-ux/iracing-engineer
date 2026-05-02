import pandas as pd

def load_and_process_data(u_file, r_file):
    u_df = pd.read_csv(u_file)
    r_df = pd.read_csv(r_file)

    # Udvidet mapping for at dække fysik-beregninger
    column_mapping = {
        'GearNum': 'gear',
        'Gear': 'gear',
        'Speed': 'speed',
        'Distance': 'distance',
        'Throttle': 'throttle',
        'Brake': 'brake',
        'Delta': 'delta',
        'Lat': 'lat',
        'Lon': 'lon',
        'LatAccel': 'lataccel', # Tilføjet
        'LongAccel': 'longaccel', # Tilføjet
        'VertAccel': 'vertaccel',
        'SteeringWheelAngle': 'steer'
    }

    u_df.rename(columns=column_mapping, inplace=True)
    r_df.rename(columns=column_mapping, inplace=True)

    # Sikkerhedsnet: Hvis kolonnerne mangler, fyld med 0 så appen ikke crasher
    critical_cols = ['gear', 'speed', 'distance', 'throttle', 'brake', 'delta', 'lataccel', 'longaccel']
    for df in [u_df, r_df]:
        for col in critical_cols:
            if col not in df.columns:
                df[col] = 0

    return u_df, r_df
