import streamlit as st
import pandas as pd
import numpy as np
import ui_components 
from scipy.stats import ks_2samp

# 1. SET PAGE CONFIG
st.set_page_config(layout="wide", page_title="Architectural Case Finder")

# 2. LOAD DATA
@st.cache_data
def load_data():
    return pd.read_csv('Category_02F.csv')

df_raw = load_data()

# --- 3. GLOBAL COLUMN DEFINITIONS (Move them here!) ---
col_id = 'Cases'
col_heat = 'Winter_Average_Radation_kWh/m2'
col_over = 'Summer_Average_Radation_kWh/m2'
col_sDA = 'sDA'
col_ASE = 'ASE'
params = ['Vertical_Steps_Section', 'Horizontal_Steps_Plan', 'Balcony_Steps', 'PV_Canopy_Steps', 'Vertical_Louvre_Steps']


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
df_filtered = apply_filter(df_filtered, 'Vertical_Steps_Section', "Vertical Steps")
df_filtered = apply_filter(df_filtered, 'Horizontal_Steps_Plan', "Horizontal Steps")
df_filtered = apply_filter(df_filtered, 'Balcony_Steps', "Balcony")
df_filtered = apply_filter(df_filtered, 'PV_Canopy_Steps', "Canopy")
df_filtered = apply_filter(df_filtered, 'Vertical_Louvre_Steps', "Louvers")



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

# --- 1. PERFORMANCE IMPROVEMENT FROM BASE CASE ---
    st.divider()
    st.subheader("📈 Performance Improvement from Base Case")
    
    # FIX: Look in the RAW data and use the Name 'Base' instead of just zeros
    base_case_search = df_raw[df_raw[col_id].astype(str).str.contains('Base', case=False, na=False)]
    
    if not base_case_search.empty:
        base_case = base_case_search.iloc[0]
        indicators = {
            'sDA': col_sDA, 
            'ASE': col_ASE, 
            'Winter Radiation': col_heat, 
            'Summer Radiation': col_over
        }
        
        # Calculate average performance of Top 10
        top_10_avg = top_10[list(indicators.values())].mean()
        
        imp_cols = st.columns(4)
        for i, (label, col) in enumerate(indicators.items()):
            b_val = base_case[col]
            t_val = top_10_avg[col]
            
            # Calculate % change
            # Note: For ASE and Summer Radiation, lower is usually better
            diff_pct = ((t_val - b_val) / (b_val + 1e-6)) * 100
            
            with imp_cols[i]:
                st.metric(label, f"{round(t_val, 1)}", f"{round(diff_pct, 1)}% vs Base")
    else:
        st.info("Note: A 'Pure Base Case' (all parameters = 0) was not found in the filtered data for comparison.")

    # --- SMART ARCHITECT INSIGHTS (Conflict & Correlation) ---
    st.divider()
    st.subheader("🧐 Strategic Conflict Analysis")
    st.info("This section identifies trade-offs. A 'Conflict' occurs when a parameter improves one score but degrades another.")

    # List of scores to check correlation against
    score_cols = ['Score_Renewables', 'Score_Thermal', 'Score_Daylight']
    
    # We use the full_df (the filtered dataset) for correlation to see overall trends
    correlation_matrix = full_df[params + score_cols].corr()

    # Create columns for parameters
    ins_cols = st.columns(len(params))

    for i, p in enumerate(params):
        with ins_cols[i]:
            st.markdown(f"#### {p.replace('_',' ')}")
            
            # Get correlations for this parameter
            corr_thermal = correlation_matrix.loc[p, 'Score_Thermal']
            corr_daylight = correlation_matrix.loc[p, 'Score_Daylight']
            
            # Determine Conflict Logic
            # If one is positive (>0.2) and one is negative (<-0.2), it's a conflict
            if (corr_thermal > 0.15 and corr_daylight < -0.15) or (corr_thermal < -0.15 and corr_daylight > 0.15):
                st.warning("⚠️ **High Conflict**")
                if corr_thermal > corr_daylight:
                    st.caption(f"Increasing this helps **Thermal** but hurts **Daylight**.")
                else:
                    st.caption(f"Increasing this helps **Daylight** but hurts **Thermal**.")
            
            elif abs(corr_thermal) > 0.3 and abs(corr_daylight) > 0.3:
                st.success("🤝 **Synergy**")
                st.caption("This parameter benefits both Energy and Daylight goals simultaneously.")
            
            else:
                st.write("⚖️ **Neutral / Balanced**")
                st.caption("Low direct conflict between primary performance goals.")

            # Show the "Target" based on Top 10 mean vs All mean
            mean_all, mean_top = full_df[p].mean(), top_10[p].mean()
            direction = "⬆️ Increase" if mean_top > mean_all else "⬇️ Decrease"
            st.markdown(f"**Top 10 Trend:** {direction}")

    # --- PERFORMANCE IMPROVEMENT FROM BASE CASE ---
    # [Paste your Base Case logic here]
