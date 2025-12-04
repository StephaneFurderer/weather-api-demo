"""
Test Folium Map with Streamlit
Lightweight test application with dummy hurricane data
"""
import folium
import streamlit as st
import pandas as pd
from streamlit_folium import st_folium
from datetime import datetime


# Page configuration
st.set_page_config(
    page_title="Folium Map Test",
    page_icon="🗺️",
    layout="wide"
)

st.title("🗺️ Folium Map Test")
st.markdown("Testing Folium maps with dummy hurricane track data")

# Dummy hurricane track data
# Format matches what create_hurricane_paths_map expects
DUMMY_HURRICANE_TRACKS = {
    'Hurricane_Alpha': {
        'records': [
            {'track_id': 'Hurricane_Alpha', 'lat': 25.0, 'lon': -70.0, 'valid_time': '2024-09-23 00:00:00'},
            {'track_id': 'Hurricane_Alpha', 'lat': 26.5, 'lon': -71.5, 'valid_time': '2024-09-23 06:00:00'},
            {'track_id': 'Hurricane_Alpha', 'lat': 28.0, 'lon': -73.0, 'valid_time': '2024-09-23 12:00:00'},
            {'track_id': 'Hurricane_Alpha', 'lat': 29.5, 'lon': -74.5, 'valid_time': '2024-09-23 18:00:00'},
        ],
        'coordinates': [
            (25.0, -70.0),
            (26.5, -71.5),
            (28.0, -73.0),
            (29.5, -74.5),
        ]
    },
    'Hurricane_Beta': {
        'records': [
            {'track_id': 'Hurricane_Beta', 'lat': 20.0, 'lon': -65.0, 'valid_time': '2024-09-23 00:00:00'},
            {'track_id': 'Hurricane_Beta', 'lat': 21.5, 'lon': -66.5, 'valid_time': '2024-09-23 06:00:00'},
            {'track_id': 'Hurricane_Beta', 'lat': 23.0, 'lon': -68.0, 'valid_time': '2024-09-23 12:00:00'},
        ],
        'coordinates': [
            (20.0, -65.0),
            (21.5, -66.5),
            (23.0, -68.0),
        ]
    },
    'Hurricane_Gamma': {
        'records': [
            {'track_id': 'Hurricane_Gamma', 'lat': 30.0, 'lon': -75.0, 'valid_time': '2024-09-23 00:00:00'},
            {'track_id': 'Hurricane_Gamma', 'lat': 31.0, 'lon': -76.0, 'valid_time': '2024-09-23 06:00:00'},
            {'track_id': 'Hurricane_Gamma', 'lat': 32.0, 'lon': -77.0, 'valid_time': '2024-09-23 12:00:00'},
            {'track_id': 'Hurricane_Gamma', 'lat': 33.0, 'lon': -78.0, 'valid_time': '2024-09-23 18:00:00'},
            {'track_id': 'Hurricane_Gamma', 'lat': 34.0, 'lon': -79.0, 'valid_time': '2024-09-24 00:00:00'},
        ],
        'coordinates': [
            (30.0, -75.0),
            (31.0, -76.0),
            (32.0, -77.0),
            (33.0, -78.0),
            (34.0, -79.0),
        ]
    }
}


def create_test_map(hurricane_tracks):
    """Create a Folium map with hurricane tracks - same function as main app"""
    # Center of Atlantic region
    MAP_CENTER = [25.0, -70.0]
    
    m = folium.Map(
        location=MAP_CENTER,
        zoom_start=5,
        tiles='OpenStreetMap'
    )
    
    # Color palette for different hurricanes
    colors = ['red', 'blue', 'green', 'purple', 'orange', 'darkred', 'lightred', 'beige', 'darkblue', 'darkgreen']
    
    for idx, (track_id, track_data) in enumerate(hurricane_tracks.items()):
        if track_data['coordinates']:
            color = colors[idx % len(colors)]
            
            # Add polyline for track
            folium.PolyLine(
                track_data['coordinates'],
                color=color,
                weight=4,
                opacity=0.8,
                popup=f"Hurricane {track_id}"
            ).add_to(m)
            
            # Add markers for start and end points
            if len(track_data['coordinates']) > 0:
                start_coord = track_data['coordinates'][0]
                end_coord = track_data['coordinates'][-1]
                
                # Start marker
                folium.Marker(
                    start_coord,
                    popup=f"{track_id} Start",
                    icon=folium.Icon(color='green', icon='play')
                ).add_to(m)
                
                # End marker
                folium.Marker(
                    end_coord,
                    popup=f"{track_id} End",
                    icon=folium.Icon(color='red', icon='stop')
                ).add_to(m)
    
    return m


# Display information
st.sidebar.header("Test Information")
st.sidebar.info("""
This test uses dummy hurricane track data to verify Folium maps work correctly.

**Expected Format:**
- Dictionary with track IDs as keys
- Each track has 'coordinates' list of (lat, lon) tuples
- PolyLines connect the coordinates
- Start/end markers show beginning and end of tracks
""")

st.sidebar.metric("Number of Tracks", len(DUMMY_HURRICANE_TRACKS))

# Display track details
with st.expander("📊 View Dummy Data Structure"):
    st.json({
        track_id: {
            'num_coordinates': len(track_data['coordinates']),
            'coordinates': track_data['coordinates'],
            'num_records': len(track_data['records'])
        }
        for track_id, track_data in DUMMY_HURRICANE_TRACKS.items()
    })

# Create and display map
st.subheader("🗺️ Hurricane Tracks Map")
st.info("You should see 3 hurricane tracks with colored lines, green start markers, and red end markers.")

try:
    test_map = create_test_map(DUMMY_HURRICANE_TRACKS)
    st_folium(test_map, width=700, height=500)
    st.success("✅ Map rendered successfully!")
except Exception as e:
    st.error(f"❌ Error creating map: {e}")
    st.exception(e)

# Display coordinates table
st.subheader("📍 Track Coordinates")
for track_id, track_data in DUMMY_HURRICANE_TRACKS.items():
    st.write(f"**{track_id}** ({len(track_data['coordinates'])} points):")
    coords_df = pd.DataFrame(track_data['coordinates'], columns=['Latitude', 'Longitude'])
    st.dataframe(coords_df, use_container_width=True)

st.markdown("---")
st.caption("If you can see the map above with colored lines and markers, Folium is working correctly! 🎉")

