import plotly.graph_objects as go
from plotly.subplots import make_subplots

def create_main_telemetry(user_df, ref_df):
    # Setup 5 rows: Speed, Delta, Throttle, Brake, G-Sum
    fig = make_subplots(rows=5, cols=1, shared_xaxes=True, vertical_spacing=0.02,
                        subplot_titles=("Speed (km/h)", "Delta (s)", "Throttle (%)", "Brake (%)", "G-Sum (G)"))
    
    dist = user_df["distance"]

    def add_dual(user_col, ref_col, row, name, unit=""):
        # Reference (Red)
        fig.add_trace(go.Scatter(x=dist, y=ref_df[ref_col], name=f"Ref {name}", 
                                 line=dict(color="#FF4B4B", width=1), opacity=0.6,
                                 hovertemplate=f"Ref: %{{y:.1f}}{unit}"), row=row, col=1)
        # User (Blue)
        fig.add_trace(go.Scatter(x=dist, y=user_df[user_col], name=f"You {name}", 
                                 line=dict(color="#1C83E1", width=2),
                                 hovertemplate=f"You: %{{y:.1f}}{unit}"), row=row, col=1)

    add_dual("speed", "speed", 1, "Speed", " km/h")
    # Delta stays as a single white line
    fig.add_trace(go.Scatter(x=dist, y=user_df["delta"], fill='tozeroy', line=dict(color="white", width=1), 
                             name="Delta", hovertemplate="Delta: %{y:.3f}s"), row=2, col=1)
    add_dual("throttle", "throttle", 3, "Throttle", "%")
    add_dual("brake", "brake", 4, "Brake", "%")
    add_dual("g_sum", "g_sum", 5, "G-Sum", " G")

    fig.update_layout(
        height=1100, 
        template="plotly_dark", 
        hovermode="x unified", # Synchronizes hover across all charts
        showlegend=False,
        margin=dict(t=50)
    )
    return fig

def create_friction_circle(user_df, ref_df):
    fig = go.Figure()
    fig.add_trace(go.Scattergl(x=ref_df["lataccel"], y=ref_df["longaccel"], mode='markers', 
                               name='Ref', marker=dict(color='#FF4B4B', size=3, opacity=0.3)))
    fig.add_trace(go.Scattergl(x=user_df["lataccel"], y=user_df["longaccel"], mode='markers', 
                               name='You', marker=dict(color='#1C83E1', size=3, opacity=0.5)))
    fig.update_layout(title="Grip Utilization (Friction Circle)", template="plotly_dark", 
                      height=450, width=450, xaxis=dict(range=[-3,3]), yaxis=dict(range=[-3,3]))
    return fig

def create_track_map(user_df, ref_df):
    fig = go.Figure()
    # Reference Line (Red - Dotted)
    fig.add_trace(go.Scatter(x=ref_df["lon"], y=ref_df["lat"], mode='lines', name='Ref Line',
                             line=dict(color='#FF4B4B', width=2, dash='dot')))
    # User Line (Blue - Solid)
    fig.add_trace(go.Scatter(x=user_df["lon"], y=user_df["lat"], mode='lines', name='Your Line',
                             line=dict(color='#1C83E1', width=3)))
    
    fig.update_layout(title="Line Comparison (Blue = You, Red = Ref)", template="plotly_dark",
                      xaxis=dict(visible=False), yaxis=dict(visible=False, scaleanchor="x"))
    return fig
