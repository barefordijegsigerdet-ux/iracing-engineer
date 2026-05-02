import streamlit as st
import pandas as pd
import plotly.graph_objects as objects
from plotly.subplots import make_subplots

# Set Page Config
st.set_page_config(page_title="iRacing Race Engineer Pro", layout="wide")

st.title("🏎️ Race Engineer Telemetry Analysis")
st.sidebar.header("Upload Lap Data")

# Help Text for User
st.sidebar.info("Upload CSV exports from Garage 61 or iRacing. Ensure both laps are from the same Car/Track combo.")

# 1. File Uploaders
user_file = st.sidebar.file_uploader("Upload YOUR Lap (CSV)", type=['csv'])
ref_file = st.sidebar.file_uploader("Upload REFERENCE Lap (CSV)", type=['csv'])

def load_data(file):
    if file is not None:
        df = pd.read_csv(file)
        # Standardizing column names (G61/iRacing common headers)
        df.columns = [c.lower().strip() for c in df.columns]
        return df
    return None

user_df = load_data(user_file)
ref_df = load_data(ref_file)

if user_df is not None and ref_df is not None:
    # 2. Key Metric Calculation
    st.subheader("Pillar Analysis: Data-Driven Performance")
    
    # Create the Telemetry Charts
    fig = make_subplots(rows=4, cols=1, 
                        shared_xaxes=True, 
                        vertical_spacing=0.02,
                        subplot_titles=("Speed (vMin Analysis)", "Delta (Time Loss)", "Throttle %", "Brake %"),
                        row_heights=[0.4, 0.2, 0.2, 0.2])

    # Distance is our X-axis
    dist_u = user_df['distance']
    dist_r = ref_df['distance']

    # --- ROW 1: SPEED ---
    fig.add_trace(objects.Scatter(x=dist_r, y=ref_df['speed'], name="Ref Speed", line=dict(color='white', dash='dash')), row=1, col=1)
    fig.add_trace(objects.Scatter(x=dist_u, y=user_df['speed'], name="User Speed", line=dict(color='#00FF00')), row=1, col=1)

    # --- ROW 2: DELTA (If available in CSV) ---
    if 'delta' in user_df.columns:
        fig.add_trace(objects.Scatter(x=dist_u, y=user_df['delta'], name="Delta", fill='tozeroy', line=dict(color='red')), row=2, col=1)
    
    # --- ROW 3: THROTTLE ---
    fig.add_trace(objects.Scatter(x=dist_r, y=ref_df['throttle'], name="Ref Throttle", line=dict(color='white', width=1, dash='dash')), row=3, col=1)
    fig.add_trace(objects.Scatter(x=dist_u, y=user_df['throttle'], name="User Throttle", line=dict(color='#00FF00', width=2)), row=3, col=1)

    # --- ROW 4: BRAKE ---
    fig.add_trace(objects.Scatter(x=dist_r, y=ref_df['brake'], name="Ref Brake", line=dict(color='white', width=1, dash='dash')), row=4, col=1)
    fig.add_trace(objects.Scatter(x=dist_u, y=user_df['brake'], name="User Brake", line=dict(color='red', width=2)), row=4, col=1)

    # Layout Updates
    fig.update_layout(height=800, template="plotly_dark", showlegend=True,
                      hovermode="x unified", title_text="Lap Telemetry Overlay")
    fig.update_xaxes(title_text="Distance (Meters)", row=4, col=1)

    st.plotly_chart(fig, use_container_width=True)

    # 3. Engineer's Automated Insight
    st.divider()
    col1, col2 = st.columns(2)
    
    with col1:
        st.header("Technical Observations")
        # Logic to find vMin
        user_vmin = user_df['speed'].min()
        ref_vmin = ref_df['speed'].min()
        
        if user_vmin < ref_vmin:
            st.error(f"⚠️ Over-slowed: Your vMin is {round(ref_vmin - user_vmin, 2)} km/h lower than the reference.")
        else:
            st.success("✅ Minimum speed is competitive.")

    with col2:
        st.header("Actionable To-Do's")
        st.write("- **Check Braking Phase:** Look for where the red line (User) starts before the white dashed line.")
        st.write("- **Throttle Timing:** Identify if the green throttle line is rising later than the reference.")

else:
    st.warning("Please upload both a User lap and a Reference lap to begin analysis.")
    st.image("https://images.unsplash.com/photo-1594736797933-d0501ba2fe65?auto=format&fit=crop&q=80&w=1000", caption="Awaiting Data...")
