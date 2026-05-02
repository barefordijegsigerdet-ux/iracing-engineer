import pandas as pd

def load_and_process_data(u_file, r_file):
    u_df = pd.read_csv(u_file)
    r_df = pd.read_csv(r_file)

    # Udvidet mapping for at dække både visning og fysik-beregninger
    column_mapping = {
        'GearNum': 'gear', 'Gear': 'gear',
        'Speed': 'speed', 'VelocityX': 'speed',
        'Distance': 'distance',
        'Throttle': 'throttle', 'Brake': 'brake',
        'Delta': 'delta',
        'LatAccel': 'lataccel', 'LongAccel': 'longaccel',
        'Lat': 'lat', 'Lon': 'lon',
        'SteeringWheelAngle': 'steer'
    }

    u_df.rename(columns=column_mapping, inplace=True)
    r_df.rename(columns=column_mapping, inplace=True)

    # --- FIX FOR TOMME/KLEMTE GRAFER ---
    for df in [u_df, r_df]:
        # Sørg for at numeriske kolonner rent faktisk behandles som tal
        for col in ['distance', 'speed', 'gear', 'lataccel', 'longaccel']:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
        
        # Sikkerhedsnet: Hvis kritiske kolonner mangler, fyld med 0
        critical_cols = ['gear', 'speed', 'distance', 'throttle', 'brake', 'delta', 'lataccel', 'longaccel']
        for col in critical_cols:
            if col not in df.columns:
                df[col] = 0

    # Sorter efter distance for at sikre en lineær x-akse på grafen
    u_df = u_df.sort_values('distance').reset_index(drop=True)
    r_df = r_df.sort_values('distance').reset_index(drop=True)

    return u_df, r_df
