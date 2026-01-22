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
# 4. SIDEBAR FILTERS (Fixed for +/- Values)
# ==========================================
st.sidebar.header("Design Choices")

def apply_filter(df, col, label):
    choice = st.sidebar.radio(label, ["Required", "Flexible", "Excluded"], horizontal=True, key=f"filter_{col}")
    if choice == "Required": 
        # "Required" means the value is NOT zero (could be positive overhang or negative recession)
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
# 6. CALCULATION ENGINE (With Unique Binary Signature Logic)
# ==========================================
if st.button("🚀 Find Best Cases", use_container_width=True):
    # Weighting Logic
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
        # A. Score Calculations (Normalization)
        df['Total_Surface'] = df['PercArea_PV_Potential'] + df['PercArea_Active_Solar_Potential']
        n_act = (df['Total_Surface'] - df['Total_Surface'].min()) / (df['Total_Surface'].max() - df['Total_Surface'].min() + 1e-6)
        df['Score_Renewables'] = n_act.clip(0, 1)

        n_heat = (df[col_heat] - df[col_heat].min()) / (df[col_heat].max() - df[col_heat].min() + 1e-6)
        n_over = 1 - (df[col_over] - df[col_over].min()) / (df[col_over].max() - df[col_over].min() + 1e-6)
        df['Score_Thermal'] = (n_heat * 0.5) + (n_over * 0.5)

        n_sda = (df[col_sDA] - df[col_sDA].min()) / (df[col_sDA].max() - df[col_sDA].min() + 1e-6)
        n_ase = 1 - (df[col_ASE] - df[col_ASE].min()) / (df[col_ASE].max() - df[col_ASE].min() + 1e-6)
        df['Score_Daylight'] = (n_sda * 0.5) + (n_ase * 0.5)

        # B. Calculate Final Weighted Score
        df['Final_Score'] = (df['Score_Renewables'] * w_renew) + \
                            (df['Score_Thermal'] * current_w_energy) + \
                            (df['Score_Daylight'] * current_w_daylight)

        # C. BINARY SIGNATURE LOGIC (Your Request)
        # Create a pattern based on which components are present (1) or absent (0)
        # If a user 'Excludes' a param, it is already 0 in df_filtered, so the signature handles it.
        df['binary_signature'] = df[params].apply(lambda row: tuple(1 if x != 0 else 0 for x in row), axis=1)

        # Sort by Final Score (Best first)
        df = df.sort_values(by='Final_Score', ascending=False)

        # D. DROP DUPLICATE STRATEGIES
        # This ensures we get the best case for 10 DIFFERENT architectural patterns
        top_df = df.drop_duplicates(subset=['binary_signature'], keep='first').head(10)
        
        # Save to session state
        st.session_state['top_10'] = top_df
        st.session_state['full_calc_df'] = df
        
        st.success(f"Displaying 10 unique architectural patterns optimized for your criteria.")

# ==========================================
# 7. DYNAMIC OUTPUTS (Global ID focus)
# ==========================================
if 'top_10' in st.session_state:
    top_10 = st.session_state['top_10']
    full_df = st.session_state['full_calc_df']
    
    st.divider()
    col_viz, col_table = st.columns([2, 1])
    
    with col_viz:
        st.subheader("🧊 3D Building Form")
        selected_global = st.selectbox("Select Building (Global ID):", top_10[col_global])
        case_data = top_10[top_10[col_global] == selected_global].iloc[0]
        
        # Performance vs Base Case Comparison
        base_case_search = df_raw[df_raw[col_id].astype(str).str.contains('Base', case=False, na=False)]
        if not base_case_search.empty:
            base_case = base_case_search.iloc[0]
            indicators = {
                'sDA (%)': (col_sDA, False), 
                'ASE (%)': (col_ASE, True), 
                'Winter Rad': (col_heat, False), 
                'Summer Rad': (col_over, True)
            }
            imp_cols = st.columns(4)
            for i, (label, (col_key, inv)) in enumerate(indicators.items()):
                b_val, c_val = base_case[col_key], case_data[col_key]
                diff_pct = ((c_val - b_val) / (b_val + 1e-6)) * 100
                with imp_cols[i]:
                    st.metric(label, f"{round(c_val, 1)}", f"{round(diff_pct, 1)}% vs Base", 
                              delta_color="inverse" if inv else "normal")
        
        inputs_3d = [case_data[p] for p in params]
        ui_components.display_3d_model("Type_A", inputs_3d)

    with col_table:
        st.subheader("🏆 Case Schedule")
        
        display_cols = [col_global, cases] + params
        st.dataframe(top_10[display_cols], hide_index=True)
        
        selected_case_id = case_data[col_id]
        st.info(f"Viewing: {selected_global} (Typology: {selected_case_id})")
    # ==========================================
    # 8. PERFORMANCE DIAGNOSTICS: {selected_global}
    # ==========================================
    st.divider()
    st.subheader(f"🧐 Performance Diagnostics: {selected_global}")
    
    top_10_means = top_10[params].mean()
    diag_cols = st.columns(len(params))
    
    for i, p in enumerate(params):
        with diag_cols[i]:
            st.markdown(f"#### {p.replace('_',' ')}")
            
            if full_df[p].max() == 0 and full_df[p].min() == 0:
                st.write("⚪ **Excluded**")
                st.caption("Feature is disabled.")
            else:
                case_val = case_data[p]
                t10_avg = top_10_means[p]
                diff = case_val - t10_avg
                
                # RESTORED: Detailed Architectural Captions
                if abs(diff) < 0.05:
                    st.write("⚖️ **Balanced**")
                    st.caption("Matches the optimal range of the top performers.")
                elif diff > 0:
                    st.write("⬆️ **Aggressive**")
                    st.caption("Higher than average. Prioritizes shading/form over light penetration.")
                else:
                    st.write("⬇️ **Conservative**")
                    st.caption("Lower than average. Favors sky visibility and maximum daylight.")
                    

    # ==========================================
    # 9. DYNAMIC STRATEGIC ADJUSTMENTS (With +/- Logic)
    # ==========================================
    st.subheader("🛠️ Case-Specific Strategic Adjustments")
    active_params = [p for p in params if full_df[p].max() != 0 or full_df[p].min() != 0]
    
    # Identify benchmarks
    best_ase = top_10[col_ASE].min()
    best_sda = top_10[col_sDA].max()
    best_winter = top_10[col_heat].max()
    best_summer = top_10[col_over].min()
    
    fixes = []
    tolerance = 0.10 

    # Glare and Daylight checks
    if case_data[col_ASE] > (best_ase * (1 + tolerance)) and case_data[col_ASE] > 10:
        fixes.append("⚠️ **Glare (ASE):** This case has higher glare than the top performers. **Fix:** Increase *Louvers* or *Canopy Depth*.")
    if case_data[col_sDA] < (best_sda * (1 - tolerance)):
        fixes.append("☀️ **Daylight (sDA):** This form is darker than the best options. **Fix:** Reduce *Balcony* depth or *Louver* thickness.")

    # Thermal Checks (Winter/Summer) with Step Directional Logic
    # [Image of architectural diagram showing the difference between building overhangs and building recessions for solar shading]
    if case_data[col_heat] < (best_winter * (1 - tolerance)):
        best_w_case = top_10[top_10[col_heat] == best_winter].iloc[0]
        best_w_val = best_w_case['Vertical_Steps_Section']
        step_type = "Overhang (+)" if best_w_val > 0 else "Recession (-)"
        fixes.append(f"❄️ **Winter Gain:** Low solar gain. Top performers use **{step_type}** steps (~{best_w_val}m) to catch low winter sun.")

    if case_data[col_over] > (best_summer * (1 + tolerance)) and case_data[col_over] > (base_case[col_over] * 0.5):
        best_s_case = top_10[top_10[col_over] == best_summer].iloc[0]
        best_s_val = best_s_case['Vertical_Steps_Section']
        step_type = "Overhang (+)" if best_s_val > 0 else "Recession (-)"
        fixes.append(f"🔥 **Summer Heat:** High radiation. Try **{step_type}** steps (~{best_s_val}m) or increasing *Canopy Depth*.")

    if fixes:
        for f in fixes: st.info(f)
    else:
        st.success("✅ **Balanced Performance:** This specific geometry manages all conflicts effectively.")
        
    # ==========================================
    # 10. EXECUTIVE DESIGN SUMMARY (Architectural Logic)
    # ==========================================
    st.divider()
    st.subheader("💬 Design Freedom & Constraints")
    st.info("This summary identifies where you must follow the data and where you can use your artistic intuition.")
    
    active_params = [p for p in params if full_df[p].max() != 0 or full_df[p].min() != 0]
    
    for p in active_params:
        # We look at how much the Top 10 "agree" on this parameter
        if full_df[p].var() > 0:
            v_ratio = top_10[p].var() / (full_df[p].var() + 1e-6)
            mean_top = top_10[p].mean()
            mean_all = full_df[p].mean()
            
            direction = "increasing" if mean_top > mean_all else "reducing"
            
            # --- ARCHITECTURAL CLASSIFICATION ---
            if v_ratio < 0.20:
                # High agreement = Architect has NO freedom here
                role = "🔴 **STRICT CONSTRAINT**"
                advice = f"The data is very rigid here. To hit these targets, you **must** focus on {direction} {p.replace('_',' ')}."
            elif v_ratio < 0.60:
                # Moderate agreement = Preferred range
                role = "🟡 **DESIGN PREFERENCE**"
                advice = f"There is a clear trend toward {direction} this value, but you have some room to negotiate the dimensions."
            else:
                # Low agreement = Complete artistic freedom
                role = "🟢 **ARTISTIC FREEDOM**"
                advice = f"Performance is stable regardless of this value. You can set {p.replace('_',' ')} based purely on **aesthetic preference**."
            
            st.markdown(f"**{p.replace('_',' ')}** | {role}")
            st.write(advice)
