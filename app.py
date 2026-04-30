import streamlit as st
import pandas as pd
import numpy as np
import os
from scipy.signal import find_peaks

st.set_page_config(page_title="Race Engineer Pro | Sector Audit", layout="wide")

# ── STYLING ────────────────────────────────────────────────────────────────────
DARK_BG = "#0e1117"
CARD_BG = "#1a1d27"
ACCENT = "#e8002d"  # Porsche red

def inject_css():
    st.markdown(f"""
    <style>
        .main {{ background-color: {DARK_BG}; color: white; }}
        .fault-card {{
            background-color: {CARD_BG};
            border-left: 4px solid {ACCENT};
            padding: 12px 16px;
            border-radius: 4px;
            margin: 8px 0;
        }}
        .warn-card {{
            background-color: {CARD_BG};
            border-left: 4px solid #f0a500;
            padding: 12px 16px;
            border-radius: 4px;
            margin: 8px 0;
        }}
        .ok-card {{
            background-color: {CARD_BG};
            border-left: 4px solid #00c46a;
            padding: 12px 16px;
            border-radius: 4px;
            margin: 8px 0;
        }}
        .section-header {{
            font-size: 1.1rem;
            font-weight: 700;
            color: #ffffff;
            margin-top: 16px;
            margin-bottom: 4px;
            border-bottom: 1px solid #2e3147;
            padding-bottom: 4px;
        }}
    </style>
    """, unsafe_allow_html=True)

def fault_card(msg): st.markdown(f'<div class="fault-card">🔴 {msg}</div>', unsafe_allow_html=True)
def warn_card(msg):  st.markdown(f'<div class="warn-card">🟡 {msg}</div>', unsafe_allow_html=True)
def ok_card(msg):    st.markdown(f'<div class="ok-card">🟢 {msg}</div>', unsafe_allow_html=True)
def section_header(msg): st.markdown(f'<div class="section-header">{msg}</div>', unsafe_allow_html=True)

# ── DATA INGESTION ─────────────────────────────────────────────────────────────
def clean_df(df):
    df.columns = df.columns.str.lower().str.replace(' ', '').str.replace('_', '')
    mapping = {
        'dist':     ['dist', 'lapdist', 'distance', 'lapdistpct'],
        'steer':    ['steer', 'steeringwheelangle', 'st'],
        'speed':    ['speed', 'vel', 'velocity', 'v'],
        'throttle': ['throttle', 'thr', 'throt'],
        'brake':    ['brake', 'brk'],
        'latg':     ['lataccel', 'latg'],
        'longg':    ['longaccel', 'lonaccel'],
        'abs':      ['absactive', 'abs']
    }
    clean_data = pd.DataFrame()
    for internal, options in mapping.items():
        match = [
            c for c in df.columns
            if any(opt == c for opt in options) or any(opt in c for opt in options)
        ]
        if match:
            clean_data[internal] = pd.to_numeric(df[match[0]], errors='coerce').fillna(0)
        else:
            clean_data[internal] = 0.0

    # Unit normalisation
    if clean_data['dist'].max() <= 1.1:
        clean_data['dist'] *= 4259
    if clean_data['steer'].abs().max() < 6.28:
        clean_data['steer'] *= (180 / np.pi)
    for g in ['latg', 'longg']:
        if clean_data[g].abs().max() > 5.0:
            clean_data[g] /= 9.81
    if clean_data['speed'].max() < 100:
        clean_data['speed'] *= 3.6

    return clean_data.sort_values('dist').reset_index(drop=True)

# ── INTERPOLATION GRID ─────────────────────────────────────────────────────────
def build_grid(df_d, df_b, n=5000):
    grid = np.linspace(0, df_b['dist'].max(), n)
    res_d, res_b = pd.DataFrame({'dist': grid}), pd.DataFrame({'dist': grid})
    for col in ['speed', 'throttle', 'brake', 'steer', 'latg', 'longg', 'abs']:
        res_d[col] = np.interp(grid, df_d['dist'], df_d[col])
        res_b[col] = np.interp(grid, df_b['dist'], df_b[col])
    return grid, res_d, res_b

# ── DELTA CALCULATION ──────────────────────────────────────────────────────────
def calc_delta(grid, res_d, res_b):
    v_d = np.maximum(res_d['speed'].values / 3.6, 1.0)
    v_b = np.maximum(res_b['speed'].values / 3.6, 1.0)
    ds  = np.diff(grid, prepend=0)
    return pd.Series(np.cumsum(ds / v_d - ds / v_b))

# ══════════════════════════════════════════════════════════════════════════════
# MODULE A — ABS AUDIT
# ══════════════════════════════════════════════════════════════════════════════
def abs_audit(grid, res_d, res_b, sec_mask, sec_name):
    """
    Detects discrete ABS events in the driver lap within a sector.
    For each event: reports track position, duration, distance scrubbed,
    and compares brake ramp rate vs benchmark at the same location.

    Physics basis:
      - ABS active = tire at/past slip peak → longitudinal force dropping
      - Brake ramp rate (% per metre) proxy for pedal aggression
      - Time lost to ABS = integral of speed deficit vs benchmark over event
    """
    section_header("MODULE A — ABS Saturation Audit")

    abs_signal = res_d['abs'].values[sec_mask]
    dist_sec   = grid[sec_mask]
    brake_d    = res_d['brake'].values[sec_mask]
    brake_b    = res_b['brake'].values[sec_mask]
    speed_d    = res_d['speed'].values[sec_mask] / 3.6
    speed_b    = res_b['speed'].values[sec_mask] / 3.6

    # ── Detect discrete ABS events (contiguous blocks where abs > 0.5) ──
    abs_binary = (abs_signal > 0.5).astype(int)
    transitions = np.diff(abs_binary, prepend=0, append=0)
    event_starts = np.where(transitions == 1)[0]
    event_ends   = np.where(transitions == -1)[0]

    # ── Total ABS distance in sector ──
    abs_dist_total = np.sum(np.diff(dist_sec, prepend=dist_sec[0]) * abs_binary)

    if len(event_starts) == 0:
        ok_card(f"No ABS events detected in {sec_name}. Brake application is within tire limits.")
        return

    st.markdown(f"**{len(event_starts)} ABS event(s) detected | Total ABS distance: {abs_dist_total:.1f}m**")

    total_time_lost = 0.0

    for i, (es, ee) in enumerate(zip(event_starts, event_ends)):
        ee = min(ee, len(dist_sec) - 1)

        event_dist_start = dist_sec[es]
        event_dist_end   = dist_sec[ee]
        event_length     = event_dist_end - event_dist_start

        # Time lost during event: ∫(1/v_d - 1/v_b) ds
        ds_event = np.diff(dist_sec[es:ee+1], prepend=dist_sec[es])
        v_d_ev   = np.maximum(speed_d[es:ee+1], 1.0)
        v_b_ev   = np.maximum(speed_b[es:ee+1], 1.0)
        t_lost   = float(np.sum(ds_event * (1.0/v_d_ev - 1.0/v_b_ev)))
        total_time_lost += t_lost

        # Brake ramp rate: peak brake% / distance from brake onset to ABS trigger
        # Search backwards from event start for brake onset (brake < 5%)
        onset_idx = es
        for j in range(es, max(es - 150, 0), -1):
            if brake_d[j] < 5.0:
                onset_idx = j
                break
        ramp_dist = max(dist_sec[es] - dist_sec[onset_idx], 1.0)
        ramp_rate_d = brake_d[es] / ramp_dist   # % per metre

        # Benchmark ramp rate at same location
        b_onset_idx = onset_idx
        for j in range(es, max(es - 150, 0), -1):
            if brake_b[j] < 5.0:
                b_onset_idx = j
                break
        b_ramp_dist    = max(dist_sec[es] - dist_sec[b_onset_idx], 1.0)
        ramp_rate_b    = brake_b[es] / b_ramp_dist

        aggression_ratio = ramp_rate_d / max(ramp_rate_b, 0.01)

        cols = st.columns(4)
        cols[0].metric("Position",      f"{event_dist_start:.0f}m")
        cols[1].metric("ABS Length",    f"{event_length:.1f}m")
        cols[2].metric("Time Lost",     f"{t_lost:+.3f}s")
        cols[3].metric("Ramp Ratio",    f"{aggression_ratio:.2f}x",
                       delta="vs benchmark", delta_color="inverse")

        if aggression_ratio > 1.4:
            fault_card(
                f"Event {i+1} @ {event_dist_start:.0f}m: Ramp rate {aggression_ratio:.1f}x benchmark. "
                f"You are loading the pedal {aggression_ratio:.1f}x faster than required. "
                f"Physical fix: Delay brake point 5–10m and build pressure progressively over "
                f"{ramp_dist*1.3:.0f}m instead of {ramp_dist:.0f}m."
            )
        elif aggression_ratio > 1.15:
            warn_card(
                f"Event {i+1} @ {event_dist_start:.0f}m: Ramp rate marginally aggressive ({aggression_ratio:.2f}x). "
                f"Reduce initial pedal load by ~15%."
            )
        else:
            warn_card(
                f"Event {i+1} @ {event_dist_start:.0f}m: Ramp rate matches benchmark. "
                f"ABS trigger may be setup-related (brake bias too far forward). "
                f"Check bias — shift rearward 1 click."
            )

    fault_card(
        f"TOTAL ABS TIME COST in {sec_name}: {total_time_lost:+.3f}s | "
        f"{abs_dist_total:.1f}m of scrubbing. This is non-recoverable — tires cannot build "
        f"cornering force while locked/sliding."
    )

# ══════════════════════════════════════════════════════════════════════════════
# MODULE B — THROTTLE DISCIPLINE
# ══════════════════════════════════════════════════════════════════════════════
def throttle_discipline(grid, res_d, res_b, sec_mask, sec_name):
    """
    Quantifies sawtooth throttle application on corner exits.

    Metrics:
      - Throttle reversals: direction changes above a noise threshold
      - Variance ratio vs benchmark
      - Throttle-to-speed correlation: smooth application = high correlation
      - Exit commitment distance: how far into exit before reaching 80% throttle

    Physics basis:
      - Rear-engine car: throttle lift under load transfers weight forward,
        unloading rear → oversteer tendency → driver backs off → cycle repeats
      - Each reversal costs ~0.02–0.05s in aero platform recovery
    """
    section_header("MODULE B — Throttle Discipline Audit")

    thr_d   = res_d['throttle'].values[sec_mask]
    thr_b   = res_b['throttle'].values[sec_mask]
    spd_d   = res_d['speed'].values[sec_mask]
    spd_b   = res_b['speed'].values[sec_mask]
    dist_sec = grid[sec_mask]

    # ── Identify exit zones: throttle > 20% and increasing ──
    # We define an exit zone as where benchmark throttle crosses 20% going upward
    b_above_20   = (thr_b > 20).astype(int)
    b_transitions = np.diff(b_above_20, prepend=0)
    exit_starts  = np.where(b_transitions == 1)[0]
    exit_ends    = np.where(b_transitions == -1)[0]

    # Pad exit_ends if lap ends on throttle
    if len(exit_ends) < len(exit_starts):
        exit_ends = np.append(exit_ends, len(dist_sec) - 1)

    NOISE_THRESHOLD = 3.0   # % — changes smaller than this are noise
    REVERSAL_PENALTY = 0.03  # seconds per reversal (empirical)

    total_reversals_d = 0
    total_reversals_b = 0
    total_estimated_cost = 0.0

    if len(exit_starts) == 0:
        warn_card("No exit zones detected in this sector. Check throttle channel mapping.")
        return

    for i, (es, ee) in enumerate(zip(exit_starts, exit_ends)):
        ee = min(ee, len(dist_sec) - 1)
        if ee - es < 5:
            continue

        zone_d = thr_d[es:ee+1]
        zone_b = thr_b[es:ee+1]
        zone_spd_d = spd_d[es:ee+1]
        zone_dist  = dist_sec[es:ee+1]

        # ── Count reversals ──
        def count_reversals(signal, threshold):
            diff = np.diff(signal)
            direction = np.where(np.abs(diff) > threshold, np.sign(diff), 0)
            direction = direction[direction != 0]
            if len(direction) < 2:
                return 0
            return int(np.sum(np.diff(direction) != 0))

        rev_d = count_reversals(zone_d, NOISE_THRESHOLD)
        rev_b = count_reversals(zone_b, NOISE_THRESHOLD)
        total_reversals_d += rev_d
        total_reversals_b += rev_b

        # ── Variance ratio ──
        var_d = float(np.var(np.diff(zone_d)))
        var_b = float(np.var(np.diff(zone_b))) + 1e-6
        variance_ratio = var_d / var_b

        # ── Throttle-speed correlation ──
        # High correlation = throttle increases → speed increases cleanly
        if np.std(zone_d) > 0.1 and np.std(zone_spd_d) > 0.1:
            corr = float(np.corrcoef(zone_d, zone_spd_d)[0, 1])
        else:
            corr = 1.0

        # ── Commitment distance (dist to reach 80% throttle) ──
        above_80_d = np.where(zone_d >= 80)[0]
        above_80_b = np.where(zone_b >= 80)[0]
        commit_d = (zone_dist[above_80_d[0]]  - zone_dist[0]) if len(above_80_d) > 0 else None
        commit_b = (zone_dist[above_80_b[0]]  - zone_dist[0]) if len(above_80_b) > 0 else None

        # ── Estimated time cost ──
        est_cost = rev_d * REVERSAL_PENALTY
        total_estimated_cost += est_cost

        # ── Display ──
        st.markdown(f"**Exit Zone {i+1} | Entry: {zone_dist[0]:.0f}m → {zone_dist[-1]:.0f}m**")
        cols = st.columns(4)
        cols[0].metric("Your Reversals",       str(rev_d))
        cols[1].metric("Benchmark Reversals",  str(rev_b))
        cols[2].metric("Variance Ratio",       f"{variance_ratio:.2f}x")
        cols[3].metric("Thr-Speed Corr",       f"{corr:.2f}")

        if commit_d is not None and commit_b is not None:
            commit_delta = commit_d - commit_b
            st.metric(
                "Commitment Distance",
                f"You: {commit_d:.0f}m | Benchmark: {commit_b:.0f}m",
                delta=f"{commit_delta:+.0f}m to 80%",
                delta_color="inverse"
            )

        if rev_d > rev_b + 2:
            fault_card(
                f"Zone {i+1} @ {zone_dist[0]:.0f}m: SAWTOOTH DETECTED — {rev_d} reversals vs "
                f"benchmark {rev_b}. Variance {variance_ratio:.1f}x higher. "
                f"Estimated cost: {est_cost:.2f}s. "
                f"Physical fix: Establish apex speed confidence first. "
                f"Trail-brake deeper to stabilise rear before committing throttle. "
                f"On 992 GT3: squeeze throttle in 3 stages — 0→30% (apex), 30→70% (track-out), "
                f"70→100% (straight). Do NOT go past 30% until car is pointing straight."
            )
        elif variance_ratio > 1.8:
            warn_card(
                f"Zone {i+1}: Throttle noisier than benchmark ({variance_ratio:.1f}x variance) "
                f"but reversal count similar. Likely micro-lifts under load. "
                f"Fix: Concentrate on a single, continuous squeeze. Record your foot position, "
                f"not the pedal value."
            )
        else:
            ok_card(f"Zone {i+1}: Throttle discipline within acceptable range of benchmark.")

    if total_reversals_d > total_reversals_b + 3:
        fault_card(
            f"SECTOR TOTAL — {total_reversals_d} reversals vs benchmark {total_reversals_b}. "
            f"Estimated throttle discipline cost: {total_estimated_cost:.2f}s. "
            f"This is a rhythm fault, not a single-corner fault. "
            f"Root cause on rear-engine car: you are reactive to the car, not proactive. "
            f"Fix the apex speed (Module C) and this symptom will reduce."
        )

# ══════════════════════════════════════════════════════════════════════════════
# MODULE C — CORNER MINIMUM SPEED AUDIT
# ══════════════════════════════════════════════════════════════════════════════

# Zandvoort GP corner definitions [name, approx_apex_dist_m, search_window_m]
ZANDVOORT_CORNERS = [
    ("T1 Tarzanbocht",       280,  80),
    ("T3 Hugenholtzbocht",   800,  80),
    ("T4 Scheivlak",        1150,  70),
    ("T5",                  1400,  70),
    ("T7 Audi S",           1750,  80),
    ("T9 Arie Luyendijk",   2100,  80),
    ("T11 Vodafone",        2550,  80),
    ("T13 Chicane Entry",   2850,  70),
    ("T14 Chicane Exit",    2980,  70),
]

def corner_min_speed(grid, res_d, res_b, sec_mask, sec_name):
    """
    For each corner apex in the sector, finds the true minimum speed
    (local minima) for driver and benchmark, then calculates:
      - Apex speed deficit
      - Time compounded onto the following straight using kinematic model:
        Δt_straight = L / v_b - L / v_d  (integrated, but simplified here)
      - The straight-line distance over which the deficit compounds

    Physics basis:
      - Apex speed is the boundary condition for the entire exit phase.
        A 5 km/h apex deficit at T1 Tarzan compounds for ~300m of straight.
      - On the 992 GT3 with rear-engine: low apex speed forces more throttle
        angle earlier → rear squat → TC intervention → further loss.
    """
    section_header("MODULE C — Corner Apex Speed Audit")

    dist_sec  = grid[sec_mask]
    spd_d_sec = res_d['speed'].values[sec_mask]
    spd_b_sec = res_b['speed'].values[sec_mask]

    STRAIGHT_ASSUMPTION_M = 200.0  # metres over which deficit compounds
    total_apex_cost       = 0.0

    corners_in_sector = [
        c for c in ZANDVOORT_CORNERS
        if sec_mask[np.searchsorted(grid, c[1], side='left').clip(0, len(grid)-1)]
    ]

    if not corners_in_sector:
        warn_card("No defined corners found in this sector range.")
        return

    for corner_name, apex_dist, window in corners_in_sector:
        lo = apex_dist - window
        hi = apex_dist + window
        win_mask = (dist_sec >= lo) & (dist_sec <= hi)

        if win_mask.sum() < 3:
            continue

        win_spd_d = spd_d_sec[win_mask]
        win_spd_b = spd_b_sec[win_mask]

        apex_spd_d = float(np.min(win_spd_d))
        apex_spd_b = float(np.min(win_spd_b))
        apex_diff  = apex_spd_d - apex_spd_b

        # Compounding time cost on following straight (kinematic)
        # Assume both cars accelerate at same rate from their respective apex speeds
        # Time for benchmark to cover L: t_b = L / v_b (mean speed approx)
        # Time for driver to cover L:    t_d = L / v_d
        # This is conservative — real cost is higher due to TC intervention delay
        v_d_ms = max(apex_spd_d / 3.6, 1.0)
        v_b_ms = max(apex_spd_b / 3.6, 1.0)
        straight_cost = STRAIGHT_ASSUMPTION_M * (1.0/v_d_ms - 1.0/v_b_ms)
        total_apex_cost += max(straight_cost, 0.0)

        # In-corner braking comparison (are we losing speed too early?)
        # Find where benchmark first hits apex speed window coming from above
        pre_mask  = (dist_sec >= lo - 150) & (dist_sec <= lo)
        if pre_mask.sum() > 3:
            brake_start_d = dist_sec[pre_mask][np.where(spd_d_sec[pre_mask] < apex_spd_d * 1.15)[0]]
            brake_start_b = dist_sec[pre_mask][np.where(spd_b_sec[pre_mask] < apex_spd_b * 1.15)[0]]
            brake_dist_d  = float(brake_start_d[0])  if len(brake_start_d)  > 0 else None
            brake_dist_b  = float(brake_start_b[0])  if len(brake_start_b)  > 0 else None
        else:
            brake_dist_d = brake_dist_b = None

        # ── Display ──
        st.markdown(f"**{corner_name} | Apex ~{apex_dist}m**")
        cols = st.columns(4)
        cols[0].metric("Your Apex Speed",      f"{apex_spd_d:.1f} km/h")
        cols[1].metric("Benchmark Apex",       f"{apex_spd_b:.1f} km/h")
        cols[2].metric("Speed Deficit",        f"{apex_diff:+.1f} km/h",
                       delta_color="inverse")
        cols[3].metric("Straight Cost",        f"{straight_cost:+.3f}s")

        if brake_dist_d and brake_dist_b:
            bd_delta = brake_dist_d - brake_dist_b
            st.metric(
                "Braking Threshold vs Benchmark",
                f"{brake_dist_d:.0f}m vs {brake_dist_b:.0f}m",
                delta=f"{bd_delta:+.0f}m",
                delta_color="normal"
            )

        if apex_diff < -8.0:
            fault_card(
                f"{corner_name}: Apex speed deficit {apex_diff:.1f} km/h. "
                f"Compounding {straight_cost:.3f}s onto following straight. "
                f"Root cause: You are over-slowing on entry (ABS scrub killing rotation). "
                f"Fix: Trust the car to rotate. Release brake 10–15m earlier, allow weight "
                f"to transfer forward naturally. The 992 GT3 rear wants to come around — "
                f"brake release IS your rotation tool. Do not hold brake through apex."
            )
        elif apex_diff < -4.0:
            warn_card(
                f"{corner_name}: Moderate apex deficit {apex_diff:.1f} km/h. "
                f"Cost: {straight_cost:.3f}s. Likely hesitation at turn-in. "
                f"Fix: Move brake release point 5m earlier."
            )
        elif apex_diff < -1.5:
            warn_card(
                f"{corner_name}: Minor deficit {apex_diff:.1f} km/h. "
                f"Within noise margin but compound check: is throttle pick-up delayed?"
            )
        else:
            ok_card(f"{corner_name}: Apex speed matches benchmark (Δ{apex_diff:+.1f} km/h).")

    fault_card(
        f"TOTAL APEX COMPOUNDING COST in {sec_name}: {total_apex_cost:+.3f}s. "
        f"NOTE: This is additive to ABS time cost — they share the same root cause."
    )

# ══════════════════════════════════════════════════════════════════════════════
# TIME THIEF (original, preserved)
# ══════════════════════════════════════════════════════════════════════════════
def time_thief_summary(grid, res_d, res_b, delta, sec_mask, sec_name):
    section_header("TIME THIEF — Peak Loss Point")
    sec_delta_val = delta[sec_mask].iloc[-1] - delta[sec_mask].iloc[0]
    sec_slopes    = np.gradient(delta[sec_mask])
    thief_idx     = int(np.argmax(sec_slopes))
    thief_dist    = grid[sec_mask][thief_idx]

    d_pt = res_d[sec_mask].iloc[thief_idx]
    b_pt = res_b[sec_mask].iloc[thief_idx]

    cols = st.columns(4)
    cols[0].metric("Sector Delta",      f"{sec_delta_val:+.3f}s")
    cols[1].metric("Loss Point",        f"{thief_dist:.0f}m")
    cols[2].metric("Speed Diff",        f"{d_pt['speed'] - b_pt['speed']:.1f} km/h")
    cols[3].metric("ABS Active",        "YES" if d_pt['abs'] > 0.5 else "NO")

    if d_pt['abs'] > 0.5:
        fault_card(
            f"Primary Time Thief @ {thief_dist:.0f}m: ABS active. "
            f"You are {d_pt['speed'] - b_pt['speed']:.1f} km/h slower than benchmark at peak loss."
        )
    elif d_pt['throttle'] < b_pt['throttle'] - 20:
        warn_card(
            f"Primary Time Thief @ {thief_dist:.0f}m: Throttle hesitation. "
            f"You: {d_pt['throttle']:.0f}% | Benchmark: {b_pt['throttle']:.0f}%."
        )

# ══════════════════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════════════════
def main():
    inject_css()

    DATA_DIR = "."
    with st.sidebar:
        st.title("🛠️ Race Engineer Config")
        st.markdown("---")
        files = sorted([f for f in os.listdir(DATA_DIR) if f.endswith('.csv')])
        if len(files) < 2:
            st.error("Need at least 2 CSV files in the working directory.")
            st.stop()
        d_file = st.selectbox("Driver Lap",    files, index=0)
        b_file = st.selectbox("Benchmark Lap", files, index=min(1, len(files)-1))
        if d_file == b_file:
            st.warning("Select different files for driver and benchmark.")
            st.stop()
        st.markdown("---")
        st.markdown("**Active Modules**")
        run_abs      = st.checkbox("A — ABS Audit",          value=True)
        run_throttle = st.checkbox("B — Throttle Discipline", value=True)
        run_apex     = st.checkbox("C — Apex Speed",          value=True)

    df_d = clean_df(pd.read_csv(os.path.join(DATA_DIR, d_file)))
    df_b = clean_df(pd.read_csv(os.path.join(DATA_DIR, b_file)))

    grid, res_d, res_b = build_grid(df_d, df_b)
    delta = calc_delta(grid, res_d, res_b)

    st.title("🏁 Race Engineer Pro — Diagnostic Engine")
    st.caption(f"Driver: `{d_file}` | Benchmark: `{b_file}` | Track: Zandvoort GP")

    total_delta = delta.iloc[-1]
    st.metric("Total Lap Delta", f"{total_delta:+.3f}s",
              delta="vs benchmark", delta_color="inverse")

    sectors = [
        {"name": "Sector 1 (Start – T3)",    "start": 0,    "end": 1050},
        {"name": "Sector 2 (T4 – T10)",      "start": 1050, "end": 2750},
        {"name": "Sector 3 (Chicane – End)", "start": 2750, "end": grid[-1]},
    ]

    for sec in sectors:
        mask_bool = (grid >= sec['start']) & (grid <= sec['end'])
        sec_delta_val = delta[mask_bool].iloc[-1] - delta[mask_bool].iloc[0]
        label = f"📌 {sec['name']}  |  Δ {sec_delta_val:+.3f}s"

        with st.expander(label, expanded=(sec['start'] == 0)):
            time_thief_summary(grid, res_d, res_b, delta, mask_bool, sec['name'])
            if run_abs:      abs_audit(          grid, res_d, res_b, mask_bool, sec['name'])
            if run_throttle: throttle_discipline(grid, res_d, res_b, mask_bool, sec['name'])
            if run_apex:     corner_min_speed(   grid, res_d, res_b, mask_bool, sec['name'])

if __name__ == "__main__":
    main()
