import streamlit as st
import pandas as pd
import numpy as np
import ui_components 
from scipy.stats import ks_2samp

# ==========================================
# 1. SETTINGS & STYLING
# ==========================================
st.set_page_config(layout="wide", page_title="Architectural Case Finder")

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

# ==========================================
# 2. GLOBAL COLUMN DEFINITIONS
# ==========================================
col_id = 'Cases_ID'
col_global = 'Global_ID'  # Updated as requested
col_heat = 'Winter_Average_Radation_kWh/m2'
col_over = 'Summer_Average_Radation_kWh/m2'
col_sDA = 'sDA'
col_ASE = 'ASE'
params = ['Vertical_Steps_Section', 'Horizontal_Steps_Plan', 'Balcony_Steps', 'PV_Canopy_Steps', 'Vertical_Louvre_Steps']

# ==========================================
# 3. DATA LOADING
# ==========================================
@st.cache_data
def load_data():
    return pd.read_csv('Category_02F.csv')

df_raw = load_data()

# ==========================================
# 4. SIDEBAR FILTERS
# ==========================================
st.sidebar.header("Design Choices")

def apply_filter(df, col, label):
    choice = st.sidebar.radio(label, ["Required", "Flexible", "Excluded"], horizontal=True, key=f"filter_{col}")
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


# ==========================================
# 5. DESIGN PRIORITIES
# ==========================================
st.title("Architectural Performance Optimization")

st.subheader("Design Priorities")
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

if renew_choice == "Mandatory":
    w_renew, pool = 0.10, 0.90
else:
    w_renew, pool = 0.0, 1.0

w_energy = (slider_val / 100) * pool
w_daylight = (daylight_display / 100) * pool

# ==========================================
# 6. CALCULATION ENGINE
# ==========================================
if st.button("🚀 Find Best Cases", use_container_width=True):
    df = df_filtered.copy()
    if df.empty:
        st.warning("No cases match your filter criteria.")
    else:
        s_area = df['Surface_Area'] if 'Surface_Area' in df.columns else 1.0
        df['Total_Surface'] = df['PercArea_PV_Potential'] + df['PercArea_Active_Solar_Potential']
        
        n_act = (df['Total_Surface'] - df['Total_Surface'].min()) / (df['Total_Surface'].max() - df['Total_Surface'].min() + 1e-6)
        n_surf_inv = 1 - (s_area - s_area.min()) / (s_area.max() - s_area.min() + 1e-6)
        df['Score_Renewables'] = ((n_act * 0.5) + (n_surf_inv * 0.5)).clip(0, 1)

        n_heat = (df[col_heat] - df[col_heat].min()) / (df[col_heat].max() - df[col_heat].min() + 1e-6)
        n_over = 1 - (df[col_over] - df[col_over].min()) / (df[col_over].max() - df[col_over].min() + 1e-6)
        df['Score_Thermal'] = (n_heat * 0.5) + (n_over * 0.5)

        n_sda = (df[col_sDA] - df[col_sDA].min()) / (df[col_sDA].max() - df[col_sDA].min() + 1e-6)
        n_ase = 1 - (df[col_ASE] - df[col_ASE].min()) / (df[col_ASE].max() - df[col_ASE].min() + 1e-6)
        df['Score_Daylight'] = (n_sda * 0.5) + (n_ase * 0.5)

        df['Final_Score'] = (df['Score_Renewables'] * w_renew) + (df['Score_Thermal'] * w_energy) + (df['Score_Daylight'] * w_daylight)

        st.session_state['top_10'] = df.sort_values('Final_Score', ascending=False).head(10)
        st.session_state['full_calc_df'] = df

# ==========================================
# 7. DYNAMIC OUTPUTS
# ==========================================
if 'top_10' in st.session_state:
    top_10 = st.session_state['top_10']
    full_df = st.session_state['full_calc_df']
    
    st.divider()
    col_viz, col_table = st.columns([2, 1])
    
    with col_viz:
        st.subheader("3D Building Form")
        selected_id = st.selectbox("Select Case ID to visualize:", top_10[col_id])
        case_data = top_10[top_10[col_id] == selected_id].iloc[0]
        
        # --- DYNAMIC PERFORMANCE VS BASE CASE (Moved here) ---
        base_case_search = df_raw[df_raw[col_id].astype(str).str.contains('Base', case=False, na=False)]
        
        if not base_case_search.empty:
            base_case = base_case_search.iloc[0]
            indicators = {
                'sDA (%)': {'col': col_sDA, 'inv': False}, 
                'ASE (%)': {'col': col_ASE, 'inv': True}, 
                'Winter Rad': {'col': col_heat, 'inv': False}, 
                'Summer Rad': {'col': col_over, 'inv': True}
            }
            
            imp_cols = st.columns(4)
            for i, (label, data) in enumerate(indicators.items()):
                b_val, c_val = base_case[data['col']], case_data[data['col']]
                diff_pct = ((c_val - b_val) / (b_val + 1e-6)) * 100
                with imp_cols[i]:
                    st.metric(label, f"{round(c_val, 1)}", f"{round(diff_pct, 1)}% vs Base", delta_color="inverse" if data['inv'] else "normal")
        
        # Visualize 3D
        inputs_3d = [case_data[p] for p in params]
        ui_components.display_3d_model("Type_A", inputs_3d)

    with col_table:
        st.subheader("🏆 Case Schedule")
        # Display Global_ID and Parameters for the Selected Case
        schedule_cols = [col_global] + params
        st.dataframe(top_10[schedule_cols], hide_index=True)
        st.info(f"Viewing: {case_data[col_global]} (Typology: {selected_id})")

    # ==========================================
   # ==========================================
    # 8. CASE-SPECIFIC STRATEGIC ANALYSIS
    # ==========================================
    st.divider()
    st.subheader(f"🧐 Strategic Analysis: Case {selected_id}")
    
    active_params = [p for p in params if full_df[p].max() > 0]
    
    if active_params:
        # 1. Calculate General Trends (Correlations)
        correlation_matrix = full_df[active_params + ['Score_Thermal', 'Score_Daylight']].corr()
        
        ins_cols = st.columns(len(active_params))

        for i, p in enumerate(active_params):
            with ins_cols[i]:
                st.markdown(f"#### {p.replace('_',' ')}")
                
                # A. Identify the General Conflict
                c_thermal = correlation_matrix.loc[p, 'Score_Thermal']
                c_daylight = correlation_matrix.loc[p, 'Score_Daylight']
                is_conflict = (c_thermal > 0.15 and c_daylight < -0.15) or (c_thermal < -0.15 and c_daylight > 0.15)
                
                # B. Look at the SPECIFIC Selected Case value
                case_value = case_data[p]
                mean_all = full_df[p].mean()
                
                # C. Provide Case-Specific Insight
                if is_conflict:
                    st.warning("⚖️ High-Conflict Zone")
                    if case_value > mean_all:
                        st.write(f"In Case {selected_id}, you chose a **higher** value. This prioritizes one goal over the other.")
                    else:
                        st.write(f"In Case {selected_id}, you chose a **lower** value to minimize the trade-off penalty.")
                
                elif abs(c_thermal) > 0.3 and abs(c_daylight) > 0.3:
                    st.success("🤝 Synergy Move")
                    st.write(f"Case {selected_id} utilizes this parameter as a core performance driver.")
                
                else:
                    st.write("⚪ Neutral Position")

                # D. Mitigation Advice (The "Fix")
                if is_conflict and c_thermal > c_daylight:
                    st.caption("💡 *Optimization Hint:* If Daylight is too low in this specific form, reduce Louvers.")
                elif is_conflict:
                    st.caption("💡 *Optimization Hint:* If Overheating occurs in this form, increase Canopy depth.")

    # ==========================================
    # 10. EXECUTIVE SUMMARY (Fixed for Exclusions)
    # ==========================================
    st.divider()
    st.subheader("💬 Executive Design Summary")
    
    for p in params:
        # Check if user has excluded this parameter
        if full_df[p].max() == 0:
            continue # Skip parameters that are excluded (always 0)
            
        mean_all, mean_top = full_df[p].mean(), top_10[p].mean()
        
        # Stability check: Only valid if there is variance in the original data
        if full_df[p].var() > 0:
            v_ratio = top_10[p].var() / (full_df[p].var() + 1e-6)
            shift = "higher values" if mean_top > mean_all else "lower values"
            stability = "critical for performance" if v_ratio < 0.6 else "flexible for design"
            
            st.write(f"• Top designs prefer **{shift}** for **{p.replace('_',' ')}**. This is **{stability}**.")
