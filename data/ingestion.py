import pandas as pd

def load_and_process_data(u_file, r_file):
    """
    Indlæser og ensretter telemetri-data fra bruger og reference.
    Håndterer forskellige kolonnenavne fra iRacing og Garage 61.
    """
    # Indlæs rå CSV data
    u_df = pd.read_csv(u_file)
    r_df = pd.read_csv(r_file)

    # Mapping-ordbog: 'Navn_i_Fil': 'Navn_i_App'
    # Dette sikrer at vi undgår KeyError, da iRacing ofte bruger forskellige navne
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
        'RPM': 'rpm',
        'SteeringWheelAngle': 'steer'
    }

    # Omdøb kolonnerne i begge DataFrames
    # Vi bruger errors='ignore', så den ikke fejler, hvis en kolonne ikke findes
    u_df.rename(columns=column_mapping, inplace=True)
    r_df.rename(columns=column_mapping, inplace=True)

    # --- SIKKERHEDS-CHECK ---
    # Vi tjekker om de kritiske kolonner findes. Hvis ikke, laver vi dem med 0-værdier
    # så charts.py ikke crasher når den prøver at tegne dem.
    required_columns = ['gear', 'speed', 'distance', 'throttle', 'brake', 'delta']
    
    for df in [u_df, r_df]:
        for col in required_columns:
            if col not in df.columns:
                df[col] = 0  # Opret kolonne med nuller hvis den mangler

    # Sørg for at distance er sorteret (vigtigt for graferne)
    u_df = u_df.sort_values('distance').reset_index(drop=True)
    r_df = r_df.sort_values('distance').reset_index(drop=True)

    return u_df, r_df
