import streamlit as st
import pandas as pd
import numpy as np
import ui_components 
from scipy.stats import ks_2samp

# ==========================================
# 1. SETTINGS & STYLING
# ==========================================
st.set_page_config(layout="wide", page_title="Architectural Case Finder")

# Fixed Sidebar Width (CSS)
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
    # Make sure this filename matches your GitHub file
    return pd.read_csv('Category_02F.csv')

df_raw = load_data()

# ==========================================
# 4. SIDEBAR FILTERS
# ==========================================
st.sidebar.header("Design Choices")

def apply_filter(df, col, label):
    choice = st.sidebar.radio(label, ["Flexible", "Required", "Excluded"], horizontal=True, key=f"filter_{col}")
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

# ==========================================
# 5. DESIGN PRIORITIES (Main UI)
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

# Hidden Weighting Logic
if renew_choice == "Mandatory":
    w_renew = 0.10
    w_energy = (slider_val / 100) * 0.90
    w_daylight = (daylight_display / 100) * 0.90
else:
    w_renew = 0.0
    w_energy = (slider_val / 100)
    w_daylight = (daylight_display / 100)

# ==========================================
# 6. CALCULATION ENGINE
# ==========================================
if st.button("🚀 Find Top 10 Best Cases", use_container_width=True):
    df = df_filtered.copy()
    
    if df.empty:
        st.warning("No cases match your filter criteria. Please adjust the sidebar.")
    else:
        # A. RENEWABLE SCORE
        s_area = df['Surface_Area'] if 'Surface_Area' in df.columns else 1.0
        df['Total_Surface'] = df['PercArea_PV_Potential'] + df['PercArea_Active_Solar_Potential']
        
        norm_Active = (df['Total_Surface'] - df['Total_Surface'].min()) / (df['Total_Surface'].max() - df['Total_Surface'].min() + 1e-6)
        imbalance_mask = (df['PercArea_PV_Potential'] < 10.0) | (df['PercArea_Active_Solar_Potential'] < 10.0)
        norm_Active[imbalance_mask] *= 0.5
        
        norm_Surf_inv = 1 - (s_area - s_area.min()) / (s_area.max() - s_area.min() + 1e-6)
        df['Score_Renewables'] = ((norm_Active * 0.5) + (norm_Surf_inv * 0.5)).clip(0, 1)

        # B. THERMAL SCORE
        n_heat = (df[col_heat] - df[col_heat].min()) / (df[col_heat].max() - df[col_heat].min() + 1e-6)
        n_over = 1 - (df[col_over] - df[col_over].min()) / (df[col_over].max() - df[col_over].min() + 1e-6)
        df['Score_Thermal'] = (n_heat * 0.5) + (n_over * 0.5)

        # C. DAYLIGHT SCORE
        n_sda = (df[col_sDA] - df[col_sDA].min()) / (df[col_sDA].max() - df[col_sDA].min() + 1e-6)
        n_ase = 1 - (df[col_ASE] - df[col_ASE].min()) / (df[col_ASE].max() - df[col_ASE].min() + 1e-6)
        df['Score_Daylight'] = (n_sda * 0.5) + (n_ase * 0.5)

        # FINAL CALCULATION
        df['Final_Score'] = (df['Score_Renewables'] * w_renew) + (df['Score_Thermal'] * w_energy) + (df['Score_Daylight'] * w_daylight)

        st.session_state['top_10'] = df.sort_values('Final_Score', ascending=False).head(10)
        st.session_state['full_calc_df'] = df

# ==========================================
# 7. VISUALIZATION & OUTPUT
# ==========================================
if 'top_10' in st.session_state:
    top_10 = st.session_state['top_10']
    full_df = st.session_state['full_calc_df']
    
    st.divider()
    col_viz, col_table = st.columns([2, 1])
    
    with col_viz:
        st.subheader("🧊 3D Building Form")
        selected_id = st.selectbox("Select Case ID to visualize:", top_10[col_id])
        case_data = top_10[top_10[col_id] == selected_id].iloc[0]
        
        inputs_3d = [case_data[p] for p in params]
        ui_components.display_3d_model("Type_A", inputs_3d)

    with col_table:
        st.subheader("🏆 Top 10 Ranked Cases")
        st.dataframe(top_10[[col_id, 'Final_Score', col_sDA, col_ASE]], hide_index=True)
        st.info(f"Viewing: Case {selected_id} | Performance Score: {round(case_data['Final_Score']*100, 1)}%")

    # ==========================================
    # 8. SMART INSIGHTS & CONFLICT ANALYSIS
    # ==========================================
    st.divider()
    st.subheader("🧐 Strategic Conflict Analysis")
    st.info("A 'Conflict' occurs when a parameter improves one score but degrades another.")

    score_cols = ['Score_Renewables', 'Score_Thermal', 'Score_Daylight']
    correlation_matrix = full_df[params + score_cols].corr()
    ins_cols = st.columns(len(params))

    for i, p in enumerate(params):
        with ins_cols[i]:
            st.markdown(f"#### {p.replace('_',' ')}")
            c_thermal = correlation_matrix.loc[p, 'Score_Thermal']
            c_daylight = correlation_matrix.loc[p, 'Score_Daylight']
            
            # Conflict Logic
            if (c_thermal > 0.15 and c_daylight < -0.15) or (c_thermal < -0.15 and c_daylight > 0.15):
                st.warning("⚠️ High Conflict")
                st.caption("Thermal and Daylight goals are pulling in opposite directions.")
            elif abs(c_thermal) > 0.3 and abs(c_daylight) > 0.3:
                st.success("🤝 Synergy")
                st.caption("Benefits both goals simultaneously.")
            else:
                st.write("⚖️ Neutral")

            # Strategy Suggestion
            mean_all, mean_top = full_df[p].mean(), top_10[p].mean()
            direction = "⬆️ Increase" if mean_top > mean_all else "⬇️ Decrease"
            st.markdown(f"**Top 10 Trend:** {direction}")

    # ==========================================
    # 9. PERFORMANCE vs BASE CASE
    # ==========================================
    st.divider()
    st.subheader("📈 Performance Improvement from Base Case")
    
    base_case_search = df_raw[df_raw[col_id].astype(str).str.contains('Base', case=False, na=False)]
    
    if not base_case_search.empty:
        base_case = base_case_search.iloc[0]
        indicators = {
            'sDA (%)': {'col': col_sDA, 'inverse': False}, 
            'ASE (%)': {'col': col_ASE, 'inverse': True}, 
            'Winter Rad': {'col': col_heat, 'inverse': False}, 
            'Summer Rad': {'col': col_over, 'inverse': True}
        }
        
        top_10_avg = top_10[[d['col'] for d in indicators.values()]].mean()
        imp_cols = st.columns(4)
        
        for i, (label, data) in enumerate(indicators.items()):
            b_val = base_case[data['col']]
            t_val = top_10_avg[data['col']]
            diff_pct = ((t_val - b_val) / (b_val + 1e-6)) * 100
            
            with imp_cols[i]:
                st.metric(
                    label=label, 
                    value=f"{round(t_val, 1)}", 
                    delta=f"{round(diff_pct, 1)}% vs Base",
                    delta_color="inverse" if data['inverse'] else "normal"
                )
    
    # ==========================================
    # 10. STATISTICAL DISTRIBUTION TABLE
    # ==========================================
    st.divider()
    st.subheader("📊 Parameter Distribution Analysis")
    dist_data = []
    for p in params:
        mean_all, mean_top = full_df[p].mean(), top_10[p].mean()
        var_all, var_top = full_df[p].var(), top_10[p].var()
        v_ratio = var_top / (var_all + 1e-6)
        _, p_val = ks_2samp(full_df[p], top_10[p])
        dist_data.append({
            "Parameter": p.replace('_', ' '), "Mean (All)": round(mean_all, 3), 
            "Mean (Top 10)": round(mean_top, 3), "Var Ratio": round(v_ratio, 3), "P-Value": round(p_val, 4)
        })
    st.table(pd.DataFrame(dist_data))

    # ==========================================
    # 11. EXECUTIVE SUMMARY
    # ==========================================
    st.divider()
    st.subheader("💬 Executive Design Summary")
    for p in params:
        mean_all, mean_top = full_df[p].mean(), top_10[p].mean()
        v_ratio = top_10[p].var() / (full_df[p].var() + 1e-6)
        _, p_val = ks_2samp(full_df[p], top_10[p])
        
        shift = "higher values" if mean_top > mean_all else "lower values"
        stability = "critical for performance" if v_ratio < 0.6 else "flexible for design"
        sig = " (Significant trend)" if p_val < 0.05 else ""
        st.write(f"• Top designs prefer **{shift}** for **{p.replace('_',' ')}**. This is **{stability}**.{sig}")
