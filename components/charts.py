import plotly.graph_objects as go
from plotly.subplots import make_subplots

def create_main_telemetry(u_df, r_df):
    # Vi udvider til 5 rækker nu
    fig = make_subplots(rows=5, cols=1, shared_xaxes=True, vertical_spacing=0.03,
                        row_heights=[0.35, 0.15, 0.15, 0.15, 0.20])

    # 1. Speed (km/h)
    fig.add_trace(go.Scatter(x=r_df['distance'], y=r_df['speed'], name="Ref Speed", line=dict(color='red', width=1)), row=1, col=1)
    fig.add_trace(go.Scatter(x=u_df['distance'], y=u_df['speed'], name="Your Speed", line=dict(color='royalblue', width=2)), row=1, col=1)

    # 2. Gear (NY!) - Vi bruger 'hv' (hold vertical) for at få de firkantede skift
    fig.add_trace(go.Scatter(x=r_df['distance'], y=r_df['gear'], name="Ref Gear", line=dict(color='red', width=1, dash='dot'), line_shape='hv'), row=2, col=1)
    fig.add_trace(go.Scatter(x=u_df['distance'], y=u_df['gear'], name="Your Gear", line=dict(color='royalblue', width=2), line_shape='hv'), row=2, col=1)

    # 3. Delta (s)
    fig.add_trace(go.Scatter(x=u_df['distance'], y=u_df['delta'], name="Delta", fill='tozeroy', line=dict(color='lightgrey')), row=3, col=1)

    # 4. Throttle (%)
    fig.add_trace(go.Scatter(x=u_df['distance'], y=u_df['throttle']*100, name="Throttle", line=dict(color='#00ff00')), row=4, col=1)

    # 5. Brake (%)
    fig.add_trace(go.Scatter(x=u_df['distance'], y=u_df['brake']*100, name="Brake", line=dict(color='#ff0000')), row=5, col=1)

    fig.update_layout(height=900, template="plotly_dark", hovermode="x unified", showlegend=False)
    
    # Navngiv y-akserne så det er nemt at læse (ligesom i image_7b8d5c.png)
    fig.update_yaxes(title_text="Speed", row=1, col=1)
    fig.update_yaxes(title_text="Gear", row=2, col=1)
    fig.update_yaxes(title_text="Delta", row=3, col=1)
    
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
