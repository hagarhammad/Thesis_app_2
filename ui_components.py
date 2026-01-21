import streamlit as st
import plotly.graph_objects as go
import numpy as np

def display_3d_model(geometry_name, inputs):
    """
    Creates a 3D massing based on:
    inputs[0]: Vertical Steps
    inputs[1]: Horizontal Steps
    inputs[2]: Balcony Depth
    inputs[3]: Canopy Depth
    inputs[4]: Louvre Depth
    """
    
    # 1. Extract values from the inputs list
    v_steps = inputs[0]
    h_steps = inputs[1]
    balcony = inputs[2]
    canopy  = inputs[3]
    louvre  = inputs[4]

    # 2. Create the Building Main Mass (The 'Base')
    # We define a simple box using coordinates
    def create_box(x_range, y_range, z_range, color, name):
        return go.Mesh3d(
            x=[x_range[0], x_range[0], x_range[1], x_range[1], x_range[0], x_range[0], x_range[1], x_range[1]],
            y=[y_range[0], y_range[1], y_range[1], y_range[0], y_range[0], y_range[1], y_range[1], y_range[0]],
            z=[z_range[0], z_range[0], z_range[0], z_range[0], z_range[1], z_range[1], z_range[1], z_range[1]],
            i=[7, 0, 0, 0, 4, 4, 6, 6, 4, 0, 3, 2],
            j=[3, 4, 1, 2, 5, 6, 5, 2, 0, 1, 6, 3],
            k=[0, 7, 2, 3, 6, 7, 1, 1, 5, 5, 7, 6],
            opacity=0.8,
            color=color,
            name=name
        )

    # 3. Build the Geometry Layers
    fig = go.Figure()

    # Base Building (Scale 5x5x10 for example)
    fig.add_trace(create_box([0, 5], [0, 5], [0, 10], 'silver', 'Main Building'))

    # Add Vertical Steps (Modifying the facade)
    if v_steps != 0:
        fig.add_trace(create_box([0, 5], [5, 5 + v_steps], [0, 10], 'royalblue', 'Vertical Step'))

    # Add Balcony (A thin slab extending out)
    if balcony > 0:
        fig.add_trace(create_box([-balcony, 0], [1, 4], [2, 2.2], 'orange', 'Balcony'))

    # Add Canopy (At the top)
    if canopy > 0:
        fig.add_trace(create_box([0, 5], [0, 5 + canopy], [10, 10.2], 'forestgreen', 'PV Canopy'))

    # 4. Final Layout Settings
    fig.update_layout(
        scene=dict(
            xaxis=dict(nticks=4, range=[-5, 10]),
            yaxis=dict(nticks=4, range=[-5, 10]),
            zaxis=dict(nticks=4, range=[0, 12]),
            aspectmode='cube'
        ),
        margin=dict(r=0, l=0, b=0, t=0),
        showlegend=True
    )

    # 5. Display in Streamlit
    st.plotly_chart(fig, use_container_width=True)
