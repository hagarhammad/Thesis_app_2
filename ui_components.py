import streamlit as st
import plotly.graph_objects as go

# ==========================================
# 1. 3D HELPER FUNCTIONS (Your original logic)
# ==========================================

def get_box_mesh(x, y, z, dx, dy, dz, color='#E6CDCF', opacity=1.0, name='Module'):
    return go.Mesh3d(
        x=[x, x+dx, x+dx, x, x, x+dx, x+dx, x],
        y=[y, y, y+dy, y+dy, y, y, y+dy, y+dy],
        z=[z, z, z, z, z+dz, z+dz, z+dz, z+dz],
        i=[7, 0, 0, 0, 4, 4, 6, 6, 4, 0, 3, 2],
        j=[3, 4, 1, 2, 5, 6, 5, 2, 0, 1, 6, 3],
        k=[0, 7, 2, 3, 6, 7, 1, 1, 5, 5, 7, 6],
        color=color, opacity=opacity, flatshading=True, name=name
    )

def get_vertical_surface(x, y_front, z_bottom, depth, height, color='#999999', opacity=0.8):
    return go.Mesh3d(
        x=[x, x, x, x],
        y=[y_front, y_front - depth, y_front - depth, y_front],
        z=[z_bottom, z_bottom, z_bottom + height, z_bottom + height],
        i=[0, 0], j=[1, 2], k=[2, 3],
        color=color, opacity=opacity, flatshading=True, name='Louver'
    )

def get_side_surface(x, y_start, y_end, z_bottom, height, color='#B87E82', opacity=1.0):
    return go.Mesh3d(
        x=[x, x, x, x],
        y=[y_start, y_end, y_end, y_start],
        z=[z_bottom, z_bottom, z_bottom + height, z_bottom + height],
        i=[0, 0], j=[1, 2], k=[2, 3],
        color=color, opacity=opacity, flatshading=True, name='SideFiller'
    )

def get_horizontal_surface(x_start, x_width, y_start, depth, z_level, color='#8A5A5E', opacity=1.0):
    return go.Mesh3d(
        x=[x_start, x_start + x_width, x_start + x_width, x_start],
        y=[y_start, y_start, y_start - depth, y_start - depth],
        z=[z_level, z_level, z_level, z_level],
        i=[0, 0], j=[1, 2], k=[2, 3],
        color=color, opacity=opacity, flatshading=True, name='Canopy'
    )

def get_frontal_surface(x_start, x_width, y, z_bottom, height, color='#E6CDCF', opacity=0.6):
    return go.Mesh3d(
        x=[x_start, x_start + x_width, x_start + x_width, x_start],
        y=[y, y, y, y],
        z=[z_bottom, z_bottom, z_bottom + height, z_bottom + height],
        i=[0, 0], j=[1, 2], k=[2, 3],
        color=color, opacity=opacity, flatshading=True, name='Handrail'
    )

# ==========================================
# 2. MAIN 3D GENERATOR
# ==========================================

def display_3d_model(geometry_type, inputs):
    """Generates the Modular 3D Building based on CSV/Slider inputs."""
    
    # Unpack Inputs (These come from the CSV row in app.py)
    try:
        step_depth_sec = inputs[0]
        step_depth_plan = inputs[1]
        balcony_depth = inputs[2]
        canopy_depth = inputs[3]
        louvre_depth = inputs[4]
    except IndexError:
        st.error("Error: Not enough input parameters.")
        return

    # Define Module Dimensions
    MOD_W = 1.8; MOD_D = 7.2; MOD_H = 3.3
    rows = 3; cols = 3 # Forced to your 3-story, 3-module request

    # Visual Flip Logic
    vis_step_sec = -step_depth_sec
    vis_step_plan = step_depth_plan

    traces = []
    
    for r in range(rows):         
        for c in range(cols):     
            pos_x = c * MOD_W
            pos_z = r * MOD_H
            pos_y = (r * vis_step_sec) + (c * vis_step_plan)
            
            # --- CANOPY ANCHOR LOGIC ---
            if r == rows - 1:
                anchor_y = pos_y 
            else:
                pos_y_above = ((r + 1) * vis_step_sec) + (c * vis_step_plan)
                anchor_y = pos_y_above

            canopy_start_y = anchor_y - balcony_depth if balcony_depth > 0 else anchor_y

            # 1. CORE ROOM
            traces.append(get_box_mesh(pos_x, pos_y, pos_z, MOD_W, MOD_D, MOD_H, '#E6CDCF', 1.0, f'Room {r}-{c}'))
            
            # 2. START COLUMN FILLER
            if c == 0 and abs(vis_step_plan) > 0.01:
                filler_start_y = pos_y - vis_step_plan
                traces.append(get_side_surface(pos_x, filler_start_y, pos_y, pos_z, MOD_H, '#B87E82'))

            # 3. BALCONY
            if balcony_depth > 0:
                traces.append(get_box_mesh(pos_x, pos_y - balcony_depth, pos_z, MOD_W, balcony_depth, 0.2, '#B87E82'))
                traces.append(get_frontal_surface(pos_x, MOD_W, pos_y - balcony_depth, pos_z, 0.9, '#E6CDCF', 0.4))

            # 4. CANOPIES
            if canopy_depth > 0:
                canopy_z = pos_z + MOD_H - 0.001 
                traces.append(get_horizontal_surface(pos_x, MOD_W, canopy_start_y, canopy_depth, canopy_z, '#8A5A5E'))
                if balcony_depth > 0:
                    traces.append(get_horizontal_surface(pos_x, MOD_W, anchor_y, balcony_depth, canopy_z, '#8A5A5E'))
            
            # 5. LOUVERS
            if louvre_depth > 0:
                left_louver_y = pos_y - vis_step_plan if (c == 0 and abs(vis_step_plan) > 0.01) else pos_y
                traces.append(get_vertical_surface(pos_x, left_louver_y, pos_z, louvre_depth, MOD_H, '#999999', 0.8))
                traces.append(get_vertical_surface(pos_x + MOD_W, pos_y, pos_z, louvre_depth, MOD_H, '#999999', 0.8))

    # CONFIGURE SCENE
    fig = go.Figure(data=traces)
    fig.update_layout(
        scene=dict(
            xaxis=dict(visible=False), yaxis=dict(visible=False), zaxis=dict(visible=False),
            aspectmode='data',
            camera=dict(eye=dict(x=1.5, y=-1.5, z=0.8))
        ),
        margin=dict(r=0, l=0, b=0, t=0), height=500, showlegend=False,
        paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)'
    )
    st.plotly_chart(fig, use_container_width=True, config={'scrollZoom': True})
