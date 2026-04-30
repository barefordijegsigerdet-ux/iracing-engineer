import streamlit as st
import pandas as pd
import numpy as np
import os

st.set_page_config(page_title="Race Engineer Pro | Sector Audit", layout="wide")

# ── STYLING ────────────────────────────────────────────────────────────────────
DARK_BG  = "#0e1117"
CARD_BG  = "#1a1d27"
ACCENT   = "#e8002d"

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
        .verdict-card {{
            background-color: #12151f;
            border: 1px solid #2e3147;
            border-top: 4px solid {ACCENT};
            padding: 16px;
            border-radius: 6px;
            margin: 12px 0;
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

def fault_card(msg):   st.markdown(f'<div class="fault-card">🔴 {msg}</div>',   unsafe_allow_html=True)
def warn_card(msg):    st.markdown(f'<div class="warn-card">🟡 {msg}</div>',    unsafe_allow_html=True)
def ok_card(msg):      st.markdown(f'<div class="ok-card">🟢 {msg}</div>',      unsafe_allow_html=True)
def verdict_card(msg): st.markdown(f'<div class="verdict-card">{msg}</div>',    unsafe_allow_html=True)
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
# FIX 1: Increased to 10000 points to reduce cumulative delta drift.
# ds minimum clamped to avoid near-zero division artifacts at lap boundaries.
def build_grid(df_d, df_b, n=10000):
    """
    Uses the benchmark lap distance as the master grid reference.
    Driver data is interpolated onto this grid so both laps share
    identical distance axis — prerequisite for accurate delta calculation.
    """
    grid = np.linspace(0, df_b['dist'].max(), n)
    res_d = pd.DataFrame({'dist': grid})
    res_b = pd.DataFrame({'dist': grid})
    for col in ['speed', 'throttle', 'brake', 'steer', 'latg', 'longg', 'abs']:
        res_d[col] = np.interp(grid, df_d['dist'], df_d[col])
        res_b[col] = np.interp(grid, df_b['dist'], df_b[col])
    return grid, res_d, res_b

# ── DELTA CALCULATION ──────────────────────────────────────────────────────────
def calc_delta(grid, res_d, res_b):
    """
    Δt = Σ(ds/v_d - ds/v_b)
    ds clamped to minimum 0.01m to prevent division artifacts
    at the lap start boundary where prepend=0 creates a zero interval.
    """
    v_d = np.maximum(res_d['speed'].values / 3.6, 1.0)
    v_b = np.maximum(res_b['speed'].values / 3.6, 1.0)
    ds  = np.maximum(np.diff(grid, prepend=grid[0]), 0.01)
    return pd.Series(np.cumsum(ds / v_d - ds / v_b))

# ── ABS EVENT MERGER ───────────────────────────────────────────────────────────
# FIX 2: Merges fragmented ABS micro-events into real braking zones.
# Events within MERGE_GAP_M metres of each other are collapsed into one.
def merge_abs_events(event_starts, event_ends, dist_array, merge_gap_m=25.0):
    """
    Physics rationale: ABS does not fire as 19 separate events.
    The brake system pulses at ~10Hz — each pulse appears as a micro-event
    in the telemetry. These pulses within a single brake application
    must be treated as one event to calculate meaningful ramp rates
    and total time cost per braking zone.
    """
    if len(event_starts) == 0:
        return [], []

    merged_starts = [event_starts[0]]
    merged_ends   = [event_ends[0]]

    for i in range(1, len(event_starts)):
        gap = dist_array[event_starts[i]] - dist_array[merged_ends[-1]]
        if gap <= merge_gap_m:
            # Extend current zone to absorb this event
            merged_ends[-1] = event_ends[i]
        else:
            merged_starts.append(event_starts[i])
            merged_ends.append(event_ends[i])

    return merged_starts, merged_ends

# ══════════════════════════════════════════════════════════════════════════════
# MODULE A — ABS AUDIT
# ══════════════════════════════════════════════════════════════════════════════
def abs_audit(grid, res_d, res_b, sec_mask, sec_name):
    section_header("MODULE A — ABS Saturation Audit")

    abs_signal = res_d['abs'].values[sec_mask]
    dist_sec   = grid[sec_mask]
    brake_d    = res_d['brake'].values[sec_mask]
    brake_b    = res_b['brake'].values[sec_mask]
    speed_d    = res_d['speed'].values[sec_mask] / 3.6
    speed_b    = res_b['speed'].values[sec_mask] / 3.6

    abs_binary  = (abs_signal > 0.5).astype(int)
    transitions = np.diff(abs_binary, prepend=0, append=0)
    raw_starts  = np.where(transitions ==  1)[0]
    raw_ends    = np.where(transitions == -1)[0]

    # Clip ends to array bounds
    raw_ends = np.minimum(raw_ends, len(dist_sec) - 1)

    abs_dist_total = float(np.sum(
        np.diff(dist_sec, prepend=dist_sec[0]) * abs_binary
    ))

    if len(raw_starts) == 0:
        ok_card(f"No ABS events in {sec_name}. Brake application within tire limits.")
        return 0.0

    # FIX 2 applied: merge micro-events into braking zones
    merged_starts, merged_ends = merge_abs_events(
        raw_starts, raw_ends, dist_sec, merge_gap_m=25.0
    )

    raw_count    = len(raw_starts)
    merged_count = len(merged_starts)

    st.markdown(
        f"**{raw_count} raw ABS pulses → merged into "
        f"{merged_count} braking zone(s) | "
        f"Total ABS distance: {abs_dist_total:.1f}m**"
    )

    total_time_lost = 0.0

    for i, (es, ee) in enumerate(zip(merged_starts, merged_ends)):
        ee = min(ee, len(dist_sec) - 1)

        zone_dist_start = dist_sec[es]
        zone_dist_end   = dist_sec[ee]
        zone_length     = zone_dist_end - zone_dist_start

        # Time lost during zone
        ds_zone  = np.maximum(np.diff(dist_sec[es:ee+1], prepend=dist_sec[es]), 0.01)
        v_d_zone = np.maximum(speed_d[es:ee+1], 1.0)
        v_b_zone = np.maximum(speed_b[es:ee+1], 1.0)
        t_lost   = float(np.sum(ds_zone * (1.0/v_d_zone - 1.0/v_b_zone)))
        total_time_lost += t_lost

        # Ramp rate: search backwards up to 200 points for true brake onset
        onset_idx = es
        for j in range(es, max(es - 200, 0), -1):
            if brake_d[j] < 5.0:
                onset_idx = j
                break
        ramp_dist_d = max(dist_sec[es] - dist_sec[onset_idx], 2.0)
        ramp_rate_d = brake_d[es] / ramp_dist_d

        b_onset_idx = es
        for j in range(es, max(es - 200, 0), -1):
            if brake_b[j] < 5.0:
                b_onset_idx = j
                break
        ramp_dist_b = max(dist_sec[es] - dist_sec[b_onset_idx], 2.0)
        ramp_rate_b = max(brake_b[es] / ramp_dist_b, 0.01)

        aggression_ratio = ramp_rate_d / ramp_rate_b

        # Peak brake pressure in zone
        peak_brake_d = float(np.max(brake_d[es:ee+1]))
        peak_brake_b = float(np.max(brake_b[es:ee+1]))

        cols = st.columns(5)
        cols[0].metric("Zone Start",    f"{zone_dist_start:.0f}m")
        cols[1].metric("Zone Length",   f"{zone_length:.1f}m")
        cols[2].metric("Time Lost",     f"{t_lost:+.3f}s")
        cols[3].metric("Ramp Ratio",    f"{aggression_ratio:.2f}x",
                       delta="vs benchmark", delta_color="inverse")
        cols[4].metric("Peak Brake Δ",  f"{peak_brake_d - peak_brake_b:+.0f}%")

        if aggression_ratio > 1.4:
            fault_card(
                f"Zone {i+1} @ {zone_dist_start:.0f}m — {zone_length:.0f}m of ABS scrubbing. "
                f"Ramp rate {aggression_ratio:.1f}x benchmark. "
                f"You are loading the pedal over {ramp_dist_d:.0f}m, "
                f"benchmark builds over {ramp_dist_b:.0f}m. "
                f"Physical fix: Move brake marker {min(int((ramp_dist_d - ramp_dist_b) * 0.5), 15)}m "
                f"later and build to peak pressure over {ramp_dist_b * 1.2:.0f}m. "
                f"Initial pedal load should be 60% of peak, not 100%."
            )
        elif aggression_ratio > 1.15:
            warn_card(
                f"Zone {i+1} @ {zone_dist_start:.0f}m — Marginally aggressive ramp "
                f"({aggression_ratio:.2f}x). Reduce initial pedal load ~15%. "
                f"Zone length {zone_length:.0f}m."
            )
        else:
            warn_card(
                f"Zone {i+1} @ {zone_dist_start:.0f}m — Ramp rate matches benchmark "
                f"({aggression_ratio:.2f}x) but ABS still firing over {zone_length:.0f}m. "
                f"Likely cause: brake bias too far forward. "
                f"Shift bias 1 click rearward and retest."
            )

    fault_card(
        f"TOTAL ABS COST — {sec_name}: {total_time_lost:+.3f}s across "
        f"{merged_count} braking zone(s) | {abs_dist_total:.1f}m scrubbing. "
        f"Tires cannot generate cornering force during ABS activation. "
        f"This time is non-recoverable within the braking zone itself."
    )

    return total_time_lost

# ══════════════════════════════════════════════════════════════════════════════
# MODULE B — THROTTLE DISCIPLINE
# ══════════════════════════════════════════════════════════════════════════════
def throttle_discipline(grid, res_d, res_b, sec_mask, sec_name):
    section_header("MODULE B — Throttle Discipline Audit")

    thr_d    = res_d['throttle'].values[sec_mask]
    thr_b    = res_b['throttle'].values[sec_mask]
    spd_d    = res_d['speed'].values[sec_mask]
    dist_sec = grid[sec_mask]

    # FIX 3: Lowered threshold from 20% to 10% to capture partial throttle exits
    # Physics basis: on rear-engine car, sawtooth begins at first throttle
    # application, not at wide-open-throttle. 10% captures the critical
    # weight-transfer initiation phase.
    EXIT_THRESHOLD   = 10.0
    NOISE_THRESHOLD  = 3.0
    REVERSAL_PENALTY = 0.025

    b_above  = (thr_b > EXIT_THRESHOLD).astype(int)
    b_trans  = np.diff(b_above, prepend=0)
    exit_starts = np.where(b_trans ==  1)[0]
    exit_ends   = np.where(b_trans == -1)[0]

    if len(exit_ends) < len(exit_starts):
        exit_ends = np.append(exit_ends, len(dist_sec) - 1)

    # Filter: minimum zone length 30m to exclude glitches
    valid = [(s, e) for s, e in zip(exit_starts, exit_ends)
             if dist_sec[min(e, len(dist_sec)-1)] - dist_sec[s] >= 30.0]

    if not valid:
        warn_card(
            "No exit zones detected. Possible causes: "
            "throttle channel mapped incorrectly, or benchmark never "
            "exceeds 10% throttle in this sector (unusual — check CSV headers)."
        )
        return 0.0

    total_reversals_d = 0
    total_reversals_b = 0
    total_est_cost    = 0.0

    def count_reversals(signal, threshold):
        diff      = np.diff(signal)
        direction = np.where(np.abs(diff) > threshold, np.sign(diff), 0)
        direction = direction[direction != 0]
        if len(direction) < 2:
            return 0
        return int(np.sum(np.diff(direction) != 0))

    for i, (es, ee) in enumerate(valid):
        ee = min(ee, len(dist_sec) - 1)
        if ee - es < 5:
            continue

        zone_d    = thr_d[es:ee+1]
        zone_b    = thr_b[es:ee+1]
        zone_spd  = spd_d[es:ee+1]
        zone_dist = dist_sec[es:ee+1]

        rev_d = count_reversals(zone_d, NOISE_THRESHOLD)
        rev_b = count_reversals(zone_b, NOISE_THRESHOLD)
        total_reversals_d += rev_d
        total_reversals_b += rev_b

        var_d = float(np.var(np.diff(zone_d)))
        var_b = float(np.var(np.diff(zone_b))) + 1e-6
        variance_ratio = var_d / var_b

        if np.std(zone_d) > 0.1 and np.std(zone_spd) > 0.1:
            corr = float(np.corrcoef(zone_d, zone_spd)[0, 1])
        else:
            corr = 1.0

        above_80_d = np.where(zone_d >= 80)[0]
        above_80_b = np.where(zone_b >= 80)[0]
        commit_d   = (zone_dist[above_80_d[0]] - zone_dist[0]) if len(above_80_d) > 0 else None
        commit_b   = (zone_dist[above_80_b[0]] - zone_dist[0]) if len(above_80_b) > 0 else None

        est_cost = rev_d * REVERSAL_PENALTY
        total_est_cost += est_cost

        st.markdown(
            f"**Exit Zone {i+1} | "
            f"{zone_dist[0]:.0f}m → {zone_dist[-1]:.0f}m**"
        )
        cols = st.columns(4)
        cols[0].metric("Your Reversals",      str(rev_d))
        cols[1].metric("Bench Reversals",     str(rev_b))
        cols[2].metric("Variance Ratio",      f"{variance_ratio:.2f}x")
        cols[3].metric("Thr–Speed Corr",      f"{corr:.2f}")

        if commit_d is not None and commit_b is not None:
            commit_delta = commit_d - commit_b
            st.metric(
                "Distance to 80% Throttle",
                f"You: {commit_d:.0f}m | Benchmark: {commit_b:.0f}m",
                delta=f"{commit_delta:+.0f}m",
                delta_color="inverse"
            )

        if rev_d > rev_b + 2:
            fault_card(
                f"Zone {i+1} @ {zone_dist[0]:.0f}m: SAWTOOTH — {rev_d} reversals "
                f"vs benchmark {rev_b}. Variance {variance_ratio:.1f}x. "
                f"Est. cost: {est_cost:.2f}s. "
                f"Physical fix — 992 GT3 exit protocol: "
                f"(1) Zero throttle through apex. "
                f"(2) 0→30% as nose points at exit kerb. "
                f"(3) 30→70% only when steering is unwinding. "
                f"(4) 70→100% when car is straight. "
                f"Any reversal in steps 2–3 unloads rear axle and resets the sequence."
            )
        elif variance_ratio > 1.8:
            warn_card(
                f"Zone {i+1}: Noisy throttle ({variance_ratio:.1f}x variance), "
                f"low reversal count. Micro-lifts under aero load. "
                f"Fix: Concentrate on foot pressure not pedal position. "
                f"A consistent squeeze is more important than the exact value."
            )
        else:
            ok_card(
                f"Zone {i+1}: Throttle discipline within benchmark range."
            )

    if total_reversals_d > total_reversals_b + 3:
        fault_card(
            f"SECTOR THROTTLE TOTAL — {total_reversals_d} reversals vs "
            f"benchmark {total_reversals_b}. Est. cost: {total_est_cost:.2f}s. "
            f"This is a rhythm fault across the whole sector, not one corner. "
            f"Root cause on rear-engine car: reactive driving. "
            f"You are responding to what the car does rather than commanding it. "
            f"Fixing apex speed (Module C) will reduce this symptom automatically."
        )

    return total_est_cost

# ══════════════════════════════════════════════════════════════════════════════
# MODULE C — CORNER MINIMUM SPEED AUDIT
# ══════════════════════════════════════════════════════════════════════════════
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
    section_header("MODULE C — Corner Apex Speed Audit")

    dist_sec  = grid[sec_mask]
    spd_d_sec = res_d['speed'].values[sec_mask]
    spd_b_sec = res_b['speed'].values[sec_mask]

    STRAIGHT_M     = 200.0
    total_apex_cost = 0.0

    corners_in_sector = []
    for c in ZANDVOORT_CORNERS:
        idx = np.searchsorted(grid, c[1], side='left')
        idx = int(np.clip(idx, 0, len(grid) - 1))
        if sec_mask[idx]:
            corners_in_sector.append(c)

    if not corners_in_sector:
        warn_card("No defined corners in this sector range.")
        return 0.0

    for corner_name, apex_dist, window in corners_in_sector:
        lo       = apex_dist - window
        hi       = apex_dist + window
        win_mask = (dist_sec >= lo) & (dist_sec <= hi)

        if win_mask.sum() < 3:
            continue

        win_spd_d = spd_d_sec[win_mask]
        win_spd_b = spd_b_sec[win_mask]

        apex_spd_d = float(np.min(win_spd_d))
        apex_spd_b = float(np.min(win_spd_b))
        apex_diff  = apex_spd_d - apex_spd_b

        v_d_ms = max(apex_spd_d / 3.6, 1.0)
        v_b_ms = max(apex_spd_b / 3.6, 1.0)
        straight_cost = STRAIGHT_M * (1.0/v_d_ms - 1.0/v_b_ms)
        total_apex_cost += max(straight_cost, 0.0)

        # Braking threshold comparison
        pre_mask = (dist_sec >= lo - 150) & (dist_sec < lo)
        if pre_mask.sum() > 3:
            spd_pre_d = spd_d_sec[pre_mask]
            spd_pre_b = spd_b_sec[pre_mask]
            dist_pre  = dist_sec[pre_mask]
            thr_d_idx = np.where(spd_pre_d < apex_spd_d * 1.15)[0]
            thr_b_idx = np.where(spd_pre_b < apex_spd_b * 1.15)[0]
            brake_dist_d = float(dist_pre[thr_d_idx[0]])  if len(thr_d_idx) > 0 else None
            brake_dist_b = float(dist_pre[thr_b_idx[0]])  if len(thr_b_idx) > 0 else None
        else:
            brake_dist_d = brake_dist_b = None

        st.markdown(f"**{corner_name} | Apex ~{apex_dist}m**")
        cols = st.columns(4)
        cols[0].metric("Your Apex Speed",  f"{apex_spd_d:.1f} km/h")
        cols[1].metric("Benchmark Apex",   f"{apex_spd_b:.1f} km/h")
        cols[2].metric("Speed Deficit",    f"{apex_diff:+.1f} km/h",
                       delta_color="inverse")
        cols[3].metric("Straight Cost",    f"{straight_cost:+.3f}s")

        if brake_dist_d is not None and brake_dist_b is not None:
            bd_delta = brake_dist_d - brake_dist_b
            st.metric(
                "Braking Threshold vs Benchmark",
                f"You: {brake_dist_d:.0f}m | Benchmark: {brake_dist_b:.0f}m",
                delta=f"{bd_delta:+.0f}m",
                delta_color="normal"
            )

        if apex_diff < -8.0:
            fault_card(
                f"{corner_name}: {apex_diff:.1f} km/h apex deficit. "
                f"Compounding {straight_cost:.3f}s onto following straight. "
                f"Root cause: ABS scrub killed tire rotation on entry, "
                f"forcing you to apex at reduced speed. "
                f"Fix: Release brake 10–15m earlier than current point. "
                f"The 992 GT3 rear axle loads under deceleration — "
                f"brake release IS your rotation tool. "
                f"Hold trail-brake through apex rather than releasing fully."
            )
        elif apex_diff < -4.0:
            warn_card(
                f"{corner_name}: {apex_diff:.1f} km/h deficit. "
                f"Cost {straight_cost:.3f}s. "
                f"Likely hesitation at turn-in or early apex. "
                f"Fix: Move brake release 5m earlier."
            )
        elif apex_diff < -1.5:
            warn_card(
                f"{corner_name}: Minor deficit {apex_diff:.1f} km/h. "
                f"Check throttle pick-up timing on exit."
            )
        else:
            ok_card(
                f"{corner_name}: Apex speed matches benchmark (Δ{apex_diff:+.1f} km/h)."
            )

    fault_card(
        f"TOTAL APEX COMPOUNDING COST — {sec_name}: {total_apex_cost:+.3f}s. "
        f"Shares root cause with ABS events — both are entry technique faults."
    )

    return total_apex_cost

# ══════════════════════════════════════════════════════════════════════════════
# TIME THIEF
# ══════════════════════════════════════════════════════════════════════════════
def time_thief_summary(grid, res_d, res_b, delta, sec_mask):
    section_header("TIME THIEF — Peak Loss Point")

    sec_delta_val = float(delta[sec_mask].iloc[-1] - delta[sec_mask].iloc[0])
    sec_slopes    = np.gradient(delta.values[sec_mask])
    thief_idx     = int(np.argmax(sec_slopes))
    thief_dist    = grid[sec_mask][thief_idx]

    d_pt = res_d[sec_mask].iloc[thief_idx]
    b_pt = res_b[sec_mask].iloc[thief_idx]

    cols = st.columns(4)
    cols[0].metric("Sector Delta",  f"{sec_delta_val:+.3f}s")
    cols[1].metric("Loss Point",    f"{thief_dist:.0f}m")
    cols[2].metric("Speed Diff",    f"{d_pt['speed'] - b_pt['speed']:.1f} km/h")
    cols[3].metric("ABS Active",    "YES" if d_pt['abs'] > 0.5 else "NO")

    if d_pt['abs'] > 0.5:
        fault_card(
            f"Primary Time Thief @ {thief_dist:.0f}m: ABS active. "
            f"{d_pt['speed'] - b_pt['speed']:.1f} km/h vs benchmark at peak loss point."
        )
    elif d_pt['throttle'] < b_pt['throttle'] - 20:
        warn_card(
            f"Primary Time Thief @ {thief_dist:.0f}m: Throttle hesitation. "
            f"You: {d_pt['throttle']:.0f}% | Benchmark: {b_pt['throttle']:.0f}%."
        )

# ══════════════════════════════════════════════════════════════════════════════
# FIX 4 — SECTOR VERDICT BLOCK
# ══════════════════════════════════════════════════════════════════════════════
def sector_verdict(sec_name, sec_delta, abs_cost, throttle_cost, apex_cost):
    """
    Outputs a ranked plain-English to-do list for the sector.
    Costs are sorted by magnitude so the driver knows exactly
    what to fix first for maximum lap time return.
    """
    section_header("SECTOR VERDICT — Ranked To-Do List")

    diagnosed_total = abs_cost + throttle_cost + apex_cost
    undiagnosed     = sec_delta - diagnosed_total

    items = [
        ("ABS Saturation — Over-aggressive brake application",
         abs_cost,
         "Build brake pressure progressively. First 30% of brake zone = 60% of peak pressure only."),
        ("Apex Speed Deficit — Entry technique killing rotation",
         apex_cost,
         "Release brake 10–15m earlier. Use trail-brake through apex to load front tire."),
        ("Throttle Discipline — Sawtooth exit application",
         throttle_cost,
         "Follow 0→30→70→100% exit sequence. No reversal until steering is unwinding."),
    ]

    # Sort by cost descending
    items.sort(key=lambda x: x[1], reverse=True)

    lines = [
        f"<strong>📋 {sec_name} — Sector Delta: {sec_delta:+.3f}s</strong><br>",
        f"Diagnosed: {diagnosed_total:+.3f}s &nbsp;|&nbsp; "
        f"Undiagnosed residual: {undiagnosed:+.3f}s<br><br>",
        "<strong>Priority Order:</strong><br>"
    ]

    for rank, (label, cost, action) in enumerate(items, 1):
        if cost > 0.005:
            icon  = "🔴" if rank == 1 else ("🟡" if rank == 2 else "🔵")
            lines.append(
                f"{icon} <strong>#{rank} — {label}</strong><br>"
                f"&nbsp;&nbsp;&nbsp;&nbsp;Cost: {cost:+.3f}s<br>"
                f"&nbsp;&nbsp;&nbsp;&nbsp;Action: {action}<br><br>"
            )

    if abs(undiagnosed) > 0.05:
        lines.append(
            f"⚪ Residual {undiagnosed:+.3f}s — likely line/gear selection. "
            f"Review track map overlay in Garage 61."
        )

    verdict_card("".join(lines))

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
        b_file = st.selectbox("Benchmark Lap", files, index=min(1, len(files) - 1))

        if d_file == b_file:
            st.warning("Select different files for driver and benchmark.")
            st.stop()

        st.markdown("---")
        st.markdown("**Active Modules**")
        run_abs      = st.checkbox("A — ABS Audit",           value=True)
        run_throttle = st.checkbox("B — Throttle Discipline",  value=True)
        run_apex     = st.checkbox("C — Apex Speed",           value=True)
        run_verdict  = st.checkbox("Sector Verdict",           value=True)

    df_d = clean_df(pd.read_csv(os.path.join(DATA_DIR, d_file)))
    df_b = clean_df(pd.read_csv(os.path.join(DATA_DIR, b_file)))

    grid, res_d, res_b = build_grid(df_d, df_b, n=10000)
    delta = calc_delta(grid, res_d, res_b)

    st.title("🏁 Race Engineer Pro — Diagnostic Engine")
    st.caption(
        f"Driver: `{d_file}`  |  "
        f"Benchmark: `{b_file}`  |  "
        f"Track: Zandvoort GP"
    )

    total_delta = float(delta.iloc[-1])
    st.metric(
        "Total Lap Delta",
        f"{total_delta:+.3f}s",
        delta="vs benchmark",
        delta_color="inverse"
    )

    # FIX 3: S1 extended to 1150m to capture full T3 exit throttle zone
    sectors = [
        {"name": "Sector 1 (Start – T3)",    "start": 0,    "end": 1150},
        {"name": "Sector 2 (T4 – T10)",      "start": 1150, "end": 2750},
        {"name": "Sector 3 (Chicane – End)", "start": 2750, "end": grid[-1]},
    ]

    for sec in sectors:
        mask_bool = (grid >= sec['start']) & (grid <= sec['end'])

        sec_delta_val = float(
            delta[mask_bool].iloc[-1] - delta[mask_bool].iloc[0]
        )
        label = f"📌 {sec['name']}  |  Δ {sec_delta_val:+.3f}s"

        with st.expander(label, expanded=(sec['start'] == 0)):

            time_thief_summary(grid, res_d, res_b, delta, mask_bool)

            abs_cost      = 0.0
            throttle_cost = 0.0
            apex_cost     = 0.0

            if run_abs:
                abs_cost      = abs_audit(
                    grid, res_d, res_b, mask_bool, sec['name'])
            if run_throttle:
                throttle_cost = throttle_discipline(
                    grid, res_d, res_b, mask_bool, sec['name'])
            if run_apex:
                apex_cost     = corner_min_speed(
                    grid, res_d, res_b, mask_bool, sec['name'])
            if run_verdict:
                sector_verdict(
                    sec['name'], sec_delta_val,
                    abs_cost, throttle_cost, apex_cost
                )

if __name__ == "__main__":
    main()
