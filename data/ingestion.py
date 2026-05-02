import pandas as pd

def load_and_process_data(u_file, r_file):
    u_df = pd.read_csv(u_file)
    r_df = pd.read_csv(r_file)

    # Mapping til at ensrette kolonnenavne fra din Porsche-fil
    column_mapping = {
        'LapDistPct': 'distance', 
        'Gear': 'gear',           
        'Speed': 'speed',
        'Throttle': 'throttle',
        'Brake': 'brake',
        'LatAccel': 'lataccel',   
        'LongAccel': 'longaccel',
        'Delta': 'delta' # Prøv at finde delta hvis den findes
    }

    u_df.rename(columns=column_mapping, inplace=True)
    r_df.rename(columns=column_mapping, inplace=True)

    # --- FIX FOR DELTA KEYERROR ---
    # Hvis 'delta' ikke findes i filen, opretter vi den med 0-værdier
    # så create_main_telemetry ikke fejler
    for df in [u_df, r_df]:
        if 'delta' not in df.columns:
            df['delta'] = 0.0  # Gør grafen flad i stedet for at crashe
            
        # Sikre numeriske data for alle kritiske kolonner
        cols = ['distance', 'speed', 'gear', 'throttle', 'brake', 'delta']
        for col in cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)

    # Sorter efter distance
    u_df = u_df.sort_values('distance').reset_index(drop=True)
    r_df = r_df.sort_values('distance').reset_index(drop=True)

    return u_df, r_df
