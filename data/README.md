# Zip Code to FIPS County Code Mapping Data

This directory contains mapping tables between US ZIP codes and FIPS county codes, derived from the US Census Bureau's ZCTA (Zip Code Tabulation Area) to County relationship file.

## Files

### `zip_to_fips_mapping.csv`
**Primary mapping** - One FIPS code per ZIP code (primary county based on highest population percentage)
- **Format:** CSV with columns `ZIP`, `FIPS`
- **Rows:** ~33,120 unique ZIP codes
- **Use case:** When you need a single county per ZIP code (most common use case)

### `zip_to_fips_mapping_all.csv`
**Complete mapping** - All ZIP-to-FIPS relationships (includes ZIP codes that span multiple counties)
- **Format:** CSV with columns `ZIP`, `FIPS`
- **Rows:** ~44,410 relationships
- **Use case:** When you need to account for ZIP codes that span multiple counties

## Data Source

- **Source:** US Census Bureau
- **URL:** https://www2.census.gov/geo/docs/maps-data/data/rel/zcta_county_rel_10.txt
- **Last Updated:** Based on 2010 Census ZCTA data
- **Format:** Comma-separated values (CSV)

## Usage

### Python/Pandas
```python
import pandas as pd

# Load primary mapping (one FIPS per ZIP)
df = pd.read_csv('data/zip_to_fips_mapping.csv', dtype={'ZIP': str, 'FIPS': str})

# Load complete mapping (all relationships)
df_all = pd.read_csv('data/zip_to_fips_mapping_all.csv', dtype={'ZIP': str, 'FIPS': str})
```

### Example Queries

**Find FIPS code for a ZIP code:**
```python
zip_code = '10001'
fips = df[df['ZIP'] == zip_code]['FIPS'].values[0]
```

**Find all ZIP codes in a county:**
```python
fips_code = '36061'  # New York County (Manhattan)
zip_codes = df[df['FIPS'] == fips_code]['ZIP'].tolist()
```

**Find all counties for a ZIP code (if it spans multiple):**
```python
zip_code = '10001'
counties = df_all[df_all['ZIP'] == zip_code]['FIPS'].tolist()
```

## Notes

- ZIP codes are stored as 5-digit strings (e.g., '00601', '10001')
- FIPS codes are 5-digit strings: first 2 digits = state, last 3 digits = county
- Some ZIP codes span multiple counties - use `zip_to_fips_mapping_all.csv` to see all relationships
- The primary mapping (`zip_to_fips_mapping.csv`) selects the county with the highest population percentage for each ZIP code

## Regenerating the Data

To regenerate these files, run the notebook `explore_census_zcta_data.ipynb` or use the script in `test_county_map.py`:

```python
from test_county_map import load_zip_to_fips_mapping
df = load_zip_to_fips_mapping()
```

