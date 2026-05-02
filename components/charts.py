import plotly.graph_objects as go
from plotly.subplots import make_subplots

def create_main_telemetry(u_df, r_df):
    # Skaber 4 rækker: Speed, Delta, Throttle, Brake
    fig = make_subplots(rows=4, cols=1, shared_xaxes=True, vertical_spacing=0.04,
                        row_heights=[0.4, 0.2, 0.2, 0.2])

    # Speed
    fig.add_trace(go.Scatter(x=r_df['distance'], y=r_df['speed'], name="Reference", line=dict(color='red', width=1)), row=1, col=1)
    fig.add_trace(go.Scatter(x=u_df['distance'], y=u_df['speed'], name="You", line=dict(color='royalblue', width=2)), row=1, col=1)

    # Delta
    fig.add_trace(go.Scatter(x=u_df['distance'], y=u_df['delta'], name="Delta", fill='tozeroy', line=dict(color='white', width=1)), row=2, col=1)

    # Throttle (Grøn som i dit billede)
    fig.add_trace(go.Scatter(x=u_df['distance'], y=u_df['throttle']*100, name="Throttle", line=dict(color='#00ff00', width=1.5)), row=3, col=1)

    # Brake (Rød som i dit billede)
    fig.add_trace(go.Scatter(x=u_df['distance'], y=u_df['brake']*100, name="Brake", line=dict(color='#ff0000', width=1.5)), row=4, col=1)

    fig.update_layout(
        height=850, 
        template="plotly_dark", 
        hovermode="closest", 
        showlegend=False,
        margin=dict(l=20, r=20, t=20, b=20)
    )
    
    fig.update_xaxes(showgrid=True, gridcolor="#222")
    fig.update_yaxes(showgrid=True, gridcolor="#222")
    
    return fig

def create_track_map(u_df, r_df, hover_dist=0):
    fig = go.Figure()
    
    # Bane-outline
    fig.add_trace(go.Scatter(x=r_df['lon'], y=r_df['lat'], mode='lines', line=dict(color='#333', width=15), hoverinfo='skip'))
    fig.add_trace(go.Scatter(x=u_df['lon'], y=u_df['lat'], mode='lines', line=dict(color='royalblue', width=2)))

    # Markøren (den hvide prik med rød kant)
    idx = (u_df['distance'] - hover_dist).abs().idxmin()
    fig.add_trace(go.Scatter(
        x=[u_df.loc[idx, 'lon']], y=[u_df.loc[idx, 'lat']],
        mode='markers', 
        marker=dict(color='white', size=12, line=dict(color='red', width=3)),
        showlegend=False
    ))

    fig.update_layout(
        template="plotly_dark", 
        height=450, 
        margin=dict(l=0, r=0, b=0, t=0),
        xaxis=dict(showgrid=False, zeroline=False, showticklabels=False, scaleanchor="y"),
        yaxis=dict(showgrid=False, zeroline=False, showticklabels=False)
    )
    return fig
