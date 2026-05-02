import plotly.graph_objects as go
from plotly.subplots import make_subplots

def create_main_telemetry(user_df, ref_df):
    fig = make_subplots(rows=5, cols=1, shared_xaxes=True, vertical_spacing=0.02,
                        subplot_titles=("Speed", "Delta", "Throttle", "Brake", "G-Sum"))
    
    dist = user_df["distance"]
    # Add Speed
    fig.add_trace(go.Scatter(x=ref_df["distance"], y=ref_df["speed"], name="Ref", line=dict(color="#FF4B4B")), row=1, col=1)
    fig.add_trace(go.Scatter(x=dist, y=user_df["speed"], name="You", line=dict(color="#1C83E1")), row=1, col=1)
    
    # Add Delta with fill
    fig.add_trace(go.Scatter(x=dist, y=user_df["delta"], fill='tozeroy', line=dict(color="white")), row=2, col=1)
    
    # Add Controls
    fig.add_trace(go.Scatter(x=dist, y=user_df["throttle"], line=dict(color="#1C83E1")), row=3, col=1)
    fig.add_trace(go.Scatter(x=dist, y=user_df["brake"], line=dict(color="#FF4B4B")), row=4, col=1)
    fig.add_trace(go.Scatter(x=dist, y=user_df["g_sum"], line=dict(color="#1C83E1")), row=5, col=1)
    
    fig.update_layout(height=1000, template="plotly_dark", showlegend=False)
    return fig

def create_friction_circle(user_df, ref_df):
    fig = go.Figure()
    fig.add_trace(go.Scattergl(x=ref_df["lataccel"], y=ref_df["longaccel"], mode='markers', name='Ref', marker=dict(color='#FF4B4B', opacity=0.3, size=3)))
    fig.add_trace(go.Scattergl(x=user_df["lataccel"], y=user_df["longaccel"], mode='markers', name='You', marker=dict(color='#1C83E1', opacity=0.5, size=3)))
    fig.update_layout(title="Friction Circle (G-G)", template="plotly_dark", height=450, width=450, 
                      xaxis=dict(range=[-3,3], title="Lateral G"), yaxis=dict(range=[-3,3], title="Longitudinal G"))
    return fig

def create_track_map(df):
    fig = go.Figure(go.Scatter(x=df["lon"], y=df["lat"], mode='lines', 
                               line=dict(color=df["speed"], colorscale='Turbo', width=5)))
    fig.update_layout(title="GPS Track Map (Speed Heatmap)", template="plotly_dark", 
                      xaxis=dict(visible=False), yaxis=dict(visible=False, scaleanchor="x"))
    return fig
