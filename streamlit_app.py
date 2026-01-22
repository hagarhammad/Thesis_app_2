import streamlit as st
import pandas as pd
import numpy as np
import ui_components 

# ==========================================
# 1. SETTINGS & STYLING
# ==========================================
st.set_page_config(layout="wide", page_title="Architectural Case Finder")

st.markdown("""
    <style>
    [data-testid="stSidebar"] { min-width: 350px; max-width: 350px; }
    </style>
    """, unsafe_allow_html=True)

# ==========================================
# 2. GLOBAL COLUMN DEFINITIONS
# ==========================================
col_id, col_global, cases = 'Cases_ID', 'Global_ID', 'Cases'
col_heat = 'Winter_Average_Radation_kWh/m2'
col_over = 'Summer_Average_Radation_kWh/m2'
col_sDA, col_ASE = 'sDA', 'ASE'
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
    if choice == "Required": return df[df[col] != 0]
    elif choice == "Excluded": return df[df[col] == 0]
    return df

df_filtered = df_raw.copy()
for p in params:
    df_filtered = apply_filter(df_filtered, p, p.replace('_', ' '))

# ==========================================
# 5. DESIGN PRIORITIES
# ==========================================
st.title("Architectural Performance Optimization")
st.subheader("Design Priorities")

slider_val = st.select_slider("Balance: Energy | Daylight Balance", options=list(range(0, 101)), value=50)
daylight_display = 100 - slider_val

col_m1, col_m2 = st.columns(2)
col_m1.metric("⚡ Energy Importance", f"{slider_val}%")
col_m2.metric("☀️ Daylight Importance", f"{daylight_display}%")

renew_choice = st.radio("Renewable Energy Strategy:", ["Ignored", "Mandatory"], horizontal=True)

# ==========================================
# 6. CALCULATION ENGINE
# ==========================================
if st.button("🚀 Find Best Cases", use_container_width=True):
    w_renew, pool = (0.10, 0.90) if renew_choice == "Mandatory" else (0.0, 1.0)
    current_w_energy = (slider_val / 100) * pool
    current_w_daylight = (daylight_display / 100) * pool
    
    df = df_filtered.copy()
    if not df.empty:
        # Normalize and Score
        df['Total_Surface'] = df['PercArea_PV_Potential'] + df['PercArea_Active_Solar_Potential']
        n_act = (df['Total_Surface'] - df['Total_Surface'].min()) / (df['Total_Surface'].max() - df['Total_Surface'].min() + 1e-6)
        
        n_heat = (df[col_heat] - df[col_heat].min()) / (df[col_heat].max() - df[col_heat].min() + 1e-6)
        n_over = 1 - (df[col_over] - df[col_over].min()) / (df[col_over].max() - df[col_over].min() + 1e-6)
        
        n_sda = (df[col_sDA] - df[col_sDA].min()) / (df[col_sDA].max() - df[col_sDA].min() + 1e-6)
        n_ase = 1 - (df[col_ASE] - df[col_ASE].min()) / (df[col_ASE].max() - df[col_ASE].min() + 1e-6)

        df['Score_Renewables'] = n_act.clip(0, 1)
        df['Score_Thermal'] = (n_heat * 0.5) + (n_over * 0.5)
        df['Score_Daylight'] = (n_sda * 0.5) + (n_ase * 0.5)

        df['Final_Score'] = (df['Score_Renewables'] * w_renew) + \
                            (df['Score_Thermal'] * current_w_energy) + \
                            (df['Score_Daylight'] * current_w_daylight)

        df['binary_signature'] = df[params].apply(lambda row: tuple(1 if x != 0 else 0 for x in row), axis=1)
        df = df.sort_values(by='Final_Score', ascending=False)
        st.session_state['top_10'] = df.drop_duplicates(subset=['binary_signature']).head(10)
        st.session_state['full_calc_df'] = df
        st.success("Optimization Complete.")

# ==========================================
# 7. OUTPUTS (Visuals & Data)
# ==========================================
if 'top_10' in st.session_state:
    top_10 = st.session_state['top_10']
    full_df = st.session_state['full_calc_df']
    
    base_case_df = df_raw[df_raw[col_id].astype(str).str.contains('Base', case=False, na=False)]
    base_case = base_case_df.iloc[0] if not base_case_df.empty else None

    st.divider()
    col_viz, col_table = st.columns([2, 1])
    
    with col_viz:
        st.subheader("🧊 Selected Building Performance")
        selected_global = st.selectbox("Select Global ID:", top_10[col_global])
        case_data = top_10[top_10[col_global] == selected_global].iloc[0]
        
        if base_case is not None:
            metrics = st.columns(4)
            vals = [('sDA (%)', col_sDA, False), ('ASE (%)', col_ASE, True), ('Winter Rad', col_heat, False), ('Summer Rad', col_over, True)]
            for i, (lab, k, inv) in enumerate(vals):
                diff = ((case_data[k] - base_case[k]) / (base_case[k] + 1e-6)) * 100
                metrics[i].metric(lab, round(case_data[k], 1), f"{round(diff, 1)}%", delta_color="inverse" if inv else "normal")
        
        ui_components.display_3d_model("Type_A", [case_data[p] for p in params])

    with col_table:
        st.subheader("🏆 Strategy Ranking")
        st.dataframe(top_10[[col_global, cases] + params], hide_index=True)

    # ==========================================
    # 8. DYNAMIC PERFORMANCE DIAGNOSTICS
    # ==========================================
    st.divider()
    st.subheader(f"🧐 Strategic Synergy: {selected_global}")
    
    # Identify goal label
    primary_goal = "Energy Efficiency" if slider_val > 50 else "Daylight Maximization"
    if slider_val == 50: primary_goal = "Balanced Design"

    diag_cols = st.columns(len(params))
    for i, p in enumerate(params):
        with diag_cols[i]:
            st.markdown(f"**{p.replace('_',' ')}**")
            
            # Compare current case against the "Winners Average"
            top_avg = top_10[p].mean()
            global_avg = full_df[p].mean()
            target_dir = "INCREASE" if top_avg > global_avg else "DECREASE"
            
            is_aligned = (target_dir == "INCREASE" and case_data[p] >= global_avg) or \
                         (target_dir == "DECREASE" and case_data[p] <= global_avg)
            
            if is_aligned:
                st.write("🤝 **Synergy**")
                st.caption(f"Aligns with {primary_goal}")
            else:
                st.write("⚔️ **Conflict**")
                st.caption(f"Conflicts with {primary_goal}")
            
            st.info(f"Target: {target_dir}")

    # ==========================================
    # 9. STRATEGIC FIXES
    # ==========================================
    st.subheader("🛠️ Performance Fixes")
    fixes = []
    tol = 0.10
    
    if case_data[col_ASE] > 10:
        fixes.append("⚠️ **High Glare:** Increase Louver depth or Canopy size.")
    if case_data[col_sDA] < (top_10[col_sDA].max() * (1 - tol)):
        fixes.append("☀️ **Low Daylight:** Reduce Balcony depth or Louver thickness.")
    
    if fixes:
        for f in fixes: st.info(f)
    else:
        st.success("✅ Geometry handles current trade-offs effectively.")

    # ==========================================
    # 10. EXECUTIVE SUMMARY
    # ==========================================
    st.divider()
    st.subheader("💬 Design Freedom")
    cols = st.columns(len(params))
    for i, p in enumerate(params):
        v_ratio = top_10[p].var() / (full_df[p].var() + 1e-6)
        label = "🔴 STRICT" if v_ratio < 0.2 else "🟡 PREFERENCE" if v_ratio < 0.6 else "🟢 FLEXIBLE"
        cols[i].write(f"**{p.split('_')[0]}**\n\n{label}")
