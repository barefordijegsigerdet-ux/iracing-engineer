import plotly.graph_objects as go
from plotly.subplots import make_subplots

def create_main_telemetry(user_df, ref_df):
    fig = make_subplots(rows=5, cols=1, shared_xaxes=True, vertical_spacing=0.02,
                        subplot_titles=("Speed", "Delta", "Throttle", "Brake", "G-Sum"))
    
    dist = user_df["distance"]
    # Traces helper
    def add_dual(user_col, ref_col, row, name):
        fig.add_trace(go.Scatter(x=dist, y=ref_df[ref_col], name=f"Ref {name}", line=dict(color="#FF4B4B", width=1), opacity=0.7), row=row, col=1)
        fig.add_trace(go.Scatter(x=dist, y=user_df[user_col], name=f"You {name}", line=dict(color="#1C83E1", width=1.5)), row=row, col=1)

    add_dual("speed", "speed", 1, "Speed")
    fig.add_trace(go.Scatter(x=dist, y=user_df["delta"], fill='tozeroy', line=dict(color="white")), row=2, col=1)
    add_dual("throttle", "throttle", 3, "Throttle")
    add_dual("brake", "brake", 4, "Brake")
    add_dual("g_sum", "g_sum", 5, "G-Sum")

    fig.update_layout(height=1100, template="plotly_dark", showlegend=False)
    return fig

def create_friction_circle(user_df, ref_df):
    fig = go.Figure()
    fig.add_trace(go.Scattergl(x=ref_df["lataccel"], y=ref_df["longaccel"], mode='markers', marker=dict(color='#FF4B4B', size=3, opacity=0.3)))
    fig.add_trace(go.Scattergl(x=user_df["lataccel"], y=user_df["longaccel"], mode='markers', marker=dict(color='#1C83E1', size=3, opacity=0.5)))
    fig.update_layout(title="Friction Circle", template="plotly_dark", height=400, width=400, xaxis=dict(range=[-3,3]), yaxis=dict(range=[-3,3]))
    return fig

def create_track_map(df):
    fig = go.Figure(go.Scattergl(x=df["lon"], y=df["lat"], mode='markers',
                                 marker=dict(color=df["speed"], colorscale='Turbo', size=4, showscale=True)))
    fig.update_layout(title="Track Map", template="plotly_dark", xaxis=dict(visible=False), yaxis=dict(visible=False, scaleanchor="x"))
    return fig
