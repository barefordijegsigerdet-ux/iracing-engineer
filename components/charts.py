import pandas as pd
import plotly.graph_objects as objects
from plotly.subplots import make_subplots

def create_telemetry_chart(user_df: pd.DataFrame, ref_df: pd.DataFrame, delta_df: pd.DataFrame):
    """
    Constructs the high-performance 4-pillar telemetry chart.
    """
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

    # Theming & Formatting
    fig.update_layout(height=850, template="plotly_dark", showlegend=True, hovermode="x unified", margin=dict(t=40, b=40))
    fig.update_xaxes(title_text="Track Distance (m)", row=4, col=1)
    
    return fig
