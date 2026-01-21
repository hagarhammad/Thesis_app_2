import streamlit as st
import pandas as pd
import numpy as np
import ui_components  # Your custom 3D drawing script
from scipy.stats import ks_2samp

# --- 1. SETTINGS & FILTERS (Original Style Kept) ---
st.set_page_config(layout="wide")

@st.cache_data
def load_data():
    return pd.read_csv('your_data.csv')

df_raw = load_data()

# The "Original Appearance" Design Filters you liked
st.sidebar.header("🛠️ Design Choices")
def apply_filter(df, col, label):
    # Keeping the radio style from your first request
    choice = st.sidebar.radio(f"{label}", ["Available", "Mandatory", "Ignored"], horizontal=True)
    if choice == "Mandatory": return df[df[col] > 0]
    elif choice == "Ignored": return df[df[col] == 0]
    return df

df_filtered = apply_filter(df_raw, 'Vertical_Louvre_Steps', "Louvers")
df_filtered = apply_filter(df_filtered, 'Balcony_Steps', "Balcony")
df_filtered = apply_filter(df_filtered, 'PV_Canopy_Steps', "Canopy")
df_filtered = apply_filter(df_filtered, 'Vertical_Steps_Section', "Vertical Steps")
df_filtered = apply_filter(df_filtered, 'Horizontal_Steps_Plan', "Horizontal Steps")

# --- 2. PRIORITY SECTION ---
st.title("🏛️ Architectural Case Optimizer")

st.subheader("⚖️ Priority Balance")
energy_val = st.select_slider("Energy (Winter/Summer) vs Daylight (sDA/ASE)", options=list(range(0, 101)), value=50)
daylight_val = 100 - energy_val

c1, c2 = st.columns(2)
c1.metric("⚡ Energy Weight", f"{energy_val}%")
c2.metric("☀️ Daylight Weight", f"{daylight_val}%")

renew_choice = st.radio("Renewable Energy Importance:", ["Ignored", "Mandatory"], horizontal=True)

# --- 3. THE CALCULATION ENGINE ---
if st.button("🚀 Find Top 10 Best Cases", use_container_width=True):
    df = df_filtered.copy()
    
    # [Calculation logic for Score_Renewables, Score_Thermal, Score_Daylight remains same as before]
    # ... (insert the score calculation block here) ...

    # Final Ranking
    w_renew = 0.10 if renew_choice == "Mandatory" else 0.0
    multiplier = 0.9 if renew_choice == "Mandatory" else 1.0
    df['Final_Score'] = (df['Score_Renewables'] * w_renew) + \
                        (df['Score_Thermal'] * (energy_val/100 * multiplier)) + \
                        (df['Score_Daylight'] * (daylight_val/100 * multiplier))

    top_10 = df.sort_values('Final_Score', ascending=False).head(10)
    st.session_state['top_10_results'] = top_10

# --- 4. 3D VISUALIZATION OF CASES ---
if 'top_10_results' in st.session_state:
    results = st.session_state['top_10_results']
    
    st.divider()
    st.subheader("🧊 Top 10 Building Forms")
    
    # We create a dropdown to pick which of the top 10 to visualize
    case_ids = results['Cases_ID'].tolist()
    selected_id = st.selectbox("Select a Case ID to visualize its 3D form:", case_ids)
    
    # Get the parameters for the SELECTED case
    case_data = results[results['Cases_ID'] == selected_id].iloc[0]
    
    # Map your CSV columns to the 5 inputs your 3D function expects
    current_inputs = [
        case_data['Vertical_Steps_Section'],
        case_data['Horizontal_Steps_Plan'],
        case_data['Balcony_Steps'],
        case_data['PV_Canopy_Steps'],
        case_data['Vertical_Louvre_Steps']
    ]

    col_3d, col_stats = st.columns([2, 1])
    
    with col_3d:
        # Drawing the building based on the CSV numbers, NOT user sliders
        ui_components.display_3d_model("your_geometry_name", current_inputs)
    
    with col_stats:
        st.write("**Case Performance:**")
        st.json({
            "sDA": f"{case_data['sDA']}%",
            "ASE": f"{case_data['ASE']}%",
            "Winter Rad": case_data['Winter_Average_Radation_kWh/m2'],
            "Summer Rad": case_data['Summer_Average_Radation_kWh/m2']
        })

    # --- 5. STATISTICAL INSIGHTS ---
    # ... (insert the Architect Insight loop here) ...

    # --- ARCHITECT INSIGHTS ---
    st.subheader("🧐 Design Insights")
    params = ['Vertical_Steps_Section', 'Horizontal_Steps_Plan', 'Balcony_Steps', 'PV_Canopy_Steps', 'Vertical_Louvre_Steps']
    
    for p in params:
        mean_all, mean_top = df[p].mean(), top_10[p].mean()
        var_all, var_top = df[p].var(), top_10[p].var()
        v_ratio = var_top / var_all if var_all > 0 else 1
        _, p_val = ks_2samp(df[p], top_10[p])
        
        direction = "higher values" if mean_top > mean_all else "lower values"
        stability = "critical for performance" if v_ratio < 0.8 else "allows for flexibility"
        significance = "This change is statistically meaningful." if p_val < 0.05 else "This change could be random."
        
        st.info(f"**{p.replace('_',' ')}**: Top designs prefer **{direction}**. This parameter is **{stability}**. {significance}")
