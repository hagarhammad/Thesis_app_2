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
    # --- FIXED: Weight Logic must be inside the button block to capture slider changes ---
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
        # A. Score Renewables
        s_area = df['Surface_Area'] if 'Surface_Area' in df.columns else 1.0
        df['Total_Surface'] = df['PercArea_PV_Potential'] + df['PercArea_Active_Solar_Potential']
        
        n_act = (df['Total_Surface'] - df['Total_Surface'].min()) / (df['Total_Surface'].max() - df['Total_Surface'].min() + 1e-6)
        n_surf_inv = 1 - (s_area - s_area.min()) / (s_area.max() - s_area.min() + 1e-6)
        df['Score_Renewables'] = ((n_act * 0.5) + (n_surf_inv * 0.5)).clip(0, 1)

        # B. Score Thermal
        n_heat = (df[col_heat] - df[col_heat].min()) / (df[col_heat].max() - df[col_heat].min() + 1e-6)
        n_over = 1 - (df[col_over] - df[col_over].min()) / (df[col_over].max() - df[col_over].min() + 1e-6)
        df['Score_Thermal'] = (n_heat * 0.5) + (n_over * 0.5)

        # C. Score Daylight
        n_sda = (df[col_sDA] - df[col_sDA].min()) / (df[col_sDA].max() - df[col_sDA].min() + 1e-6)
        n_ase = 1 - (df[col_ASE] - df[col_ASE].min()) / (df[col_ASE].max() - df[col_ASE].min() + 1e-6)
        df['Score_Daylight'] = (n_sda * 0.5) + (n_ase * 0.5)

        # D. Apply the Weights (Capturing the current slider position)
        df['Final_Score'] = (df['Score_Renewables'] * w_renew) + \
                            (df['Score_Thermal'] * current_w_energy) + \
                            (df['Score_Daylight'] * current_w_daylight)

        # Sort and Save
        st.session_state['top_10'] = df.sort_values('Final_Score', ascending=False).head(10)
        st.session_state['full_calc_df'] = df
        
        # Display feedback for verification
        st.success(f"Optimized for: Energy ({round(current_w_energy*100)}%) | Daylight ({round(current_w_daylight*100)}%)")

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
        
        # FIX: Dropdown now uses Global_ID for selection
        selected_global = st.selectbox("Select Building (Global ID):", top_10[col_global])
        
        # Link the selected Global ID back to the data
        case_data = top_10[top_10[col_global] == selected_global].iloc[0]
        current_id = case_data[col_id] # Used for 3D logic
        
        # --- DYNAMIC PERFORMANCE VS BASE CASE ---
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
                    st.metric(label, f"{round(c_val, 1)}", f"{round(diff_pct, 1)}% vs Base", 
                              delta_color="inverse" if data['inv'] else "normal")
        
        # Visualize 3D using the case data
        inputs_3d = [case_data[p] for p in params]
        ui_components.display_3d_model("Type_A", inputs_3d)

    with col_table:
        st.subheader("🏆 Selected Case Schedule")
        # Show Global_ID as the primary column in the table
        schedule_cols = [col_global] + params
        st.dataframe(top_10[schedule_cols], hide_index=True)
        st.info(f"Viewing: {selected_global} (Internal Case: {current_id})")

    # ==========================================
    # 8. PERFORMANCE DIAGNOSTICS (Updated for Global ID)
    # ==========================================
    st.divider()
    st.subheader(f"🧐 Performance Diagnostics: {selected_global}")
    
    # Define active_params globally within this block
    active_params = [p for p in params if full_df[p].max() > 0]
    top_10_means = top_10[params].mean()
    
    diag_cols = st.columns(len(params))
    for i, p in enumerate(params):
        with diag_cols[i]:
            case_val = case_data[p]
            t10_avg = top_10_means[p]
            st.markdown(f"#### {p.replace('_',' ')}")
            diff = case_val - t10_avg
            
            if abs(diff) < 0.05:
                st.write("⚖️ **Balanced**")
            elif diff > 0:
                st.write("⬆️ **Aggressive**")
            else:
                st.write("⬇️ **Conservative**")

    # ==========================================
    # 9. DYNAMIC MITIGATION (The "Fix" Logic)
    # ==========================================
    st.subheader("🛠️ Strategic Adjustments")
    
    best_ase_val = top_10[col_ASE].min()
    best_sda_val = top_10[col_sDA].max()
    best_ase_case = top_10[top_10[col_ASE] == best_ase_val].iloc[0]
    
    fixes = []
    if case_data[col_ASE] > best_ase_val:
        if 'Vertical_Louvre_Steps' in active_params:
            target_louver = best_ase_case['Vertical_Louvre_Steps']
            fixes.append(f"⚠️ **Glare (ASE):** {selected_global} has more glare than the best performers. **Fix:** Adjust *Louvers* toward {target_louver}m.")
        else:
            fixes.append(f"⚠️ **Glare (ASE):** High levels. **Fix:** Increase *Canopy Depth* or *Vertical Steps*.")

    if case_data[col_sDA] < best_sda_val:
        fixes.append(f"☀️ **Daylight (sDA):** Lower than top-tier options. **Fix:** Reduce *Balcony* depth or *Louver* thickness.")

    if fixes:
        for f in fixes:
            st.info(f)
    else:
        st.success("✅ **Balanced Performance:** No conflicts detected for this specific geometry.")
