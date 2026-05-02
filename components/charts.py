import plotly.graph_objects as go
from plotly.subplots import make_subplots

def create_main_telemetry(user_df, r_df):
    # Opret subplots (5 rækker: Speed, Delta, Throttle, Brake, G-Sum)
    fig = make_subplots(rows=5, cols=1, shared_xaxes=True, vertical_spacing=0.02,
                        row_heights=[0.3, 0.15, 0.15, 0.15, 0.25])

    # --- Speed ---
    fig.add_trace(go.Scatter(x=r_df['distance'], y=r_df['speed'], name="Ref Speed", line=dict(color='red', dash='dash', width=1)), row=1, col=1)
    fig.add_trace(go.Scatter(x=user_df['distance'], y=user_df['speed'], name="You Speed", line=dict(color='royalblue', width=2)), row=1, col=1)

    # --- Delta ---
    fig.add_trace(go.Scatter(x=user_df['distance'], y=user_df['delta'], name="Delta", fill='tozeroy', line=dict(color='gray')), row=2, col=1)

    # --- Throttle ---
    fig.add_trace(go.Scatter(x=r_df['distance'], y=r_df['throttle']*100, name="Ref Throttle", line=dict(color='red', dash='dash', width=1)), row=3, col=1)
    fig.add_trace(go.Scatter(x=user_df['distance'], y=user_df['throttle']*100, name="You Throttle", line=dict(color='royalblue', width=2)), row=3, col=1)

    # --- Brake ---
    fig.add_trace(go.Scatter(x=r_df['distance'], y=r_df['brake']*100, name="Ref Brake", line=dict(color='red', dash='dash', width=1)), row=4, col=1)
    fig.add_trace(go.Scatter(x=user_df['distance'], y=user_df['brake']*100, name="You Brake", line=dict(color='royalblue', width=2)), row=4, col=1)

    # --- G-Sum ---
    fig.add_trace(go.Scatter(x=user_df['distance'], y=user_df['g_sum'], name="G-Sum", line=dict(color='magenta', width=1)), row=5, col=1)

    fig.update_layout(
        template="plotly_dark",
        height=800,
        margin=dict(l=50, r=20, t=30, b=50),
        hovermode='closest', # Vigtigt for at fange enkelte punkter
        showlegend=False
    )
    
    # Fjern x-akse labels fra de øverste grafer (da de deler x-akse)
    fig.update_xaxes(showticklabels=False, row=1, col=1)
    fig.update_xaxes(showticklabels=False, row=2, col=1)
    fig.update_xaxes(showticklabels=False, row=3, col=1)
    fig.update_xaxes(showticklabels=False, row=4, col=1)
    fig.update_xaxes(title_text="Distance (m)", row=5, col=1)

    return fig

def create_track_map(user_df, ref_df, hover_dist=None):
    fig = go.Figure()

    # 1. Asfalten (Tykkere baggrund)
    fig.add_trace(go.Scatter(
        x=ref_df["lon"], y=ref_df["lat"],
        mode='lines',
        line=dict(color='#2a2a2a', width=20),
        hoverinfo='skip',
        showlegend=False
    ))

    # 2. Referencelinjen
    fig.add_trace(go.Scatter(
        x=ref_df["lon"], y=ref_df["lat"],
        mode='lines',
        name='Reference',
        line=dict(color='red', width=2),
        hoverinfo='skip'
    ))

    # 3. Din linje
    fig.add_trace(go.Scatter(
        x=user_df["lon"], y=user_df["lat"],
        mode='lines',
        name='You',
        line=dict(color='royalblue', width=2),
        hoverinfo='skip'
    ))

    # 4. LIVE POSITION (Prikken fra Garage 61)
    if hover_dist is not None:
        # Find nærmeste koordinat baseret på distancen
        idx = (user_df['distance'] - hover_dist).abs().idxmin()
        fig.add_trace(go.Scatter(
            x=[user_df.loc[idx, 'lon']], 
            y=[user_df.loc[idx, 'lat']],
            mode='markers',
            marker=dict(color='white', size=12, line=dict(color='red', width=3)),
            name='Nu',
            showlegend=False
        ))

    fig.update_layout(
        template="plotly_dark",
        plot_bgcolor='rgba(0,0,0,0)',
        paper_bgcolor='rgba(0,0,0,0)',
        margin=dict(l=0, r=0, t=0, b=0),
        xaxis=dict(showgrid=False, zeroline=False, showticklabels=False, scaleanchor="y"),
        yaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
        dragmode='pan'
    )

    return fig
