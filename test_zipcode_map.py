"""
Zip Code Volume Map Visualization
Streamlit app to visualize volume data by US zip code on an interactive map
Uses Plotly for easier zip code boundary visualization
"""
import folium
import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
import json
from typing import Dict, List, Tuple
import io

# Try to import plotly for better zip code mapping
try:
    import plotly.express as px
    import plotly.graph_objects as go
    PLOTLY_AVAILABLE = True
except ImportError:
    PLOTLY_AVAILABLE = False
    st.warning("⚠️ Plotly not installed. Install with: pip install plotly")

# Try to import geopandas for easier GeoJSON handling
try:
    import geopandas as gpd
    GEOPANDAS_AVAILABLE = True
except ImportError:
    GEOPANDAS_AVAILABLE = False

# Try to import requests for downloading boundaries
try:
    import requests
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False

# Try to import uszipcode for zip code data
try:
    from uszipcode import SearchEngine
    USZIPCODE_AVAILABLE = True
except ImportError:
    USZIPCODE_AVAILABLE = False

# Page configuration
st.set_page_config(
    page_title="Zip Code Volume Map",
    page_icon="🗺️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Flag to force HTML rendering (set to True to bypass st_folium completely)
FORCE_HTML_RENDERING = False

st.title("🗺️ Zip Code Volume Map")
st.markdown("Visualize volume data by US zip code with proportional coloring")

# Sample data for testing
SAMPLE_DATA = """zip,volume
10001,1500
10002,2300
10003,1800
90210,3200
90211,2100
60601,2800
60602,1900
77001,2500
77002,1700
33101,3000
33102,2200
"""


def load_zipcode_data(data_input: str) -> pd.DataFrame:
    """Load zip code and volume data from CSV string or file."""
    try:
        # Try to read as CSV string
        df = pd.read_csv(io.StringIO(data_input))
        
        # Validate required columns
        if 'zip' not in df.columns or 'volume' not in df.columns:
            raise ValueError("Data must contain 'zip' and 'volume' columns")
        
        # Ensure zip codes are strings and volumes are numeric
        df['zip'] = df['zip'].astype(str).str.zfill(5)  # Pad to 5 digits
        df['volume'] = pd.to_numeric(df['volume'], errors='coerce')
        
        # Remove rows with invalid volumes
        df = df.dropna(subset=['volume'])
        
        return df
    except Exception as e:
        st.error(f"Error loading data: {e}")
        return pd.DataFrame()


def calculate_percentages(df: pd.DataFrame) -> pd.DataFrame:
    """Calculate volume percentages for each zip code."""
    df = df.copy()
    total_volume = df['volume'].sum()
    if total_volume > 0:
        df['percentage'] = (df['volume'] / total_volume) * 100
        df['percentage'] = df['percentage'].round(2)
    else:
        df['percentage'] = 0.0
    return df


def get_color_for_percentage(percentage: float, max_percentage: float) -> str:
    """Get color based on percentage (darker = higher percentage)."""
    if max_percentage == 0:
        return '#808080'  # Gray
    
    # Normalize percentage to 0-1 range
    normalized = percentage / max_percentage
    
    # Color scale: light blue -> dark blue -> purple -> red
    # Using a gradient from blue (low) to red (high)
    if normalized < 0.25:
        # Light blue
        return '#87CEEB'
    elif normalized < 0.5:
        # Medium blue
        return '#4169E1'
    elif normalized < 0.75:
        # Purple
        return '#9370DB'
    else:
        # Red (highest)
        return '#DC143C'


def create_zipcode_map(df: pd.DataFrame, geojson_data: Dict = None, zip_coordinates: Dict = None) -> folium.Map:
    """Create a Folium map with zip code volumes using actual boundaries."""
    # Center on US (approximately center of continental US)
    us_center = [39.8283, -98.5795]
    
    m = folium.Map(
        location=us_center,
        zoom_start=4,
        tiles='OpenStreetMap'
    )
    
    if df.empty:
        return m
    
    # Calculate percentages
    df_with_pct = calculate_percentages(df)
    max_percentage = df_with_pct['percentage'].max()
    
    # Create a dictionary mapping zip codes to data
    zip_data_map = {}
    for idx, row in df_with_pct.iterrows():
        zip_code = str(row['zip']).zfill(5)
        zip_data_map[zip_code] = {
            'volume': row['volume'],
            'percentage': row['percentage']
        }
    
    # If GeoJSON is provided, use choropleth with actual boundaries
    if geojson_data:
        return create_choropleth_map_with_geojson(df_with_pct, geojson_data, m)
    
    # If zip_coordinates from uszipcode are available, use those
    if zip_coordinates:
        has_bounds = any('bounds' in coord or 'border' in coord for coord in zip_coordinates.values())
        
        if has_bounds:
            st.success("✅ Using zip code boundaries from uszipcode library!")
        else:
            st.info("💡 Using coordinates from uszipcode. Some zip codes may have bounds data.")
        
        for idx, row in df_with_pct.iterrows():
            zip_code = str(row['zip']).zfill(5)
            volume = row['volume']
            percentage = row['percentage']
            
            if zip_code in zip_coordinates:
                coord = zip_coordinates[zip_code]
                lat = coord['lat']
                lon = coord['lng']
                city = coord.get('city', '')
                state = coord.get('state', '')
                county = coord.get('county', '')
                
                color = get_color_for_percentage(percentage, max_percentage)
                
                # Try to use border polygon first
                if 'border' in coord and coord['border']:
                    try:
                        # border might be a list of coordinates or a polygon
                        border = coord['border']
                        if isinstance(border, list) and len(border) > 0:
                            # Create polygon from border coordinates
                            folium.Polygon(
                                locations=border,
                                color='black',
                                weight=2,
                                fillColor=color,
                                fillOpacity=0.7,
                                popup=folium.Popup(
                                    f"""
                                    <b>Zip Code: {zip_code}</b><br>
                                    {city}, {state}<br>
                                    {county}<br>
                                    Volume: {volume:,.0f}<br>
                                    Percentage: {percentage:.2f}%
                                    """,
                                    parse_html=False
                                ),
                                tooltip=f"Zip {zip_code}: {volume:,.0f} ({percentage:.2f}%)"
                            ).add_to(m)
                            continue
                    except Exception as e:
                        pass  # Fall back to bounds or marker
                
                # Try to use bounds to create a rectangle
                if 'bounds' in coord and coord['bounds']:
                    try:
                        bounds = coord['bounds']
                        # Create rectangle from bounds
                        rectangle_coords = [
                            [bounds['north'], bounds['west']],  # NW
                            [bounds['north'], bounds['east']],  # NE
                            [bounds['south'], bounds['east']],  # SE
                            [bounds['south'], bounds['west']],  # SW
                            [bounds['north'], bounds['west']]   # Close polygon
                        ]
                        
                        folium.Polygon(
                            locations=rectangle_coords,
                            color='black',
                            weight=2,
                            fillColor=color,
                            fillOpacity=0.7,
                            popup=folium.Popup(
                                f"""
                                <b>Zip Code: {zip_code}</b><br>
                                {city}, {state}<br>
                                {county}<br>
                                Volume: {volume:,.0f}<br>
                                Percentage: {percentage:.2f}%<br>
                                <small>(Approximate bounds)</small>
                                """,
                                parse_html=False
                            ),
                            tooltip=f"Zip {zip_code}: {volume:,.0f} ({percentage:.2f}%)"
                        ).add_to(m)
                        continue
                    except Exception as e:
                        pass  # Fall back to marker
                
                # Fallback: use circle marker
                radius = max(8, min(30, volume / 200))  # Scale radius by volume
                folium.CircleMarker(
                    location=[lat, lon],
                    radius=radius,
                    popup=folium.Popup(
                        f"""
                        <b>Zip Code: {zip_code}</b><br>
                        {city}, {state}<br>
                        {county}<br>
                        Volume: {volume:,.0f}<br>
                        Percentage: {percentage:.2f}%
                        """,
                        parse_html=False
                    ),
                    color='black',
                    weight=2,
                    fillColor=color,
                    fillOpacity=0.7,
                    tooltip=f"Zip {zip_code}: {volume:,.0f} ({percentage:.2f}%)"
                ).add_to(m)
        
        add_legend(m)
        return m
    
    # Otherwise, show message that GeoJSON or uszipcode is needed
    st.warning("⚠️ No boundaries or coordinates loaded. Use uszipcode library or upload GeoJSON file.")
    st.info("💡 Options: 1) Use 'uszipcode Library' option for automatic coordinates, or 2) Upload GeoJSON for actual boundaries.")
    
    # Fallback: show approximate locations (but indicate boundaries are needed)
    for idx, row in df_with_pct.iterrows():
        zip_code = str(row['zip']).zfill(5)
        volume = row['volume']
        percentage = row['percentage']
        
        # Estimate coordinates (this is just a fallback - not accurate)
        lat = 39.8283 + (hash(zip_code) % 1000) / 1000 - 5
        lon = -98.5795 + (hash(zip_code) % 1000) / 1000 - 5
        
        color = get_color_for_percentage(percentage, max_percentage)
        
        # Add circle marker as fallback
        folium.CircleMarker(
            location=[lat, lon],
            radius=8,
            popup=folium.Popup(
                f"""
                <b>Zip Code: {zip_code}</b><br>
                Volume: {volume:,.0f}<br>
                Percentage: {percentage:.2f}%<br>
                <small>(Use uszipcode or upload GeoJSON for accurate locations)</small>
                """,
                parse_html=False
            ),
            color='black',
            weight=2,
            fillColor=color,
            fillOpacity=0.7,
            tooltip=f"Zip {zip_code}: {volume:,.0f} ({percentage:.2f}%)"
        ).add_to(m)
    
    # Add legend
    add_legend(m)
    
    return m


def create_plotly_zipcode_map(df: pd.DataFrame, geojson_data: Dict) -> go.Figure:
    """Create a Plotly choropleth map with zip code boundaries."""
    if not PLOTLY_AVAILABLE:
        raise ImportError("Plotly is not installed. Install with: pip install plotly")
    
    # Calculate percentages
    df_with_pct = calculate_percentages(df)
    
    # Create a mapping of zip codes to volumes/percentages
    # We need to match zip codes in the GeoJSON to our data
    zip_volume_map = {}
    for idx, row in df_with_pct.iterrows():
        zip_code = str(row['zip']).zfill(5)
        zip_volume_map[zip_code] = {
            'volume': row['volume'],
            'percentage': row['percentage']
        }
    
    # Extract zip codes from GeoJSON and create a dataframe for plotly
    plotly_data = []
    for feature in geojson_data.get('features', []):
        props = feature.get('properties', {})
        zip_code = (
            str(props.get('ZCTA5CE20') or  # 2025 Census format
            props.get('ZCTA5CE10') or  # Older Census format
            props.get('ZIPCODE') or 
            props.get('ZIP') or
            props.get('zip') or
            props.get('GEOID20') or
            props.get('GEOID10') or '').zfill(5)
        )
        
        if zip_code and zip_code in zip_volume_map:
            plotly_data.append({
                'zip': zip_code,
                'volume': zip_volume_map[zip_code]['volume'],
                'percentage': zip_volume_map[zip_code]['percentage']
            })
    
    if not plotly_data:
        st.warning("⚠️ No matching zip codes found between your data and GeoJSON. Check zip code format.")
        return go.Figure()
    
    plotly_df = pd.DataFrame(plotly_data)
    
    # Detect the correct featureidkey by checking first feature
    featureidkey = 'properties.ZCTA5CE20'  # Default for 2025 Census
    if geojson_data.get('features'):
        first_props = geojson_data['features'][0].get('properties', {})
        if 'ZCTA5CE20' in first_props:
            featureidkey = 'properties.ZCTA5CE20'
        elif 'ZCTA5CE10' in first_props:
            featureidkey = 'properties.ZCTA5CE10'
        elif 'ZIPCODE' in first_props:
            featureidkey = 'properties.ZIPCODE'
        elif 'GEOID20' in first_props:
            featureidkey = 'properties.GEOID20'
    
    # Create choropleth map
    fig = px.choropleth(
        plotly_df,
        geojson=geojson_data,
        locations='zip',
        color='percentage',
        featureidkey=featureidkey,
        color_continuous_scale=['#87CEEB', '#4169E1', '#9370DB', '#DC143C'],
        range_color=(0, plotly_df['percentage'].max()),
        labels={'percentage': 'Volume Percentage (%)', 'volume': 'Volume'},
        hover_data=['volume', 'percentage'],
        title='Zip Code Volume Map'
    )
    
    fig.update_geos(
        fitbounds="locations",
        visible=False,
        projection_type="albers usa"
    )
    
    fig.update_layout(
        height=600,
        margin={"r":0,"t":0,"l":0,"b":0}
    )
    
    return fig


def add_legend(m: folium.Map):
    """Add legend to the map."""
    legend_html = '''
    <div style="position: fixed; 
                bottom: 50px; left: 50px; width: 220px; height: 140px; 
                background-color: white; border:2px solid grey; z-index:9999; 
                font-size:14px; padding: 10px; border-radius: 5px; box-shadow: 0 0 15px rgba(0,0,0,0.2);">
    <p style="margin: 0 0 10px 0; font-weight: bold; font-size: 16px;">Volume Percentage</p>
    <p style="margin: 5px 0;"><span style="display: inline-block; width: 20px; height: 20px; background-color: #87CEEB; border: 1px solid black; margin-right: 5px;"></span> 0-25%</p>
    <p style="margin: 5px 0;"><span style="display: inline-block; width: 20px; height: 20px; background-color: #4169E1; border: 1px solid black; margin-right: 5px;"></span> 25-50%</p>
    <p style="margin: 5px 0;"><span style="display: inline-block; width: 20px; height: 20px; background-color: #9370DB; border: 1px solid black; margin-right: 5px;"></span> 50-75%</p>
    <p style="margin: 5px 0;"><span style="display: inline-block; width: 20px; height: 20px; background-color: #DC143C; border: 1px solid black; margin-right: 5px;"></span> 75-100%</p>
    <p style="margin: 10px 0 0 0; font-size: 12px; color: #666;">Gray = No data</p>
    </div>
    '''
    m.get_root().html.add_child(folium.Element(legend_html))


def create_choropleth_map_with_geojson(df: pd.DataFrame, geojson_data: Dict, m: folium.Map = None) -> folium.Map:
    """Create a choropleth map with actual zip code boundaries from GeoJSON."""
    if m is None:
        us_center = [39.8283, -98.5795]
        m = folium.Map(
            location=us_center,
            zoom_start=4,
            tiles='OpenStreetMap'
        )
    
    if df.empty or not geojson_data:
        return m
    
    # Calculate percentages
    df_with_pct = calculate_percentages(df)
    max_percentage = df_with_pct['percentage'].max()
    
    # Create a dictionary mapping zip codes to data
    zip_data_map = {}
    for idx, row in df_with_pct.iterrows():
        zip_code = str(row['zip']).zfill(5)
        zip_data_map[zip_code] = {
            'volume': row['volume'],
            'percentage': row['percentage'],
            'color': get_color_for_percentage(row['percentage'], max_percentage)
        }
    
    # Style function for GeoJSON - colors zip codes based on volume percentage
    def style_function(feature):
        # Try different common property names for zip codes in GeoJSON
        # Census 2025 shapefiles typically use ZCTA5CE20
        props = feature.get('properties', {})
        zip_code = (
            props.get('ZCTA5CE20') or  # 2025 Census format
            props.get('ZCTA5CE10') or  # Older Census format
            props.get('ZIPCODE') or 
            props.get('ZIP') or
            props.get('zip') or
            props.get('GEOID20') or
            props.get('GEOID10')
        )
        
        if zip_code:
            zip_code = str(zip_code).zfill(5)
            zip_info = zip_data_map.get(zip_code)
            if zip_info:
                return {
                    'fillColor': zip_info['color'],
                    'color': 'black',
                    'weight': 1.5,
                    'fillOpacity': 0.7,
                    'dashArray': None
                }
        
        # Gray for zip codes not in data
        return {
            'fillColor': '#808080',
            'color': 'gray',
            'weight': 1,
            'fillOpacity': 0.3,
            'dashArray': '5, 5'
        }
    
    # Tooltip function to show zip code and volume info
    def on_each_feature(feature, layer):
        props = feature.get('properties', {})
        zip_code = (
            props.get('ZCTA5CE20') or  # 2025 Census format
            props.get('ZCTA5CE10') or  # Older Census format
            props.get('ZIPCODE') or 
            props.get('ZIP') or
            props.get('zip') or
            props.get('GEOID20') or
            props.get('GEOID10')
        )
        
        if zip_code:
            zip_code = str(zip_code).zfill(5)
            zip_info = zip_data_map.get(zip_code)
            if zip_info:
                popup_content = f"""
                <b>Zip Code: {zip_code}</b><br>
                Volume: {zip_info['volume']:,.0f}<br>
                Percentage: {zip_info['percentage']:.2f}%
                """
            else:
                popup_content = f"<b>Zip Code: {zip_code}</b><br>No volume data"
            
            layer.bind_popup(folium.Popup(popup_content, parse_html=False))
            layer.bind_tooltip(f"Zip {zip_code}: {zip_info['volume']:,.0f} ({zip_info['percentage']:.2f}%)" if zip_info else f"Zip {zip_code}: No data")
    
    # Add GeoJSON layer with actual zip code boundaries
    folium.GeoJson(
        geojson_data,
        style_function=style_function,
        on_each_feature=on_each_feature,
        tooltip=folium.GeoJsonTooltip(
            fields=[],
            aliases=[],
            localize=True
        )
    ).add_to(m)
    
    # Add legend
    add_legend(m)
    
    return m


# Sidebar for data input
st.sidebar.header("📊 Data Input")

input_method = st.sidebar.radio(
    "Choose input method:",
    ["Sample Data", "Upload CSV", "Manual Entry"]
)

# GeoJSON/Shapefile upload for zip code boundaries
st.sidebar.header("🗺️ Map Boundaries")

boundary_method = st.sidebar.radio(
    "Boundary source:",
    ["Use uszipcode Library (Easiest!)", "Upload GeoJSON (Fast!)", "Convert Shapefile to GeoJSON", "Load from Local Folder"],
    help="uszipcode provides coordinates automatically. GeoJSON is faster for boundaries."
)

geojson_data = None
zip_coordinates = None  # For uszipcode method

if boundary_method == "Use uszipcode Library (Easiest!)":
    if not USZIPCODE_AVAILABLE:
        st.sidebar.error("⚠️ uszipcode not installed. Install with: pip install uszipcode==1.0.1")
        st.sidebar.info("💡 This library provides zip code coordinates automatically - no files needed!")
    else:
        st.sidebar.success("✅ uszipcode library available!")
        st.sidebar.info("💡 This will get coordinates for your zip codes automatically.")
        
        if not df.empty:
            if st.sidebar.button("Get Zip Code Coordinates"):
                loading_msg = st.sidebar.empty()
                loading_msg.info("⏳ Fetching coordinates from uszipcode...")
                try:
                    search = SearchEngine()
                    zip_coords_dict = {}
                    
                    for idx, row in df.iterrows():
                        zip_code = str(row['zip']).zfill(5)
                        try:
                            result = search.by_zipcode(zip_code)
                            if result and result.lat and result.lng:
                                zip_data = {
                                    'lat': result.lat,
                                    'lng': result.lng,
                                    'city': result.major_city or '',
                                    'state': result.state or '',
                                    'county': result.county or ''
                                }
                                
                                # Add bounds if available (for creating rectangles)
                                if hasattr(result, 'bounds_west') and result.bounds_west:
                                    zip_data['bounds'] = {
                                        'west': result.bounds_west,
                                        'east': result.bounds_east,
                                        'north': result.bounds_north,
                                        'south': result.bounds_south
                                    }
                                
                                # Add border polygon if available
                                if hasattr(result, 'border') and result.border:
                                    zip_data['border'] = result.border
                                elif hasattr(result, 'polygon') and result.polygon:
                                    zip_data['border'] = result.polygon
                                
                                zip_coords_dict[zip_code] = zip_data
                        except Exception as e:
                            continue
                    
                    zip_coordinates = zip_coords_dict
                    loading_msg.empty()
                    st.sidebar.success(f"✅ Found coordinates for {len(zip_coords_dict)} zip codes!")
                    st.sidebar.info(f"Missing: {len(df) - len(zip_coords_dict)} zip codes")
                except Exception as e:
                    loading_msg.empty()
                    st.sidebar.error(f"Error fetching coordinates: {e}")
        else:
            st.sidebar.warning("⚠️ Load your zip code data first!")

elif boundary_method == "Upload GeoJSON (Fast!)":
    uploaded_file = st.sidebar.file_uploader(
        "Upload GeoJSON file",
        type=['geojson', 'json'],
        help="Upload a GeoJSON file (.geojson/.json) - this is much faster than shapefiles!"
    )
    
    if uploaded_file is not None:
        try:
            file_ext = uploaded_file.name.lower()
            
            if file_ext.endswith(('.geojson', '.json')):
                # Handle GeoJSON - this is fast!
                geojson_data = json.load(uploaded_file)
                st.sidebar.success(f"✅ GeoJSON loaded successfully!")
                if 'features' in geojson_data:
                    st.sidebar.info(f"Found {len(geojson_data['features'])} zip code boundaries")
            else:
                st.sidebar.error("Please upload a GeoJSON file (.geojson or .json)")
                
        except Exception as e:
            st.sidebar.error(f"Error loading GeoJSON: {e}")
            geojson_data = None

elif boundary_method == "Convert Shapefile to GeoJSON":
    st.sidebar.info("💡 Convert your shapefile to GeoJSON once, then reuse it!")
    
    folder_path = st.sidebar.text_input(
        "Path to shapefile folder",
        value="tl_2025_us_zcta520",
        help="Enter the path to the folder containing .shp files"
    )
    
    if folder_path and GEOPANDAS_AVAILABLE:
        import os
        if os.path.exists(folder_path):
            shp_files = [f for f in os.listdir(folder_path) if f.endswith('.shp')]
            if shp_files:
                selected_shp = st.sidebar.selectbox(
                    "Select shapefile:",
                    shp_files
                )
                
                output_name = st.sidebar.text_input(
                    "Output GeoJSON filename",
                    value=selected_shp.replace('.shp', '_filtered.geojson'),
                    help="Name for the converted GeoJSON file"
                )
                
                filter_option = st.sidebar.checkbox(
                    "Filter to zip codes in my data only",
                    value=True,
                    help="Only convert zip codes you have data for (much smaller file!)"
                )
                
                if st.sidebar.button("Convert to GeoJSON"):
                    loading_msg = st.sidebar.empty()
                    loading_msg.info("⏳ Converting shapefile to GeoJSON...")
                    try:
                        shp_path = os.path.join(folder_path, selected_shp)
                        
                        # Read shapefile
                        loading_msg.info("⏳ Reading shapefile...")
                        gdf = gpd.read_file(shp_path)
                        
                        # Filter if requested
                        if filter_option and not df.empty:
                            # Detect zip code column
                            zip_cols = [c for c in gdf.columns if 'ZCTA5CE20' in c.upper() or 'ZCTA5CE10' in c.upper() or 'ZIP' in c.upper()]
                            if zip_cols:
                                zip_col = zip_cols[0]
                                needed_zips = set(df['zip'].astype(str).str.zfill(5).tolist())
                                loading_msg.info(f"⏳ Filtering to {len(needed_zips)} zip codes...")
                                gdf = gdf[gdf[zip_col].astype(str).str.zfill(5).isin(needed_zips)]
                        
                        # Convert to GeoJSON
                        loading_msg.info("⏳ Converting to GeoJSON...")
                        geojson_str = gdf.to_json()
                        geojson_data = json.loads(geojson_str)
                        
                        # Save to file
                        output_path = os.path.join(folder_path, output_name)
                        with open(output_path, 'w') as f:
                            json.dump(geojson_data, f)
                        
                        loading_msg.empty()
                        st.sidebar.success(f"✅ Converted and saved to: {output_path}")
                        st.sidebar.info(f"Found {len(geojson_data['features'])} zip code boundaries")
                        st.sidebar.success("💡 Now use 'Upload GeoJSON' option to load this file quickly!")
                        
                    except Exception as e:
                        loading_msg.empty()
                        st.sidebar.error(f"Error converting: {e}")
                        st.sidebar.exception(e)
            else:
                st.sidebar.error(f"No .shp file found in {folder_path}")
        else:
            st.sidebar.warning(f"Folder not found: {folder_path}")
    elif not GEOPANDAS_AVAILABLE:
        st.sidebar.warning("⚠️ GeoPandas required. Install with: pip install geopandas")

elif boundary_method == "Load from Local Folder":
    
    # Local folder option - load GeoJSON files
    folder_path = st.sidebar.text_input(
        "Path to folder with GeoJSON files",
        value="tl_2025_us_zcta520",
        help="Enter the path to the folder containing GeoJSON files"
    )
    
    if folder_path:
        import os
        if os.path.exists(folder_path):
            # Look for GeoJSON files first
            geojson_files = [f for f in os.listdir(folder_path) if f.endswith(('.geojson', '.json'))]
            shp_files = [f for f in os.listdir(folder_path) if f.endswith('.shp')]
            
            if geojson_files:
                selected_file = st.sidebar.selectbox(
                    "Select GeoJSON file:",
                    geojson_files,
                    help="Choose a GeoJSON file (fast!)"
                )
                
                if st.sidebar.button("Load GeoJSON"):
                    try:
                        file_path = os.path.join(folder_path, selected_file)
                        with open(file_path, 'r') as f:
                            geojson_data = json.load(f)
                        st.sidebar.success(f"✅ Loaded {selected_file}!")
                        st.sidebar.info(f"Found {len(geojson_data['features'])} zip code boundaries")
                    except Exception as e:
                        st.sidebar.error(f"Error loading GeoJSON: {e}")
            elif shp_files:
                st.sidebar.warning("⚠️ Only shapefiles found. Use 'Convert Shapefile to GeoJSON' option first!")
                st.sidebar.info(f"Found {len(shp_files)} shapefile(s) - convert to GeoJSON for faster loading")
            else:
                st.sidebar.error(f"No GeoJSON or shapefile found in {folder_path}")
        else:
            st.sidebar.warning(f"Folder not found: {folder_path}")
    folder_path = st.sidebar.text_input(
        "Path to shapefile folder",
        value="tl_2025_us_zcta520",
        help="Enter the path to the folder containing .shp files (e.g., 'tl_2025_us_zcta520')"
    )
    
    if folder_path:
        if GEOPANDAS_AVAILABLE:
            import os
            if os.path.exists(folder_path):
                # Find .shp file in folder
                shp_files = [f for f in os.listdir(folder_path) if f.endswith('.shp')]
                if shp_files:
                    selected_shp = st.sidebar.selectbox(
                        "Select shapefile:",
                        shp_files,
                        help="Choose which .shp file to load"
                    )
                    
                    # Check if we have data loaded to filter
                    filter_option = st.sidebar.checkbox(
                        "Filter to zip codes in my data only (MUCH faster!)",
                        value=True,
                        help="Only load boundaries for zip codes you have volume data for. This is much faster!"
                    )
                    
                    if st.sidebar.button("Load Shapefile"):
                        loading_msg = st.sidebar.empty()
                        loading_msg.info(f"⏳ Loading {selected_shp}...")
                        try:
                            shp_path = os.path.join(folder_path, selected_shp)
                            
                            # First, detect the zip code column
                            # Read just a sample to get column names
                            sample_gdf = gpd.read_file(shp_path, rows=10)
                            zip_col = None
                            cols = sample_gdf.columns.tolist()
                            zip_cols = [c for c in cols if 'ZCTA5CE20' in c.upper() or 'ZCTA5CE10' in c.upper() or 'ZIP' in c.upper() or 'GEOID' in c.upper()]
                            if zip_cols:
                                zip_col = zip_cols[0]
                            
                            # If filtering and we have data, only load matching zip codes
                            if filter_option and not df.empty and zip_col:
                                loading_msg.info(f"⏳ Filtering shapefile to {len(df)} zip codes...")
                                # Get list of zip codes we need
                                needed_zips = set(df['zip'].astype(str).str.zfill(5).tolist())
                                
                                # Read and filter in chunks to be memory efficient
                                # Read the full file but filter immediately
                                loading_msg.info(f"⏳ Reading shapefile (this may take a minute for full US file)...")
                                full_gdf = gpd.read_file(shp_path)
                                
                                loading_msg.info(f"⏳ Filtering to {len(needed_zips)} zip codes...")
                                # Filter to only zip codes we need
                                filtered_gdf = full_gdf[full_gdf[zip_col].astype(str).str.zfill(5).isin(needed_zips)]
                                
                                if len(filtered_gdf) > 0:
                                    geojson_data = json.loads(filtered_gdf.to_json())
                                    loading_msg.empty()
                                    st.sidebar.success(f"✅ Loaded {len(filtered_gdf)} boundaries (filtered from {len(full_gdf)})!")
                                    st.sidebar.info(f"Found {len(geojson_data['features'])} matching zip codes")
                                else:
                                    loading_msg.empty()
                                    st.sidebar.warning(f"⚠️ No matching zip codes found. Check your zip code format.")
                                    st.sidebar.info(f"Shapefile uses column: {zip_col}")
                                    geojson_data = None
                            else:
                                # Load full file (slow!)
                                if not filter_option:
                                    st.sidebar.warning("⚠️ Loading full US shapefile - this will take a while!")
                                loading_msg.info(f"⏳ Reading full shapefile (30,000+ zip codes - be patient!)...")
                                gdf = gpd.read_file(shp_path)
                                geojson_data = json.loads(gdf.to_json())
                                loading_msg.empty()
                                st.sidebar.success(f"✅ Loaded {selected_shp}!")
                                st.sidebar.info(f"Found {len(geojson_data['features'])} zip code boundaries")
                            
                            # Show available columns
                            if zip_col:
                                st.sidebar.success(f"📌 Using zip code column: {zip_col}")
                                    
                        except Exception as e:
                            loading_msg.empty()
                            st.sidebar.error(f"Error loading shapefile: {e}")
                            st.sidebar.exception(e)
                else:
                    st.sidebar.error(f"No .shp file found in {folder_path}")
            else:
                st.sidebar.warning(f"⚠️ Folder not found: {folder_path}")
                st.sidebar.info("💡 Make sure the folder path is correct relative to the app directory")
        else:
            st.sidebar.warning("⚠️ GeoPandas required. Install with: pip install geopandas")
            st.sidebar.info("💡 Or upload the .shp file directly using 'Upload File' option")

df = pd.DataFrame()

if input_method == "Sample Data":
    st.sidebar.info("Using sample data. Switch to 'Upload CSV' or 'Manual Entry' for your own data.")
    df = load_zipcode_data(SAMPLE_DATA)
    
elif input_method == "Upload CSV":
    uploaded_file = st.sidebar.file_uploader(
        "Upload CSV file",
        type=['csv'],
        help="CSV file must have 'zip' and 'volume' columns"
    )
    if uploaded_file is not None:
        try:
            csv_string = uploaded_file.read().decode('utf-8')
            df = load_zipcode_data(csv_string)
        except Exception as e:
            st.sidebar.error(f"Error reading file: {e}")
    
elif input_method == "Manual Entry":
    manual_data = st.sidebar.text_area(
        "Enter CSV data (zip,volume):",
        value="zip,volume\n10001,1500\n10002,2300",
        height=200,
        help="Format: zip,volume (one per line)"
    )
    if manual_data:
        df = load_zipcode_data(manual_data)

# Display data summary
if not df.empty:
    st.sidebar.success(f"✅ Loaded {len(df)} zip codes")
    st.sidebar.metric("Total Volume", f"{df['volume'].sum():,.0f}")
    
    # Show data preview
    with st.sidebar.expander("📋 Preview Data"):
        st.dataframe(df.head(10), use_container_width=True)
    
    # Calculate and show statistics
    df_with_pct = calculate_percentages(df)
    
    st.subheader("📈 Volume Statistics")
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("Total Zip Codes", len(df))
    with col2:
        st.metric("Total Volume", f"{df['volume'].sum():,.0f}")
    with col3:
        st.metric("Average Volume", f"{df['volume'].mean():,.0f}")
    with col4:
        st.metric("Max Volume", f"{df['volume'].max():,.0f}")
    
    # Show top zip codes
    st.subheader("🏆 Top 10 Zip Codes by Volume")
    top_zips = df_with_pct.nlargest(10, 'volume')[['zip', 'volume', 'percentage']]
    top_zips.columns = ['Zip Code', 'Volume', 'Percentage (%)']
    st.dataframe(top_zips, use_container_width=True)
    
    # Create and display map
    st.subheader("🗺️ Zip Code Volume Map")
    if geojson_data:
        st.success("✅ Using actual zip code boundaries from GeoJSON file!")
        st.info("💡 Map shows zip code boundaries colored by volume percentage. Gray areas have no data.")
    else:
        st.warning("⚠️ No GeoJSON boundaries loaded. Upload a GeoJSON file in the sidebar to see actual zip code shapes.")
        st.info("💡 Currently showing approximate marker locations. Upload GeoJSON for accurate boundaries.")
    
    try:
            zipcode_map = create_zipcode_map(df, geojson_data, zip_coordinates)
        
        # Render map
        if FORCE_HTML_RENDERING:
            map_html = zipcode_map._repr_html_()
            components.html(map_html, width=900, height=600, scrolling=False)
            st.success("✅ Map rendered successfully with HTML!")
        else:
            try:
                from streamlit_folium import st_folium
                st_folium(zipcode_map, width=900, height=600, returned_objects=[])
                st.success("✅ Map rendered successfully!")
            except Exception as folium_error:
                st.warning(f"Using HTML fallback: {str(folium_error)[:100]}")
                map_html = zipcode_map._repr_html_()
                components.html(map_html, width=900, height=600, scrolling=False)
                st.success("✅ Map rendered with HTML fallback!")
    except Exception as e:
        st.error(f"❌ Error creating map: {e}")
        st.exception(e)
    
    # Instructions for using GeoJSON
    with st.expander("ℹ️ Tips for Faster Loading"):
        st.markdown("""
        **Why is it slow?**
        - Full US shapefile has 30,000+ zip codes (~100MB+)
        - Loading and converting takes time
        
        **Solutions:**
        1. ✅ **Filter to your zip codes only** (checkbox in sidebar) - MUCH faster!
        2. Download state-specific shapefiles instead of full US
        3. Pre-convert to GeoJSON (one-time, then reuse)
        4. Use a smaller sample of your data for testing
        
        **Recommended Libraries:**
        - **Plotly**: Better built-in support for choropleth maps (install: `pip install plotly`)
        - **GeoPandas**: Easier GeoJSON handling (install: `pip install geopandas`)
        
        **Data Sources:**
        - US Census Bureau: https://www.census.gov/geographies/mapping-files/time-series/geo/tiger-line-file.html
        - Look for "ZCTA5" (Zip Code Tabulation Areas) boundaries
        - Download state-specific files for faster loading
        """)
    
else:
    st.info("👈 Please load data using the sidebar options to see the map.")
    
    # Show sample format
    st.subheader("📝 Expected Data Format")
    st.code("""
zip,volume
10001,1500
10002,2300
10003,1800
90210,3200
    """, language="csv")

