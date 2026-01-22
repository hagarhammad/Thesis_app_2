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
    # Added a unique prefix to the key to prevent DuplicateElementKey errors
    choice = st.sidebar.radio(label, ["Required", "Flexible", "Excluded"], horizontal=True, key=f"sidebar_{col}")
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
    # ==========================================
    # 8. DYNAMIC PERFORMANCE DIAGNOSTICS (FINAL)
    # ==========================================
    st.subheader(f"🧐 Strategic Synergy: {selected_global}")
    
    # Pretty names for architectural clarity
    pretty_names = {
        'Vertical_Steps_Section': 'Vertical Steps',
        'Horizontal_Steps_Plan': 'Horizontal Steps',
        'Balcony_Steps': 'Balcony',
        'PV_Canopy_Steps': 'Canopy Depth',
        'Vertical_Louvre_Steps': 'Louver Extrusion'
    }
    
    # Detect excluded parameters (all zeros after filtering)
    excluded_params = [
        p for p in params
        if df_filtered[p].nunique() == 1 and df_filtered[p].iloc[0] == 0
    ]
    
    # Safe correlation
    def safe_corr(a, b):
        if a.nunique() < 2 or b.nunique() < 2:
            return 0.0
        c = a.corr(b)
        return 0.0 if pd.isna(c) else c
    
    influence = {p: safe_corr(full_df[p], full_df['Final_Score']) for p in params}
    
    diag_cols = st.columns(len(params))
    
    for i, p in enumerate(params):
        with diag_cols[i]:
            st.markdown(f"#### {pretty_names[p]}")
    
            # If excluded → skip analysis
            if p in excluded_params:
                st.write("⚪ **Excluded from design — not evaluated.**")
                continue
    
            corr = influence[p]
            strength = abs(corr)
            direction = "Positive" if corr > 0 else "Negative"
    
            st.write(f"**Influence:** {direction} ({strength:.2f})")
    
            # Strength classification
            if strength < 0.15:
                st.caption("Minimal impact on performance.")
                st.write("No adjustment recommended.")
                continue
            elif strength < 0.35:
                st.caption("Moderate influence on performance.")
            else:
                st.caption("Strong driver of performance.")
    
            # Directional guidance
            current_val = case_data[p] if pd.notna(case_data[p]) else 0
            avg_val = full_df[p].mean()
    
            if corr > 0:
                if current_val < avg_val:
                    st.info("Higher values tend to improve performance.")
                else:
                    st.success("This parameter supports performance.")
            else:
                if current_val > avg_val:
                    st.info("Lower values tend to improve performance.")
                else:
                    st.success("This parameter supports performance.")
    
    
    # ==========================================
    # 9. STRATEGIC ADJUSTMENTS (FINAL)
    # ==========================================
    st.subheader("🛠️ Strategic Adjustments")
    
    fixes = []
    
    numeric_df = full_df.select_dtypes(include=[np.number])
    p25 = numeric_df.quantile(0.25)
    p75 = numeric_df.quantile(0.75)
    
    def safe_compare(val, threshold):
        return pd.notna(val) and pd.notna(threshold)
    
    # ASE – glare
    if safe_compare(case_data[col_ASE], p75.get(col_ASE, None)):
        if case_data[col_ASE] > p75[col_ASE]:
            fixes.append("High **ASE** indicates potential glare. Consider deeper shading or denser louvers.")
    
    # sDA – daylight
    if safe_compare(case_data[col_sDA], p25.get(col_sDA, None)):
        if case_data[col_sDA] < p25[col_sDA]:
            fixes.append("Low **sDA** suggests insufficient daylight. Reducing balcony depth or adjusting façade geometry may help.")
    
    # Winter radiation – passive gain
    if safe_compare(case_data[col_heat], p25.get(col_heat, None)):
        if case_data[col_heat] < p25[col_heat]:
            fixes.append("Low winter solar exposure. Increasing façade protrusions or adjusting step geometry may improve passive gains.")
    
    # Summer radiation – overheating
    if safe_compare(case_data[col_over], p75.get(col_over, None)):
        if case_data[col_over] > p75[col_over]:
            fixes.append("High summer radiation. Enhanced shading or deeper overhangs can reduce overheating risk.")
    
    if fixes:
        for f in fixes:
            st.info(f)
    else:
        st.success("Performance indicators fall within balanced percentile ranges.")
    
    
    # ==========================================
    # 10. DESIGN FREEDOM (FINAL)
    # ==========================================
    st.subheader("💬 Design Freedom")
    
    for p in params:
    
        # Excluded parameters → special message
        if p in excluded_params:
            st.write(f"**{pretty_names[p]}** | ⚪ Excluded from design — no freedom analysis.")
            continue
    
        # If no variation → constrained
        if top_10[p].nunique() < 2 or full_df[p].nunique() < 2:
            st.write(f"**{pretty_names[p]}** | 🔴 Limited flexibility — parameter shows almost no variation.")
            continue
    
        top_iqr = top_10[p].quantile(0.75) - top_10[p].quantile(0.25)
        full_iqr = full_df[p].quantile(0.75) - full_df[p].quantile(0.25)
    
        if full_iqr == 0 or pd.isna(full_iqr):
            ratio = 0
        else:
            ratio = top_iqr / (full_iqr + 1e-6)
    
        if ratio < 0.25:
            st.write(f"**{pretty_names[p]}** | 🔴 Limited flexibility — top performers converge tightly.")
        elif ratio < 0.60:
            st.write(f"**{pretty_names[p]}** | 🟡 Moderate flexibility — controlled variation among top cases.")
        else:
            st.write(f"**{pretty_names[p]}** | 🟢 High flexibility — wide range of successful configurations.")
