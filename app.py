# app.py - Race Engineer Pro v5.0
import streamlit as st
import pandas as pd
import numpy as np
import os
import google.generativeai as genai

st.set_page_config(page_title="Race Engineer Pro", layout="wide", page_icon="🏁")

# ── GEMINI SETUP ───────────────────────────────────────────────────────────────
genai.configure(api_key=st.secrets["GEMINI_API_KEY"])

# ── STYLING ────────────────────────────────────────────────────────────────────
def inject_css():
    st.markdown("""
    <style>
        .main { background-color: #0e1117; color: white; }
        .fault-card {
            background-color: #1a1d27;
            border-left: 4px solid #e8002d;
            padding: 12px 16px;
            border-radius: 4px;
            margin: 8px 0;
        }
        .warn-card {
            background-color: #1a1d27;
            border-left: 4px solid #f0a500;
            padding: 12px 16px;
            border-radius: 4px;
            margin: 8px 0;
        }
        .ok-card {
            background-color: #1a1d27;
            border-left: 4px solid #00c46a;
            padding: 12px 16px;
            border-radius: 4px;
            margin: 8px 0;
        }
        .verdict-card {
            background-color: #12151f;
            border: 1px solid #2e3147;
            border-top: 4px solid #e8002d;
            padding: 16px;
            border-radius: 6px;
            margin: 12px 0;
        }
        .section-header {
            font-size: 1.1rem;
            font-weight: 700;
            color: #ffffff;
            margin-top: 16px;
            margin-bottom: 4px;
            border-bottom: 1px solid #2e3147;
            padding-bottom: 4px;
        }
        .coming-soon {
            background-color: #1a1d27;
            border: 2px dashed #2e3147;
            padding: 40px;
            border-radius: 8px;
            text-align: center;
            color: #666;
        }
    </style>
    """, unsafe_allow_html=True)

def fault_card(msg):     st.markdown(f'<div class="fault-card">🔴 {msg}</div>', unsafe_allow_html=True)
def warn_card(msg):      st.markdown(f'<div class="warn-card">🟡 {msg}</div>', unsafe_allow_html=True)
def ok_card(msg):        st.markdown(f'<div class="ok-card">🟢 {msg}</div>', unsafe_allow_html=True)
def verdict_card(msg):   st.markdown(f'<div class="verdict-card">{msg}</div>', unsafe_allow_html=True)
def section_header(msg): st.markdown(f'<div class="section-header">{msg}</div>', unsafe_allow_html=True)

# ── CAR & TRACK DEFINITIONS ────────────────────────────────────────────────────
CARS = [
    "Porsche 911 GT3 Cup (992.2)",
    "Porsche 911 GT3 R (992)",
    "Ferrari 296 GT3",
    "Lamborghini Huracán GT3 EVO2",
    "BMW M4 GT3",
    "Mercedes-AMG GT3 2020",
    "Audi R8 LMS EVO II GT3",
    "McLaren 720S GT3 EVO",
    "Other (type below)",
]

TRACKS = {
    "Circuit Zandvoort (GP)": {
        "length_m": 4259,
        "sectors": [
            {"name": "Sector 1 (Start – T3)",    "start": 0,    "end": 1150},
            {"name": "Sector 2 (T4 – T10)",      "start": 1150, "end": 2750},
            {"name": "Sector 3 (Chicane – End)", "start": 2750, "end": 4259},
        ],
        "corners": [
            ("T1 Tarzanbocht",     280,  80),
            ("T3 Hugenholtzbocht", 800,  80),
            ("T4 Scheivlak",      1150,  70),
            ("T5",                1400,  70),
            ("T7 Audi S",         1750,  80),
            ("T9 Arie Luyendijk", 2100,  80),
            ("T11 Vodafone",      2550,  80),
            ("T13 Chicane Entry", 2850,  70),
            ("T14 Chicane Exit",  2980,  70),
        ]
    },
    "Spa-Francorchamps": {
        "length_m": 7004,
        "sectors": [
            {"name": "Sector 1 (Start – Eau Rouge)", "start": 0,    "end": 2000},
            {"name": "Sector 2 (Kemmel – Stavelot)",  "start": 2000, "end": 5000},
            {"name": "Sector 3 (Pouhon – Finish)",    "start": 5000, "end": 7004},
        ],
        "corners": [
            ("T1 La Source",   180,  80),
            ("Eau Rouge",      750,  80),
            ("Raidillon",      900,  80),
            ("Kemmel",        1800,  80),
            ("Les Combes",    2200,  80),
            ("Malmedy",       2600,  70),
            ("Rivage",        3200,  80),
            ("Pouhon",        4200,  80),
            ("Fagnes",        4800,  70),
            ("Stavelot",      5200,  80),
            ("Blanchimont",   6000,  80),
            ("Bus Stop",      6600,  70),
        ]
    },
    "Nürburgring GP": {
        "length_m": 5148,
        "sectors": [
            {"name": "Sector 1 (Start – T6)",    "start": 0,    "end": 1800},
            {"name": "Sector 2 (T7 – T13)",      "start": 1800, "end": 3600},
            {"name": "Sector 3 (T14 – Finish)",  "start": 3600, "end": 5148},
        ],
        "corners": [
            ("T1 Mercedes",   350,  80),
            ("T2",            600,  70),
            ("T4 Ford",      1100,  80),
            ("T6 Dunlop",    1700,  80),
            ("T8",           2200,  80),
            ("T11",          2800,  80),
            ("T13",          3500,  80),
            ("T14",          3800,  80),
            ("T16 Veedol",   4500,  80),
        ]
    },
    "Other (type below)": {
        "length_m": 4000,
        "sectors": [
            {"name": "Sector 1", "start": 0,    "end": 1333},
            {"name": "Sector 2", "start": 1333, "end": 2666},
            {"name": "Sector 3", "start": 2666, "end": 4000},
        ],
        "corners": []
    }
}

# ── DATA INGESTION ─────────────────────────────────────────────────────────────
def clean_df(df, track_length_m=4259):
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
        match = [c for c in df.columns
                 if any(opt == c for opt in options) or any(opt in c for opt in options)]
        if match:
            clean_data[internal] = pd.to_numeric(df[match[0]], errors='coerce').fillna(0)
        else:
            clean_data[internal] = 0.0

    if clean_data['dist'].max() <= 1.1:
        clean_data['dist'] *= track_length_m
    if clean_data['steer'].abs().max() < 6.28:
        clean_data['steer'] *= (180 / np.pi)
    for g in ['latg', 'longg']:
        if clean_data[g].abs().max() > 5.0:
            clean_data[g] /= 9.81
    if clean_data['speed'].max() < 100:
        clean_data['speed'] *= 3.6

    # FIX 1 — Brake normalisation
    # Garage 61 exports brake as 0.0–1.0 float, not 0–100%.
    # Normalise to 0–100 so peak brake delta and ramp rate calculations
    # produce meaningful numbers instead of always showing 0.
    if clean_data['brake'].max() <= 1.0:
        clean_data['brake'] *= 100.0

    return clean_data.sort_values('dist').reset_index(drop=True)

def build_grid(df_d, df_b, n=10000):
    grid  = np.linspace(0, df_b['dist'].max(), n)
    res_d = pd.DataFrame({'dist': grid})
    res_b = pd.DataFrame({'dist': grid})
    for col in ['speed', 'throttle', 'brake', 'steer', 'latg', 'longg', 'abs']:
        res_d[col] = np.interp(grid, df_d['dist'], df_d[col])
        res_b[col] = np.interp(grid, df_b['dist'], df_b[col])
    return grid, res_d, res_b

def calc_delta(grid, res_d, res_b):
    v_d = np.maximum(res_d['speed'].values / 3.6, 1.0)
    v_b = np.maximum(res_b['speed'].values / 3.6, 1.0)
    ds  = np.maximum(np.diff(grid, prepend=grid[0]), 0.01)
    return pd.Series(np.cumsum(ds / v_d - ds / v_b))

# ── ABS EVENT MERGER ───────────────────────────────────────────────────────────
def merge_abs_events(event_starts, event_ends, dist_array, merge_gap_m=25.0):
    if len(event_starts) == 0:
        return [], []
    merged_starts = [event_starts[0]]
    merged_ends   = [event_ends[0]]
    for i in range(1, len(event_starts)):
        gap = dist_array[event_starts[i]] - dist_array[merged_ends[-1]]
        if gap <= merge_gap_m:
            merged_ends[-1] = event_ends[i]
        else:
            merged_starts.append(event_starts[i])
            merged_ends.append(event_ends[i])
    return merged_starts, merged_ends

# ── FIX 2 — Aggression label ──────────────────────────────────────────────────
def aggression_label(ratio):
    """
    Converts the ramp ratio number into plain English.
    Ratio = how fast you loaded the brake vs the benchmark.
    1.0x = identical. 2.0x = twice as aggressive.
    """
    if ratio < 1.15:
        return "Fine"
    elif ratio < 1.4:
        return "A bit hard"
    elif ratio < 2.5:
        return "Too hard"
    elif ratio < 5.0:
        return "Way too hard"
    else:
        return "Panic stab"

# ══════════════════════════════════════════════════════════════════════════════
# MODULE A — ABS AUDIT
# ══════════════════════════════════════════════════════════════════════════════
def abs_audit(grid, res_d, res_b, sec_mask, sec_name):
    section_header("ABS Check")

    abs_signal = res_d['abs'].values[sec_mask]
    dist_sec   = grid[sec_mask]
    brake_d    = res_d['brake'].values[sec_mask]
    brake_b    = res_b['brake'].values[sec_mask]
    speed_d    = res_d['speed'].values[sec_mask] / 3.6
    speed_b    = res_b['speed'].values[sec_mask] / 3.6

    abs_binary  = (abs_signal > 0.5).astype(int)
    transitions = np.diff(abs_binary, prepend=0, append=0)
    raw_starts  = np.where(transitions ==  1)[0]
    raw_ends    = np.minimum(np.where(transitions == -1)[0], len(dist_sec) - 1)

    abs_dist_total = float(np.sum(np.diff(dist_sec, prepend=dist_sec[0]) * abs_binary))

    if len(raw_starts) == 0:
        ok_card(f"Clean braking in {sec_name}. ABS isn't being triggered — nice.")
        return 0.0

    merged_starts, merged_ends = merge_abs_events(
        raw_starts, raw_ends, dist_sec, merge_gap_m=25.0
    )
    merged_count = len(merged_starts)

    st.markdown(
        f"**{merged_count} braking zone(s) with ABS | "
        f"{abs_dist_total:.1f}m total scrubbing**"
    )

    total_time_lost = 0.0

    for i, (es, ee) in enumerate(zip(merged_starts, merged_ends)):
        ee = min(ee, len(dist_sec) - 1)

        zone_dist_start = dist_sec[es]
        zone_length     = dist_sec[ee] - zone_dist_start

        ds_zone  = np.maximum(np.diff(dist_sec[es:ee+1], prepend=dist_sec[es]), 0.01)
        v_d_zone = np.maximum(speed_d[es:ee+1], 1.0)
        v_b_zone = np.maximum(speed_b[es:ee+1], 1.0)
        t_lost   = float(np.sum(ds_zone * (1.0/v_d_zone - 1.0/v_b_zone)))
        total_time_lost += t_lost

        # Ramp rate — how quickly brake pressure was built to ABS trigger point
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

        # FIX 1 — Peak brake delta now meaningful because brake is 0–100
        peak_brake_d = float(np.max(brake_d[es:ee+1]))
        peak_brake_b = float(np.max(brake_b[es:ee+1]))
        peak_brake_delta = peak_brake_d - peak_brake_b

        # FIX 2 — Plain English aggression label instead of raw ratio
        label = aggression_label(aggression_ratio)

        cols = st.columns(5)
        cols[0].metric("Where",          f"{zone_dist_start:.0f}m")
        cols[1].metric("Length",         f"{zone_length:.1f}m")
        cols[2].metric("Time Lost",      f"{t_lost:+.3f}s")
        cols[3].metric("Brake Entry",    label)
        cols[4].metric("Peak Brake Δ",   f"{peak_brake_delta:+.0f}%")

        if aggression_ratio > 1.4:
            fault_card(
                f"Zone {i+1} at {zone_dist_start:.0f}m — you're hitting the brake "
                f"way harder than needed ({label}). "
                f"That's {zone_length:.0f}m of the tire skidding instead of braking. "
                f"Fix: Brake a touch later and build pressure over "
                f"{ramp_dist_b * 1.2:.0f}m instead of stabbing it. "
                f"Start at 60%, not 100%."
            )
        elif aggression_ratio > 1.15:
            warn_card(
                f"Zone {i+1} at {zone_dist_start:.0f}m — brake entry is "
                f"{label.lower()}. Back off the initial pedal load by about 15%."
            )
        else:
            warn_card(
                f"Zone {i+1} at {zone_dist_start:.0f}m — your brake application "
                f"is actually fine, but ABS is still firing. "
                f"Brake bias might be too far forward. "
                f"Try shifting it 1 click rearward."
            )

    fault_card(
        f"Total braking cost in {sec_name}: {total_time_lost:+.3f}s — "
        f"{abs_dist_total:.1f}m where the tires were sliding instead of working."
    )
    return total_time_lost

# ══════════════════════════════════════════════════════════════════════════════
# MODULE B — THROTTLE DISCIPLINE
# ══════════════════════════════════════════════════════════════════════════════
def throttle_discipline(grid, res_d, res_b, sec_mask, sec_name):
    section_header("Throttle Check")

    thr_d    = res_d['throttle'].values[sec_mask]
    thr_b    = res_b['throttle'].values[sec_mask]
    spd_d    = res_d['speed'].values[sec_mask]
    dist_sec = grid[sec_mask]

    EXIT_THRESHOLD   = 10.0
    NOISE_THRESHOLD  = 3.0
    REVERSAL_PENALTY = 0.025

    b_above     = (thr_b > EXIT_THRESHOLD).astype(int)
    b_trans     = np.diff(b_above, prepend=0)
    exit_starts = np.where(b_trans ==  1)[0]
    exit_ends   = np.where(b_trans == -1)[0]

    if len(exit_ends) < len(exit_starts):
        exit_ends = np.append(exit_ends, len(dist_sec) - 1)

    valid = [(s, e) for s, e in zip(exit_starts, exit_ends)
             if dist_sec[min(e, len(dist_sec)-1)] - dist_sec[s] >= 30.0]

    if not valid:
        warn_card("No throttle exit zones found in this sector. Check your CSV file.")
        return 0.0

    def count_reversals(signal, threshold):
        diff      = np.diff(signal)
        direction = np.where(np.abs(diff) > threshold, np.sign(diff), 0)
        direction = direction[direction != 0]
        if len(direction) < 2:
            return 0
        return int(np.sum(np.diff(direction) != 0))

    total_reversals_d = 0
    total_reversals_b = 0
    total_est_cost    = 0.0

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

        var_d          = float(np.var(np.diff(zone_d)))
        var_b          = float(np.var(np.diff(zone_b))) + 1e-6
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

        st.markdown(f"**Exit Zone {i+1} | {zone_dist[0]:.0f}m → {zone_dist[-1]:.0f}m**")
        cols = st.columns(4)
        cols[0].metric("Your Lifts",      str(rev_d))
        cols[1].metric("Benchmark Lifts", str(rev_b))
        cols[2].metric("Smoothness",      f"{variance_ratio:.2f}x noisier")
        cols[3].metric("Throttle-Speed",  f"{corr:.2f}")

        if commit_d is not None and commit_b is not None:
            commit_delta = commit_d - commit_b
            st.metric(
                "Distance to full throttle",
                f"You: {commit_d:.0f}m | Benchmark: {commit_b:.0f}m",
                delta=f"{commit_delta:+.0f}m",
                delta_color="inverse"
            )

        if rev_d > rev_b + 2:
            fault_card(
                f"Zone {i+1} at {zone_dist[0]:.0f}m — you're lifting off the throttle "
                f"{rev_d} times where the benchmark does it {rev_b} times. "
                f"That's costing you ~{est_cost:.2f}s right there. "
                f"On this car, every time you lift, the rear unsettles and you lose the exit. "
                f"Fix: Squeeze it in stages — 30% at apex, 70% when unwinding, "
                f"100% when straight. No lifting once you've started."
            )
        elif variance_ratio > 1.8:
            warn_card(
                f"Zone {i+1} — not many full lifts but your throttle foot is nervous. "
                f"{variance_ratio:.1f}x more movement than the benchmark. "
                f"Relax your foot and commit to a smooth squeeze."
            )
        else:
            ok_card(f"Zone {i+1} — clean exit. That's what it should look like.")

    if total_reversals_d > total_reversals_b + 3:
        fault_card(
            f"Across the whole {sec_name} — {total_reversals_d} throttle lifts vs "
            f"benchmark's {total_reversals_b}. Est. cost: {total_est_cost:.2f}s. "
            f"This isn't a one-corner problem, it's a habit. "
            f"The fix starts with trusting your apex speed more — "
            f"sort the braking first and the throttle will follow."
        )
    return total_est_cost

# ══════════════════════════════════════════════════════════════════════════════
# MODULE C — APEX SPEED AUDIT
# ══════════════════════════════════════════════════════════════════════════════
def corner_min_speed(grid, res_d, res_b, sec_mask, sec_name, corners):
    section_header("Corner Speed Check")

    dist_sec  = grid[sec_mask]
    spd_d_sec = res_d['speed'].values[sec_mask]
    spd_b_sec = res_b['speed'].values[sec_mask]

    STRAIGHT_M      = 200.0
    total_apex_cost = 0.0

    corners_in_sector = []
    for c in corners:
        idx = int(np.clip(np.searchsorted(grid, c[1], side='left'), 0, len(grid) - 1))
        if sec_mask[idx]:
            corners_in_sector.append(c)

    if not corners_in_sector:
        warn_card("No corners mapped for this sector yet.")
        return 0.0

    for corner_name, apex_dist, window in corners_in_sector:
        win_mask = (dist_sec >= apex_dist - window) & (dist_sec <= apex_dist + window)
        if win_mask.sum() < 3:
            continue

        apex_spd_d = float(np.min(spd_d_sec[win_mask]))
        apex_spd_b = float(np.min(spd_b_sec[win_mask]))
        apex_diff  = apex_spd_d - apex_spd_b

        v_d_ms        = max(apex_spd_d / 3.6, 1.0)
        v_b_ms        = max(apex_spd_b / 3.6, 1.0)
        straight_cost = STRAIGHT_M * (1.0/v_d_ms - 1.0/v_b_ms)
        total_apex_cost += max(straight_cost, 0.0)

        st.markdown(f"**{corner_name}**")
        cols = st.columns(4)
        cols[0].metric("Your Apex Speed",  f"{apex_spd_d:.1f} km/h")
        cols[1].metric("Benchmark Apex",   f"{apex_spd_b:.1f} km/h")
        cols[2].metric("Difference",       f"{apex_diff:+.1f} km/h",
                       delta_color="inverse")
        cols[3].metric("Cost on exit",     f"{straight_cost:+.3f}s")

        if apex_diff < -8.0:
            fault_card(
                f"{corner_name} — you're {abs(apex_diff):.1f} km/h slower through the apex "
                f"and that's costing {straight_cost:.3f}s on the straight alone. "
                f"The braking is killing your rotation. "
                f"Release the brake 10–15m earlier and let the car rotate. "
                f"Don't hold the brake through the apex — that's what's slowing you down."
            )
        elif apex_diff < -4.0:
            warn_card(
                f"{corner_name} — {abs(apex_diff):.1f} km/h off the benchmark. "
                f"Costs {straight_cost:.3f}s. Try releasing the brake 5m earlier at turn-in."
            )
        elif apex_diff < -1.5:
            warn_card(
                f"{corner_name} — small deficit of {abs(apex_diff):.1f} km/h. "
                f"Worth checking your throttle pick-up timing on the exit."
            )
        else:
            ok_card(f"{corner_name} — apex speed is right on benchmark. Good.")

    fault_card(
        f"Total apex speed cost across {sec_name}: {total_apex_cost:+.3f}s — "
        f"this compounds onto every straight after each corner."
    )
    return total_apex_cost

# ══════════════════════════════════════════════════════════════════════════════
# TIME THIEF
# ══════════════════════════════════════════════════════════════════════════════
def time_thief_summary(grid, res_d, res_b, delta, sec_mask):
    section_header("Biggest Loss Point")

    sec_delta_val = float(delta[sec_mask].iloc[-1] - delta[sec_mask].iloc[0])
    sec_slopes    = np.gradient(delta.values[sec_mask])
    thief_idx     = int(np.argmax(sec_slopes))
    thief_dist    = grid[sec_mask][thief_idx]

    d_pt = res_d[sec_mask].iloc[thief_idx]
    b_pt = res_b[sec_mask].iloc[thief_idx]

    cols = st.columns(4)
    cols[0].metric("Sector Time",  f"{sec_delta_val:+.3f}s")
    cols[1].metric("Where",        f"{thief_dist:.0f}m")
    cols[2].metric("Speed Gap",    f"{d_pt['speed'] - b_pt['speed']:.1f} km/h")
    cols[3].metric("ABS Active",   "YES" if d_pt['abs'] > 0.5 else "NO")

    if d_pt['abs'] > 0.5:
        fault_card(
            f"Biggest loss at {thief_dist:.0f}m — ABS is active and you're "
            f"{abs(d_pt['speed'] - b_pt['speed']):.1f} km/h off the benchmark right there."
        )
    elif d_pt['throttle'] < b_pt['throttle'] - 20:
        warn_card(
            f"Biggest loss at {thief_dist:.0f}m — you're at {d_pt['throttle']:.0f}% throttle "
            f"where the benchmark is at {b_pt['throttle']:.0f}%. You're hesitating."
        )

# ══════════════════════════════════════════════════════════════════════════════
# SECTOR VERDICT
# ══════════════════════════════════════════════════════════════════════════════
def sector_verdict(sec_name, sec_delta, abs_cost, throttle_cost, apex_cost):
    section_header("What To Fix")

    diagnosed_total = abs_cost + throttle_cost + apex_cost
    undiagnosed     = sec_delta - diagnosed_total

    items = [
        ("Braking — too aggressive on entry",
         abs_cost,
         "Build brake pressure progressively. Start at 60% and ramp up. Don't stab it."),
        ("Corner speed — losing rotation on entry",
         apex_cost,
         "Release the brake earlier. Let the car rotate. Trail-brake through the apex."),
        ("Throttle — lifting off on exit",
         throttle_cost,
         "30% throttle at apex, 70% when unwinding, 100% when straight. No lifting."),
    ]
    items.sort(key=lambda x: x[1], reverse=True)

    lines = [
        f"<strong>📋 {sec_name} — Total gap: {sec_delta:+.3f}s</strong><br>",
        f"We can explain {diagnosed_total:+.3f}s of that. "
        f"Residual: {undiagnosed:+.3f}s (line choice, gear selection).<br><br>",
        "<strong>Fix these in order:</strong><br>"
    ]

    for rank, (label, cost, action) in enumerate(items, 1):
        if cost > 0.005:
            icon = "🔴" if rank == 1 else ("🟡" if rank == 2 else "🔵")
            lines.append(
                f"{icon} <strong>#{rank} — {label}</strong><br>"
                f"&nbsp;&nbsp;&nbsp;Cost: {cost:+.3f}s<br>"
                f"&nbsp;&nbsp;&nbsp;Fix: {action}<br><br>"
            )

    if abs(undiagnosed) > 0.05:
        lines.append(
            f"⚪ {undiagnosed:+.3f}s still unaccounted for — "
            f"check your line in Garage 61."
        )

    verdict_card("".join(lines))

# ══════════════════════════════════════════════════════════════════════════════
# TAB 1 — SECTOR AUDIT
# ══════════════════════════════════════════════════════════════════════════════
def tab_sector_audit():
    st.header("Sector Audit")

    with st.sidebar:
        st.markdown("---")
        st.markdown("**Car & Track**")
        car_select  = st.selectbox("Car", CARS)
        custom_car  = ""
        if car_select == "Other (type below)":
            custom_car = st.text_input("Car name")
        car_name = custom_car if custom_car else car_select

        track_select = st.selectbox("Track", list(TRACKS.keys()))
        custom_track = ""
        if track_select == "Other (type below)":
            custom_track = st.text_input("Track name")
        track_config = TRACKS[track_select]
        track_length = track_config["length_m"]
        if track_select == "Other (type below)":
            track_length = st.number_input("Track length (m)", value=4000, step=100)
            track_config["length_m"] = track_length

        st.markdown("---")
        st.markdown("**Lap Files**")
        d_file = st.file_uploader("Your lap (CSV)",       type="csv", key="driver_lap")
        b_file = st.file_uploader("Benchmark lap (CSV)",  type="csv", key="bench_lap")

        st.markdown("---")
        st.markdown("**Modules**")
        run_abs      = st.checkbox("ABS Check",      value=True)
        run_throttle = st.checkbox("Throttle Check", value=True)
        run_apex     = st.checkbox("Corner Speed",   value=True)
        run_verdict  = st.checkbox("Verdict",        value=True)

    if not d_file or not b_file:
        st.info("Upload your lap file and a benchmark lap in the sidebar to get started.")
        return

    df_d = clean_df(pd.read_csv(d_file), track_length)
    df_b = clean_df(pd.read_csv(b_file), track_length)

    grid, res_d, res_b = build_grid(df_d, df_b, n=10000)
    delta       = calc_delta(grid, res_d, res_b)
    total_delta = float(delta.iloc[-1])

    st.caption(
        f"Car: **{car_name}** | "
        f"Track: **{track_select if track_select != 'Other (type below)' else custom_track}**"
    )
    st.metric("Total Lap Gap", f"{total_delta:+.3f}s",
              delta="vs benchmark", delta_color="inverse")

    sectors = track_config["sectors"]
    corners = track_config["corners"]

    if track_select == "Other (type below)":
        sectors[-1]["end"] = track_length

    for sec in sectors:
        mask_bool     = (grid >= sec['start']) & (grid <= sec['end'])
        sec_delta_val = float(delta[mask_bool].iloc[-1] - delta[mask_bool].iloc[0])
        label         = f"📌 {sec['name']}  |  {sec_delta_val:+.3f}s"

        with st.expander(label, expanded=(sec['start'] == 0)):
            time_thief_summary(grid, res_d, res_b, delta, mask_bool)

            abs_cost = throttle_cost = apex_cost = 0.0

            if run_abs:
                abs_cost      = abs_audit(grid, res_d, res_b, mask_bool, sec['name'])
            if run_throttle:
                throttle_cost = throttle_discipline(grid, res_d, res_b, mask_bool, sec['name'])
            if run_apex:
                apex_cost     = corner_min_speed(
                    grid, res_d, res_b, mask_bool, sec['name'], corners)
            if run_verdict:
                sector_verdict(sec['name'], sec_delta_val, abs_cost, throttle_cost, apex_cost)

# ══════════════════════════════════════════════════════════════════════════════
# TAB 2 — DRIVER COACH
# ══════════════════════════════════════════════════════════════════════════════
def tab_driver_coach():
    st.header("Driver Coach")
    st.caption("Upload your lap and benchmark — get a plain-English coaching brief.")

    col1, col2 = st.columns(2)
    with col1:
        car_coach = st.selectbox("Car", CARS, key="coach_car")
        if car_coach == "Other (type below)":
            car_coach = st.text_input("Car name", key="coach_car_custom")
    with col2:
        track_coach = st.selectbox("Track", list(TRACKS.keys()), key="coach_track")
        if track_coach == "Other (type below)":
            track_coach = st.text_input("Track name", key="coach_track_custom")

    d_file = st.file_uploader("Your lap (CSV)",      type="csv", key="coach_driver")
    b_file = st.file_uploader("Benchmark lap (CSV)", type="csv", key="coach_bench")

    extra_context = st.text_area(
        "Anything specific you want coaching on? (optional)",
        placeholder="e.g. I keep getting oversteer at T3 on the way out..."
    )

    if not d_file or not b_file:
        st.info("Upload both lap files above to get your coaching brief.")
        return

    if st.button("Get Coaching Brief", type="primary"):
        track_cfg    = TRACKS.get(track_coach, TRACKS["Other (type below)"])
        track_length = track_cfg["length_m"]

        df_d = clean_df(pd.read_csv(d_file), track_length)
        df_b = clean_df(pd.read_csv(b_file), track_length)

        grid, res_d, res_b = build_grid(df_d, df_b, n=10000)
        delta   = calc_delta(grid, res_d, res_b)
        sectors = track_cfg["sectors"]
        corners = track_cfg["corners"]

        summary_lines = [
            f"Car: {car_coach}",
            f"Track: {track_coach}",
            f"Total lap delta: {float(delta.iloc[-1]):+.3f}s (positive = driver is slower)",
        ]

        for sec in sectors:
            mask          = (grid >= sec['start']) & (grid <= sec['end'])
            sec_delta_val = float(delta[mask].iloc[-1] - delta[mask].iloc[0])
            abs_pct       = 100.0 * float(np.mean(res_d['abs'].values[mask] > 0.5))
            avg_spd_diff  = float(np.mean(
                res_d['speed'].values[mask] - res_b['speed'].values[mask]
            ))
            summary_lines.append(
                f"{sec['name']}: delta={sec_delta_val:+.3f}s, "
                f"ABS active {abs_pct:.1f}% of sector, "
                f"avg speed diff {avg_spd_diff:+.1f} km/h"
            )

        for corner_name, apex_dist, window in corners:
            mask_win = (grid >= apex_dist - window) & (grid <= apex_dist + window)
            if mask_win.sum() < 3:
                continue
            apex_d = float(np.min(res_d['speed'].values[mask_win]))
            apex_b = float(np.min(res_b['speed'].values[mask_win]))
            summary_lines.append(
                f"{corner_name}: apex {apex_d:.1f} km/h vs benchmark {apex_b:.1f} km/h "
                f"(diff {apex_d - apex_b:+.1f} km/h)"
            )

        telemetry_summary = "\n".join(summary_lines)

        prompt = f"""
You are a direct, no-nonsense racing driver coach.
You speak plainly — no jargon, no fluff.
You give specific, actionable feedback a club-level sim racer can actually use.

Here is the telemetry data from one session:
{telemetry_summary}
{"Driver's note: " + extra_context if extra_context else ""}

Give me:
1. The single biggest thing costing this driver time and exactly how to fix it (2-3 sentences max)
2. A ranked list of the top 3 things to work on this session, with one specific physical action for each
3. One thing the driver is actually doing well (find something positive in the data)
4. A one-line focus cue they can repeat to themselves on track

Keep it direct. No bullet-point overload. Talk to them like a coach in a garage, not a textbook.
"""

        with st.spinner("Analysing your session..."):
            _model = genai.GenerativeModel("gemini-2.0-flash")
            response = _model.generate_content(prompt)
            st.markdown("### Your Coaching Brief")
            st.markdown(response.text)

# ══════════════════════════════════════════════════════════════════════════════
# TAB 3 — SESSION ANALYSIS
# ══════════════════════════════════════════════════════════════════════════════
def tab_session_analysis():
    st.header("Session Analysis")
    st.caption("Upload your full session CSV from Garage 61 for fuel, consistency and pace analysis.")

    session_file = st.file_uploader("Session CSV (all laps)", type="csv", key="session_csv")

    if not session_file:
        st.info("Upload your session CSV to get started.")
        return

    df = pd.read_csv(session_file)
    df.columns = df.columns.str.strip()

    col_map = {}
    for col in df.columns:
        cl = col.lower().replace(' ', '').replace('_', '')
        if 'laptime' in cl or cl == 'laptime':   col_map['lap_time']   = col
        if cl == 'lap':                           col_map['lap']        = col
        if 'fuel' in cl and 'used' in cl:         col_map['fuel_used']  = col
        if 'fuel' in cl and 'level' in cl:        col_map['fuel_level'] = col
        if 'sector1' in cl or cl == 'sector1':   col_map['s1']         = col
        if 'sector2' in cl or cl == 'sector2':   col_map['s2']         = col
        if 'sector3' in cl or cl == 'sector3':   col_map['s3']         = col
        if 'tracktemp' in cl:                     col_map['track_temp'] = col
        if 'airtemp' in cl or 'airtemperature' in cl: col_map['air_temp'] = col
        if 'clean' in cl:                         col_map['clean']      = col

    has = lambda k: k in col_map

    if has('clean'):
        clean_df_s = df[df[col_map['clean']] == 1].copy()
        st.caption(f"{len(clean_df_s)} clean laps of {len(df)} total")
    else:
        clean_df_s = df.copy()

    if has('lap_time'):
        clean_df_s[col_map['lap_time']] = pd.to_numeric(
            clean_df_s[col_map['lap_time']], errors='coerce')
        clean_df_s = clean_df_s.dropna(subset=[col_map['lap_time']])

    # ── PACE & CONSISTENCY ─────────────────────────────────────────────────────
    section_header("Pace & Consistency")
    if has('lap_time') and has('lap'):
        time_col = col_map['lap_time']
        lap_col  = col_map['lap']
        best     = clean_df_s[time_col].min()
        avg      = clean_df_s[time_col].mean()
        worst    = clean_df_s[time_col].max()
        std_dev  = clean_df_s[time_col].std()

        cols = st.columns(4)
        cols[0].metric("Best Lap",    f"{best:.3f}s")
        cols[1].metric("Average",     f"{avg:.3f}s")
        cols[2].metric("Worst Lap",   f"{worst:.3f}s")
        cols[3].metric("Consistency", f"±{std_dev:.3f}s")

        if std_dev < 0.5:
            ok_card("Very consistent pace. Focus on outright speed now.")
        elif std_dev < 1.5:
            warn_card(
                f"±{std_dev:.3f}s lap-to-lap variation. "
                f"Some inconsistent laps in there — look at where the big ones are."
            )
        else:
            fault_card(
                f"±{std_dev:.3f}s variation is too high. "
                f"Sort consistency before chasing lap time."
            )

        chart_data = clean_df_s[[lap_col, time_col]].set_index(lap_col)
        st.line_chart(chart_data, use_container_width=True)

    # ── SECTOR BREAKDOWN ───────────────────────────────────────────────────────
    if has('s1') and has('s2') and has('s3'):
        section_header("Sector Breakdown")
        for s_key in ['s1', 's2', 's3']:
            clean_df_s[col_map[s_key]] = pd.to_numeric(
                clean_df_s[col_map[s_key]], errors='coerce')

        sector_stats = {}
        for s_key, s_label in [('s1','S1'), ('s2','S2'), ('s3','S3')]:
            s_data = clean_df_s[col_map[s_key]].dropna()
            if len(s_data) > 0:
                sector_stats[s_label] = {
                    'best': s_data.min(),
                    'avg':  s_data.mean(),
                    'std':  s_data.std(),
                }

        cols = st.columns(3)
        for i, (label, stats) in enumerate(sector_stats.items()):
            cols[i].metric(f"{label} Best", f"{stats['best']:.3f}s")
            cols[i].metric(f"{label} Avg",  f"{stats['avg']:.3f}s")
            cols[i].metric(f"{label} Var",  f"±{stats['std']:.3f}s")

        if sector_stats:
            weakest = max(sector_stats.items(), key=lambda x: x[1]['std'])
            warn_card(
                f"Most inconsistent sector: {weakest[0]} "
                f"(±{weakest[1]['std']:.3f}s). That's where to focus."
            )

    # ── FUEL ANALYSIS ──────────────────────────────────────────────────────────
    if has('fuel_used'):
        section_header("Fuel Analysis")
        clean_df_s[col_map['fuel_used']] = pd.to_numeric(
            clean_df_s[col_map['fuel_used']], errors='coerce')
        fuel_data = clean_df_s[col_map['fuel_used']].dropna()
        avg_fuel  = fuel_data.mean()
        max_fuel  = fuel_data.max()
        min_fuel  = fuel_data.min()

        cols = st.columns(3)
        cols[0].metric("Avg Fuel/Lap", f"{avg_fuel:.2f}L")
        cols[1].metric("Max Fuel/Lap", f"{max_fuel:.2f}L")
        cols[2].metric("Min Fuel/Lap", f"{min_fuel:.2f}L")

        for tank_size in [55, 60, 65, 70]:
            if avg_fuel > 0:
                laps_per_stint = int(tank_size / avg_fuel)
                st.write(
                    f"With a {tank_size}L tank — "
                    f"approx **{laps_per_stint} laps** per stint."
                )
                break

        if max_fuel - min_fuel > avg_fuel * 0.3:
            warn_card(
                f"Fuel usage varies {min_fuel:.2f}–{max_fuel:.2f}L per lap. "
                f"That's inconsistent throttle application across laps."
            )
        else:
            ok_card("Fuel usage is consistent lap to lap.")

    # ── TRACK CONDITION ────────────────────────────────────────────────────────
    if has('track_temp') and has('lap_time'):
        section_header("Track Condition vs Pace")
        clean_df_s[col_map['track_temp']] = pd.to_numeric(
            clean_df_s[col_map['track_temp']], errors='coerce')
        temp_lap = clean_df_s[[col_map['track_temp'], col_map['lap_time']]].dropna()
        if len(temp_lap) > 3:
            corr = float(temp_lap.corr().iloc[0, 1])
            st.write(f"Track temp vs lap time correlation: **{corr:.2f}**")
            if corr < -0.3:
                ok_card("Warmer track = faster laps. Rubber going down through the session.")
            elif corr > 0.3:
                warn_card("Warmer track = slower laps. Possible tyre overheating.")
            else:
                st.write("No strong link between track temp and your pace this session.")

    # ── AI SESSION SUMMARY ─────────────────────────────────────────────────────
    section_header("AI Session Summary")
    if st.button("Get Session Summary from AI", type="primary"):
        summary_data = []
        if has('lap_time'):
            summary_data.append(
                f"Lap times — Best: {clean_df_s[col_map['lap_time']].min():.3f}s, "
                f"Avg: {clean_df_s[col_map['lap_time']].mean():.3f}s, "
                f"Std dev: {clean_df_s[col_map['lap_time']].std():.3f}s"
            )
        if has('fuel_used'):
            summary_data.append(
                f"Fuel — Avg per lap: {clean_df_s[col_map['fuel_used']].mean():.2f}L"
            )
        if has('s1') and has('s2') and has('s3'):
            for s_key, s_label in [('s1','S1'),('s2','S2'),('s3','S3')]:
                s_data = clean_df_s[col_map[s_key]].dropna()
                if len(s_data):
                    summary_data.append(
                        f"{s_label} — Best: {s_data.min():.3f}s, "
                        f"Avg: {s_data.mean():.3f}s, "
                        f"Std: {s_data.std():.3f}s"
                    )

        prompt = f"""
You are a direct racing engineer reviewing a driver's session data.
Plain language only. No jargon. Talk like you're in the garage.

Session data:
{chr(10).join(summary_data)}
Total laps analysed: {len(clean_df_s)}

Give me:
1. One-paragraph summary of how the session went
2. The single most important thing to improve next session
3. A specific target lap time for next session based on the data

Keep it short and direct.
"""
        with st.spinner("Reading your session..."):
            _model = genai.GenerativeModel("gemini-2.0-flash")
            response = _model.generate_content(prompt)
            st.markdown(response.text)

# ══════════════════════════════════════════════════════════════════════════════
# TAB 4 — GARAGE (SCAFFOLDED)
# ══════════════════════════════════════════════════════════════════════════════
def tab_garage():
    st.header("Garage Advisor")
    st.markdown("""
    <div class="coming-soon">
        <h3>🔧 Coming Soon</h3>
        <p>Upload your setup and describe what's feeling wrong —
        the engineer tells you exactly what to adjust.</p>
        <p>HTML setup upload and manual input both supported.</p>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("---")
    st.markdown("**Preview — Manual Input (not yet active)**")
    col1, col2 = st.columns(2)
    with col1:
        st.text_input("Car",          placeholder="Porsche 992.2 GT3 Cup", disabled=True)
        st.text_input("Track",        placeholder="Zandvoort GP",          disabled=True)
        st.slider("TC Level (1–10)",  1, 10, 5,                            disabled=True)
        st.slider("ABS Setting",      1, 10, 5,                            disabled=True)
        st.number_input("Brake Bias",                                       disabled=True)
    with col2:
        st.number_input("Ride Height Front (mm)", disabled=True)
        st.number_input("Ride Height Rear (mm)",  disabled=True)
        st.number_input("Tyre Pressure FL (psi)", disabled=True)
        st.number_input("Tyre Pressure FR (psi)", disabled=True)
    st.text_area(
        "What's feeling wrong?",
        placeholder="e.g. The rear is snapping on exit of slow corners...",
        disabled=True
    )
    st.button("Ask the Engineer", disabled=True)

# ══════════════════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════════════════
def main():
    inject_css()
    st.title("🏁 Race Engineer Pro")

    tab1, tab2, tab3, tab4 = st.tabs([
        "📊 Sector Audit",
        "🎯 Driver Coach",
        "📋 Session Analysis",
        "🔧 Garage"
    ])
    with tab1: tab_sector_audit()
    with tab2: tab_driver_coach()
    with tab3: tab_session_analysis()
    with tab4: tab_garage()

if __name__ == "__main__":
    main()
