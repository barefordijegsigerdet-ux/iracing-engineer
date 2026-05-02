import numpy as np

def calculate_physics_metrics(user_df, ref_df):
    """
    Beregner avancerede metrics som G-sum for at analysere dækkets udnyttelse.
    """
    for df in [user_df, ref_df]:
        # Beregn G-Sum (kombineret lateral og longitudinal kraft)
        # Vi sikrer os at værdierne eksisterer via ingestion.py
        df['g_sum'] = np.sqrt(df['lataccel']**2 + df['longaccel']**2)
        
        # Beregn dækslip-estimat (simpelt eksempel baseret på fart og rat)
        # Kan udvides hvis du har WheelSpeed data
        if 'steer' in df.columns:
            df['slip_est'] = (df['steer'].abs() * df['speed']) / 1000
        else:
            df['slip_est'] = 0

    return user_df, ref_df
