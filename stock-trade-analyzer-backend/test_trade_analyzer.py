"""
Test script to inspect Excel file and test the Trade Analyzer API
Run this in the stock-trade-analyzer-backend directory
"""

import pandas as pd
import requests
import json
from pathlib import Path
import time
from typing import Dict, List

# ============== CONFIGURATION ==============
EXCEL_FILE = "Stocks_Order_History_3499151741_01-04-2020_04-12-2025.xlsx"
API_BASE_URL = "http://localhost:8000"
API_TIMEOUT = 30


class ExcelInspector:
    """Inspect and display Excel file structure"""
    
    def __init__(self, filepath: str):
        self.filepath = filepath
        self.df = None
        
    def load(self) -> bool:
        """Load Excel file"""
        try:
            self.df = pd.read_excel(self.filepath, skiprows=5)
            print(f"✓ Successfully loaded Excel file: {self.filepath}\n")
            return True
        except FileNotFoundError:
            print(f"✗ File not found: {self.filepath}")
            return False
        except Exception as e:
            print(f"✗ Error loading file: {e}")
            return False
    
    def inspect(self):
        """Display file inspection results"""
        if self.df is None:
            return
            
        print("=" * 80)
        print("EXCEL FILE INSPECTION (skiprows=5)")
        print("=" * 80)
        
        # Basic info
        print(f"\n📊 BASIC INFORMATION:")
        print(f"  Rows: {len(self.df)}")
        print(f"  Columns: {len(self.df.columns)}")
        print(f"  Memory Usage: {self.df.memory_usage(deep=True).sum() / 1024:.2f} KB")
        
        # Column info
        print(f"\n📋 COLUMN NAMES & TYPES:")
        for idx, (col, dtype) in enumerate(zip(self.df.columns, self.df.dtypes), 1):
            print(f"  {idx:2d}. {col:35} → {dtype}")
        
        # Missing values
        print(f"\n⚠️  MISSING VALUES:")
        missing = self.df.isnull().sum()
        has_missing = missing[missing > 0]
        if len(has_missing) > 0:
            for col, count in has_missing.items():
                print(f"  {col}: {count} ({count/len(self.df)*100:.1f}%)")
        else:
            print(f"  None - data is complete ✓")
        
        # Data ranges
        print(f"\n📈 DATA RANGES:")
        for col in self.df.columns:
            if pd.api.types.is_numeric_dtype(self.df[col]):
                min_val = self.df[col].min()
                max_val = self.df[col].max()
                print(f"  {col:35} → Min: {min_val:>12}, Max: {max_val:>12}")
            elif pd.api.types.is_datetime64_any_dtype(self.df[col]):
                print(f"  {col:35} → From: {self.df[col].min()}, To: {self.df[col].max()}")
            else:
                unique_count = self.df[col].nunique()
                print(f"  {col:35} → {unique_count} unique values")
        
        # Sample rows
        print(f"\n📌 FIRST 5 ROWS:")
        print(self.df.head().to_string(index=False))
        
        print(f"\n📌 LAST 5 ROWS:")
        print(self.df.tail().to_string(index=False))
        
        # Unique symbols
        symbol_cols = [col for col in self.df.columns if 'symbol' in col.lower() or 'isin' in col.lower() or 'stock' in col.lower()]
        if symbol_cols:
            print(f"\n🏷️  SYMBOLS/STOCKS:")
            for col in symbol_cols:
                symbols = self.df[col].unique()
                print(f"  {col}: {len(symbols)} unique → {', '.join(map(str, symbols[:5]))}")
                if len(symbols) > 5:
                    print(f"        ... and {len(symbols) - 5} more")


class APITester:
    """Test the Trade Analyzer API"""
    
    def __init__(self, base_url: str = API_BASE_URL):
        self.base_url = base_url
        self.session = requests.Session()
        
    def health_check(self) -> bool:
        """Check if API is running"""
        try:
            print(f"\n🔍 Checking API health at {self.base_url}...")
            response = self.session.get(f"{self.base_url}/health", timeout=5)
            if response.status_code == 200:
                data = response.json()
                print(f"✓ API is running")
                print(f"  Status: {data.get('status')}")
                print(f"  Timestamp: {data.get('timestamp')}")
                return True
            else:
                print(f"✗ API returned status {response.status_code}")
                return False
        except requests.ConnectionError:
            print(f"✗ Cannot connect to API at {self.base_url}")
            print(f"  Make sure backend is running: python stock_analyzer_backend_v2.py")
            return False
        except Exception as e:
            print(f"✗ Error: {e}")
            return False
    
    def upload_and_analyze(self, filepath: str, skip_rows: int = None) -> Dict:
        """
        Upload Excel file and get analysis results
        
        Args:
            filepath: Path to Excel file
            skip_rows: Optional - number of rows to skip (None = auto-detect)
        """
        try:
            print(f"\n📤 Uploading {Path(filepath).name}...")
            if skip_rows is not None:
                print(f"   (with skip_rows={skip_rows})")
            else:
                print(f"   (auto-detecting header rows)")
            
            with open(filepath, 'rb') as f:
                files = {'file': f}
                params = {}
                if skip_rows is not None:
                    params['skip_rows'] = skip_rows
                
                response = self.session.post(
                    f"{self.base_url}/analyze-xlsx",
                    files=files,
                    params=params,
                    timeout=API_TIMEOUT
                )
            
            if response.status_code == 200:
                result = response.json()
                print(f"✓ Analysis successful!")
                return result
            else:
                print(f"✗ API error ({response.status_code})")
                try:
                    error_detail = response.json().get('detail', 'Unknown error')
                    print(f"  Error: {error_detail}")
                except:
                    print(f"  Response: {response.text}")
                return None
                
        except requests.ConnectionError:
            print(f"✗ Cannot connect to API")
            return None
        except Exception as e:
            print(f"✗ Error uploading file: {e}")
            return None
    
    def test_single_trade(self, entry: float, exit_price: float, qty: int, commission: float = 0) -> Dict:
        """Test single trade analysis endpoint"""
        try:
            print(f"\n🔄 Testing single trade endpoint...")
            data = {
                "entry_price": entry,
                "exit_price": exit_price,
                "quantity": qty,
                "commission": commission
            }
            response = self.session.post(
                f"{self.base_url}/single-trade",
                json=data,
                timeout=API_TIMEOUT
            )
            
            if response.status_code == 200:
                result = response.json()
                print(f"✓ Single trade analysis successful!")
                return result
            else:
                print(f"✗ API error ({response.status_code}): {response.text}")
                return None
                
        except Exception as e:
            print(f"✗ Error: {e}")
            return None


def format_currency(value: float) -> str:
    """Format value as currency"""
    return f"₹{value:,.2f}"


def display_analysis_results(result: Dict):
    """Pretty print analysis results"""
    if not result:
        return
    
    print("\n" + "=" * 80)
    print("ANALYSIS RESULTS")
    print("=" * 80)
    
    # Summary
    if 'summary' in result:
        summary = result['summary']
        print(f"\n📋 SUMMARY:")
        print(f"  File: {summary.get('file_name', 'N/A')}")
        print(f"  Rows Skipped: {summary.get('rows_skipped', 0)}")
        print(f"  Rows Processed: {summary.get('rows_processed', 0)}")
        print(f"  Unique Symbols: {summary.get('total_symbols', 0)}")
        print(f"  Analysis Date: {summary.get('analysis_date', 'N/A')}")
    
    # Metrics
    if 'metrics' in result:
        metrics = result['metrics']
        print(f"\n💹 KEY METRICS:")
        print(f"  Total Trades: {metrics.get('total_trades', 0)}")
        print(f"  Closed Trades: {metrics.get('closed_trades', 0)}")
        print(f"  Open Trades: {metrics.get('open_trades', 0)}")
        print(f"  Winning Trades: {metrics.get('winning_trades', 0)}")
        print(f"  Losing Trades: {metrics.get('losing_trades', 0)}")
        print(f"  Win Rate: {metrics.get('win_rate', 0):.2f}%")
        print(f"  Total P&L: {format_currency(metrics.get('total_pnl', 0))}")
        print(f"  Profit Factor: {metrics.get('profit_factor', 0):.2f}")
        print(f"  Best Trade: {format_currency(metrics.get('best_trade', 0))}")
        print(f"  Worst Trade: {format_currency(metrics.get('worst_trade', 0))}")
        print(f"  Avg Win: {format_currency(metrics.get('avg_win', 0))}")
        print(f"  Avg Loss: {format_currency(metrics.get('avg_loss', 0))}")
    
    # Positions (NEW)
    if 'positions' in result and result['positions']:
        positions = result['positions']
        print(f"\n📈 CURRENT POSITIONS ({len(positions)} holdings):")
        print(f"  {'Symbol':<10} {'Quantity':>12} {'Avg Price':>15} {'Total Cost':>15}")
        print(f"  {'-'*10} {'-'*12} {'-'*15} {'-'*15}")
        
        total_investment = 0
        for pos in sorted(positions, key=lambda x: x['symbol']):
            symbol = pos['symbol']
            qty = pos['quantity']
            avg_price = pos['avg_price']
            total_cost = pos['total_cost']
            total_investment += total_cost
            
            print(f"  {symbol:<10} {qty:>12} {format_currency(avg_price):>15} {format_currency(total_cost):>15}")
        
        print(f"  {'-'*10} {'-'*12} {'-'*15} {'-'*15}")
        print(f"  {'TOTAL':<10} {'':<12} {'':<15} {format_currency(total_investment):>15}")
    
    # Trades sample
    if 'trades' in result and result['trades']:
        trades = result['trades']
        print(f"\n📊 TRADE SAMPLE (First 10 closed trades):")
        print(f"  Total trades: {len(trades)}")
        
        closed_count = 0
        for i, trade in enumerate(trades):
            if trade['status'] == 'Open':
                continue
            if closed_count >= 10:
                break
            
            closed_count += 1
            status_emoji = "✓" if trade['pnl'] > 0 else "✗" if trade['pnl'] < 0 else "○"
            print(f"\n  Trade {closed_count}: {status_emoji} {trade['symbol']}")
            print(f"    Buy:  {trade['entry_date']} @ {format_currency(trade['entry_price'])}")
            if trade['exit_date']:
                print(f"    Sell: {trade['exit_date']} @ {format_currency(trade['exit_price'])}")
                print(f"    Qty:  {trade['quantity']} units | Commission: {format_currency(trade['commission'])}")
                print(f"    P&L:  {format_currency(trade['pnl'])} ({trade['pnl_percent']:+.2f}%)")
            else:
                print(f"    Status: OPEN (Qty: {trade['quantity']})")
            print(f"    Status: {trade['status']}")


def display_single_trade_result(result: Dict):
    """Pretty print single trade result"""
    if not result:
        return
    
    print("\n" + "-" * 80)
    print("SINGLE TRADE RESULT:")
    print("-" * 80)
    print(f"Entry Price:  {format_currency(result.get('entry_price', 0))}")
    print(f"Exit Price:   {format_currency(result.get('exit_price', 0))}")
    print(f"Quantity:     {result.get('quantity', 0)}")
    print(f"Commission:   {format_currency(result.get('commission', 0))}")
    print(f"P&L:          {format_currency(result.get('pnl', 0))}")
    print(f"Return %:     {result.get('pnl_percent', 0):+.2f}%")
    print(f"Status:       {result.get('status', 'N/A')}")


def main():
    """Main test workflow"""
    print("\n" + "=" * 80)
    print("STOCK TRADE ANALYZER - TEST SUITE")
    print("=" * 80)
    
    # Step 1: Inspect Excel file
    print("\n▶ STEP 1: INSPECT EXCEL FILE")
    inspector = ExcelInspector(EXCEL_FILE)
    if not inspector.load():
        return
    inspector.inspect()
    
    # Step 2: Check API health
    print("\n\n▶ STEP 2: CHECK API HEALTH")
    tester = APITester(API_BASE_URL)
    if not tester.health_check():
        print("\n⚠️  Backend API is not running!")
        print("Start it with: python stock_analyzer_backend_v2.py")
        return
    
    # Step 3: Upload and analyze (auto-detect)
    print("\n\n▶ STEP 3: UPLOAD AND ANALYZE (AUTO-DETECT)")
    result = tester.upload_and_analyze(EXCEL_FILE)
    if result:
        display_analysis_results(result)
    
    # Step 4: Upload and analyze (explicit skip_rows)
    print("\n\n▶ STEP 4: UPLOAD AND ANALYZE (WITH skip_rows=5)")
    result_explicit = tester.upload_and_analyze(EXCEL_FILE, skip_rows=5)
    if result_explicit:
        display_analysis_results(result_explicit)
    
    # Step 5: Test single trade
    print("\n\n▶ STEP 5: TEST SINGLE TRADE ENDPOINT")
    single_result = tester.test_single_trade(
        entry=2500,
        exit_price=2700,
        qty=10,
        commission=0
    )
    if single_result:
        display_single_trade_result(single_result)
    
    print("\n\n" + "=" * 80)
    print("TEST SUITE COMPLETE")
    print("=" * 80 + "\n")


if __name__ == "__main__":
    main()