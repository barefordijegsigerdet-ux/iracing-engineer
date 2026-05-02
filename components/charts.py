import plotly.graph_objects as go
from plotly.subplots import make_subplots

def create_main_telemetry(user_df, ref_df):
    fig = make_subplots(
        rows=5, cols=1, 
        shared_xaxes=True,
        vertical_spacing=0.02,
        subplot_titles=("Speed (km/h)", "Delta (s)", "Throttle (%)", "Brake (%)", "G-Sum (G)")
    )

    # Common function to add traces
    def add_dual_trace(column, row, name_suffix, color_user="royalblue", color_ref="red"):
        fig.add_trace(go.Scatter(x=user_df["distance"], y=user_df[column], name=f"You {name_suffix}", line=dict(color=color_user, width=2)), row=row, col=1)
        fig.add_trace(go.Scatter(x=ref_df["distance"], y=ref_df[column], name=f"Ref {name_suffix}", line=dict(color=color_ref, width=1.5, dash='dot')), row=row, col=1)

    # Add Traces
    add_dual_trace("speed", 1, "Speed")
    
    # Delta (Special Case: Area Chart)
    fig.add_trace(go.Scatter(x=user_df["distance"], y=user_df["delta"], fill='tozeroy', name="Time Delta", line=dict(color="lightgrey")), row=2, col=1)
    
    add_dual_trace("throttle", 3, "Throttle")
    add_dual_trace("brake", 4, "Brake")
    add_dual_trace("g_sum", 5, "G-Sum")

    # --- FIX THE AXES ---
    # Throttle/Brake: 0 to 105 for headroom
    fig.update_yaxes(range=[-5, 105], row=3, col=1)
    fig.update_yaxes(range=[-5, 105], row=4, col=1)
    
    # G-Sum: 0 to 4 (Standard Racing Gs)
    fig.update_yaxes(range=[0, 4], row=5, col=1)

    fig.update_layout(height=1000, template="plotly_dark", showlegend=False, margin=dict(l=50, r=20, t=50, b=50))
    return fig

def create_friction_circle(user_df, ref_df):
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=ref_df["lataccel"], y=ref_df["longaccel"], mode='markers', name='Ref', marker=dict(color='red', size=2, opacity=0.3)))
    fig.add_trace(go.Scatter(x=user_df["lataccel"], y=user_df["longaccel"], mode='markers', name='You', marker=dict(color='royalblue', size=3, opacity=0.6)))
    
    fig.update_layout(
        title="Grip Efficiency (Friction Circle)",
        xaxis=dict(title="Lateral G", range=[-3, 3]),
        yaxis=dict(title="Longitudinal G", range=[-3, 3]),
        width=600, height=600, template="plotly_dark"
    )
    return fig

def create_track_map(user_df, ref_df):
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=ref_df["lon"], y=ref_df["lat"], name="Reference Line", line=dict(color="red", dash="dash")))
    fig.add_trace(go.Scatter(x=user_df["lon"], y=user_df["lat"], name="Your Line", line=dict(color="royalblue")))
    
    fig.update_layout(
        title="Driving Line (Overlay)",
        xaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
        yaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
        template="plotly_dark", paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)'
    )
    return fig
