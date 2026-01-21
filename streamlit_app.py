import streamlit as st
import pandas as pd
import numpy as np
import ui_components  # Ensure ui_components.py is in your GitHub
from scipy.stats import ks_2samp

st.set_page_config(layout="wide", page_title="Architectural Case Finder")

# 1. LOAD DATA
@st.cache_data
def load_data():
    # Make sure this filename matches exactly what you uploaded to GitHub
    df = pd.read_csv('Category_02F.csv')
    return df

df_raw = load_data()

# --- SIDEBAR: DESIGN FILTERS (Original Radio Style) ---
st.sidebar.header("🛠️ Design Choices")
def apply_filter(df, col, label):
    choice = st.sidebar.radio(f"{label}", ["Available", "Mandatory", "Ignored"], horizontal=True, key=f"filter_{col}")
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

# --- MAIN UI ---
st.title("🏙️ Architectural Performance Optimizer")

st.subheader("⚖️ Design Priorities")
# Split-view priority slider
energy_val = st.select_slider(
    "Balance: Energy Importance (Left) vs Daylight (Right)", 
    options=list(range(0, 101)), 
    value=50
)
daylight_val = 100 - energy_val

col_m1, col_m2 = st.columns(2)
col_m1.metric("⚡ Energy Weight", f"{energy_val}%")
col_m2.metric("☀️ Daylight Weight", f"{daylight_val}%")

renew_choice = st.radio("Renewable Energy Strategy:", ["Ignored", "Mandatory"], horizontal=True)

# --- CALCULATION ENGINE ---
if st.button("🚀 Find Top 10 Best Cases", use_container_width=True):
    # We work on a copy of the filtered data
    df = df_filtered.copy()
    
    if df.empty:
        st.warning("No cases match your filter criteria. Please adjust the sidebar.")
    else:
        # A. RENEWABLE SCORE
        # Note: If 'Surface_Area' is not in your CSV, we use a placeholder of 1.0 to avoid KeyError
        s_area = df['Surface_Area'] if 'Surface_Area' in df.columns else 1.0
        
        df['Total_Surface'] = df['PercArea_PV_Potential'] + df['PercArea_Active_Solar_Potential']
        
        # Normalize (added 1e-6 to prevent division by zero)
        norm_Active = (df['Total_Surface'] - df['Total_Surface'].min()) / (df['Total_Surface'].max() - df['Total_Surface'].min() + 1e-6)
        
        # Penalty for imbalance
        imbalance_mask = (df['PercArea_PV_Potential'] < 10.0) | (df['PercArea_Active_Solar_Potential'] < 10.0)
        norm_Active[imbalance_mask] *= 0.5
        
        norm_Surf_inv = 1 - (s_area - s_area.min()) / (s_area.max() - s_area.min() + 1e-6)
        df['Score_Renewables'] = ((norm_Active * 0.5) + (norm_Surf_inv * 0.5)).clip(0, 1)

        # B. THERMAL SCORE (Maximize Winter, Minimize Summer)
        n_heat = (df['Winter_Average_Radation_kWh/m2'] - df['Winter_Average_Radation_kWh/m2'].min()) / (df['Winter_Average_Radation_kWh/m2'].max() - df['Winter_Average_Radation_kWh/m2'].min() + 1e-6)
        n_over = 1 - (df['Summer_Average_Radation_kWh/m2'] - df['Summer_Average_Radation_kWh/m2'].min()) / (df['Summer_Average_Radation_kWh/m2'].max() - df['Summer_Average_Radation_kWh/m2'].min() + 1e-6)
        df['Score_Thermal'] = (n_heat * 0.5) + (n_over * 0.5)

        # C. DAYLIGHT SCORE
        n_sda = (df['sDA'] - df['sDA'].min()) / (df['sDA'].max() - df['sDA'].min() + 1e-6)
        n_ase = 1 - (df['ASE'] - df['ASE'].min()) / (df['ASE'].max() - df['ASE'].min() + 1e-6)
        df['Score_Daylight'] = (n_sda * 0.5) + (n_ase * 0.5)

        # D. FINAL WEIGHTING
        w_renew = 0.10 if renew_choice == "Mandatory" else 0.0
        mult = 0.9 if renew_choice == "Mandatory" else 1.0
        
        df['Final_Score'] = (df['Score_Renewables'] * w_renew) + \
                            (df['Score_Thermal'] * (energy_val/100 * mult)) + \
                            (df['Score_Daylight'] * (daylight_val/100 * mult))

        # SAVE TO SESSION STATE
        st.session_state['top_10'] = df.sort_values('Final_Score', ascending=False).head(10)
        st.session_state['full_calc_df'] = df

# --- DISPLAY & 3D VISUALIZATION ---
if 'top_10' in st.session_state:
    top_10 = st.session_state['top_10']
    full_df = st.session_state['full_calc_df']
    
    st.divider()
    
    col_viz, col_table = st.columns([2, 1])
    
    with col_viz:
        st.subheader("🧊 3D Building Form")
        selected_id = st.selectbox("Select Case ID to visualize:", top_10['Cases_ID'])
        
        # Get data for the specific chosen building
        case_data = top_10[top_10['Cases_ID'] == selected_id].iloc[0]
        
        # Pack parameters for the 3D function
        inputs_3d = [
            case_data['Vertical_Steps_Section'],
            case_data['Horizontal_Steps_Plan'],
            case_data['Balcony_Steps'],
            case_data['PV_Canopy_Steps'],
            case_data['Vertical_Louvre_Steps']
        ]
        
        # Run the 3D function from your other file
        ui_components.display_3d_model(f"Case {selected_id}", inputs_3d)

    with col_table:
        st.subheader("🏆 Top 10 Ranked Cases")
        st.dataframe(
            top_10[['Cases_ID', 'Final_Score', 'sDA', 'ASE']], 
            hide_index=True,
            use_container_width=True
        )
        st.write(f"**Current View:** Case {selected_id}")
        st.info(f"Final Score: {round(case_data['Final_Score']*100, 2)}%")

    # --- ARCHITECT INSIGHTS (Comparison) ---
    st.divider()
    st.subheader("🧐 Design Insights")
    params = ['Vertical_Steps_Section', 'Horizontal_Steps_Plan', 'Balcony_Steps', 'PV_Canopy_Steps', 'Vertical_Louvre_Steps']
    
    cols = st.columns(len(params))
    
    for i, p in enumerate(params):
        with cols[i]:
            mean_all, mean_top = full_df[p].mean(), top_10[p].mean()
            var_all = full_df[p].var()
            var_top = top_10[p].var()
            v_ratio = var_top / var_all if var_all > 0 else 1
            _, p_val = ks_2samp(full_df[p], top_10[p])
            
            direction = "Higher values" if mean_top > mean_all else "Lower values"
            stability = "Critical for performance" if v_ratio < 0.7 else "Allows for flexibility"
            
            st.markdown(f"**{p.replace('_',' ')}**")
            st.write(f"• Prefer: **{direction}**")
            st.write(f"• Role: **{stability}**")
            if p_val < 0.05:
                st.caption("✅ Statistically Significant")
            else:
                st.caption("⚪ High Variance")
