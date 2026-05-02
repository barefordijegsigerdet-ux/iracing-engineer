import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as objects
from plotly.subplots import make_subplots
import difflib

# ==========================================
# MODULE: DATA INGESTION & NORMALIZATION
# ==========================================

def normalize_telemetry(df: pd.DataFrame) -> pd.DataFrame:
    """
    Standardizes varying telemetry headers from iRacing, G61, and VRS into a single schema.
    Uses dictionary aliases first, then falls back to fuzzy matching.
    """
    # 1. Clean current columns
    df.columns =[str(c).lower().strip() for c in df.columns]

    # 2. Define target schema and known aliases
    SCHEMA = {
        'distance': ['distance', 'distance (m)', 'lapdist', 'lap_distance', 'dist', 'lapdistpct'],
        'speed': ['speed', 'speed (km/h)', 'speed (mph)', 'velocity', 'v'],
        'throttle': ['throttle', 'throttle %', 'throttle_raw', 'gas', 'accel'],
        'brake': ['brake', 'brake %', 'brake_raw', 'dec', 'brake_pedal'],
        'time':['time', 'sessiontime', 'laptime', 'current_time']
    }

    normalized_columns = {}
    for target, aliases in SCHEMA.items():
        found = False
        # Phase A: Exact Alias Match
        for col in df.columns:
            if col in aliases:
                normalized_columns[col] = target
                found = True
                break
        
        # Phase B: Fuzzy Match Fallback
        if not found:
            matches = difflib.get_close_matches(target, df.columns, n=1, cutoff=0.65)
            if matches:
                normalized_columns[matches[0]] = target

    # Rename columns to our standard schema
    df = df.rename(columns=normalized_columns)
    
    # Validation: Ensure critical physics pillars exist
    essential = ['distance', 'speed', 'throttle', 'brake']
    missing =[col for col in essential if col not in df.columns]
    
    if missing:
        raise KeyError(f"Telemetry missing critical headers after normalization: {missing}. Found: {list(df.columns)}")
        
    return df

@st.cache_data(show_spinner=False)
def load_and_process_data(file_bytes) -> pd.DataFrame:
    """Cached function to parse and normalize the uploaded CSV."""
    df = pd.read_csv(file_bytes)
    return normalize_telemetry(df)


# ==========================================
# MODULE: PHYSICS & METRICS
# ==========================================

def calculate_physics_delta(user_df: pd.DataFrame, ref_df: pd.DataFrame) -> pd.DataFrame:
    """
    Physics-First calculation. If delta is missing, calculates it by integrating time 
    from speed over distance (dt = dx / v). Interpolates to a common spatial grid.
    """
    try:
        # Create a common spatial vector (distance)
        max_dist = min(user_df['distance'].max(), ref_df['distance'].max())
        common_dist = np.linspace(0, max_dist, 1000)

        # Interpolate speeds onto the common spatial grid (convert to m/s if needed, assuming km/h here)
        # We enforce a minimum speed of 1 km/h to prevent division by zero in tight hairpins/spins.
        v_user = np.maximum(np.interp(common_dist, user_df['distance'], user_df['speed']), 1.0) / 3.6
        v_ref = np.maximum(np.interp(common_dist, ref_df['distance'], ref_df['speed']), 1.0) / 3.6

        # Calculate time steps (dt = dx / v)
        dx = np.diff(common_dist, prepend=0)
        t_user = np.cumsum(dx / v_user)
        t_ref = np.cumsum(dx / v_ref)

        # Delta = User Time - Ref Time (Positive means user is slower/losing time)
        delta_time = t_user - t_ref
        
        return pd.DataFrame({'distance': common_dist, 'delta': delta_time})
    except Exception as e:
        raise ValueError(f"Physics integration failed. Check telemetry spatial data. Err: {e}")


# ==========================================
# MODULE: STREAMLIT UI (app.py)
# ==========================================

def main():
    st.set_page_config(page_title="iRacing Race Engineer Pro", layout="wide")
    st.title("🏎️ Race Engineer Telemetry Analysis")
    
    st.sidebar.header("Upload Lap Data")
    st.sidebar.info("Upload CSV exports from Garage 61, VRS, or iRacing. The pipeline will auto-normalize headers.")

    user_file = st.sidebar.file_uploader("Upload YOUR Lap (CSV)", type=['csv'])
    ref_file = st.sidebar.file_uploader("Upload REFERENCE Lap (CSV)", type=['csv'])

    if user_file and ref_file:
        try:
            # 1. Safely Load and Normalize
            with st.spinner("Normalizing telemetry schemas..."):
                user_df = load_and_process_data(user_file)
                ref_df = load_and_process_data(ref_file)
                
            # 2. Physics / Math Processing
            with st.spinner("Calculating spatial deltas..."):
                if 'delta' not in user_df.columns:
                    delta_df = calculate_physics_delta(user_df, ref_df)
                else:
                    delta_df = user_df[['distance', 'delta']]

            # 3. Visualization
            st.subheader("Pillar Analysis: Data-Driven Performance")
            
            fig = make_subplots(
                rows=4, cols=1, 
                shared_xaxes=True, 
                vertical_spacing=0.04,
                subplot_titles=("Speed (vMin Analysis)", "Time Delta", "Throttle %", "Brake %"),
                row_heights=[0.35, 0.25, 0.2, 0.2]
            )

            # Spatial Vectors
            dist_u, dist_r = user_df['distance'], ref_df['distance']

            # ROW 1: SPEED
            fig.add_trace(objects.Scatter(x=dist_r, y=ref_df['speed'], name="Ref Speed", line=dict(color='white', dash='dash')), row=1, col=1)
            fig.add_trace(objects.Scatter(x=dist_u, y=user_df['speed'], name="User Speed", line=dict(color='#00FF00')), row=1, col=1)

            # ROW 2: DELTA
            fig.add_trace(objects.Scatter(x=delta_df['distance'], y=delta_df['delta'], name="Time Delta", fill='tozeroy', line=dict(color='#ff3333')), row=2, col=1)
            
            # ROW 3: THROTTLE
            fig.add_trace(objects.Scatter(x=dist_r, y=ref_df['throttle'], name="Ref Throttle", line=dict(color='white', width=1, dash='dash')), row=3, col=1)
            fig.add_trace(objects.Scatter(x=dist_u, y=user_df['throttle'], name="User Throttle", line=dict(color='#00FF00', width=2)), row=3, col=1)

            # ROW 4: BRAKE
            fig.add_trace(objects.Scatter(x=dist_r, y=ref_df['brake'], name="Ref Brake", line=dict(color='white', width=1, dash='dash')), row=4, col=1)
            fig.add_trace(objects.Scatter(x=dist_u, y=user_df['brake'], name="User Brake", line=dict(color='red', width=2)), row=4, col=1)

            fig.update_layout(height=850, template="plotly_dark", showlegend=True, hovermode="x unified", margin=dict(t=40, b=40))
            fig.update_xaxes(title_text="Track Distance (m)", row=4, col=1)
            
            st.plotly_chart(fig, use_container_width=True)

            # 4. Engineer Insights
            st.divider()
            col1, col2 = st.columns(2)
            
            with col1:
                st.header("Technical Observations")
                user_vmin, ref_vmin = user_df['speed'].min(), ref_df['speed'].min()
                
                if user_vmin < ref_vmin - 2.0: # Add 2km/h tolerance
                    st.error(f"⚠️ Over-slowed: Your vMin is {round(ref_vmin - user_vmin, 1)} km/h lower than the reference.")
                else:
                    st.success("✅ Minimum speed is competitive.")

            with col2:
                st.header("Actionable To-Do's")
                st.write("- **Check Braking Phase:** Look for where the red line (User) starts before the white dashed line.")
                st.write("- **Throttle Timing:** Identify if the green throttle line is rising later than the reference.")

        except KeyError as ke:
            st.error(f"❌ Schema Error: Missing vital telemetry column. {ke}")
        except ValueError as ve:
            st.error(f"❌ Processing Error: Unprocessable values in telemetry. {ve}")
        except Exception as e:
            st.error(f"❌ An unexpected application error occurred: {e}")
            
    else:
        # Safe Degradation State
        st.warning("Please upload both a User lap and a Reference lap to begin analysis.")
        st.info("The application expects a CSV containing at least: Distance, Speed, Throttle, and Brake.")

if __name__ == "__main__":
    main()
