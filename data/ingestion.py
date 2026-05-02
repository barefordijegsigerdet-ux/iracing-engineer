import pandas as pd

def load_and_process_data(u_file, r_file):
    u_df = pd.read_csv(u_file)
    r_df = pd.read_csv(r_file)

    # Mapping til at ensrette kolonnenavne (Fixer KeyError 'gear')
    column_mapping = {
        'GearNum': 'gear',
        'Gear': 'gear',
        'Speed': 'speed',
        'Distance': 'distance',
        'Throttle': 'throttle',
        'Brake': 'brake',
        'Delta': 'delta',
        'Lat': 'lat',
        'Lon': 'lon'
    }

    # Omdøb i begge DataFrames
    u_df.rename(columns=column_mapping, inplace=True)
    r_df.rename(columns=column_mapping, inplace=True)

    # Sikkerhedsnet: Hvis en kolonne mangler helt
    expected_cols = ['gear', 'speed', 'distance', 'throttle', 'brake', 'delta']
    for col in expected_cols:
        if col not in u_df.columns: u_df[col] = 0
        if col not in r_df.columns: r_df[col] = 0

    return u_df, r_df
