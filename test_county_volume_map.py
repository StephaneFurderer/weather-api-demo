"""
County-Level Volume Map
Adapted from Plotly's choropleth maps tutorial for volume data visualization
"""
import streamlit as st
import pandas as pd
import plotly.express as px
from urllib.request import urlopen
import json
import io
import ssl

# Disable SSL verification for GitHub raw content (common issue)
ssl._create_default_https_context = ssl._create_unverified_context

st.set_page_config(
    page_title="County Volume Map",
    page_icon="🗺️",
    layout="wide"
)

st.title("🗺️ County-Level Volume Map")
st.markdown("Visualize volume data by US county using choropleth maps")

# Sample data format: county_fips, volume
SAMPLE_DATA = """county_fips,volume
01001,1500
01003,2300
01005,1800
04013,3200
06037,2100
06059,2800
12011,1900
17031,2500
22071,1700
36061,3000
"""

@st.cache_data
def load_county_geojson():
    """Load county GeoJSON data from Plotly's example."""
    try:
        with urlopen('https://raw.githubusercontent.com/plotly/datasets/master/geojson-counties-fips.json') as response:
            counties = json.load(response)
        return counties
    except Exception as e:
        st.error(f"Error loading GeoJSON: {e}")
        return None

def load_county_data(data_input: str) -> pd.DataFrame:
    """Load county FIPS and volume data from CSV string."""
    try:
        df = pd.read_csv(io.StringIO(data_input))
        
        # Validate required columns
        if 'county_fips' not in df.columns or 'volume' not in df.columns:
            raise ValueError("Data must contain 'county_fips' and 'volume' columns")
        
        # Ensure FIPS codes are strings and padded to 5 digits
        df['county_fips'] = df['county_fips'].astype(str).str.zfill(5)
        df['volume'] = pd.to_numeric(df['volume'], errors='coerce')
        df = df.dropna(subset=['volume'])
        
        return df
    except Exception as e:
        st.error(f"Error loading data: {e}")
        return pd.DataFrame()

# Sidebar for data input
st.sidebar.header("📊 Data Input")

input_method = st.sidebar.radio(
    "Choose input method:",
    ["Sample Data", "Upload CSV", "Manual Entry"]
)

df = pd.DataFrame()

if input_method == "Sample Data":
    st.sidebar.info("Using sample county data. Format: county_fips,volume")
    df = load_county_data(SAMPLE_DATA)
    
elif input_method == "Upload CSV":
    uploaded_file = st.sidebar.file_uploader(
        "Upload CSV file",
        type=['csv'],
        help="CSV file must have 'county_fips' and 'volume' columns. FIPS codes should be 5 digits."
    )
    if uploaded_file is not None:
        try:
            csv_string = uploaded_file.read().decode('utf-8')
            df = load_county_data(csv_string)
        except Exception as e:
            st.sidebar.error(f"Error reading file: {e}")
    
elif input_method == "Manual Entry":
    manual_data = st.sidebar.text_area(
        "Enter CSV data (county_fips,volume):",
        value="county_fips,volume\n01001,1500\n01003,2300",
        height=200,
        help="Format: county_fips,volume (one per line). FIPS codes are 5 digits."
    )
    if manual_data:
        df = load_county_data(manual_data)

# Load GeoJSON
st.sidebar.header("🗺️ Map Data")
counties_geojson = load_county_geojson()

if counties_geojson:
    st.sidebar.success(f"✅ Loaded {len(counties_geojson['features'])} county boundaries")

# Display results
if not df.empty and counties_geojson:
    # Calculate percentages
    total_volume = df['volume'].sum()
    df['percentage'] = (df['volume'] / total_volume * 100).round(2)
    
    st.sidebar.success(f"✅ Loaded {len(df)} counties")
    st.sidebar.metric("Total Volume", f"{total_volume:,.0f}")
    
    # Statistics
    st.subheader("📈 Volume Statistics")
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("Total Counties", len(df))
    with col2:
        st.metric("Total Volume", f"{df['volume'].sum():,.0f}")
    with col3:
        st.metric("Average Volume", f"{df['volume'].mean():,.0f}")
    with col4:
        st.metric("Max Volume", f"{df['volume'].max():,.0f}")
    
    # Top counties
    st.subheader("🏆 Top 10 Counties by Volume")
    top_counties = df.nlargest(10, 'volume')[['county_fips', 'volume', 'percentage']]
    top_counties.columns = ['County FIPS', 'Volume', 'Percentage (%)']
    st.dataframe(top_counties, use_container_width=True)
    
    # Create choropleth map
    st.subheader("🗺️ County Volume Map")
    st.info("💡 Map shows counties colored by volume. Gray counties have no data.")
    
    # Color scale options
    color_scale = st.selectbox(
        "Color Scale",
        ["Viridis", "Plasma", "Blues", "Reds", "Greens", "Purples", "Oranges"],
        help="Choose the color scheme for the map"
    )
    
    # Create the map
    fig = px.choropleth(
        df,
        geojson=counties_geojson,
        locations='county_fips',  # Matches the 'id' field in GeoJSON
        color='volume',
        color_continuous_scale=color_scale,
        scope="usa",
        labels={'volume': 'Volume', 'percentage': 'Percentage (%)'},
        hover_data=['percentage']
    )
    
    fig.update_layout(
        margin={"r": 0, "t": 0, "l": 0, "b": 0},
        height=600,
        title_text='Volume by County'
    )
    
    st.plotly_chart(fig, use_container_width=True)
    
    # Data table
    with st.expander("📊 View Full Data"):
        st.dataframe(df, use_container_width=True)
    
    # Instructions
    with st.expander("ℹ️ About County FIPS Codes"):
        st.markdown("""
        **FIPS Codes:**
        - FIPS (Federal Information Processing Standards) codes uniquely identify US counties
        - Format: 5 digits (e.g., 01001 = Autauga County, Alabama)
        - First 2 digits = State code
        - Last 3 digits = County code
        
        **Finding FIPS Codes:**
        - [Census Bureau FIPS Codes](https://www.census.gov/library/reference/code-lists/ansi.html)
        - [FIPS Code Lookup](https://www.census.gov/geographies/reference-files.html)
        
        **Data Format:**
        Your CSV should have:
        - `county_fips`: 5-digit FIPS code (as string or number)
        - `volume`: Numeric volume value
        
        Example:
        ```
        county_fips,volume
        01001,1500
        01003,2300
        06037,3200
        ```
        """)
    
elif not df.empty:
    st.warning("⚠️ County boundaries not loaded. Please check your internet connection.")
    
elif not counties_geojson:
    st.warning("⚠️ Please load your county data using the sidebar options.")
    
else:
    st.info("👈 Please load data using the sidebar options to see the map.")
    
    # Show sample format
    st.subheader("📝 Expected Data Format")
    st.code("""
county_fips,volume
01001,1500
01003,2300
06037,3200
    """, language="csv")
    
    st.info("💡 **Tip**: Use 5-digit FIPS codes. You can find FIPS codes at the Census Bureau website.")

