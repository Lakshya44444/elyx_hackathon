# elyx_1_visual_themed_creative.py

import os, re, glob
from datetime import datetime, timedelta

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

# --------------------------
# Config & Styling
# --------------------------
st.set_page_config(page_title="Elyx Member Journey", layout="wide", initial_sidebar_state="expanded")

# Initialize session state for page management
if 'page' not in st.session_state:
    st.session_state.page = 'Summary Dashboard'

# --------------------------
# Utilities
# --------------------------
REF_PATTERN = re.compile(r"\[(\d+)\]")

def extract_refs(text: str) -> list[int]:
    if not isinstance(text, str): return []
    return [int(m.group(1)) for m in REF_PATTERN.finditer(text)]

@st.cache_data(show_spinner=False)
def parse_dt(value):
    if pd.isna(value):
        return pd.NaT
    if isinstance(value, (pd.Timestamp, datetime)):
        return pd.to_datetime(value)
    s = str(value).strip()
    m = re.match(r"^\[([^\]]+)\]", s)
    if m: s = m.group(1)
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M",
                "%d/%m/%Y %H:%M", "%d-%m-%Y %H:%M",
                "%m/%d/%y, %I:%M %p", "%m/%d/%y %I:%M %p"):
        try:
            return datetime.strptime(s, fmt)
        except Exception:
            pass
    return pd.to_datetime(s, errors="coerce")

def parse_datetime_col(series: pd.Series) -> pd.Series:
    return series.apply(parse_dt)

def _normalize_chat_df(df: pd.DataFrame, source_name: str) -> pd.DataFrame:
    col_map = {
        'time': 'timestamp', 'date': 'timestamp', 'datetime': 'timestamp',
        'text': 'message', 'msg': 'message', 'content': 'message',
        'from': 'speaker', 'author': 'speaker', 'name': 'speaker',
        'sender': 'speaker'
    }
    df = df.rename(columns={k: v for k, v in col_map.items() if k in df.columns and v not in df.columns})
    for c in ['timestamp','message','speaker']:
        if c not in df.columns:
            df[c] = np.nan
    df['timestamp'] = parse_datetime_col(df['timestamp'])
    if 'ref_id' not in df.columns:
        df['ref_id'] = df['message'].apply(lambda s: extract_refs(str(s))[0] if extract_refs(str(s)) else np.nan)
    df['source_file'] = source_name
    base = ['timestamp','speaker','message','ref_id','episode_id','event','source_file']
    keep = [c for c in base if c in df.columns] + [c for c in df.columns if c not in base]
    df = df.dropna(subset=['timestamp']).sort_values('timestamp')
    return df[keep]

def _flatten_json_maybe(df_or_list) -> pd.DataFrame:
    if isinstance(df_or_list, list):
        return pd.json_normalize(df_or_list)
    if isinstance(df_or_list, pd.DataFrame) and df_or_list.shape[1] == 1 and isinstance(df_or_list.iloc[0,0], (list, dict)):
        return pd.json_normalize(df_or_list.iloc[0,0])
    return df_or_list

# --------------------------
# Loaders
# --------------------------
@st.cache_data(show_spinner=False)
def load_conversations(folder: str) -> pd.DataFrame:
    files = sorted(glob.glob(os.path.join(folder, "*conversation*.json")))
    dfs = []
    for f in files:
        try:
            raw = pd.read_json(f, typ='frame', convert_dates=False)
            raw = _flatten_json_maybe(raw)
            df = _normalize_chat_df(raw, source_name=os.path.basename(f))
            dfs.append(df)
        except Exception as e:
            print(f"[WARN] Could not parse {f}: {e}")
    if dfs:
        return pd.concat(dfs, ignore_index=True).sort_values("timestamp")
    return pd.DataFrame(columns=["timestamp","speaker","message","ref_id","source_file"])

@st.cache_data(show_spinner=False)
def load_decisions(folder: str) -> pd.DataFrame:
    files = sorted(glob.glob(os.path.join(folder, "*decisions*.json"))) + \
            sorted(glob.glob(os.path.join(folder, "*_decisions*.json")))
    dfs = []
    for f in files:
        try:
            raw = pd.read_json(f, typ='frame', convert_dates=False)
            raw = _flatten_json_maybe(raw)
            df = raw.copy()
            if 'date' in df.columns:
                df['date'] = parse_datetime_col(df['date']).dt.date
            else:
                if 'timestamp' in df.columns:
                    df['date'] = parse_datetime_col(df['timestamp']).dt.date
            for col in ['decision','category','owner','episode_id','reason_refs','notes','status']:
                if col not in df.columns:
                    df[col] = np.nan
            df['source_file'] = os.path.basename(f)
            dfs.append(df[['date','decision','category','owner','episode_id','reason_refs','notes','status','source_file']])
        except Exception as e:
            print(f"[WARN] Could not parse {f}: {e}")
    if dfs:
        return pd.concat(dfs, ignore_index=True).sort_values(["date","owner","decision"])
    return pd.DataFrame(columns=['date','decision','category','owner','episode_id','reason_refs','notes','status','source_file'])

@st.cache_data(show_spinner=False)
def load_hours(folder: str) -> pd.DataFrame:
    files = sorted(glob.glob(os.path.join(folder, "*hours*.csv")))
    dfs = []
    for f in files:
        try:
            df = pd.read_csv(f)
            if 'date' in df.columns:
                df['date'] = parse_datetime_col(df['date']).dt.date
            else:
                if 'timestamp' in df.columns:
                    df['date'] = parse_datetime_col(df['timestamp']).dt.date
            for c in ['role','hours','type']:
                if c not in df.columns: df[c] = np.nan
            df['source_file'] = os.path.basename(f)
            dfs.append(df[['date','role','hours','type','source_file']])
        except Exception as e:
            print(f"[WARN] Could not parse {f}: {e}")
    if dfs:
        return pd.concat(dfs, ignore_index=True)
    return pd.DataFrame(columns=['date','role','hours','type','source_file'])

@st.cache_data(show_spinner=False)
def load_sample_journey():
    data = {
        'Episode': [1, 2, 3, 4, 5, 6],
        'Title': [
            "Initial Health Inquiry & Onboarding",
            "Clarification, Data Gathering & Initial Workout Plan",
            "Member Dissatisfaction & Service Feedback",
            "Health Optimization Plan & Continued Feedback",
            "Medical Coordination & Device Management",
            "Disagreement on Medical Advice & AI Capabilities"
        ],
        'Start Date': [
            datetime(2025, 4, 25),
            datetime(2025, 5, 3),
            datetime(2025, 5, 13),
            datetime(2025, 5, 15),
            datetime(2025, 5, 21),
            datetime(2025, 6, 19)
        ],
        'End Date': [
            datetime(2025, 4, 28),
            datetime(2025, 5, 12),
            datetime(2025, 5, 14),
            datetime(2025, 5, 24),
            datetime(2025, 6, 6),
            datetime(2025, 6, 23)
        ],
        'Trigger': [
            "Member expresses concern about high intensity minutes on his Garmin watch.",
            "Follow-up on high-intensity minutes and initiation of data gathering and workout planning.",
            "Member expresses significant dissatisfaction with the perceived lack of progress.",
            "Elyx provides a 'Health Optimization Plan,' and the member continues to provide critical feedback.",
            "A mix of medical coordination and managing the member’s wearable devices.",
            "A significant disagreement arises between the advice of an Elyx doctor and the member’s primary care physician."
        ],
        'Friction Points': [
            "None.",
            "Communication: Member has to ask who is messaging him. Data Access: Elyx needs to request access to medical records. Workout Plan Accessibility: The member found the plan difficult to access due to a password requirement.",
            "Perceived Inaction: The member feels that Elyx has not made any tangible impact. Lack of Proactivity: The member points out that Elyx should be able to track his activity levels. Communication Channel Confusion: A debate ensues about what constitutes 'founder comments' versus 'customer comments'.",
            "Plan Quality: The member feels the plan is not comprehensive, lacks prioritization, and doesn't explain the 'why'. Scheduling: A workout is scheduled without consulting the member's preferences. Lack of Context: The member complains that workout invitations lack context.",
            "Medical Records: Difficulty in obtaining records. Device Issues: The member wants to switch from an Oura ring to a Whoop band. Logistics: A new Whoop band is ordered, but there are concerns about it arriving before the member travels.",
            "Conflicting Medical Opinions: The member’s primary doctor strongly disagrees with the prescription of Cozaar. AI Limitations: The member requests an AI-generated report to justify the prescription, but the Elyx team has to manage his expectations. Report Quality: The AI-generated reports lack citations and are not easily understandable."
        ],
        'Before State': [
            "Proactive and data-driven about his health, but feeling that his current health management is 'very random and uncoordinated.'",
            "Engaged with the Elyx service, has shared initial health data and concerns, and is awaiting the proposed lifestyle consultation.",
            "Becoming more actively involved in the process, but also starting to experience some friction with the service's execution (communication, accessibility).",
            "Frustrated and questioning the value of the service. He is now taking on a more directive role, providing feedback on how the service should operate.",
            "Still feeling that the service is not meeting his expectations for proactivity and personalization. He is becoming more granular in his feedback, pointing out specific instances of poor execution.",
            "The member is now more of a 'co-manager' of his health journey, actively involved in decisions about his medical care and the tools used to monitor his health."
        ],
        'After State': [
            "Engaged with the Elyx service, has shared initial health data and concerns, and is awaiting the proposed lifestyle consultation.",
            "Becoming more actively involved in the process, but also starting to experience some friction with the service's execution (communication, accessibility).",
            "Frustrated and questioning the value of the service. He is now taking on a more directive role, providing feedback on how the service should operate.",
            "Still feeling that the service is not meeting his expectations for proactivity and personalization. He is becoming more granular in his feedback, pointing out specific instances of poor execution.",
            "The member is now more of a 'co-manager' of his health journey, actively involved in decisions about his medical care and the tools used to monitor his health.",
            "The member is now more skeptical of the service's recommendations and is pushing for more evidence-based justifications. He is also providing direct feedback on the development of the company's technology."
        ]
    }
    df = pd.DataFrame(data)
    df['Duration'] = (df['End Date'] - df['Start Date']).dt.days
    return df

# --------------------------
# Analytics helpers
# --------------------------
def kpi_response_times(chat_df: pd.DataFrame) -> dict:
    if chat_df.empty: return {"median_minutes": np.nan, "avg_minutes": np.nan, "count": 0}
    df = chat_df[['timestamp','speaker']].copy()
    df['is_member'] = df['speaker'].str.lower().str.contains("member|client|patient").fillna(False)
    times = []
    df_sorted = chat_df.sort_values('timestamp')
    for i, row in df_sorted.iterrows():
        if isinstance(row['speaker'], str) and re.search(r"(member|client|patient)", row['speaker'], re.I):
            subsequent = df_sorted[df_sorted['timestamp'] > row['timestamp']]
            reply = subsequent[~subsequent['speaker'].str.lower().str.contains("member|client|patient", na=False)].head(1)
            if not reply.empty:
                delta = (reply.iloc[0]['timestamp'] - row['timestamp']).total_seconds()/60.0
                if delta >= 0:
                    times.append(delta)
    if not times:
        return {"median_minutes": np.nan, "avg_minutes": np.nan, "count": 0}
    return {
        "median_minutes": float(np.median(times)),
        "avg_minutes": float(np.mean(times)),
        "count": len(times)
    }

def derive_daily_summary(chat_subset: pd.DataFrame) -> str:
    if chat_subset.empty:
        return "No activity."
    speakers = chat_subset['speaker'].fillna("Unknown").value_counts().to_dict()
    refs = chat_subset['message'].astype(str).apply(extract_refs).explode().dropna().astype(int)
    bullets = []
    bullets.append(f"Messages: {chat_subset.shape[0]} | Speakers: {len(speakers)}")
    major = ", ".join([f"{k} ({v})" for k,v in list(speakers.items())[:5]])
    bullets.append(f"Top speakers: {major}")
    if refs.size:
        bullets.append(f"Reference tags seen: {', '.join(map(str, sorted(refs.unique())[:12]))}")
    joined_msgs = " ".join(chat_subset['message'].astype(str).str.lower().tolist())
    if any(k in joined_msgs for k in ["med", "mounjaro", "cozaar", "rx", "dose", "prescrib"]):
        bullets.append("Medication discussion detected.")
    if any(k in joined_msgs for k in ["workout", "train", "gym", "physio", "mobility"]):
        bullets.append("Training/physio discussion detected.")
    if any(k in joined_msgs for k in ["diet", "nutrition", "calorie", "protein", "supplement", "cg m", "cgm"]):
        bullets.append("Nutrition/supplement discussion detected.")
    if any(k in joined_msgs for k in ["sleep", "hrv", "oura", "whoop"]):
        bullets.append("Sleep/wearables discussion detected.")
    return " • ".join(bullets)

def derive_monthly_summary(chat_df: pd.DataFrame, decisions_df: pd.DataFrame) -> pd.DataFrame:
    chat_monthly = chat_df.groupby(pd.Grouper(key='timestamp', freq='M')).size().reset_index(name='messages')
    chat_monthly['month'] = chat_monthly['timestamp'].dt.to_period('M')

    decisions_df['date'] = pd.to_datetime(decisions_df['date'])
    decisions_monthly = decisions_df.groupby(pd.Grouper(key='date', freq='M')).size().reset_index(name='decisions')
    decisions_monthly['month'] = decisions_monthly['date'].dt.to_period('M')

    df = pd.merge(chat_monthly[['month', 'messages']], decisions_monthly[['month', 'decisions']], on='month', how='outer')
    df['month'] = df['month'].astype(str)
    df = df[['month', 'messages', 'decisions']]
    return df.sort_values('month').fillna(0)

def derive_weekly_discussions_summary(chat_df: pd.DataFrame, decisions_df: pd.DataFrame) -> pd.DataFrame:
    if decisions_df.empty:
        return pd.DataFrame(columns=['Week', 'Decisions Made', 'Key Discussion Points'])

    decisions_df['date'] = pd.to_datetime(decisions_df['date'])
    decisions_df['reason_refs'] = decisions_df['reason_refs'].apply(lambda x: extract_refs(str(x)))
    dec_expanded = decisions_df.explode('reason_refs')

    dec_chats = pd.merge(dec_expanded, chat_df, left_on='reason_refs', right_on='ref_id', how='left')

    weekly_summary = dec_chats.groupby(pd.Grouper(key='date', freq='W-MON')).apply(
        lambda week_group: pd.Series({
            'Decisions Made': ", ".join(week_group['decision'].dropna().unique()),
            'Key Discussion Points': " • ".join(week_group['message'].dropna().apply(lambda x: x[:200] + '...' if len(x)>200 else x).unique())
        })
    ).reset_index()

    weekly_summary['Week'] = weekly_summary['date'].dt.strftime('%Y Week %W')
    return weekly_summary[['Week', 'Decisions Made', 'Key Discussion Points']]

PERSONAS = {
    "Ruby": "Concierge – empathetic, organized, proactive (scheduling, reminders, logistics).",
    "Dr. Warren": "Medical Strategist – clinical authority; interprets labs, sets medical direction.",
    "Advik": "Performance Scientist – wearable data (Whoop/Oura), sleep/HRV/stress insights.",
    "Carla": "Nutritionist – designs nutrition & supplements, explains 'why', coordinates with chef.",
    "Rachel": "Physiotherapist – strength, mobility, rehab, programming.",
    "Neel": "Concierge Lead – strategic reviews, de-escalation, long-term vision and value.",
}

# --------------------------
# DATA LOAD
# --------------------------
HERE = os.path.dirname(os.path.abspath(__file__))
chats = load_conversations(HERE)
decisions = load_decisions(HERE)
hours = load_hours(HERE)
journey_episodes = load_sample_journey()

if chats.empty:
    st.error("⚠️ No conversation JSON found. Place files like 'week03_conversation.json' next to elyx_1.py.")
    st.stop()

# --------------------------
# SIDEBAR FILTERS AND THEME TOGGLE
# --------------------------
with st.sidebar:
    st.header("Filters 📊")
    mind = chats['timestamp'].min().date()
    maxd = chats['timestamp'].max().date()
    date_rng = st.date_input("🗓️ Date range", (mind, maxd))
    speaker_opts = sorted(chats['speaker'].dropna().unique().tolist())
    pick_speakers = st.multiselect("🗣️ Speakers", options=speaker_opts, default=speaker_opts)
    kw = st.text_input("🔍 Search keyword in chats", "")
    st.markdown("---")
    theme = st.radio("Select Theme", ("Dark", "Light"))
    st.markdown("---")
    page = st.radio("Navigation", ("Summary Dashboard", "Detailed Journey", "Internal Metrics & Personas"))

# Set page in session state
st.session_state.page = page

# Apply theme-specific colors and CSS
if theme == "Dark":
    bg_color = "#0f172a"
    text_color = "#e2e8f0"
    container_bg = "#1e293b"
    container_border = "#334155"
    primary_color = "#38bdf8"
    secondary_color = "#aed581"
    grid_color = "#334155"
    link_color = "#93c5fd"
    header_bg_color = "linear-gradient(to right, #1e293b, #15223a)"
    header_text_color = "#e2e8f0"
else: # Light theme
    bg_color = "#f8fafc"
    text_color = "#1e293b"
    container_bg = "#ffffff"
    container_border = "#e2e8f0"
    primary_color = "#3883f8"
    secondary_color = "#6c9ef8"
    grid_color = "#e2e8f0"
    link_color = "#1d4ed8"
    header_bg_color = "linear-gradient(to right, #ffffff, #f1f5f9)"
    header_text_color = "#1e293b"

# Apply CSS based on theme
st.markdown(
    f"""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap');
    
    html, body, [data-testid="stAppViewContainer"] {{
        font-family: 'Inter', sans-serif;
        background-color: {bg_color};
        color: {text_color};
        background: {bg_color};
        background-attachment: fixed;
    }}
    .st-emotion-cache-z5f87b {{
        padding-top: 0rem;
    }}
    .header-bar {{
        position: fixed;
        top: 0;
        left: 0;
        right: 0;
        height: 60px;
        background: {header_bg_color};
        color: {header_text_color};
        display: flex;
        align-items: center;
        justify-content: space-between;
        padding: 0 2rem;
        box-shadow: 0 2px 10px rgba(0, 0, 0, 0.1);
        z-index: 999;
    }}
    .header-bar h1 {{
        margin: 0;
        font-size: 1.5rem;
        font-weight: 700;
        color: {primary_color};
    }}
    .header-bar nav a {{
        color: {header_text_color};
        text-decoration: none;
        margin-left: 1.5rem;
        font-weight: 600;
        transition: color 0.2s ease;
    }}
    .header-bar nav a:hover {{
        color: {primary_color};
    }}
    .content-padding {{
        padding-top: 80px;
    }}
    .main-header {{
        font-size: 2.5rem;
        font-weight: 700;
        color: {primary_color};
        margin-bottom: 0.5rem;
    }}
    .kpi-container {{
        padding: 1.2rem;
        border-radius: 12px;
        background-color: {container_bg};
        box-shadow: 0 4px 10px rgba(0, 0, 0, 0.2);
        margin-bottom: 1.5rem;
        display: flex;
        align-items: center;
        gap: 1rem;
        border: 1px solid {container_border};
        opacity: 0;
        animation: fadeIn 0.5s ease-in-out forwards;
    }}
    @keyframes fadeIn {{
        from {{ opacity: 0; transform: translateY(10px); }}
        to {{ opacity: 1; transform: translateY(0); }}
    }}
    .kpi-container:hover {{
        transform: translateY(-5px);
        box-shadow: 0 8px 20px rgba(0,0,0,0.3);
        transition: transform 0.3s ease, box-shadow 0.3s ease;
    }}
    .kpi-value, .kpi-label {{
        color: {text_color};
    }}
    .kpi-label {{
        color: {text_color};
    }}
    .pill {{
        display:inline-block; padding:4px 12px; border-radius:999px;
        background-color:{primary_color}; color:{bg_color}; font-weight:600;
        margin-right:8px; font-size:0.8rem;
    }}
    .section-header {{
        color: {primary_color};
        font-weight: 600;
        font-size: 1.8rem;
        margin-top: 2.5rem;
        margin-bottom: 1rem;
    }}
    .stDataFrame {{
        background-color: {container_bg} !important;
        border: 1px solid {container_border} !important;
        color: {text_color} !important;
        border-radius: 8px;
    }}
    .stDataFrame table thead th {{
        background-color: {container_border} !important;
        color: {text_color} !important;
    }}
    div[data-testid="stTextInput"] > div > div > input,
    div[data-testid="stDateInput"] > div > div > div > input {{
        background-color: {container_bg} !important;
        color: {text_color} !important;
        border: 1px solid {container_border} !important;
    }}
    div[data-testid="stSelectbox"] > div[role="listbox"] {{
        background-color: {container_bg} !important;
        border: 1px solid {container_border} !important;
        color: {text_color} !important;
    }}
    a {{
        color: {link_color} !important;
    }}
    .st-emotion-cache-1dp5x4q {{
        color: {text_color} !important;
    }}
    .st-emotion-cache-1nm7p14 {{
        background-color: {container_bg} !important;
    }}
    .st-emotion-cache-1v04x99 {{
        color: {text_color};
    }}
    .st-emotion-cache-1a6x46i {{
        background-color: {container_bg};
        border: 1px solid {container_border};
        border-radius: 8px;
    }}
    .st-emotion-cache-1r650w {{
        background-color: {container_bg} !important;
        border: 1px solid {container_border} !important;
        border-radius: 8px;
    }}
    .st-emotion-cache-14nj81w {{
        background: {header_bg_color};
        border-radius: 12px;
        border: 1px solid {container_border};
        box-shadow: 0 4px 10px rgba(0, 0, 0, 0.2);
    }}
    </style>
    """,
    unsafe_allow_html=True
)

# Apply filters
mask = (chats['timestamp'].dt.date >= date_rng[0]) & (chats['timestamp'].dt.date <= date_rng[1])
if pick_speakers:
    mask &= chats['speaker'].isin(pick_speakers)
if kw.strip():
    mask &= chats['message'].astype(str).str.contains(re.escape(kw.strip()), case=False, na=False)

chats_f = chats.loc[mask].sort_values('timestamp')

# --------------------------
# MAIN PAGE LAYOUT
# --------------------------

# Display the custom header bar
st.markdown(f"""
<div class="header-bar">
    <h1>Elyx</h1>
    <nav>
        <a href="#kpis-section">KPIs</a>
        <a href="#journey-map-section">Journey Map</a>
        <a href="#weekly-summary-section">Weekly Summary</a>
        <a href="#daily-snapshot-section">Daily Snapshot</a>
        <a href="#decision-traceability-section">Decisions</a>
        <a href="#internal-metrics-section">Metrics</a>
        <a href="#persona-dashboard-section">Personas</a>
        <a href="#chat-browser-section">Browser</a>
    </nav>
</div>
<div class="content-padding"></div>
""", unsafe_allow_html=True)


st.markdown("<h1 class='main-header'>Elyx Member Journey & Decision Traceability</h1>", unsafe_allow_html=True)
st.caption("A dashboard to explore a member's journey, decisions, and internal effort. Now with a sample journey map.")

if st.session_state.page == 'Summary Dashboard':
    # KPIs
    st.markdown("<h2 id='kpis-section' class='section-header'>Key Performance Indicators</h2>", unsafe_allow_html=True)
    colA, colB, colC, colD = st.columns(4)
    with colA:
        with st.container(border=True):
            st.markdown(f"<p class='kpi-label'>💬 Messages</p><p class='kpi-value'>{int(chats_f.shape[0])}</p>", unsafe_allow_html=True)
    with colB:
        with st.container(border=True):
            st.markdown(f"<p class='kpi-label'>🗣️ Unique Speakers</p><p class='kpi-value'>{int(chats_f['speaker'].nunique())}</p>", unsafe_allow_html=True)
    with colC:
        rt = kpi_response_times(chats_f)
        with st.container(border=True):
            st.markdown(f"<p class='kpi-label'>⏱️ Median Response Time</p><p class='kpi-value'>{f'{rt['median_minutes']:.0f} min' if rt['count'] else '—'}</p>", unsafe_allow_html=True)
    with colD:
        with st.container(border=True):
            st.markdown(f"<p class='kpi-label'>✅ Decisions in Range</p><p class='kpi-value'>{int(decisions[decisions['date'].between(date_rng[0], date_rng[1])].shape[0]) if not decisions.empty else 0}</p>", unsafe_allow_html=True)

    # ---
    # MEMBER JOURNEY MAP
    # ---
    st.markdown("<h2 id='journey-map-section' class='section-header'>Member Journey Map</h2>", unsafe_allow_html=True)
    st.caption("This visualization shows the member's journey as a series of episodes, with color-coded sentiment and duration.")
    st.dataframe(journey_episodes)
    # Create a Gantt-like chart for the journey
    fig_journey = go.Figure()
    for idx, row in journey_episodes.iterrows():
        color = "rgba(56, 189, 248, 0.7)" # Blue
        if "Dissatisfaction" in row["Title"]:
            color = "rgba(248, 113, 113, 0.7)" # Red
        elif "Disagreement" in row["Title"]:
            color = "rgba(251, 191, 36, 0.7)" # Yellow
        
        fig_journey.add_trace(go.Bar(
            x=[row['Duration']],
            y=[row['Title']],
            name=f"Episode {row['Episode']}",
            orientation='h',
            marker_color=color,
            hovertemplate=f"<b>Episode {row['Episode']}: {row['Title']}</b><br>Start: {row['Start Date'].strftime('%Y-%m-%d')}<br>End: {row['End Date'].strftime('%Y-%m-%d')}<br>Duration: {row['Duration']} days<br>Trigger: {row['Trigger']}<br>Friction: {row['Friction Points']}<extra></extra>"
        ))
        
    fig_journey.update_layout(
        barmode='stack',
        title="Member Journey Episodes",
        plot_bgcolor='rgba(0,0,0,0)',
        paper_bgcolor='rgba(0,0,0,0)',
        font_color=text_color,
        showlegend=False,
        xaxis_title="Duration in Days",
        yaxis_title="Episode"
    )
    fig_journey.update_xaxes(gridcolor=grid_color)
    fig_journey.update_yaxes(gridcolor=grid_color)
    st.plotly_chart(fig_journey, use_container_width=True)

    # Detailed Episode Breakdown
    st.markdown("### Detailed Episode Breakdown")
    ep_titles = {row['Episode']: f"Episode {row['Episode']}: {row['Title']}" for _, row in journey_episodes.iterrows()}
    selected_episode = st.selectbox("Select an Episode for Details", options=list(ep_titles.keys()), format_func=lambda x: ep_titles[x])
    ep_data = journey_episodes[journey_episodes['Episode'] == selected_episode].iloc[0]
    with st.container(border=True):
        st.markdown(f"**Trigger:** {ep_data['Trigger']}")
        st.markdown(f"**Friction Points:** {ep_data['Friction Points']}")
        st.markdown(f"**Before State:** {ep_data['Before State']}")
        st.markdown(f"**After State:** {ep_data['After State']}")

    # ---
    # TIMELINE (message volume per day + optional hours overlay)
    # ---
    st.markdown("<h2 class='section-header'>Activity Timeline</h2>", unsafe_allow_html=True)
    msg_daily = chats_f.groupby(chats_f['timestamp'].dt.date).size().reset_index(name='messages')
    fig1 = px.bar(msg_daily, x='timestamp', y='messages', color_discrete_sequence=[primary_color])
    fig1.update_layout(
        margin=dict(l=0,r=0,t=0,b=0),
        xaxis_title="Date",
        yaxis_title="Messages",
        plot_bgcolor='rgba(0,0,0,0)',
        paper_bgcolor='rgba(0,0,0,0)',
        font_color=text_color
    )
    fig1.update_xaxes(showgrid=False)
    fig1.update_yaxes(gridcolor=grid_color)
    st.plotly_chart(fig1, use_container_width=True)

elif st.session_state.page == 'Detailed Journey':
    # ---
    # WEEKLY SUMMARY
    # ---
    st.markdown("<h2 class='section-header'>Weekly Decisions & Discussions Summary</h2>", unsafe_allow_html=True)
    weekly_summary_table = derive_weekly_discussions_summary(chats, decisions)
    if not weekly_summary_table.empty:
        st.caption("This table links key decisions to the chat conversations that informed them, providing a weekly overview of important discussions.")
        st.dataframe(weekly_summary_table, use_container_width=True, height=300)
    else:
        st.caption("No decisions found to summarize weekly discussions.")
    
    # ---
    # DAILY SNAPSHOT
    # ---
    st.markdown("<h2 class='section-header'>Daily Situation Snapshot</h2>", unsafe_allow_html=True)

    all_days = chats['timestamp'].dt.date.unique()
    default_day = all_days[-1] if all_days.size else datetime.now().date()
    pick_day = st.date_input("🗓️ Pick a day", default_day)

    day_mask = chats['timestamp'].dt.date == pick_day
    day_chats = chats.loc[day_mask].sort_values("timestamp")

    left, right = st.columns([1.8, 1])
    with left:
        with st.container(border=True):
            st.subheader(f"💬 Chats on {pick_day}")
            st.dataframe(day_chats[['timestamp','speaker','ref_id','message','source_file']], use_container_width=True, height=340)
            st.download_button(
                "Download chats for this day (CSV)",
                data=day_chats.to_csv(index=False).encode("utf-8"),
                file_name=f"chats_{pick_day}.csv",
                mime="text/csv",
            )

    with right:
        with st.container(border=True):
            st.subheader("💡 Auto-summary")
            st.markdown(f"<div class='tight'><p>{derive_daily_summary(day_chats)}</p></div>", unsafe_allow_html=True)
        st.markdown("---")
        if not decisions.empty:
            day_decs = decisions[decisions['date'] == pick_day]
            with st.container(border=True):
                st.subheader("✅ Decisions on this day")
                if day_decs.empty:
                    st.caption("No decisions recorded.")
                else:
                    st.dataframe(day_decs[['date','decision','category','owner','status','source_file']], use_container_width=True, height=180)
        st.markdown("---")
        if not hours.empty:
            day_hours = hours[hours['date'] == pick_day]
            with st.container(border=True):
                st.subheader("⏱️ Internal hours on this day")
                if day_hours.empty:
                    st.caption("No hours recorded.")
                else:
                    st.dataframe(day_hours[['date','role','hours','type','source_file']], use_container_width=True, height=180)

    # ---
    # DECISION TRACEABILITY
    # ---
    st.markdown("<h2 class='section-header'>Decisions & Why They Were Made</h2>", unsafe_allow_html=True)
    if decisions.empty:
        st.caption("Upload or place decisions JSON files (e.g., week05_decisions.json) to enable this section.")
    else:
        with st.container(border=True):
            decisions_in_range = decisions[decisions['date'].between(date_rng[0], date_rng[1])] if isinstance(date_rng, tuple) else decisions
            if decisions_in_range.empty:
                st.caption("No decisions in the selected range.")
            else:
                dec_labels = decisions_in_range.apply(
                    lambda r: f"{r['date']} — {r['decision']} ({r['category']}) by {r['owner']}", axis=1).tolist()
                picked = st.selectbox("Pick a decision to view context", options=dec_labels, index=0)
                picked_row = decisions_in_range.iloc[dec_labels.index(picked)]
                st.markdown(
                    f"""
                    <p><b>Decision:</b> {picked_row['decision']}</p>
                    <p><b>Date:</b> {picked_row['date']}</p>
                    <p><b>Category:</b> {picked_row['category']} • <b>Owner:</b> {picked_row['owner']}</p>
                    <p><b>Status:</b> {picked_row.get('status','')}</p>
                    <p><b>Notes:</b> {picked_row.get('notes','')}</p>
                    """, unsafe_allow_html=True)
                refs = extract_refs(str(picked_row.get('reason_refs', '')))
                if refs:
                    ctx = chats[chats['ref_id'].isin(refs)].sort_values('timestamp')
                    if not ctx.empty:
                        st.write("**Reasoning context (from chats referenced in decision):**")
                        st.dataframe(ctx[['timestamp','speaker','ref_id','message','source_file']], use_container_width=True, height=220)
                    else:
                        st.caption("No chat messages matched the referenced IDs. Check the [ref] numbers.")
                else:
                    st.caption("No [ref] numbers provided for this decision. Add them in the `reason_refs` field in decisions JSON.")

elif st.session_state.page == 'Internal Metrics & Personas':
    # ---
    # INTERNAL EFFORT & METRICS
    # ---
    st.markdown("<h2 class='section-header'>Internal Effort & Metrics</h2>", unsafe_allow_html=True)

    if hours.empty:
        st.caption("Place an hours CSV (e.g., hours.csv or week06_hours.csv with columns date,role,hours,type).")
    else:
        hrs_rng = hours[hours['date'].between(date_rng[0], date_rng[1])] if isinstance(date_rng, tuple) else hours
        if hrs_rng.empty:
            st.caption("No hours recorded for the selected range.")
        else:
            col1, col2 = st.columns(2)
            with col1:
                figh = px.bar(hrs_rng, x="date", y="hours", color="role", barmode="group", title="Hours per day by role",
                              color_discrete_sequence=px.colors.qualitative.Pastel)
                figh.update_layout(
                    margin=dict(l=0,r=0,t=30,b=0),
                    plot_bgcolor='rgba(0,0,0,0)',
                    paper_bgcolor='rgba(0,0,0,0)',
                    font_color=text_color
                )
                figh.update_xaxes(showgrid=False)
                figh.update_yaxes(gridcolor=grid_color)
                st.plotly_chart(figh, use_container_width=True)
            with col2:
                with st.container(border=True):
                    st.subheader("Total hours by role")
                    by_role = hrs_rng.groupby("role", as_index=False)['hours'].sum().sort_values('hours', ascending=False)
                    st.dataframe(by_role, use_container_width=True, height=260)

    # ---
    # PERSONA DASHBOARD
    # ---
    st.markdown("<h2 class='section-header'>Personas & Participation</h2>", unsafe_allow_html=True)
    speakers_seen = chats['speaker'].dropna()
    by_speaker = speakers_seen.value_counts().reset_index()
    by_speaker.columns = ['speaker','messages']
    colP1, colP2 = st.columns([1.2, 1])
    with colP1:
        figp = px.bar(by_speaker, x='speaker', y='messages', color_discrete_sequence=px.colors.qualitative.Pastel)
        figp.update_layout(
            xaxis={'categoryorder':'total descending'},
            title="Messages by speaker",
            margin=dict(l=0,r=0,t=30,b=0),
            plot_bgcolor='rgba(0,0,0,0)',
            paper_bgcolor='rgba(0,0,0,0)',
            font_color=text_color
        )
        figp.update_xaxes(showgrid=False)
        figp.update_yaxes(gridcolor=grid_color)
        st.plotly_chart(figp, use_container_width=True)
    with colP2:
        st.write("### Persona Notes")
        for name, desc in PERSONAS.items():
            if name in speakers_seen.values:
                st.markdown(f"<div class='pill'>{name}</div> {desc}", unsafe_allow_html=True)

# ---
# CHAT BROWSER & EXPORT
# ---
st.markdown("<h2 class='section-header'>Chat Browser & Exports</h2>", unsafe_allow_html=True)
view_cols = [c for c in ['timestamp','speaker','ref_id','episode_id','event','message','source_file'] if c in chats_f.columns]
st.dataframe(chats_f[view_cols], use_container_width=True)

colD1, colD2 = st.columns(2)
with colD1:
    st.download_button(
        "Download filtered chats (CSV)",
        data=chats_f.to_csv(index=False).encode("utf-8"),
        file_name="filtered_chats.csv",
        mime="text/csv",
    )
with colD2:
    if not decisions.empty:
        st.download_button(
            "Download filtered decisions (CSV)",
            data=decisions[decisions['date'].between(date_rng[0], date_rng[1])].to_csv(index=False).encode("utf-8"),
            file_name="filtered_decisions.csv",
            mime="text/csv",
        )

st.caption("💡 Tip: decisions JSON fields = `date`, `decision`, `category`, `owner`, `episode_id` (optional), `reason_refs` (e.g. \"[10][13]\"), `notes`, `status`.")
