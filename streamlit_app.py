"""
LightWeight Streamlit App: Hurricane Paths

Displays hurricane paths for a given date using weather-api-demo
"""
import folium
import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
from streamlit_folium import st_folium
from datetime import datetime
import os

# client utilities for external API calls
import httpx
from typing import Dict, Any, Optional
from datetime import datetime, timedelta


# Visualization settings
MAP_CENTER = [25.0, -70.0]  # Center of Atlantic region
MAP_ZOOM = 5
DEFAULT_MAP_TILES = 'OpenStreetMap'

# Flag to force HTML rendering (set to True to bypass st_folium completely)
FORCE_HTML_RENDERING = False


# Page configuration
st.set_page_config(
    page_title="Hurricane Paths",
    page_icon="🌀",
    layout="wide",
    initial_sidebar_state="expanded"
)




class WeatherLabAPIClient:
    """Client for weather-lab-data-api"""
    
    def __init__(self, base_url: str = "https://weather-lab-data-api-production.up.railway.app"):
        self.base_url = base_url
        self.client = httpx.Client(timeout=30.0)
    
    def get_data(self, date: str) -> Dict[str, Any]:
        """Get hurricane data for a specific date"""
        url = f"{self.base_url}/data"
        params = {"date": date}
        try:
            response = self.client.get(url, params=params)
            response.raise_for_status()
            return response.json()
        except httpx.ConnectError as e:
            raise ConnectionError(f"Could not connect to API at {self.base_url}. Check your internet connection and API URL.") from e
        except httpx.TimeoutException as e:
            raise TimeoutError(f"API request timed out. The server at {self.base_url} may be slow or unavailable.") from e
        except httpx.HTTPStatusError as e:
            raise ValueError(f"API returned error {e.response.status_code}: {e.response.text}") from e
    
    def test_connection(self) -> bool:
        """Test if API is reachable"""
        try:
            response = self.client.get(f"{self.base_url}/health", timeout=5.0)
            return response.status_code == 200
        except Exception:
            return False
    
    def close(self):
        """Close the HTTP client"""
        self.client.close()

# Initialize API client in session state
if 'weather_client' not in st.session_state:
    # Allow API URL to be configured via environment variable or use default
    api_url = os.getenv('WEATHER_API_URL', 'https://weather-lab-data-api-production.up.railway.app')
    st.session_state.weather_client = WeatherLabAPIClient(base_url=api_url)


def extract_hurricane_tracks(records):
    """Extract hurricane tracks from weather data records."""
    tracks = {}
    
    for record in records:
        track_id = record.get('track_id')
        if not track_id:
            continue
        
        if track_id not in tracks:
            tracks[track_id] = {
                'records': [],
                'coordinates': []
            }
        
        tracks[track_id]['records'].append(record)
        
        # Extract coordinates
        lat = record.get('lat')
        lon = record.get('lon')
        if lat is not None and lon is not None:
            try:
                tracks[track_id]['coordinates'].append((float(lat), float(lon)))
            except (ValueError, TypeError):
                pass
    
    # Sort coordinates by valid_time if available
    for track_id, track_data in tracks.items():
        if track_data['records']:
            try:
                sorted_records = sorted(
                    track_data['records'],
                    key=lambda x: x.get('valid_time', '')
                )
                track_data['records'] = sorted_records
                track_data['coordinates'] = [
                    (float(r.get('lat', 0)), float(r.get('lon', 0)))
                    for r in sorted_records
                    if r.get('lat') is not None and r.get('lon') is not None
                ]
            except:
                pass
    
    return tracks


def get_hurricane_category(wind_speed_knots):
    """Get hurricane category based on wind speed."""
    if wind_speed_knots < 34:
        return "Tropical Depression"
    elif wind_speed_knots < 64:
        return "Tropical Storm"
    elif wind_speed_knots < 83:
        return "Category 1"
    elif wind_speed_knots < 96:
        return "Category 2"
    elif wind_speed_knots < 113:
        return "Category 3"
    elif wind_speed_knots < 137:
        return "Category 4"
    else:
        return "Category 5"


def create_hurricane_paths_map(hurricane_tracks):
    """Create map showing hurricane tracks."""
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
                popup=folium.Popup(f"Hurricane {track_id}", parse_html=False)
            ).add_to(m)
            
            # Add markers for start and end points
            if len(track_data['coordinates']) > 0:
                start_coord = track_data['coordinates'][0]
                end_coord = track_data['coordinates'][-1]
                
                # Start marker
                folium.Marker(
                    start_coord,
                    popup=folium.Popup(f"{track_id} Start", parse_html=False),
                    icon=folium.Icon(color='green', icon='play')
                ).add_to(m)
                
                # End marker
                folium.Marker(
                    end_coord,
                    popup=folium.Popup(f"{track_id} End", parse_html=False),
                    icon=folium.Icon(color='red', icon='stop')
                ).add_to(m)
    
    return m

def main():
    """Main page function."""
    st.header("Hurricane Paths")
    
    # API Configuration (in sidebar)
    with st.sidebar.expander("⚙️ API Settings"):
        api_url = st.text_input(
            "API URL",
            value=st.session_state.weather_client.base_url,
            help="Change the API endpoint URL if needed"
        )
        if api_url != st.session_state.weather_client.base_url:
            st.session_state.weather_client = WeatherLabAPIClient(base_url=api_url)
        
        # Test connection button
        if st.button("🔌 Test API Connection"):
            if st.session_state.weather_client.test_connection():
                st.success("✅ API is reachable!")
            else:
                st.error("❌ Cannot reach API. Check URL and network connection.")
    
    # Date selector
    selected_date = st.date_input(
        "Select Date",
        value=datetime.now().date(),
        help="Choose the date to view hurricane paths"
    )
    
    # Fetch weather data
    if st.button("Load Hurricane Data", type="primary"):
        with st.spinner("Fetching hurricane data..."):
            try:
                # Fetch weather data from weather-lab-data-api
                weather_data = st.session_state.weather_client.get_data(
                    date=selected_date.strftime('%Y-%m-%d')
                )
                
                # Store in session state
                st.session_state.paths_weather_data = weather_data
                st.session_state.paths_selected_date = selected_date
                st.success("Hurricane data loaded successfully!")
                
            except Exception as e:
                st.error(f"Error loading hurricane data: {e}")
                return
    
    # Display results if available
    if 'paths_weather_data' in st.session_state and st.session_state.paths_weather_data:
        weather_data = st.session_state.paths_weather_data
        records = weather_data.get('records', [])
        meta = weather_data.get('meta', {})
        
        if records:
            # Extract hurricane tracks
            hurricane_tracks = extract_hurricane_tracks(records)
            
            # Summary metrics
            col1, col2, col3 = st.columns(3)
            
            with col1:
                st.metric("Total Records", len(records))
            
            with col2:
                st.metric("Active Hurricanes", len(hurricane_tracks))
            
            with col3:
                if meta.get('cached'):
                    st.metric("Data Source", "Cached")
                else:
                    st.metric("Data Source", "Fresh")
            
            # Hurricane list
            st.subheader("Active Hurricanes")
            hurricane_list = []
            for track_id, track_data in hurricane_tracks.items():
                if track_data['coordinates']:
                    max_wind = max(record.get('maximum_sustained_wind_speed_knots', 0) or 0 for record in track_data['records'])
                    hurricane_list.append({
                        'Track ID': track_id,
                        'Records': len(track_data['records']),
                        'Max Wind Speed (knots)': round(max_wind, 1),
                        'Category': get_hurricane_category(max_wind)
                    })
            
            if hurricane_list:
                hurricane_df = pd.DataFrame(hurricane_list)
                st.dataframe(hurricane_df, use_container_width=True)
            
            # Create map with hurricane tracks
            st.subheader("Hurricane Paths Map")
            paths_map = create_hurricane_paths_map(hurricane_tracks)
            
            # Render map - use HTML if FORCE_HTML_RENDERING is True or if st_folium fails
            if FORCE_HTML_RENDERING:
                # Direct HTML rendering - bypasses JSON serialization completely
                map_html = paths_map._repr_html_()
                components.html(map_html, width=700, height=500, scrolling=False)
            else:
                # Try st_folium first, fallback to HTML if it fails
                try:
                    st_folium(paths_map, width=700, height=500, returned_objects=[])
                except Exception as e:
                    # Fallback: render as HTML to avoid JSON serialization issues
                    st.warning(f"Using HTML fallback due to serialization error. Set FORCE_HTML_RENDERING=True to skip st_folium.")
                    map_html = paths_map._repr_html_()
                    components.html(map_html, width=700, height=500, scrolling=False)
            
            # Hurricane details table
            st.subheader("Hurricane Records")
            records_df = pd.DataFrame(records)
            if not records_df.empty:
                # Select relevant columns
                display_columns = ['track_id', 'valid_time', 'lat', 'lon', 'maximum_sustained_wind_speed_knots']
                available_columns = [col for col in display_columns if col in records_df.columns]
                st.dataframe(records_df[available_columns], use_container_width=True)
                
                # Export button
                csv = records_df.to_csv(index=False)
                st.download_button(
                    label="Download Hurricane Data (CSV)",
                    data=csv,
                    file_name=f"hurricane_paths_{selected_date}.csv",
                    mime="text/csv"
                )
        else:
            st.info(f"No hurricane records found for {selected_date.strftime('%Y-%m-%d')}.")
    else:
        st.info("Select a date and click 'Load Hurricane Data' to view hurricane paths.")


# Run the page
main()

