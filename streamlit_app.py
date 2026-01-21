import streamlit as st
import pandas as pd
import numpy as np
import ui_components 
from scipy.stats import ks_2samp

# 1. SET PAGE CONFIG
st.set_page_config(layout="wide", page_title="Architectural Case Finder")

# 2. FIXED SIDEBAR WIDTH (CSS Injection)
st.markdown(
    """
    <style>
    [data-testid="stSidebar"] {
        min-width: 350px;
        max-width: 350px;
    }
    </style>
    """,
    unsafe_allow_html=True
)

# 3. LOAD DATA
@st.cache_data
def load_data():
    df = pd.read_csv('Category_02F.csv')
    return df

df_raw = load_data()

# --- SIDEBAR: DESIGN FILTERS ---
st.sidebar.header("Design Choices")
def apply_filter(df, col, label):
    choice = st.sidebar.radio(f"{label}", ["Required", "Flexible", "Excluded"], horizontal=True, key=f"filter_{col}")
    if choice == "Required": 
        return df[df[col] > 0]
    elif choice == "Excluded": 
        return df[df[col] == 0]
    return df

df_filtered = df_raw.copy()
df_filtered = apply_filter(df_filtered, 'Vertical_Louvre_Steps', "Louvers")
df_filtered = apply_filter(df_filtered, 'Balcony_Steps', "Balcony")
df_filtered = apply_filter(df_filtered, 'PV_Canopy_Steps', "Canopy")
df_filtered = apply_filter(df_filtered, 'Vertical_Steps_Section', "Vertical Steps")
df_filtered = apply_filter(df_filtered, 'Horizontal_Steps_Plan', "Horizontal Steps")

# --- MAIN UI ---
st.title("Architectural Performance Optimization")

st.subheader("Design Priorities")
# User-facing slider for Energy vs Daylight
slider_val = st.select_slider(
    "Balance: Energy | Daylight Balance", 
    options=list(range(0, 101)), 
    value=50
)
daylight_display = 100 - slider_val

col_m1, col_m2 = st.columns(2)
col_m1.metric("⚡ Energy Importance", f"{slider_val}%")
col_m2.metric("☀️ Daylight Importance", f"{daylight_display}%")

renew_choice = st.radio("Renewable Energy Strategy:", ["Ignored", "Mandatory"], horizontal=True)

# --- CALCULATION ENGINE (Hidden Logic) ---
# Calculations happen behind the scenes
if renew_choice == "Mandatory":
    w_renew = 0.10
    w_energy = (slider_val / 100) * 0.90
    w_daylight = (daylight_display / 100) * 0.90
else:
    w_renew = 0.0
    w_energy = (slider_val / 100)
    w_daylight = (daylight_display / 100)

if st.button("Find Top 10 Best Cases", use_container_width=True):
    df = df_filtered.copy()
    
    if df.empty:
        st.warning("No cases match your filter criteria. Please adjust the sidebar.")
    else:
        # A. RENEWABLE SCORE
        s_area = df['Surface_Area'] if 'Surface_Area' in df.columns else 1.0
        df['Total_Surface'] = df['PercArea_PV_Potential'] + df['PercArea_Active_Solar_Potential']
        
        # Normalize
        norm_Active = (df['Total_Surface'] - df['Total_Surface'].min()) / (df['Total_Surface'].max() - df['Total_Surface'].min() + 1e-6)
        imbalance_mask = (df['PercArea_PV_Potential'] < 10.0) | (df['PercArea_Active_Solar_Potential'] < 10.0)
        norm_Active[imbalance_mask] *= 0.5
        
        norm_Surf_inv = 1 - (s_area - s_area.min()) / (s_area.max() - s_area.min() + 1e-6)
        df['Score_Renewables'] = ((norm_Active * 0.5) + (norm_Surf_inv * 0.5)).clip(0, 1)

        # B. THERMAL SCORE
        n_heat = (df['Winter_Average_Radation_kWh/m2'] - df['Winter_Average_Radation_kWh/m2'].min()) / (df['Winter_Average_Radation_kWh/m2'].max() - df['Winter_Average_Radation_kWh/m2'].min() + 1e-6)
        n_over = 1 - (df['Summer_Average_Radation_kWh/m2'] - df['Summer_Average_Radation_kWh/m2'].min()) / (df['Summer_Average_Radation_kWh/m2'].max() - df['Summer_Average_Radation_kWh/m2'].min() + 1e-6)
        df['Score_Thermal'] = (n_heat * 0.5) + (n_over * 0.5)

        # C. DAYLIGHT SCORE
        n_sda = (df['sDA'] - df['sDA'].min()) / (df['sDA'].max() - df['sDA'].min() + 1e-6)
        n_ase = 1 - (df['ASE'] - df['ASE'].min()) / (df['ASE'].max() - df['ASE'].min() + 1e-6)
        df['Score_Daylight'] = (n_sda * 0.5) + (n_ase * 0.5)

        # FINAL CALCULATION using the hidden weights
        df['Final_Score'] = (df['Score_Renewables'] * w_renew) + \
                            (df['Score_Thermal'] * w_energy) + \
                            (df['Score_Daylight'] * w_daylight)

        st.session_state['top_10'] = df.sort_values('Final_Score', ascending=False).head(10)
        st.session_state['full_calc_df'] = df

# --- OUTPUT SECTION ---
if 'top_10' in st.session_state:
    top_10 = st.session_state['top_10']
    full_df = st.session_state['full_calc_df']
    
    st.divider()
    col_viz, col_table = st.columns([2, 1])
    
    with col_viz:
        st.subheader("🧊 3D Building Form")
        selected_id = st.selectbox("Select Case ID to visualize:", top_10['Cases_ID'])
        case_data = top_10[top_10['Cases_ID'] == selected_id].iloc[0]
        
        inputs_3d = [
            case_data['Vertical_Steps_Section'],
            case_data['Horizontal_Steps_Plan'],
            case_data['Balcony_Steps'],
            case_data['PV_Canopy_Steps'],
            case_data['Vertical_Louvre_Steps']
        ]
        ui_components.display_3d_model(f"Case {selected_id}", inputs_3d)

    with col_table:
        st.subheader("🏆 Top 10 Ranked Cases")
        st.dataframe(
            top_10[['Cases_ID', 'Final_Score', 'sDA', 'ASE']], 
            hide_index=True,
            use_container_width=True
        )
        st.info(f"Viewing: Case {selected_id}")

    # --- INSIGHTS ---
    st.divider()
    st.subheader("Design Insights")
    params = ['Vertical_Steps_Section', 'Horizontal_Steps_Plan', 'Balcony_Steps', 'PV_Canopy_Steps', 'Vertical_Louvre_Steps']
    
    cols = st.columns(len(params))
    for p in params:
    mean_all = full_df[p].mean()
    mean_top = top_10[p].mean()
    var_ratio = top_10[p].var() / (full_df[p].var() + 1e-6)
    
    # Directional Logic
    direction = "increase" if mean_top > mean_all else "decrease"
    
    # Importance Logic (Sensitivity)
    if var_ratio < 0.2:
        importance = "CORE CONSTRAINT: This value is strictly required for high performance."
    elif var_ratio < 0.6:
        importance = "RECOMMENDED: This value is preferred but has some room for adjustment."
    else:
        importance = "FLEXIBLE: You can modify this based on aesthetic preference without losing performance."

    # Final Output
    st.markdown(f"### {p.replace('_',' ')}")
    st.write(f"👉 **Direction:** To reach the Top 10, you should **{direction}** this parameter.")
    st.write(f"📐 **Architect's Freedom:** {importance}")
