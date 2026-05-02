import plotly.graph_objects as go
from plotly.subplots import make_subplots

def create_main_telemetry(u_df, r_df):
    fig = make_subplots(rows=4, cols=1, shared_xaxes=True, vertical_spacing=0.03,
                        row_heights=[0.4, 0.2, 0.2, 0.2])

    # Speed
    fig.add_trace(go.Scatter(x=r_df['distance'], y=r_df['speed'], name="Reference", line=dict(color='red', width=1)), row=1, col=1)
    fig.add_trace(go.Scatter(x=u_df['distance'], y=u_df['speed'], name="Dig", line=dict(color='royalblue', width=2)), row=1, col=1)

    # Delta
    fig.add_trace(go.Scatter(x=u_df['distance'], y=u_df['delta'], name="Delta", fill='tozeroy', line=dict(color='lightgrey')), row=2, col=1)

    # Throttle
    fig.add_trace(go.Scatter(x=u_df['distance'], y=u_df['throttle']*100, name="Throttle", line=dict(color='#00ff00')), row=3, col=1)

    # Brake
    fig.add_trace(go.Scatter(x=u_df['distance'], y=u_df['brake']*100, name="Brake", line=dict(color='#ff0000')), row=4, col=1)

    fig.update_layout(height=800, template="plotly_dark", hovermode="x unified", showlegend=False)
    return fig

def create_track_map(u_df, r_df, hover_dist=0):
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=r_df['lon'], y=r_df['lat'], mode='lines', line=dict(color='#333', width=10), hoverinfo='skip'))
    fig.add_trace(go.Scatter(x=u_df['lon'], y=u_df['lat'], mode='lines', line=dict(color='royalblue', width=3)))

    idx = (u_df['distance'] - hover_dist).abs().idxmin()
    fig.add_trace(go.Scatter(
        x=[u_df.loc[idx, 'lon']], y=[u_df.loc[idx, 'lat']],
        mode='markers', marker=dict(color='white', size=12, line=dict(color='red', width=3))
    ))

    fig.update_layout(template="plotly_dark", height=400, margin=dict(l=0,r=0,b=0,t=0),
                      xaxis=dict(visible=False), yaxis=dict(visible=False, scaleanchor="x"))
    return fig
