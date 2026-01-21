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
        st.info(f"Viewing: {selected_global} (Typology: {current_id})")

    # ==========================================
    # 8. PERFORMANCE DIAGNOSTICS: {selected_global}
    # ==========================================
    st.divider()
    st.subheader(f"🧐 Performance Diagnostics: {selected_global}")
    
    active_params = [p for p in params if full_df[p].max() > 0]
    top_10_means = top_10[params].mean()
    
    diag_cols = st.columns(len(params))
    for i, p in enumerate(params):
        with diag_cols[i]:
            st.markdown(f"#### {p.replace('_',' ')}")
            
            # CHECK: If the parameter is excluded (Max value is 0 in the filtered set)
            if full_df[p].max() == 0:
                st.write("⚪ **Excluded**")
                st.caption("This feature is currently disabled via the sidebar filters.")
            else:
                case_val = case_data[p]
                t10_avg = top_10_means[p]
                diff = case_val - t10_avg
                
                # Compare this case to the "winning average"
                if abs(diff) < 0.05:
                    st.write("⚖️ **Balanced**")
                    st.caption("Matches the optimal range found in the top performers.")
                elif diff > 0:
                    st.write("⬆️ **Aggressive**")
                    st.caption(f"Uses more than the average top case. Prioritizes shading/form over light.")
                else:
                    st.write("⬇️ **Conservative**")
                    st.caption(f"Uses less than the average top case. Favors sky visibility/light.")

    # ==========================================
    # 9. DYNAMIC STRATEGIC ADJUSTMENTS (With Tolerance)
    # ==========================================
    st.subheader("🛠️ Case-Specific Strategic Adjustments")
    
    active_params = [p for p in params if full_df[p].max() > 0]
    
    # Identify benchmarks
    best_ase = top_10[col_ASE].min()
    best_sda = top_10[col_sDA].max()
    best_winter = top_10[col_heat].max()
    best_summer = top_10[col_over].min()
    
    fixes = []
    # Use a 10% tolerance so we don't flag minor differences
    tolerance = 0.10 

    # 1. GLARE CHECK: Only flag if ASE is > 10% worse than the best winner AND > 10% absolute
    if case_data[col_ASE] > (best_ase * (1 + tolerance)) and case_data[col_ASE] > 10:
        fixes.append(f"⚠️ **Glare (ASE):** This case has higher glare than the top performers. **Fix:** Increase *Louvers* or *Canopy Depth*.")

    # 2. DAYLIGHT CHECK: Only flag if sDA is > 10% lower than the best winner
    if case_data[col_sDA] < (best_sda * (1 - tolerance)):
        fixes.append(f"☀️ **Daylight (sDA):** This form is slightly darker than the best options. **Fix:** Reduce *Balcony* depth or *Louver* thickness.")

    # 3. WINTER RAD: Only flag if it's significantly lower than the best winter case
    if case_data[col_heat] < (best_winter * (1 - tolerance)):
        # Find a case that did better in winter to suggest a value
        best_w_val = top_10[top_10[col_heat] == best_winter]['Vertical_Steps_Section'].values[0]
        fixes.append(f"❄️ **Winter Heat Gain:** Low solar gain. **Fix:** Try *Vertical Steps* closer to {best_w_val}m to allow deeper winter sun.")

    # 4. SUMMER RAD: Only flag if Summer Rad is within 20% of the Base Case 
    # (If it's already 79% better than Base, don't flag it!)
    if case_data[col_over] > (best_summer * (1 + tolerance)) and case_data[col_over] > (base_case[col_over] * 0.5):
        fixes.append(f"🔥 **Summer Overheating:** Could be further optimized. **Fix:** Increase *Canopy* or *Horizontal Steps*.")

    # DISPLAY THE FIXES
    if fixes:
        for f in fixes:
            st.info(f)
    else:
        st.success("✅ **Optimal Performance:** This specific geometry is performing at the top of its class across all metrics.")
    
    # ==========================================
    # 10. EXECUTIVE DESIGN SUMMARY
    # ==========================================
    st.divider()
    st.subheader("💬 Executive Design Summary")
    
    # Analyze only parameters that are not excluded and have variation
    summary_params = [p for p in params if full_df[p].max() > 0]
    
    if summary_params:
        for p in summary_params:
            # Calculate metrics for the summary
            mean_all = full_df[p].mean()
            mean_top = top_10[p].mean()
            
            # Variance check: Does the Top 10 agree on this value?
            if full_df[p].var() > 0:
                v_ratio = top_10[p].var() / (full_df[p].var() + 1e-6)
                direction = "higher values" if mean_top > mean_all else "lower values"
                
                # Assign Architectural Roles based on statistical convergence
                if v_ratio < 0.25:
                    role = "a **Fixed Requirement** for this performance level."
                elif v_ratio < 0.65:
                    role = "a **Critical Priority** with high consistency among winners."
                else:
                    role = "a **Flexible Feature** (multiple values work; adjust for aesthetics)."
                
                st.write(f"• Top designs prefer **{direction}** for **{p.replace('_',' ')}**. In this scenario, it is {role}")
    else:
        st.write("No active parameters to summarize. Please adjust sidebar filters.")
