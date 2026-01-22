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
col_global = 'Global_ID'
cases = 'Cases'
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
        return df[df[col] != 0]
    elif choice == "Excluded": 
        return df[df[col] == 0]
    return df

df_filtered = df_raw.copy()
for p in params:
    df_filtered = apply_filter(df_filtered, p, p.replace('_', ' '))

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

# ==========================================
# 6. CALCULATION ENGINE
# ==========================================
if st.button("🚀 Find Best Cases", use_container_width=True):
    if renew_choice == "Mandatory":
        w_renew, pool = 0.10, 0.90
    else:
        w_renew, pool = 0.0, 1.0

    current_w_energy = (slider_val / 100) * pool
    current_w_daylight = (daylight_display / 100) * pool
    
    df = df_filtered.copy()
    if df.empty:
        st.warning("No cases match your filter criteria.")
    else:
        # A. Score Calculations
        df['Total_Surface'] = df['PercArea_PV_Potential'] + df['PercArea_Active_Solar_Potential']
        n_act = (df['Total_Surface'] - df['Total_Surface'].min()) / (df['Total_Surface'].max() - df['Total_Surface'].min() + 1e-6)
        df['Score_Renewables'] = n_act.clip(0, 1)

        n_heat = (df[col_heat] - df[col_heat].min()) / (df[col_heat].max() - df[col_heat].min() + 1e-6)
        n_over = 1 - (df[col_over] - df[col_over].min()) / (df[col_over].max() - df[col_over].min() + 1e-6)
        df['Score_Thermal'] = (n_heat * 0.5) + (n_over * 0.5)

        n_sda = (df[col_sDA] - df[col_sDA].min()) / (df[col_sDA].max() - df[col_sDA].min() + 1e-6)
        n_ase = 1 - (df[col_ASE] - df[col_ASE].min()) / (df[col_ASE].max() - df[col_ASE].min() + 1e-6)
        df['Score_Daylight'] = (n_sda * 0.5) + (n_ase * 0.5)

        # B. Weighted Scoring
        df['Final_Score'] = (df['Score_Renewables'] * w_renew) + \
                            (df['Score_Thermal'] * current_w_energy) + \
                            (df['Score_Daylight'] * current_w_daylight)

        # C. Unique Binary Strategy Drop
        df['binary_signature'] = df[params].apply(lambda row: tuple(1 if x != 0 else 0 for x in row), axis=1)
        df = df.sort_values(by='Final_Score', ascending=False)
        top_df = df.drop_duplicates(subset=['binary_signature'], keep='first').head(10)
        
        st.session_state['top_10'] = top_df
        st.session_state['full_calc_df'] = df
        st.success("Optimized: Found unique architectural strategies.")

# ==========================================
# 7. OUTPUTS
# ==========================================
if 'top_10' in st.session_state:
    top_10 = st.session_state['top_10']
    full_df = st.session_state['full_calc_df']
    
    # Pre-fetch Base Case for calculations
    base_case_df = df_raw[df_raw[col_id].astype(str).str.contains('Base', case=False, na=False)]
    base_case = base_case_df.iloc[0] if not base_case_df.empty else None

    st.divider()
    col_viz, col_table = st.columns([2, 1])
    
    with col_viz:
        st.subheader("🧊 3D Building Form")
        selected_global = st.selectbox("Select Building (Global ID):", top_10[col_global])
        case_data = top_10[top_10[col_global] == selected_global].iloc[0]
        
        if base_case is not None:
            indicators = {'sDA (%)': (col_sDA, False), 'ASE (%)': (col_ASE, True), 'Winter Rad': (col_heat, False), 'Summer Rad': (col_over, True)}
            imp_cols = st.columns(4)
            for i, (label, (col_key, inv)) in enumerate(indicators.items()):
                b_val, c_val = base_case[col_key], case_data[col_key]
                diff_pct = ((c_val - b_val) / (b_val + 1e-6)) * 100
                with imp_cols[i]:
                    st.metric(label, f"{round(c_val, 1)}", f"{round(diff_pct, 1)}% vs Base", delta_color="inverse" if inv else "normal")
        
        inputs_3d = [case_data[p] for p in params]
        ui_components.display_3d_model("Type_A", inputs_3d)

    with col_table:
        st.subheader("🏆 Case Schedule")
        st.dataframe(top_10[[col_global, cases] + params], hide_index=True)
        st.info(f"Viewing Typology: {case_data[col_id]}")

    # ==========================================
    # 8. DIAGNOSTICS & ADJUSTMENTS
    # ==========================================
    st.divider()
    st.subheader(f"🧐 Performance Diagnostics: {selected_global}")
    
    top_10_means = top_10[params].mean()
    diag_cols = st.columns(len(params))
    
    for i, p in enumerate(params):
        with diag_cols[i]:
            st.markdown(f"#### {p.replace('_',' ')}")
            
            # --- THE EXCLUSION CHECK ---
            # If the user excluded this in the sidebar, both max and min in top_10 will be 0
            if top_10[p].max() == 0 and top_10[p].min() == 0:
                st.write("⚪ **Not Used**")
                st.caption("This feature is excluded from the current design strategy.")
            else:
                case_val, t10_avg = case_data[p], top_10_means[p]
                diff = case_val - t10_avg
                
                if abs(diff) < 0.05: 
                    st.write("⚖️ **Balanced**")
                    st.caption("Matches optimal range.")
                elif diff > 0: 
                    st.write("⬆️ **Aggressive**")
                    st.caption("Greater than average.")
                else: 
                    st.write("⬇️ **Conservative**")
                    st.caption("Lower than average.")

    # ==========================================
    # 9. STRATEGIC FIXES (With Thermal & Directional Logic)
    # ==========================================
    st.subheader("🛠️ Strategic Adjustments")
    fixes = []
    tol = 0.10
    
    # Benchmarks for comparison
    best_ase = top_10[col_ASE].min()
    best_sda = top_10[col_sDA].max()
    best_winter = top_10[col_heat].max()
    best_summer = top_10[col_over].min()

    # 1. Glare Check
    if case_data[col_ASE] > (best_ase * (1 + tol)) and case_data[col_ASE] > 10:
        fixes.append("⚠️ **Glare (ASE):** High levels detected. **Fix:** Increase *Louvers* or *Canopy* depth.")
    
    # 2. Daylight Check
    if case_data[col_sDA] < (best_sda * (1 - tol)):
        fixes.append("☀️ **Daylight (sDA):** Form is slightly dark. **Fix:** Reduce *Balcony* depth or *Louver* thickness.")

    # 3. Winter Heat gain (Using Recession vs Overhang Logic)
    if case_data[col_heat] < (best_winter * (1 - tol)):
        # Find if the best winter case uses positive or negative steps
        best_w_val = top_10[top_10[col_heat] == best_winter]['Vertical_Steps_Section'].values[0]
        step_type = "Overhang (+)" if best_w_val > 0 else "Recession (-)"
        fixes.append(f"❄️ **Winter Gain:** Low. Top performers use **{step_type}** steps (~{best_w_val}m).")

    # 4. Summer Heat gain
    if case_data[col_over] > (best_summer * (1 + tol)) and case_data[col_over] > (base_case[col_over] * 0.5):
        best_s_val = top_10[top_10[col_over] == best_summer]['Vertical_Steps_Section'].values[0]
        step_type = "Overhang (+)" if best_s_val > 0 else "Recession (-)"
        fixes.append(f"🔥 **Summer Heat:** High radiation. Try **{step_type}** steps (~{best_s_val}m).")
    
    # Display Fixes
    if fixes:
        for f in fixes:
            st.info(f)
    else:
        st.success("✅ **Optimal Geometry:** This case manages performance conflicts effectively.")

    # ==========================================
    # 10. EXECUTIVE SUMMARY
    # ==========================================
    st.divider()
    st.subheader("💬 Design Freedom")
    for p in params:
        if full_df[p].var() > 0:
            v_ratio = top_10[p].var() / (full_df[p].var() + 1e-6)
            if v_ratio < 0.20:
                st.write(f"**{p}** | 🔴 **STRICT CONSTRAINT**")
            elif v_ratio < 0.60:
                st.write(f"**{p}** | 🟡 **PREFERENCE**")
            else:
                st.write(f"**{p}** | 🟢 **ARTISTIC FREEDOM**")
