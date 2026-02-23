#!/usr/bin/env python3
"""
Take Rate Analysis Tool
Analyzes take rate data to provide insights and recommendations
"""

import pandas as pd
import numpy as np
import json
from pathlib import Path
from typing import Dict, List, Optional
import sys

class TakeRateAnalyzer:
    """Analyzes take rate data and generates insights"""
    
    def __init__(self, data: pd.DataFrame):
        """
        Initialize analyzer with take rate data
        
        Expected columns:
        - transaction_id, date, seller_id, category, transaction_value, 
          take_rate, fees_collected, etc.
        """
        self.df = data.copy()
        self.insights = {}
        
    def basic_statistics(self) -> Dict:
        """Calculate basic statistics"""
        stats = {
            'total_transactions': len(self.df),
            'total_volume': self.df.get('transaction_value', pd.Series([0])).sum(),
            'total_fees': self.df.get('fees_collected', pd.Series([0])).sum(),
        }
        
        if 'take_rate' in self.df.columns:
            stats['avg_take_rate'] = self.df['take_rate'].mean()
            stats['median_take_rate'] = self.df['take_rate'].median()
            stats['min_take_rate'] = self.df['take_rate'].min()
            stats['max_take_rate'] = self.df['take_rate'].max()
            stats['std_take_rate'] = self.df['take_rate'].std()
        
        if 'transaction_value' in self.df.columns:
            stats['avg_transaction_value'] = self.df['transaction_value'].mean()
            stats['median_transaction_value'] = self.df['transaction_value'].median()
        
        if 'fees_collected' in self.df.columns and 'transaction_value' in self.df.columns:
            stats['effective_take_rate'] = (
                stats['total_fees'] / stats['total_volume'] * 100
                if stats['total_volume'] > 0 else 0
            )
        
        return stats
    
    def analyze_by_category(self) -> pd.DataFrame:
        """Analyze take rates by category"""
        if 'category' not in self.df.columns:
            return pd.DataFrame()
        
        category_analysis = self.df.groupby('category').agg({
            'transaction_value': ['sum', 'mean', 'count'],
            'fees_collected': 'sum',
            'take_rate': ['mean', 'std', 'min', 'max']
        }).round(2)
        
        category_analysis['effective_rate'] = (
            category_analysis[('fees_collected', 'sum')] / 
            category_analysis[('transaction_value', 'sum')] * 100
        ).round(2)
        
        return category_analysis
    
    def analyze_by_seller(self) -> pd.DataFrame:
        """Analyze take rates by seller"""
        if 'seller_id' not in self.df.columns:
            return pd.DataFrame()
        
        seller_analysis = self.df.groupby('seller_id').agg({
            'transaction_value': ['sum', 'mean', 'count'],
            'fees_collected': 'sum',
            'take_rate': ['mean', 'std']
        }).round(2)
        
        seller_analysis['effective_rate'] = (
            seller_analysis[('fees_collected', 'sum')] / 
            seller_analysis[('transaction_value', 'sum')] * 100
        ).round(2)
        
        seller_analysis = seller_analysis.sort_values(
            by=('transaction_value', 'sum'), 
            ascending=False
        )
        
        return seller_analysis
    
    def analyze_by_time_period(self, period: str = 'M') -> pd.DataFrame:
        """Analyze take rates over time"""
        if 'date' not in self.df.columns:
            return pd.DataFrame()
        
        self.df['date'] = pd.to_datetime(self.df['date'])
        self.df['period'] = self.df['date'].dt.to_period(period)
        
        time_analysis = self.df.groupby('period').agg({
            'transaction_value': ['sum', 'count'],
            'fees_collected': 'sum',
            'take_rate': 'mean'
        }).round(2)
        
        time_analysis['effective_rate'] = (
            time_analysis[('fees_collected', 'sum')] / 
            time_analysis[('transaction_value', 'sum')] * 100
        ).round(2)
        
        return time_analysis
    
    def identify_opportunities(self) -> Dict:
        """Identify improvement opportunities"""
        opportunities = {
            'low_rate_high_volume': [],
            'high_rate_low_volume': [],
            'inconsistent_rates': [],
            'recommendations': []
        }
        
        # Analyze by category if available
        if 'category' in self.df.columns:
            cat_analysis = self.analyze_by_category()
            if not cat_analysis.empty:
                # Find categories with low rates but high volume
                high_volume = cat_analysis[('transaction_value', 'sum')].nlargest(5)
                for cat in high_volume.index:
                    avg_rate = cat_analysis.loc[cat, ('take_rate', 'mean')]
                    if avg_rate < cat_analysis[('take_rate', 'mean')].mean():
                        opportunities['low_rate_high_volume'].append({
                            'category': cat,
                            'volume': high_volume[cat],
                            'current_rate': avg_rate,
                            'opportunity': 'Consider rate increase'
                        })
        
        # Analyze by seller if available
        if 'seller_id' in self.df.columns:
            seller_analysis = self.analyze_by_seller()
            if not seller_analysis.empty:
                # Top sellers by volume
                top_sellers = seller_analysis.head(10)
                for seller_id in top_sellers.index:
                    volume = top_sellers.loc[seller_id, ('transaction_value', 'sum')]
                    rate = top_sellers.loc[seller_id, ('take_rate', 'mean')]
                    opportunities['recommendations'].append({
                        'seller_id': seller_id,
                        'volume': volume,
                        'rate': rate,
                        'action': 'Consider volume-based tiered pricing'
                    })
        
        # Rate consistency analysis
        if 'take_rate' in self.df.columns:
            rate_std = self.df['take_rate'].std()
            if rate_std > self.df['take_rate'].mean() * 0.3:  # High variance
                opportunities['inconsistent_rates'].append({
                    'issue': 'High variance in take rates',
                    'std': rate_std,
                    'recommendation': 'Standardize rate structure'
                })
        
        return opportunities
    
    def generate_report(self) -> str:
        """Generate comprehensive analysis report"""
        report = []
        report.append("=" * 80)
        report.append("TAKE RATE ANALYSIS REPORT")
        report.append("=" * 80)
        report.append("")
        
        # Basic Statistics
        stats = self.basic_statistics()
        report.append("## BASIC STATISTICS")
        report.append("-" * 80)
        for key, value in stats.items():
            if isinstance(value, (int, float)):
                if 'rate' in key.lower() or 'percentage' in key.lower():
                    report.append(f"{key.replace('_', ' ').title()}: {value:.2f}%")
                elif 'value' in key.lower() or 'fees' in key.lower() or 'volume' in key.lower():
                    report.append(f"{key.replace('_', ' ').title()}: ${value:,.2f}")
                else:
                    report.append(f"{key.replace('_', ' ').title()}: {value:,.0f}")
            else:
                report.append(f"{key.replace('_', ' ').title()}: {value}")
        report.append("")
        
        # Category Analysis
        if 'category' in self.df.columns:
            cat_analysis = self.analyze_by_category()
            if not cat_analysis.empty:
                report.append("## ANALYSIS BY CATEGORY")
                report.append("-" * 80)
                report.append(cat_analysis.to_string())
                report.append("")
        
        # Seller Analysis (Top 10)
        if 'seller_id' in self.df.columns:
            seller_analysis = self.analyze_by_seller()
            if not seller_analysis.empty:
                report.append("## TOP 10 SELLERS BY VOLUME")
                report.append("-" * 80)
                report.append(seller_analysis.head(10).to_string())
                report.append("")
        
        # Time Series Analysis
        if 'date' in self.df.columns:
            time_analysis = self.analyze_by_time_period()
            if not time_analysis.empty:
                report.append("## TIME SERIES ANALYSIS (Monthly)")
                report.append("-" * 80)
                report.append(time_analysis.to_string())
                report.append("")
        
        # Opportunities
        opportunities = self.identify_opportunities()
        report.append("## IMPROVEMENT OPPORTUNITIES")
        report.append("-" * 80)
        
        if opportunities['low_rate_high_volume']:
            report.append("\n### Low Rate, High Volume Categories:")
            for opp in opportunities['low_rate_high_volume']:
                report.append(f"  - {opp['category']}: ${opp['volume']:,.2f} volume, {opp['current_rate']:.2f}% rate")
                report.append(f"    → {opp['opportunity']}")
        
        if opportunities['recommendations']:
            report.append("\n### Recommendations:")
            for rec in opportunities['recommendations'][:5]:  # Top 5
                report.append(f"  - Seller {rec['seller_id']}: {rec['action']}")
        
        if opportunities['inconsistent_rates']:
            for issue in opportunities['inconsistent_rates']:
                report.append(f"\n### {issue['issue']}:")
                report.append(f"  - Standard Deviation: {issue['std']:.2f}%")
                report.append(f"  - Recommendation: {issue['recommendation']}")
        
        report.append("")
        report.append("=" * 80)
        
        return "\n".join(report)


def load_data(file_path: str) -> pd.DataFrame:
    """Load data from various file formats"""
    path = Path(file_path)
    
    if not path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")
    
    if path.suffix == '.csv':
        return pd.read_csv(file_path)
    elif path.suffix in ['.xlsx', '.xls']:
        return pd.read_excel(file_path)
    elif path.suffix == '.json':
        return pd.read_json(file_path)
    else:
        raise ValueError(f"Unsupported file format: {path.suffix}")


def main():
    """Main function"""
    if len(sys.argv) < 2:
        print("Usage: python analyze_take_rates.py <data_file> [output_file]")
        print("\nSupported formats: CSV, Excel (.xlsx, .xls), JSON")
        print("\nExpected columns in data:")
        print("  - transaction_id (optional)")
        print("  - date (optional)")
        print("  - seller_id (optional)")
        print("  - category (optional)")
        print("  - transaction_value (required)")
        print("  - take_rate (required)")
        print("  - fees_collected (optional, can be calculated)")
        sys.exit(1)
    
    data_file = sys.argv[1]
    output_file = sys.argv[2] if len(sys.argv) > 2 else None
    
    try:
        # Load data
        print(f"Loading data from {data_file}...")
        df = load_data(data_file)
        print(f"Loaded {len(df)} records")
        print(f"Columns: {', '.join(df.columns)}")
        print()
        
        # Calculate fees if not provided
        if 'fees_collected' not in df.columns and 'take_rate' in df.columns and 'transaction_value' in df.columns:
            df['fees_collected'] = df['transaction_value'] * df['take_rate'] / 100
            print("Calculated fees_collected from transaction_value and take_rate")
        
        # Analyze
        analyzer = TakeRateAnalyzer(df)
        report = analyzer.generate_report()
        
        # Output
        if output_file:
            with open(output_file, 'w') as f:
                f.write(report)
            print(f"\nReport saved to {output_file}")
        else:
            print(report)
        
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
