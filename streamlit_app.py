import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from scipy.stats import ks_2samp

st.set_page_config(layout="wide", page_title="Architectural Case Finder")

# 1. LOAD DATA
@st.cache_data
def load_data():
    # Make sure this matches your uploaded file name on GitHub
    df = pd.read_csv('Category_02F.csv') 
    return df

df_raw = load_data().copy()

# --- CONSTANTS ---
col_id = 'Cases_ID'
col_heat = 'Winter_Average_Radation_kWh/m2'
col_over = 'Summer_Average_Radation_kWh/m2'
col_sDA = 'sDA'
col_ASE = 'ASE'
col_pv = 'PercArea_PV_Potential'
col_active = 'PercArea_Active_Solar_Potential'
# Design Params for 3D
params_3d = ['Vertical_Steps_Section', 'Horizontal_Steps_Plan', 'Balcony_Steps']

# --- SIDEBAR: DESIGN CHOICES ---
st.sidebar.header("🛠️ Design Filters")
def apply_filter(df, col, label):
    choice = st.sidebar.selectbox(f"{label}", ["Available", "Mandatory", "Ignored"])
    if choice == "Mandatory": return df[df[col] > 0]
    if choice == "Ignored": return df[df[col] == 0]
    return df

df_filtered = df_raw.copy()
df_filtered = apply_filter(df_filtered, 'Vertical_Louvre_Steps', "Louvers")
df_filtered = apply_filter(df_filtered, 'Balcony_Steps', "Balcony")
df_filtered = apply_filter(df_filtered, 'PV_Canopy_Steps', "Canopy")
df_filtered = apply_filter(df_filtered, 'Vertical_Steps_Section', "Vertical Steps")
df_filtered = apply_filter(df_filtered, 'Horizontal_Steps_Plan', "Horizontal Steps")

# --- MAIN: PRIORITY VISUALIZER ---
st.title("🏛️ Performance Case Finder")

st.subheader("⚖️ Priority Balance")
energy_val = st.select_slider(
    "Drag to balance Energy vs Daylight",
    options=list(range(0, 101)),
    value=50
)
daylight_val = 100 - energy_val

# Visual Feedback for the user
c1, c2 = st.columns(2)
c1.metric("⚡ Energy Importance", f"{energy_val}%")
c2.metric("☀️ Daylight Importance", f"{daylight_val}%")

renew_choice = st.segmented_control("Renewable Energy Strategy:", ["Ignored", "Mandatory"], default="Ignored")

if st.button("🚀 Find Top 10 Best Cases", use_container_width=True):
    df = df_filtered.copy()
    
    # CALCULATIONS
    # Renewables
    df['Total_Surface'] = df[col_pv] + df[col_active]
    norm_Active = (df['Total_Surface'] - df['Total_Surface'].min()) / (df['Total_Surface'].max() - df['Total_Surface'].min())
    imbalance_mask = (df[col_pv] < 10.0) | (df[col_active] < 10.0)
    norm_Active[imbalance_mask] *= 0.5
    norm_Surf_inv = 1 - (df['Surface_Area'] - df['Surface_Area'].min()) / (df['Surface_Area'].max() - df['Surface_Area'].min())
    df['Score_Renewables'] = ((norm_Active * 0.5) + (norm_Surf_inv * 0.5)).clip(0, 1)

    # Thermal
    n_heat = (df[col_heat] - df[col_heat].min()) / (df[col_heat].max() - df[col_heat].min())
    n_over = 1 - (df[col_over] - df[col_over].min()) / (df[col_over].max() - df[col_over].min())
    df['Score_Thermal'] = (n_heat * 0.5) + (n_over * 0.5)

    # Daylight
    n_sda = (df[col_sDA] - df[col_sDA].min()) / (df[col_sDA].max() - df[col_sDA].min())
    n_ase = 1 - (df[col_ASE] - df[col_ASE].min()) / (df[col_ASE].max() - df[col_ASE].min())
    df['Score_Daylight'] = (n_sda * 0.5) + (n_ase * 0.5)

    # Weighting Logic
    w_renew = 0.10 if renew_choice == "Mandatory" else 0.0
    multiplier = 0.9 if renew_choice == "Mandatory" else 1.0
    w_energy = (energy_val / 100) * multiplier
    w_daylight = (daylight_val / 100) * multiplier

    df['Final_Score'] = (df['Score_Renewables'] * w_renew) + (df['Score_Thermal'] * w_energy) + (df['Score_Daylight'] * w_daylight)
    top_10 = df.sort_values('Final_Score', ascending=False).head(10)

    # --- 3D VISUALIZATION ---
    st.subheader("🧊 3D Case Distribution (Top 10)")
    fig = go.Figure(data=[go.Scatter3d(
        x=top_10['Vertical_Steps_Section'],
        y=top_10['Horizontal_Steps_Plan'],
        z=top_10['Balcony_Steps'],
        mode='markers+text',
        text=top_10[col_id],
        marker=dict(size=10, color=top_10['Final_Score'], colorscale='Viridis', opacity=0.8)
    )])
    fig.update_layout(scene=dict(xaxis_title='Vert Steps', yaxis_title='Horiz Steps', zaxis_title='Balcony Steps'))
    st.plotly_chart(fig, use_container_width=True)

    # --- ARCHITECT INSIGHTS ---
    st.subheader("🧐 Design Insights")
    params = ['Vertical_Steps_Section', 'Horizontal_Steps_Plan', 'Balcony_Steps', 'PV_Canopy_Steps', 'Vertical_Louvre_Steps']
    
    for p in params:
        mean_all, mean_top = df[p].mean(), top_10[p].mean()
        var_all, var_top = df[p].var(), top_10[p].var()
        v_ratio = var_top / var_all if var_all > 0 else 1
        _, p_val = ks_2samp(df[p], top_10[p])
        
        direction = "higher values" if mean_top > mean_all else "lower values"
        stability = "critical for performance" if v_ratio < 0.8 else "allows for flexibility"
        significance = "This change is statistically meaningful." if p_val < 0.05 else "This change could be random."
        
        st.info(f"**{p.replace('_',' ')}**: Top designs prefer **{direction}**. This parameter is **{stability}**. {significance}")
