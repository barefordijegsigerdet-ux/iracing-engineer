import plotly.graph_objects as go
from plotly.subplots import make_subplots

def create_main_telemetry(user_df, ref_df):
    fig = make_subplots(
        rows=5, cols=1, 
        shared_xaxes=True,
        vertical_spacing=0.02,
        subplot_titles=("Speed (km/h)", "Delta (s)", "Throttle (%)", "Brake (%)", "G-Sum (G)")
    )

    def add_dual_trace(column, row, name_suffix, unit, color_user="royalblue", color_ref="red"):
        # Hovertemplate der viser værdi + enhed
        h_template = f"%{{y:.1f}} {unit}<extra></extra>"
        
        # Din linje
        fig.add_trace(go.Scatter(
            x=user_df["distance"], y=user_df[column], 
            name=f"You", mode='lines', 
            hovertemplate=h_template,
            line=dict(color=color_user, width=2)), row=row, col=1)
        
        # Referencelinje
        fig.add_trace(go.Scatter(
            x=ref_df["distance"], y=ref_df[column], 
            name=f"Ref", mode='lines', 
            hovertemplate=h_template,
            line=dict(color=color_ref, width=1.5, dash='dot')), row=row, col=1)

    # Tilføj grafer med enheder
    add_dual_trace("speed", 1, "Speed", "km/h")
    
    # Delta (Special case)
    fig.add_trace(go.Scatter(
        x=user_df["distance"], y=user_df["delta"], 
        fill='tozeroy', name="Delta", 
        hovertemplate="%{y:.3f} s<extra></extra>",
        line=dict(color="grey")), row=2, col=1)
        
    add_dual_trace("throttle", 3, "Throttle", "%")
    add_dual_trace("brake", 4, "Brake", "%")
    add_dual_trace("g_sum", 5, "G-Sum", "G")

    # Layout indstillinger
    fig.update_layout(
        height=1000, 
        template="plotly_dark", 
        hovermode="x unified", # Dette samler alle værdier i ét vindue ved musen
        showlegend=True, # Det hjælper at se hvem der er hvem i hover
        margin=dict(l=50, r=20, t=50, b=50)
    )

    # Akser
    fig.update_yaxes(range=[-5, 105], row=3, col=1)
    fig.update_yaxes(range=[-5, 105], row=4, col=1)
    fig.update_yaxes(range=[0, 4], row=5, col=1)
    
    return fig
def create_friction_circle(user_df, ref_df):
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=ref_df["lataccel"], y=ref_df["longaccel"], mode='markers', name='Ref', marker=dict(color='red', size=2, opacity=0.3)))
    fig.add_trace(go.Scatter(x=user_df["lataccel"], y=user_df["longaccel"], mode='markers', name='You', marker=dict(color='royalblue', size=3, opacity=0.6)))
    fig.update_layout(xaxis=dict(title="Lateral G", range=[-3, 3]), yaxis=dict(title="Longitudinal G", range=[-3, 3]), template="plotly_dark")
    return fig

def create_track_map(user_df, ref_df, hover_dist=None):
    fig = go.Figure()

    # 1. Banen (Asfalt)
    fig.add_trace(go.Scatter(
        x=ref_df["lon"], y=ref_df["lat"],
        mode='lines',
        line=dict(color='#2a2a2a', width=20),
        hoverinfo='skip',
        showlegend=False
    ))

    # 2. Reference (Rød)
    fig.add_trace(go.Scatter(
        x=ref_df["lon"], y=ref_df["lat"],
        mode='lines',
        name='Reference',
        line=dict(color='#ff4b4b', width=2),
        hoverinfo='skip'
    ))

    # 3. Dig (Blå)
    fig.add_trace(go.Scatter(
        x=user_df["lon"], y=user_df["lat"],
        mode='lines',
        name='You',
        line=dict(color='#1f77b4', width=2),
        hoverinfo='skip'
    ))

    # 4. LIVE MARKØR (Den røde prik)
    if hover_dist is not None:
        # Find nærmeste punkt baseret på distancen fra grafen
        idx = (user_df['distance'] - hover_dist).abs().idxmin()
        car_lat = user_df.loc[idx, 'lat']
        car_lon = user_df.loc[idx, 'lon']

        fig.add_trace(go.Scatter(
            x=[car_lon], y=[car_lat],
            mode='markers+text',
            marker=dict(color='white', size=12, line=dict(color='red', width=3)),
            name='Din position',
            showlegend=False
        ))

   # Layout indstillinger
    fig.update_layout(
        height=800, # Vi sætter en fast højde her også
        template="plotly_dark", 
        hovermode="closest", # Skift fra "x unified" til "closest"
        showlegend=True,
        margin=dict(l=50, r=20, t=50, b=50),
        clickmode='event+select' # Vigtigt: Tillad både klik og valg
    )

    return fig
