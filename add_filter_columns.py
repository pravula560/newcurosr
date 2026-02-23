#!/usr/bin/env python3
"""
Script to add filter-related columns to a dataset
Creates columns for filter validation and status tracking
"""

import pandas as pd
import numpy as np
from typing import Optional, List, Dict


def add_filter_columns(df: pd.DataFrame, 
                       filter_columns: Optional[List[str]] = None,
                       status_column: Optional[str] = None,
                       filter_17_columns: Optional[List[str]] = None) -> pd.DataFrame:
    """
    Add filter-related columns to a dataframe
    
    Parameters:
    -----------
    df : pd.DataFrame
        Input dataframe
    filter_columns : list, optional
        List of column names that represent filters (boolean or pass/fail)
        If None, will look for columns containing 'filter' or 'Filter'
    status_column : str, optional
        Column name for status matching. If None, will look for 'status' or 'Status'
    filter_17_columns : list, optional
        List of 17 specific filter columns. If None, will use first 17 filter columns
    
    Returns:
    --------
    pd.DataFrame with added filter columns
    """
    df = df.copy()
    
    # Auto-detect filter columns if not provided
    if filter_columns is None:
        filter_columns = [col for col in df.columns 
                         if 'filter' in col.lower() or 'pass' in col.lower() 
                         or 'fail' in col.lower()]
    
    # Auto-detect status column if not provided
    if status_column is None:
        status_candidates = [col for col in df.columns if 'status' in col.lower()]
        status_column = status_candidates[0] if status_candidates else None
    
    # Convert filter columns to boolean if needed
    def convert_to_bool(value):
        if pd.isna(value):
            return False
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)):
            return bool(value)
        if isinstance(value, str):
            return value.lower() in ['true', 'pass', 'yes', '1', 'y']
        return False
    
    # Calculate Failed_Filter_Count
    if filter_columns:
        filter_df = df[filter_columns].map(convert_to_bool)
        df['Failed_Filter_Count'] = (~filter_df).sum(axis=1)
        
        # All_Filters_Pass: True if all filters pass (all True)
        df['All_Filters_Pass'] = filter_df.all(axis=1)
        
        # Any_Filter_Fail: True if any filter fails (any False)
        df['Any_Filter_Fail'] = ~filter_df.all(axis=1)
    else:
        # If no filter columns found, initialize with zeros/False
        df['Failed_Filter_Count'] = 0
        df['All_Filters_Pass'] = False
        df['Any_Filter_Fail'] = True
    
    # Status_Matches_AllFilters: True if status matches and all filters pass
    if status_column and status_column in df.columns:
        # Assuming status should be 'pass' or similar when all filters pass
        df['Status_Matches_AllFilters'] = (
            df['All_Filters_Pass'] & 
            (df[status_column].astype(str).str.lower().isin(['pass', 'passed', 'true', '1', 'yes', 'y']))
        )
    else:
        df['Status_Matches_AllFilters'] = df['All_Filters_Pass']
    
    # Handle 17 specific filters
    if filter_17_columns is None and filter_columns:
        filter_17_columns = filter_columns[:17]  # Take first 17
    
    if filter_17_columns and len(filter_17_columns) > 0:
        filter_17_df = df[filter_17_columns].map(convert_to_bool)
        df['Failed_Filter_Count_17'] = (~filter_17_df).sum(axis=1)
        df['All_17_Filters_Pass'] = filter_17_df.all(axis=1)
        df['Any_17_Filter_Fail'] = ~filter_17_df.all(axis=1)
    else:
        # Initialize with default values if no 17 filters specified
        df['Failed_Filter_Count_17'] = 0
        df['All_17_Filters_Pass'] = False
        df['Any_17_Filter_Fail'] = True
    
    return df


def create_template_with_filter_columns(num_rows: int = 10, 
                                       num_filters: int = 20,
                                       include_17_filters: bool = True) -> pd.DataFrame:
    """
    Create a template dataframe with filter columns
    
    Parameters:
    -----------
    num_rows : int
        Number of rows to create
    num_filters : int
        Number of filter columns to create
    include_17_filters : bool
        Whether to ensure at least 17 filter columns exist
    
    Returns:
    --------
    pd.DataFrame with template structure
    """
    np.random.seed(42)
    
    # Ensure at least 17 filters if requested
    if include_17_filters and num_filters < 17:
        num_filters = 17
    
    # Create filter columns
    filter_data = {}
    for i in range(1, num_filters + 1):
        filter_data[f'Filter_{i}'] = np.random.choice([True, False], size=num_rows, p=[0.7, 0.3])
    
    # Create other columns
    data = {
        'ID': range(1, num_rows + 1),
        'Status': np.random.choice(['Pass', 'Fail', 'Pending'], size=num_rows, p=[0.6, 0.3, 0.1]),
        **filter_data
    }
    
    df = pd.DataFrame(data)
    
    # Add the filter calculation columns
    df = add_filter_columns(
        df, 
        filter_columns=[f'Filter_{i}' for i in range(1, num_filters + 1)],
        status_column='Status',
        filter_17_columns=[f'Filter_{i}' for i in range(1, 18)] if num_filters >= 17 else None
    )
    
    return df


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        # Load existing file and add columns
        input_file = sys.argv[1]
        output_file = sys.argv[2] if len(sys.argv) > 2 else input_file.replace('.csv', '_with_filters.csv')
        
        print(f"Loading {input_file}...")
        
        if input_file.endswith('.csv'):
            df = pd.read_csv(input_file)
        elif input_file.endswith(('.xlsx', '.xls')):
            df = pd.read_excel(input_file)
        else:
            print(f"Unsupported file format: {input_file}")
            sys.exit(1)
        
        print(f"Original columns: {list(df.columns)}")
        print(f"Original shape: {df.shape}")
        
        # Add filter columns
        df = add_filter_columns(df)
        
        print(f"\nNew columns added:")
        new_cols = ['Failed_Filter_Count', 'All_Filters_Pass', 'Any_Filter_Fail', 
                   'Status_Matches_AllFilters', 'Failed_Filter_Count_17', 
                   'All_17_Filters_Pass', 'Any_17_Filter_Fail']
        for col in new_cols:
            if col in df.columns:
                print(f"  - {col}")
        
        print(f"\nNew shape: {df.shape}")
        
        # Save
        if output_file.endswith('.csv'):
            df.to_csv(output_file, index=False)
        elif output_file.endswith(('.xlsx', '.xls')):
            df.to_excel(output_file, index=False)
        
        print(f"\nSaved to {output_file}")
    else:
        # Create template
        print("Creating template dataframe with filter columns...")
        df = create_template_with_filter_columns(num_rows=20, num_filters=20)
        
        print(f"\nCreated dataframe with shape: {df.shape}")
        print(f"\nColumns: {list(df.columns)}")
        print(f"\nFirst few rows:")
        print(df.head())
        
        # Save template
        df.to_csv('filter_template.csv', index=False)
        print(f"\nTemplate saved to filter_template.csv")
