import sqlite3
import time
from pathlib import Path

import pandas as pd
import streamlit as st

# Dashboard for the HiveMQ -> SQLite motor telemetry project.
# Keep this file in the same folder as motor_data.db.

DB_PATH = Path(__file__).with_name("motor_data.db")

st.set_page_config(
    page_title="Motor Predictive Maintenance",
    page_icon="⚙️",
    layout="wide",
)

st.title("⚙️ Industrial Motor Monitoring")
st.caption("Live dashboard for motor telemetry stored from HiveMQ in SQLite")

with st.sidebar:
    st.header("Dashboard settings")
    refresh_seconds = st.slider("Refresh interval (seconds)", 2, 30, 5)
    rows_to_show = st.selectbox("Recent readings to show", [10, 25, 50, 100], index=1)
    auto_refresh = st.checkbox("Auto-refresh dashboard", value=True)
    st.caption(f"Database: {DB_PATH.name}")

def load_data():
    if not DB_PATH.exists():
        return pd.DataFrame()

    try:
        with sqlite3.connect(DB_PATH, timeout=5) as conn:
            return pd.read_sql_query(
                """
                SELECT
                    id,
                    machine_id,
                    reading_number,
                    timestamp,
                    temperature,
                    vibration_rms,
                    current,
                    status,
                    received_at
                FROM motor_data
                ORDER BY id DESC
                """,
                conn,
            )
    except (sqlite3.Error, pd.errors.DatabaseError) as exc:
        st.error(f"Could not read the SQLite database: {exc}")
        return pd.DataFrame()

df = load_data()

if not DB_PATH.exists():
    st.error(f"Database file not found: {DB_PATH}")
    st.info(
        "Copy this dashboard file into the same folder as motor_data.db, "
        "then run it again."
    )
    st.stop()

if df.empty:
    st.warning("No motor readings found yet. Start your HiveMQ publisher and SQLite subscriber.")
    st.stop()

# Convert columns safely for charting and metrics.
for column in ["temperature", "vibration_rms", "current", "reading_number"]:
    df[column] = pd.to_numeric(df[column], errors="coerce")

df["status"] = df["status"].fillna("UNKNOWN").astype(str).str.upper()
df["chart_time"] = pd.to_datetime(df["timestamp"], errors="coerce", utc=True)
df = df.sort_values("id")
latest = df.iloc[-1]

# Top-level status and metrics.
status = str(latest.get("status", "UNKNOWN"))
status_color = {
    "HEALTHY": "normal",
    "WARNING": "off",
    "CRITICAL": "inverse",
}.get(status, "off")

if status == "CRITICAL":
    st.error("Latest motor status: CRITICAL — inspect the motor and verify the sensor readings.")
elif status == "WARNING":
    st.warning("Latest motor status: WARNING — monitor the motor for worsening conditions.")
elif status == "HEALTHY":
    st.success("Latest motor status: HEALTHY")
else:
    st.info(f"Latest motor status: {status}")

machine_id = latest.get("machine_id", "Unknown")
st.caption(
    f"Machine: **{machine_id}** · "
    f"Latest reading: **{latest.get('reading_number', 'N/A')}** · "
    f"Rows stored: **{len(df)}**"
)

c1, c2, c3, c4 = st.columns(4)
temp = latest.get("temperature")
vib = latest.get("vibration_rms")
current = latest.get("current")

c1.metric("Temperature", "—" if pd.isna(temp) else f"{temp:.2f} °C")
c2.metric("Vibration RMS", "—" if pd.isna(vib) else f"{vib:.2f} mm/s")
c3.metric("Current", "—" if pd.isna(current) else f"{current:.2f} A")
c4.metric("Total readings", f"{len(df):,}")

st.subheader("Sensor trends")
chart_df = df.dropna(subset=["chart_time"]).set_index("chart_time")
if chart_df.empty:
    st.info("No valid timestamps available for plotting.")
else:
    left, right = st.columns(2)
    with left:
        st.markdown("**Temperature (°C)**")
        st.line_chart(chart_df[["temperature"]], height=260)
        st.markdown("**Vibration RMS (mm/s)**")
        st.line_chart(chart_df[["vibration_rms"]], height=260)
    with right:
        st.markdown("**Current (A)**")
        st.line_chart(chart_df[["current"]], height=260)

st.subheader("Motor status history")
status_counts = df["status"].value_counts().rename_axis("Status").reset_index(name="Readings")
st.bar_chart(status_counts.set_index("Status"), height=220)

st.subheader("Recent readings")
recent = df.sort_values("id", ascending=False).head(rows_to_show).copy()
recent = recent[
    ["id", "machine_id", "reading_number", "timestamp",
     "temperature", "vibration_rms", "current", "status"]
]
st.dataframe(recent, use_container_width=True, hide_index=True)

csv_data = df.sort_values("id", ascending=False).to_csv(index=False).encode("utf-8")
st.download_button(
    "Download all readings as CSV",
    data=csv_data,
    file_name="motor_telemetry.csv",
    mime="text/csv",
)

st.caption(
    "Note: this dashboard displays the status published by your current Python simulator. "
    "It does not independently diagnose faults or calculate remaining useful life."
)

if auto_refresh:
    time.sleep(refresh_seconds)
    st.rerun()
