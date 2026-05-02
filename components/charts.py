import plotly.graph_objects as go
from plotly.subplots import make_subplots

def create_main_telemetry(user_df, ref_df):
    fig = make_subplots(
        rows=5, cols=1, 
        shared_xaxes=True, 
        vertical_spacing=0.02,
        subplot_titles=("Speed (km/h)", "Delta (s)", "Throttle (%)", "Brake (%)", "G-Sum (G)")
    )
    
    # Distance is our X-axis
    u_dist = user_df["distance"]
    r_dist = ref_df["distance"]

    # Helper to add both traces to a row
    def add_dual_trace(user_data, ref_data, row_idx):
        # Add Reference (Red)
        fig.add_trace(go.Scatter(x=r_dist, y=ref_data, name="Reference", 
                                 line=dict(color="#FF4B4B", width=1.5), opacity=0.8), row=row_idx, col=1)
        # Add User (Blue)
        fig.add_trace(go.Scatter(x=u_dist, y=user_data, name="You", 
                                 line=dict(color="#1C83E1", width=1.5)), row=row_idx, col=1)

    # 1. Speed
    add_dual_trace(user_df["speed"], ref_df["speed"], 1)
    
    # 2. Delta (Only one line needed, usually user vs ref)
    fig.add_trace(go.Scatter(x=u_dist, y=user_df["delta"], fill='tozeroy', 
                             line=dict(color="white", width=1), name="Delta"), row=2, col=1)
    
    # 3. Throttle
    add_dual_trace(user_df["throttle"], ref_df["throttle"], 3)
    
    # 4. Brake
    add_dual_trace(user_df["brake"], ref_df["brake"], 4)
    
    # 5. G-Sum
    add_dual_trace(user_df["g_sum"], ref_df["g_sum"], 5)
    
    fig.update_layout(height=1200, template="plotly_dark", showlegend=False)
    # Remove redundant labels to keep it clean
    fig.update_xaxes(title_text="Distance (m)", row=5, col=1)
    
    return fig
def create_track_map(df):
    # Using Scattergl with markers to allow color arrays (Speed Heatmap)
    fig = go.Figure(go.Scattergl(
        x=df["lon"], 
        y=df["lat"], 
        mode='markers', # Changed from 'lines' to 'markers' to support color arrays
        marker=dict(
            color=df["speed"],
            colorscale='Turbo',
            size=4,
            showscale=True,
            colorbar=dict(title="Speed (km/h)")
        ),
        hovertemplate="Speed: %{marker.color:.1f} km/h<extra></extra>"
    ))
    
    fig.update_layout(
        title="GPS Track Map (Speed Heatmap)", 
        template="plotly_dark", 
        xaxis=dict(visible=False), 
        yaxis=dict(
            visible=False, 
            scaleanchor="x", 
            scaleratio=1
        ),
        margin=dict(l=20, r=20, t=40, b=20)
    )
    return fig
