import streamlit as st
import pandas as pd
import numpy as np
from scipy.stats import ks_2samp

st.set_page_config(layout="wide", page_title="Architectural Case Finder")

# 1. LOAD DATA
@st.cache_data
def load_data():
    # Replace 'data.csv' with your actual filename
    df = pd.read_csv('Category_02F.csv')
    return df

df_raw = load_data().copy()

# Define Column Names
col_id = 'Cases_ID'
col_heat = 'Winter_Average_Radation_kWh/m2'
col_over = 'Summer_Average_Radation_kWh/m2'
col_sDA = 'sDA'
col_ASE = 'ASE'
col_pv = 'PercArea_PV_Potential'
col_active = 'PercArea_Active_Solar_Potential'

# --- SIDEBAR: DESIGN CHOICES (Filtering) ---
st.sidebar.header("🛠️ Design Choices")

def apply_filter(df, col, label):
    choice = st.sidebar.radio(f"{label}", ["Available", "Mandatory", "Ignored"], horizontal=True)
    if choice == "Mandatory":
        return df[df[col] > 0]
    elif choice == "Ignored":
        return df[df[col] == 0]
    return df

df_filtered = df_raw.copy()
df_filtered = apply_filter(df_filtered, 'Vertical_Louvre_Steps', "Louvers")
df_filtered = apply_filter(df_filtered, 'Balcony_Steps', "Balcony")
df_filtered = apply_filter(df_filtered, 'PV_Canopy_Steps', "Canopy")
df_filtered = apply_filter(df_filtered, 'Vertical_Steps_Section', "Vertical Steps")
df_filtered = apply_filter(df_filtered, 'Horizontal_Steps_Plan', "Horizontal Steps")

# --- MAIN PAGE: DESIGN PRIORITIES (Scoring) ---
st.title("Architectural Performance Optimizer")

col1, col2 = st.columns(2)

with col1:
    st.subheader("🎯 Design Priorities")
    renew_choice = st.radio("Renewable Energy Importance:", ["Ignored", "Mandatory"])
    
    # Logic: If Mandatory, Energy + Daylight share 90%, Renewables gets 10%
    energy_val = st.slider("Energy Importance vs Daylight", 0, 100, 50)
    daylight_val = 100 - energy_val

# --- CALCULATION ENGINE ---
if st.button("Generate Top 20 Cases"):
    df = df_filtered.copy()
    
    # A. Renewable Score
    df['Total_Surface'] = df[col_pv] + df[col_active]
    norm_Active = (df['Total_Surface'] - df['Total_Surface'].min()) / (df['Total_Surface'].max() - df['Total_Surface'].min())
    imbalance_mask = (df[col_pv] < 10.0) | (df[col_active] < 10.0)
    norm_Active[imbalance_mask] *= 0.5
    
    # Surface area normalization (assuming 'Surface_Area' column exists)
    norm_Surface_inv = 1 - (df['Surface_Area'] - df['Surface_Area'].min()) / (df['Surface_Area'].max() - df['Surface_Area'].min())
    df['Score_Renewables'] = ((norm_Active * 0.5) + (norm_Surface_inv * 0.5)).clip(0, 1)

    # B. Thermal Score
    norm_heat = (df[col_heat] - df[col_heat].min()) / (df[col_heat].max() - df[col_heat].min())
    norm_overheat_inv = 1 - (df[col_over] - df[col_over].min()) / (df[col_over].max() - df[col_over].min())
    df['Score_Thermal'] = (norm_heat * 0.5) + (norm_overheat_inv * 0.5)

    # C. Daylight Score
    norm_sDA = (df[col_sDA] - df[col_sDA].min()) / (df[col_sDA].max() - df[col_sDA].min())
    norm_ASE_inv = 1 - (df[col_ASE] - df[col_ASE].min()) / (df[col_ASE].max() - df[col_ASE].min())
    df['Score_Daylight'] = (norm_sDA * 0.5) + (norm_ASE_inv * 0.5)

    # FINAL WEIGHTING
    if renew_choice == "Mandatory":
        w_renew = 0.10
        w_energy = (energy_val / 100) * 0.9
        w_daylight = (daylight_val / 100) * 0.9
    else:
        w_renew = 0.0
        w_energy = energy_val / 100
        w_daylight = daylight_val / 100

    df['Final_Score'] = (df['Score_Renewables'] * w_renew) + \
                        (df['Score_Thermal'] * w_energy) + \
                        (df['Score_Daylight'] * w_daylight)

    top_20 = df.sort_values('Final_Score', ascending=False).head(20)

    # --- DISPLAY RESULTS ---
    st.write(f"### Found {len(df)} matching cases. Top 20 shown below:")
    st.dataframe(top_20[[col_id, 'Final_Score', col_sDA, col_ASE, col_heat, col_over]])

    # --- INSIGHTS ENGINE ---
    st.divider()
    st.subheader("🧐 Architect's Insights")
    
    params = ['Vertical_Steps_Section', 'Horizontal_Steps_Plan', 'Balcony_Steps', 'PV_Canopy_Steps', 'Vertical_Louvre_Steps']
    
    for p in params:
        mean_all = df[p].mean()
        mean_top = top_20[p].mean()
        var_all = df[p].var()
        var_top = top_20[p].var()
        
        # Stats logic
        v_ratio = var_top / var_all if var_all != 0 else 1
        stat, p_val = ks_2samp(df[p], top_20[p])
        
        # Translate to Sentences
        direction = "higher values" if mean_top > mean_all else "lower values"
        significance = "This change is statistically meaningful." if p_val < 0.05 else "This change could be random."
        stability = "critical for performance" if v_ratio < 0.8 else "allows for flexibility"

        st.markdown(f"**{p.replace('_',' ')}**: Top designs prefer **{direction}**. This parameter is **{stability}**. _{significance}_")
