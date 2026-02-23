# Filter Columns Utility

This utility adds filter-related columns to your dataset for tracking filter validation and status.

## Columns Created

The script automatically creates the following columns:

1. **Failed_Filter_Count** - Count of filters that failed (False) for each row
2. **All_Filters_Pass** - Boolean: True if all filters pass (all True)
3. **Any_Filter_Fail** - Boolean: True if any filter fails (any False)
4. **Status_Matches_AllFilters** - Boolean: True if status matches and all filters pass
5. **Failed_Filter_Count_17** - Count of failed filters among the first 17 filters
6. **All_17_Filters_Pass** - Boolean: True if all 17 filters pass
7. **Any_17_Filter_Fail** - Boolean: True if any of the 17 filters fail

## Usage

### Option 1: Add columns to existing file

```bash
python3 add_filter_columns.py your_data.csv output_with_filters.csv
```

Or for Excel files:
```bash
python3 add_filter_columns.py your_data.xlsx output_with_filters.xlsx
```

### Option 2: Create template

```bash
python3 add_filter_columns.py
```

This creates a `filter_template.csv` with sample data and all filter columns.

## Input Data Format

Your input file should have:
- Filter columns (boolean True/False, or Pass/Fail, or 1/0)
- Optional: A Status column for `Status_Matches_AllFilters` calculation

The script will auto-detect:
- Columns containing "filter", "pass", or "fail" in the name
- A "status" column for status matching

## Example

```python
import pandas as pd
from add_filter_columns import add_filter_columns

# Load your data
df = pd.read_csv('your_data.csv')

# Add filter columns
df_with_filters = add_filter_columns(
    df,
    filter_columns=['Filter_1', 'Filter_2', 'Filter_3'],  # Optional: specify filter columns
    status_column='Status',  # Optional: specify status column
    filter_17_columns=['Filter_1', 'Filter_2', ..., 'Filter_17']  # Optional: specify 17 filters
)

# Save result
df_with_filters.to_csv('output.csv', index=False)
```

## Column Logic

- **Failed_Filter_Count**: Counts how many filter columns are False/0/Fail
- **All_Filters_Pass**: True only when ALL filter columns are True/1/Pass
- **Any_Filter_Fail**: True when ANY filter column is False/0/Fail
- **Status_Matches_AllFilters**: True when status indicates "pass" AND all filters pass
- **Failed_Filter_Count_17**: Same as Failed_Filter_Count but only for first 17 filters
- **All_17_Filters_Pass**: True only when all of the first 17 filters pass
- **Any_17_Filter_Fail**: True when any of the first 17 filters fail

## Supported File Formats

- CSV (`.csv`)
- Excel (`.xlsx`, `.xls`)

## Requirements

Install dependencies:
```bash
pip install pandas numpy openpyxl
```

Or use the requirements file:
```bash
pip install -r requirements.txt
```
