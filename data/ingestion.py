import pandas as pd

def load_and_process_data(u_file, r_file):
    u_df = pd.read_csv(u_file)
    r_df = pd.read_csv(r_file)

    # Mapping der matcher din Zandvoort-fil præcis
    column_mapping = {
        'LapDistPct': 'distance',  # Fixer image_7ab439.png x-akse
        'Gear': 'gear',            # Fixer KeyError: 'gear'
        'Speed': 'speed',
        'Throttle': 'throttle',
        'Brake': 'brake',
        'LatAccel': 'lataccel',    # Fixer KeyError i physics.py
        'LongAccel': 'longaccel',
        'SteeringWheelAngle': 'steer'
    }

    u_df.rename(columns=column_mapping, inplace=True)
    r_df.rename(columns=column_mapping, inplace=True)

    # Konverter til tal og håndter manglende værdier
    numeric_cols = ['distance', 'speed', 'gear', 'throttle', 'brake', 'lataccel', 'longaccel']
    for df in [u_df, r_df]:
        for col in numeric_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
            else:
                df[col] = 0

    # Sorter efter distance for at undgå zig-zag grafer
    u_df = u_df.sort_values('distance').reset_index(drop=True)
    r_df = r_df.sort_values('distance').reset_index(drop=True)

    return u_df, r_df
