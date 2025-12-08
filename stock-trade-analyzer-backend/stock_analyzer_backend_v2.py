from fastapi import FastAPI, UploadFile, File, HTTPException, Request, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
from typing import List, Dict, Optional
import pandas as pd
import openpyxl
from openpyxl.utils import get_column_letter
import json
from datetime import datetime, timedelta
import io
import traceback
import os
import httpx

app = FastAPI(title="Stock Trade Analyzer API", version="2.0.0")

# Upstox Configuration - Set these as environment variables on Render
UPSTOX_API_KEY = os.environ.get("UPSTOX_API_KEY", "")
UPSTOX_API_SECRET = os.environ.get("UPSTOX_API_SECRET", "")
UPSTOX_REDIRECT_URI = os.environ.get("UPSTOX_REDIRECT_URI", "https://your-app.onrender.com/upstox/callback")
# FRONTEND_URL is optional - if not set, callback will return JSON instead of redirecting
FRONTEND_URL = os.environ.get("FRONTEND_URL", "")

# In-memory token storage (use Redis/DB in production)
upstox_tokens: Dict[str, Dict] = {}

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Pydantic Models
class TradeData(BaseModel):
    symbol: str
    entry_price: float
    entry_date: str
    exit_price: Optional[float] = None
    exit_date: Optional[str] = None
    quantity: int
    pnl: float
    pnl_percent: float
    status: str  # "Profitable", "Loss", "Open"
    commission: float = 0

class PositionData(BaseModel):
    symbol: str
    quantity: int
    avg_price: float
    total_cost: float

class AnalysisResult(BaseModel):
    trades: List[TradeData]
    positions: List[PositionData]
    metrics: Dict
    summary: Dict

# Helper Functions
def detect_data_start_row(file_content: bytes) -> int:
    """
    Auto-detect where actual data starts by looking for required column headers.
    Returns the row number to skip to, or 0 if data starts at row 0.
    """
    try:
        # Read without skipping to examine headers
        excel_file = io.BytesIO(file_content)
        wb = openpyxl.load_workbook(excel_file)
        ws = wb.active
        
        required_keywords = ['symbol', 'isin', 'scrip', 'date', 'order', 'price', 'quantity', 'qty']
        
        # Check first 10 rows for header row
        for row_idx in range(1, min(11, ws.max_row + 1)):
            row_values = [str(cell.value).lower() if cell.value else '' for cell in ws[row_idx]]
            row_text = ' '.join(row_values)
            
            # Count how many required keywords are in this row
            match_count = sum(1 for keyword in required_keywords if keyword in row_text)
            
            # If this row has multiple keywords, it's likely the header
            if match_count >= 3:
                return row_idx  # Return the row number (1-indexed)
        
        return 0  # Default: no headers found, assume data starts at row 1
    
    except Exception as e:
        print(f"Auto-detect warning: {e}, using default skip_rows=5")
        return 5


def parse_excel_file(file_content: bytes, skip_rows: Optional[int] = None) -> tuple:
    """
    Parse Excel file and return DataFrame with actual skip_rows used.
    
    Args:
        file_content: Raw file bytes
        skip_rows: Number of rows to skip (None = auto-detect, default tries 5 first)
    
    Returns:
        Tuple of (DataFrame, rows_skipped)
    """
    try:
        excel_file = io.BytesIO(file_content)
        
        # Determine skip_rows strategy
        if skip_rows is not None:
            # User specified skip_rows
            df = pd.read_excel(excel_file, skiprows=skip_rows)
            rows_skipped = skip_rows
        else:
            # Try default of 5 first (common for broker exports)
            try:
                df = pd.read_excel(excel_file, skiprows=5)
                rows_skipped = 5
                
                # Verify we got actual data with expected columns
                df_normalized = df.copy()
                df_normalized.columns = df_normalized.columns.str.strip().str.lower()
                
                expected_cols = ['symbol', 'date', 'order_type', 'price', 'quantity']
                expected_present = sum(1 for col in expected_cols if col in df_normalized.columns or any(alt in df_normalized.columns for alt in ['isin', 'scrip', 'side', 'buy_sell', 'qty', 'shares', 'execution date and time', 'type', 'value']))
                
                if expected_present < 3:
                    # Not a good match, try auto-detect
                    raise ValueError("Expected columns not found with skip_rows=5")
            
            except Exception:
                # Fall back to auto-detection
                excel_file.seek(0)
                detected_skip = detect_data_start_row(excel_file.getvalue())
                excel_file.seek(0)
                
                if detected_skip > 0:
                    df = pd.read_excel(excel_file, skiprows=detected_skip - 1)
                    rows_skipped = detected_skip - 1
                else:
                    # Last resort: read without skipping
                    excel_file.seek(0)
                    df = pd.read_excel(excel_file)
                    rows_skipped = 0
        
        if df.empty:
            raise ValueError("Resulting dataframe is empty")
        
        return df, rows_skipped
    
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error reading Excel file: {str(e)}")


def normalize_column_names(df: pd.DataFrame) -> pd.DataFrame:
    """Normalize column names to standard format"""
    df.columns = df.columns.str.strip().str.lower()
    return df


def match_trades_fifo(orders: pd.DataFrame) -> tuple:
    """
    Match BUY and SELL orders using FIFO (First In, First Out) algorithm
    Tracks average price for each stock
    Returns: (trades_list, positions_list)
    """
    print(f"DEBUG match_trades_fifo: Starting with {len(orders)} rows")
    print(f"DEBUG match_trades_fifo: Columns available: {list(orders.columns)}")
    
    trades = []
    open_positions = {}
    stock_avg_prices = {}  # Track average price per stock
    
    # Sort by date
    try:
        print(f"DEBUG match_trades_fifo: Attempting to sort by 'date'")
        print(f"DEBUG match_trades_fifo: Date column type: {orders['date'].dtype}")
        print(f"DEBUG match_trades_fifo: Sample date values: {orders['date'].head(3).tolist()}")
        orders = orders.sort_values('date')
        print(f"DEBUG match_trades_fifo: Sort successful")
    except KeyError as ke:
        print(f"ERROR in match_trades_fifo: KeyError when accessing 'date' - {ke}")
        print(f"ERROR: Available columns: {list(orders.columns)}")
        raise
    except Exception as e:
        print(f"ERROR in match_trades_fifo: {type(e).__name__}: {e}")
        raise
    
    for idx, (_, row) in enumerate(orders.iterrows()):
        try:
            symbol = str(row.get('symbol', 'UNKNOWN')).upper().strip()
            order_type = str(row.get('order_type', 'BUY')).upper().strip()
            price = float(row.get('price', 0)) if pd.notna(row.get('price')) else 0
            quantity = int(float(row.get('quantity', 0))) if pd.notna(row.get('quantity')) else 0
            date = row['date']
            commission = float(row.get('commission', 0)) if pd.notna(row.get('commission', 0)) else 0
            
            if quantity <= 0:
                continue
            
            if symbol not in open_positions:
                open_positions[symbol] = {'buys': [], 'sells': []}
                stock_avg_prices[symbol] = {'quantity': 0, 'total_cost': 0, 'avg_price': 0}
            
            if 'BUY' in order_type:
                # Add to open positions
                open_positions[symbol]['buys'].append({
                    'price': price,
                    'quantity': quantity,
                    'date': date,
                    'commission': commission
                })
                
                # Update average price for this stock
                current_qty = stock_avg_prices[symbol]['quantity']
                current_cost = stock_avg_prices[symbol]['total_cost']
                
                new_total_cost = current_cost + (price * quantity) + commission
                new_total_qty = current_qty + quantity
                
                stock_avg_prices[symbol]['quantity'] = new_total_qty
                stock_avg_prices[symbol]['total_cost'] = new_total_cost
                stock_avg_prices[symbol]['avg_price'] = new_total_cost / new_total_qty if new_total_qty > 0 else 0
                
                print(f"  BUY {symbol}: {quantity} @ ₹{price:.2f} | Avg Price: ₹{stock_avg_prices[symbol]['avg_price']:.2f} | Total Qty: {new_total_qty}")
                
            elif 'SELL' in order_type:
                # Match with oldest BUY orders (FIFO)
                remaining_qty = quantity
                
                while remaining_qty > 0 and open_positions[symbol]['buys']:
                    buy = open_positions[symbol]['buys'][0]
                    
                    if buy['quantity'] <= remaining_qty:
                        # Complete match
                        matched_qty = buy['quantity']
                        pnl = (price - buy['price']) * matched_qty - (buy['commission'] + commission)
                        pnl_percent = ((price - buy['price']) / buy['price'] * 100) if buy['price'] != 0 else 0
                        
                        trades.append({
                            'symbol': symbol,
                            'entry_price': buy['price'],
                            'entry_date': str(buy['date']),
                            'exit_price': price,
                            'exit_date': str(date),
                            'quantity': matched_qty,
                            'pnl': round(pnl, 2),
                            'pnl_percent': round(pnl_percent, 2),
                            'status': 'Profitable' if pnl > 0 else 'Loss' if pnl < 0 else 'Breakeven',
                            'commission': round(buy['commission'] + commission, 2)
                        })
                        
                        remaining_qty -= matched_qty
                        open_positions[symbol]['buys'].pop(0)
                    else:
                        # Partial match
                        matched_qty = remaining_qty
                        pnl = (price - buy['price']) * matched_qty - (buy['commission'] + commission)
                        pnl_percent = ((price - buy['price']) / buy['price'] * 100) if buy['price'] != 0 else 0
                        
                        trades.append({
                            'symbol': symbol,
                            'entry_price': buy['price'],
                            'entry_date': str(buy['date']),
                            'exit_price': price,
                            'exit_date': str(date),
                            'quantity': matched_qty,
                            'pnl': round(pnl, 2),
                            'pnl_percent': round(pnl_percent, 2),
                            'status': 'Profitable' if pnl > 0 else 'Loss' if pnl < 0 else 'Breakeven',
                            'commission': round(buy['commission'] + commission, 2)
                        })
                        
                        buy['quantity'] -= matched_qty
                        remaining_qty = 0
                
                # Update average price after sell (reduce quantity)
                current_qty = stock_avg_prices[symbol]['quantity']
                current_cost = stock_avg_prices[symbol]['total_cost']
                
                # Reduce by sold quantity proportionally
                if current_qty > 0:
                    cost_per_unit = current_cost / current_qty
                    reduction = quantity * cost_per_unit
                    
                    new_total_qty = max(0, current_qty - quantity)
                    new_total_cost = max(0, current_cost - reduction)
                    
                    stock_avg_prices[symbol]['quantity'] = new_total_qty
                    stock_avg_prices[symbol]['total_cost'] = new_total_cost
                    stock_avg_prices[symbol]['avg_price'] = new_total_cost / new_total_qty if new_total_qty > 0 else 0
                    
                    print(f"  SELL {symbol}: {quantity} @ ₹{price:.2f} | Remaining Qty: {new_total_qty} | Avg Price: ₹{stock_avg_prices[symbol]['avg_price']:.2f}")
                
        except Exception as e:
            print(f"ERROR in match_trades_fifo row {idx}: {type(e).__name__} - {e}")
            raise
    
    # Add open positions
    for symbol, positions in open_positions.items():
        for buy in positions['buys']:
            trades.append({
                'symbol': symbol,
                'entry_price': buy['price'],
                'entry_date': str(buy['date']),
                'exit_price': None,
                'exit_date': None,
                'quantity': buy['quantity'],
                'pnl': 0,
                'pnl_percent': 0,
                'status': 'Open',
                'commission': buy['commission']
            })
    
    # Build positions list from stock_avg_prices
    print(f"\nDEBUG match_trades_fifo: Final Average Prices by Stock:")
    positions = []
    for symbol, avg_data in stock_avg_prices.items():
        if avg_data['quantity'] > 0:
            positions.append({
                'symbol': symbol,
                'quantity': avg_data['quantity'],
                'avg_price': round(avg_data['avg_price'], 2),
                'total_cost': round(avg_data['total_cost'], 2)
            })
            print(f"  {symbol}: Avg Price = ₹{avg_data['avg_price']:.2f} | Remaining Qty: {avg_data['quantity']} | Total Cost: ₹{avg_data['total_cost']:.2f}")
    
    print(f"DEBUG match_trades_fifo: Created {len(trades)} trades, {len(positions)} open positions\n")
    return trades, positions


def calculate_metrics(trades: List[Dict]) -> Dict:
    """Calculate portfolio metrics from matched trades"""
    if not trades:
        return {}
    
    closed_trades = [t for t in trades if t['status'] != 'Open']
    open_trades = [t for t in trades if t['status'] == 'Open']
    
    if not closed_trades:
        return {
            'total_trades': len(trades),
            'closed_trades': 0,
            'open_trades': len(open_trades),
            'win_rate': 0,
            'total_pnl': 0,
            'avg_win': 0,
            'avg_loss': 0,
            'best_trade': 0,
            'worst_trade': 0,
            'profit_factor': 0
        }
    
    winning_trades = [t for t in closed_trades if t['pnl'] > 0]
    losing_trades = [t for t in closed_trades if t['pnl'] < 0]
    
    total_pnl = sum(t['pnl'] for t in closed_trades)
    win_rate = (len(winning_trades) / len(closed_trades) * 100) if closed_trades else 0
    
    avg_win = sum(t['pnl'] for t in winning_trades) / len(winning_trades) if winning_trades else 0
    avg_loss = abs(sum(t['pnl'] for t in losing_trades) / len(losing_trades)) if losing_trades else 0
    
    best_trade = max((t['pnl'] for t in closed_trades), default=0)
    worst_trade = min((t['pnl'] for t in closed_trades), default=0)
    
    gross_profit = sum(t['pnl'] for t in winning_trades) if winning_trades else 0
    gross_loss = abs(sum(t['pnl'] for t in losing_trades)) if losing_trades else 0
    
    profit_factor = gross_profit / gross_loss if gross_loss > 0 else 0
    
    return {
        'total_trades': len(trades),
        'closed_trades': len(closed_trades),
        'open_trades': len(open_trades),
        'winning_trades': len(winning_trades),
        'losing_trades': len(losing_trades),
        'win_rate': round(win_rate, 2),
        'total_pnl': round(total_pnl, 2),
        'avg_win': round(avg_win, 2),
        'avg_loss': round(avg_loss, 2),
        'best_trade': round(best_trade, 2),
        'worst_trade': round(worst_trade, 2),
        'profit_factor': round(profit_factor, 2)
    }


# API Routes
@app.get("/")
@app.head("/")
async def root():
    return {
        "message": "Stock Trade Analyzer API v2.0.0",
        "endpoints": [
            "/analyze-xlsx - POST: Upload Excel file for analysis (query param: skip_rows=5)",
            "/health - GET: Check API health"
        ]
    }


@app.get("/health")
async def health_check():
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}


@app.post("/analyze-xlsx", response_model=AnalysisResult)
async def analyze_xlsx(file: UploadFile = File(...), skip_rows: Optional[int] = None):
    """
    Analyze uploaded Excel file with trade data.
    
    Handles files with broker header information by:
    1. Trying skip_rows parameter if provided
    2. Defaulting to skip_rows=5 (common broker format)
    3. Auto-detecting header row if default doesn't work
    
    Args:
        file: Excel file (.xlsx)
        skip_rows: Optional - number of header rows to skip (default: auto-detect, usually 5)
    
    Expected columns: Symbol, Date, Order Type, Price, Quantity, Commission
    """
    try:
        print("\n" + "="*80)
        print("ANALYZING FILE")
        print("="*80)
        
        # Read file with smart skip_rows handling
        contents = await file.read()
        print(f"File received: {file.filename}")
        
        df, rows_skipped = parse_excel_file(contents, skip_rows=skip_rows)
        print(f"✓ Parsed Excel file with skiprows={rows_skipped}")
        print(f"  Columns before normalization: {list(df.columns)}")
        
        # Normalize columns
        df = normalize_column_names(df)
        print(f"✓ Normalized column names")
        print(f"  Columns after normalization: {list(df.columns)}")
        
        # Map alternative column names to standard format
        # This handles broker-specific column naming conventions
        column_mapping = {
            'symbol': ['symbol', 'isin', 'scrip', 'stock symbol', 'ticker', 'stock name'],
            'date': ['date', 'date_time', 'order_date', 'execution date and time', 'execution date', 'trade date'],
            'order_type': ['order_type', 'side', 'buy_sell', 'bs', 'type', 'order status', 'trans type'],
            'price': ['price', 'rate', 'bid', 'ask', 'value', 'trade price', 'execution price'],
            'quantity': ['quantity', 'qty', 'shares', 'no of units'],
            'commission': ['commission', 'brokerage', 'fees', 'charges', 'transaction charges']
        }
        
        # Apply column mapping
        print(f"✓ Applying column mapping...")
        price_from_value = False
        
        # Check if 'value' column exists before mapping
        if 'value' in df.columns:
            price_from_value = True
            print(f"  ⚠ Detected 'Value' column - will need to divide by quantity")
        
        for standard_col, alternatives in column_mapping.items():
            if standard_col not in df.columns:
                for alt in alternatives:
                    if alt in df.columns:
                        df[standard_col] = df[alt]
                        print(f"  Mapped '{alt}' → '{standard_col}'")
                        break
        
        print(f"✓ Columns after mapping: {list(df.columns)}")
        
        # Validate we have minimum required columns
        required_columns = ['symbol', 'date', 'order_type', 'price', 'quantity']
        missing_cols = [col for col in required_columns if col not in df.columns]
        
        if missing_cols:
            print(f"✗ Missing required columns: {missing_cols}")
            print(f"  Available: {list(df.columns)}")
            raise ValueError(f"Missing required columns: {missing_cols}. Available columns: {list(df.columns)}")
        
        print(f"✓ All required columns present")
        
        # Parse dates FIRST - handle multiple date formats
        if 'date' in df.columns:
            print(f"✓ Processing date column...")
            print(f"  Sample values: {df['date'].head(3).tolist()}")
            print(f"  Data type: {df['date'].dtype}")
            
            try:
                # Try the specific broker date format first
                df['date'] = pd.to_datetime(df['date'], format='%d-%m-%Y %H:%M %p', errors='coerce')
                # For rows that didn't parse, try generic parsing
                mask = df['date'].isna()
                if mask.any():
                    print(f"  ⚠ {mask.sum()} rows failed specific format, trying generic...")
                    df.loc[mask, 'date'] = pd.to_datetime(df.loc[mask, 'date'], errors='coerce')
            except Exception as e:
                print(f"  Exception during date parsing: {e}")
                df['date'] = pd.to_datetime(df['date'], errors='coerce')
            
            print(f"  After parsing - type: {df['date'].dtype}")
            print(f"  Sample values: {df['date'].head(3).tolist()}")
        
        # Remove rows with NaT (invalid) dates before data type conversions
        initial_rows = len(df)
        df = df.dropna(subset=['date'])
        print(f"✓ Dropped {initial_rows - len(df)} rows with invalid dates")
        
        # Clean and convert data types
        print(f"✓ Converting data types...")
        if 'quantity' in df.columns:
            df['quantity'] = pd.to_numeric(df['quantity'], errors='coerce').fillna(0).astype(int)
            print(f"  Quantity: {df['quantity'].dtype} (min={df['quantity'].min()}, max={df['quantity'].max()})")
        
        if 'price' in df.columns:
            df['price'] = pd.to_numeric(df['price'], errors='coerce').fillna(0)
            # If price came from 'value' column, divide by quantity to get unit price
            if price_from_value:
                print(f"  ⚠ Price came from 'Value' column, calculating unit price = Value / Quantity")
                df['price'] = df['price'] / df['quantity'].replace(0, 1)  # Avoid division by zero
            print(f"  Price: {df['price'].dtype} (min={df['price'].min():.2f}, max={df['price'].max():.2f})")
        
        if 'commission' in df.columns:
            df['commission'] = pd.to_numeric(df['commission'], errors='coerce').fillna(0)
        else:
            df['commission'] = 0.0
        print(f"  Commission added")
        
        # Clean order_type - extract BUY or SELL
        if 'order_type' in df.columns:
            print(f"✓ Processing order_type column...")
            print(f"  Unique values: {df['order_type'].unique()}")
            df['order_type'] = df['order_type'].astype(str).str.upper().str.strip()
            initial_len = len(df)
            df = df[df['order_type'].isin(['BUY', 'SELL'])]
            print(f"  Filtered from {initial_len} to {len(df)} rows (kept only BUY/SELL)")
        
        # Remove rows with missing critical data
        initial_len = len(df)
        df = df.dropna(subset=['symbol', 'date', 'order_type', 'price', 'quantity'])
        print(f"✓ Dropped {initial_len - len(df)} rows with missing critical data")
        
        df = df[df['quantity'] > 0]  # Only positive quantities
        
        print(f"✓ Final dataset: {len(df)} rows, {len(df.columns)} columns")
        
        if df.empty:
            raise ValueError("No valid trade data found after cleaning")
        
        # Match trades
        print(f"✓ Matching trades with FIFO algorithm...")
        trades, positions = match_trades_fifo(df)
        print(f"✓ Matched {len(trades)} trades, {len(positions)} open positions")
        
        # Calculate metrics
        metrics = calculate_metrics(trades)
        print(f"✓ Calculated metrics")
        
        # Prepare summary
        summary = {
            'file_name': file.filename,
            'rows_processed': len(df),
            'rows_skipped': rows_skipped,
            'analysis_date': datetime.now().isoformat(),
            'total_symbols': len(set(t['symbol'] for t in trades))
        }
        
        print(f"✓ Analysis complete!")
        print("="*80 + "\n")
        
        return AnalysisResult(
            trades=trades,
            positions=positions,
            metrics=metrics,
            summary=summary
        )
    
    except Exception as e:
        print(f"\n✗ ERROR: {type(e).__name__}: {str(e)}")
        print("="*80)
        print(traceback.format_exc())
        print("="*80 + "\n")
        raise HTTPException(
            status_code=400,
            detail=f"Error processing file: {str(e)}"
        )


@app.post("/single-trade")
async def analyze_single_trade(data: Dict):
    """
    Analyze a single trade
    Expected: {
        "entry_price": float,
        "exit_price": float,
        "quantity": int,
        "commission": float
    }
    """
    try:
        entry_price = float(data.get('entry_price', 0))
        exit_price = float(data.get('exit_price', 0))
        quantity = int(data.get('quantity', 1))
        commission = float(data.get('commission', 0))
        
        pnl = (exit_price - entry_price) * quantity - commission
        pnl_percent = ((exit_price - entry_price) / entry_price * 100) if entry_price != 0 else 0
        
        return {
            'entry_price': entry_price,
            'exit_price': exit_price,
            'quantity': quantity,
            'pnl': round(pnl, 2),
            'pnl_percent': round(pnl_percent, 2),
            'status': 'Profitable' if pnl > 0 else 'Loss' if pnl < 0 else 'Breakeven',
            'commission': commission
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/upstox/callback")
async def upstox_callback(code: str = Query(None), state: str = Query(None)):
    """
    OAuth callback endpoint for Upstox.
    Exchanges authorization code for access token.
    """
    if not code:
        raise HTTPException(status_code=400, detail="Authorization code not received")
    
    try:
        # Exchange code for access token
        token_url = "https://api.upstox.com/v2/login/authorization/token"
        
        payload = {
            "code": code,
            "client_id": UPSTOX_API_KEY,
            "client_secret": UPSTOX_API_SECRET,
            "redirect_uri": UPSTOX_REDIRECT_URI,
            "grant_type": "authorization_code"
        }
        
        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "application/json"
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.post(token_url, data=payload, headers=headers)
            
            if response.status_code != 200:
                print(f"Upstox token error: {response.text}")
                raise HTTPException(
                    status_code=response.status_code, 
                    detail=f"Failed to get access token: {response.text}"
                )
            
            token_data = response.json()
        
        # Store token (use user_id from state or generate session)
        session_id = state or "default_user"
        upstox_tokens[session_id] = {
            "access_token": token_data.get("access_token"),
            "expires_at": datetime.now() + timedelta(hours=24),  # Upstox tokens valid for 1 day
            "user_id": token_data.get("user_id"),
            "email": token_data.get("email")
        }
        
        print(f"✓ Upstox login successful for user: {token_data.get('email')}")
        
        # If FRONTEND_URL is set, redirect there; otherwise return JSON
        if FRONTEND_URL:
            return RedirectResponse(url=f"{FRONTEND_URL}?upstox_connected=true&session={session_id}")
        else:
            # Return JSON with session info - frontend can poll /upstox/status
            return {
                "success": True,
                "message": "Upstox connected successfully",
                "session": session_id,
                "user_id": token_data.get("user_id"),
                "email": token_data.get("email")
            }
    
    except httpx.RequestError as e:
        print(f"Upstox callback network error: {e}")
        raise HTTPException(status_code=500, detail=f"Network error: {str(e)}")
    except Exception as e:
        print(f"Upstox callback error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/upstox/auth-url")
async def get_upstox_auth_url(state: str = Query(None)):
    """
    Generate Upstox authorization URL for OAuth login.
    Frontend should redirect user to this URL.
    """
    if not UPSTOX_API_KEY:
        raise HTTPException(status_code=500, detail="Upstox API key not configured")
    
    auth_url = (
        f"https://api.upstox.com/v2/login/authorization/dialog"
        f"?client_id={UPSTOX_API_KEY}"
        f"&redirect_uri={UPSTOX_REDIRECT_URI}"
        f"&response_type=code"
    )
    
    if state:
        auth_url += f"&state={state}"
    
    return {"auth_url": auth_url}


@app.get("/upstox/profile")
async def get_upstox_profile(session: str = Query("default_user")):
    """Get Upstox user profile"""
    token_info = upstox_tokens.get(session)
    
    if not token_info or datetime.now() > token_info.get("expires_at", datetime.min):
        raise HTTPException(status_code=401, detail="Not authenticated with Upstox. Please login first.")
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                "https://api.upstox.com/v2/user/profile",
                headers={
                    "Authorization": f"Bearer {token_info['access_token']}",
                    "Accept": "application/json"
                }
            )
            
            if response.status_code != 200:
                raise HTTPException(status_code=response.status_code, detail=response.text)
            
            return response.json()
    except httpx.RequestError as e:
        raise HTTPException(status_code=500, detail=f"Network error: {str(e)}")


@app.get("/upstox/trades")
async def get_upstox_trades(
    session: str = Query("default_user"),
    from_date: str = Query(None, description="Start date (YYYY-MM-DD)"),
    to_date: str = Query(None, description="End date (YYYY-MM-DD)")
):
    """
    Fetch trade history from Upstox and analyze it.
    Returns analyzed trades in the same format as /analyze-xlsx
    """
    token_info = upstox_tokens.get(session)
    
    if not token_info or datetime.now() > token_info.get("expires_at", datetime.min):
        raise HTTPException(status_code=401, detail="Not authenticated with Upstox. Please login first.")
    
    try:
        # Set default date range (last 30 days)
        if not to_date:
            to_date = datetime.now().strftime("%Y-%m-%d")
        if not from_date:
            from_date = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
        
        async with httpx.AsyncClient() as client:
            # Fetch trade book
            response = await client.get(
                "https://api.upstox.com/v2/order/trades/get-trades-for-day",
                headers={
                    "Authorization": f"Bearer {token_info['access_token']}",
                    "Accept": "application/json"
                }
            )
            
            if response.status_code != 200:
                print(f"Upstox trades error: {response.text}")
                raise HTTPException(status_code=response.status_code, detail=response.text)
            
            trades_data = response.json()
        
        # Transform Upstox data to our format
        trades_list = trades_data.get("data", [])
        
        if not trades_list:
            return {
                "trades": [],
                "positions": [],
                "metrics": {},
                "summary": {
                    "file_name": "Upstox API",
                    "rows_processed": 0,
                    "analysis_date": datetime.now().isoformat(),
                    "total_symbols": 0
                }
            }
        
        # Convert to DataFrame
        df = pd.DataFrame(trades_list)
        
        # Map Upstox columns to our standard format
        df = df.rename(columns={
            'tradingsymbol': 'symbol',
            'trade_date': 'date',
            'transaction_type': 'order_type',
            'average_price': 'price',
            'traded_quantity': 'quantity',
            'brokerage': 'commission'
        })
        
        # Ensure required columns exist
        if 'commission' not in df.columns:
            df['commission'] = 0.0
        
        # Parse dates
        df['date'] = pd.to_datetime(df['date'], errors='coerce')
        df = df.dropna(subset=['date'])
        
        # Convert data types
        df['quantity'] = pd.to_numeric(df['quantity'], errors='coerce').fillna(0).astype(int)
        df['price'] = pd.to_numeric(df['price'], errors='coerce').fillna(0)
        df['commission'] = pd.to_numeric(df['commission'], errors='coerce').fillna(0)
        
        # Standardize order_type
        df['order_type'] = df['order_type'].astype(str).str.upper().str.strip()
        df = df[df['order_type'].isin(['BUY', 'SELL'])]
        
        # Match trades using FIFO
        trades, positions = match_trades_fifo(df)
        metrics = calculate_metrics(trades)
        
        return {
            "trades": trades,
            "positions": positions,
            "metrics": metrics,
            "summary": {
                "file_name": "Upstox API",
                "rows_processed": len(df),
                "analysis_date": datetime.now().isoformat(),
                "total_symbols": len(set(t['symbol'] for t in trades))
            }
        }
    
    except httpx.RequestError as e:
        raise HTTPException(status_code=500, detail=f"Network error: {str(e)}")
    except Exception as e:
        print(f"Error fetching Upstox trades: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/upstox/holdings")
async def get_upstox_holdings(session: str = Query("default_user")):
    """Fetch current holdings from Upstox"""
    token_info = upstox_tokens.get(session)
    
    if not token_info or datetime.now() > token_info.get("expires_at", datetime.min):
        raise HTTPException(status_code=401, detail="Not authenticated with Upstox. Please login first.")
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                "https://api.upstox.com/v2/portfolio/long-term-holdings",
                headers={
                    "Authorization": f"Bearer {token_info['access_token']}",
                    "Accept": "application/json"
                }
            )
            
            if response.status_code != 200:
                raise HTTPException(status_code=response.status_code, detail=response.text)
            
            holdings_data = response.json()
        
        # Transform to our positions format
        holdings = holdings_data.get("data", [])
        positions = []
        
        for h in holdings:
            positions.append({
                "symbol": h.get("tradingsymbol", ""),
                "quantity": int(h.get("quantity", 0)),
                "avg_price": float(h.get("average_price", 0)),
                "total_cost": float(h.get("average_price", 0)) * int(h.get("quantity", 0)),
                "current_price": float(h.get("last_price", 0)),
                "pnl": float(h.get("pnl", 0)),
                "day_change": float(h.get("day_change", 0))
            })
        
        return {"holdings": positions}
    
    except httpx.RequestError as e:
        raise HTTPException(status_code=500, detail=f"Network error: {str(e)}")


@app.get("/upstox/status")
async def upstox_connection_status(session: str = Query("default_user")):
    """Check if user is connected to Upstox"""
    token_info = upstox_tokens.get(session)
    
    if not token_info:
        return {"connected": False, "message": "Not connected"}
    
    if datetime.now() > token_info.get("expires_at", datetime.min):
        return {"connected": False, "message": "Token expired"}
    
    return {
        "connected": True,
        "user_id": token_info.get("user_id"),
        "email": token_info.get("email"),
        "expires_at": token_info.get("expires_at").isoformat()
    }


@app.post("/upstox/quotes")
async def get_upstox_quotes(
    data: Dict,
    session: str = Query("default_user")
):
    """
    Fetch current market prices for given symbols from Upstox.
    
    Request body:
    {
        "symbols": ["RELIANCE", "TCS", "INFY"],
        "exchange": "NSE"  // optional, defaults to NSE
    }
    
    Returns:
    {
        "quotes": {
            "RELIANCE": {"symbol": "RELIANCE", "ltp": 2650.50, "change": 25.30, "change_percent": 0.96},
            "TCS": {"symbol": "TCS", "ltp": 3450.00, "change": -15.20, "change_percent": -0.44}
        },
        "failed": ["UNKNOWN_SYMBOL"]
    }
    """
    token_info = upstox_tokens.get(session)
    
    if not token_info or datetime.now() > token_info.get("expires_at", datetime.min):
        raise HTTPException(status_code=401, detail="Not authenticated with Upstox. Please login first.")
    
    symbols = data.get("symbols", [])
    exchange = data.get("exchange", "NSE").upper()
    
    if not symbols:
        return {"quotes": {}, "failed": []}
    
    try:
        # Build instrument keys for Upstox API
        # Format: EXCHANGE|SYMBOL (e.g., NSE_EQ|RELIANCE, NSE_EQ|INE002A01018)
        instrument_keys = []
        symbol_mapping = {}  # Map instrument key back to original symbol
        
        for symbol in symbols:
            # Clean the symbol
            clean_symbol = symbol.strip().upper()
            # Upstox uses NSE_EQ for equity segment
            instrument_key = f"{exchange}_EQ|{clean_symbol}"
            instrument_keys.append(instrument_key)
            symbol_mapping[instrument_key] = clean_symbol
        
        # Upstox market quotes API
        # API endpoint for multiple quotes
        quotes_url = "https://api.upstox.com/v2/market-quote/quotes"
        
        async with httpx.AsyncClient() as client:
            response = await client.get(
                quotes_url,
                params={"instrument_key": ",".join(instrument_keys)},
                headers={
                    "Authorization": f"Bearer {token_info['access_token']}",
                    "Accept": "application/json"
                }
            )
            
            if response.status_code != 200:
                print(f"Upstox quotes error: {response.status_code} - {response.text}")
                # Try LTP endpoint as fallback (lighter weight)
                ltp_url = "https://api.upstox.com/v2/market-quote/ltp"
                response = await client.get(
                    ltp_url,
                    params={"instrument_key": ",".join(instrument_keys)},
                    headers={
                        "Authorization": f"Bearer {token_info['access_token']}",
                        "Accept": "application/json"
                    }
                )
                
                if response.status_code != 200:
                    raise HTTPException(
                        status_code=response.status_code,
                        detail=f"Failed to fetch quotes: {response.text}"
                    )
            
            quotes_data = response.json()
        
        # Parse response
        quotes_result = {}
        failed_symbols = []
        
        data_dict = quotes_data.get("data", {})
        
        for instrument_key, original_symbol in symbol_mapping.items():
            quote_info = data_dict.get(instrument_key)
            
            if quote_info:
                # Full quote response
                if "ohlc" in quote_info:
                    ltp = float(quote_info.get("last_price", 0))
                    prev_close = float(quote_info.get("ohlc", {}).get("close", ltp))
                    change = ltp - prev_close
                    change_percent = (change / prev_close * 100) if prev_close > 0 else 0
                    
                    quotes_result[original_symbol] = {
                        "symbol": original_symbol,
                        "ltp": round(ltp, 2),
                        "open": float(quote_info.get("ohlc", {}).get("open", 0)),
                        "high": float(quote_info.get("ohlc", {}).get("high", 0)),
                        "low": float(quote_info.get("ohlc", {}).get("low", 0)),
                        "close": prev_close,
                        "change": round(change, 2),
                        "change_percent": round(change_percent, 2),
                        "volume": int(quote_info.get("volume", 0))
                    }
                # LTP only response
                elif "last_price" in quote_info:
                    ltp = float(quote_info.get("last_price", 0))
                    quotes_result[original_symbol] = {
                        "symbol": original_symbol,
                        "ltp": round(ltp, 2),
                        "change": 0,
                        "change_percent": 0
                    }
                else:
                    failed_symbols.append(original_symbol)
            else:
                failed_symbols.append(original_symbol)
        
        print(f"✓ Fetched quotes for {len(quotes_result)} symbols, {len(failed_symbols)} failed")
        
        return {
            "quotes": quotes_result,
            "failed": failed_symbols
        }
    
    except httpx.RequestError as e:
        print(f"Upstox quotes network error: {e}")
        raise HTTPException(status_code=500, detail=f"Network error: {str(e)}")
    except Exception as e:
        print(f"Error fetching quotes: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/upstox/enrich-positions")
async def enrich_positions_with_prices(
    data: Dict,
    session: str = Query("default_user")
):
    """
    Takes positions from Excel analysis and enriches them with current prices from Upstox.
    
    Request body:
    {
        "positions": [
            {"symbol": "RELIANCE", "quantity": 10, "avg_price": 2500, "total_cost": 25000},
            {"symbol": "TCS", "quantity": 5, "avg_price": 3500, "total_cost": 17500}
        ]
    }
    
    Returns positions with current_price, current_value, unrealized_pnl, pnl_percent added.
    """
    token_info = upstox_tokens.get(session)
    
    if not token_info or datetime.now() > token_info.get("expires_at", datetime.min):
        raise HTTPException(status_code=401, detail="Not authenticated with Upstox. Please login first.")
    
    positions = data.get("positions", [])
    
    if not positions:
        return {"positions": [], "total_current_value": 0, "total_unrealized_pnl": 0}
    
    # Extract symbols
    symbols = [p.get("symbol", "") for p in positions if p.get("symbol")]
    
    # Fetch quotes
    try:
        quotes_response = await get_upstox_quotes({"symbols": symbols}, session=session)
        quotes = quotes_response.get("quotes", {})
    except Exception as e:
        print(f"Failed to fetch quotes for enrichment: {e}")
        quotes = {}
    
    # Enrich positions
    enriched_positions = []
    total_current_value = 0
    total_unrealized_pnl = 0
    total_cost = 0
    
    for pos in positions:
        symbol = pos.get("symbol", "").upper().strip()
        quantity = pos.get("quantity", 0)
        avg_price = pos.get("avg_price", 0)
        position_cost = pos.get("total_cost", avg_price * quantity)
        
        enriched = {
            "symbol": symbol,
            "quantity": quantity,
            "avg_price": round(avg_price, 2),
            "total_cost": round(position_cost, 2)
        }
        
        # Add live price data if available
        quote = quotes.get(symbol)
        if quote:
            current_price = quote.get("ltp", 0)
            current_value = current_price * quantity
            unrealized_pnl = current_value - position_cost
            pnl_percent = (unrealized_pnl / position_cost * 100) if position_cost > 0 else 0
            
            enriched.update({
                "current_price": round(current_price, 2),
                "current_value": round(current_value, 2),
                "unrealized_pnl": round(unrealized_pnl, 2),
                "pnl_percent": round(pnl_percent, 2),
                "day_change": quote.get("change", 0),
                "day_change_percent": quote.get("change_percent", 0),
                "price_available": True
            })
            
            total_current_value += current_value
            total_unrealized_pnl += unrealized_pnl
        else:
            enriched.update({
                "current_price": None,
                "current_value": None,
                "unrealized_pnl": None,
                "pnl_percent": None,
                "price_available": False
            })
        
        total_cost += position_cost
        enriched_positions.append(enriched)
    
    total_pnl_percent = (total_unrealized_pnl / total_cost * 100) if total_cost > 0 else 0
    
    return {
        "positions": enriched_positions,
        "total_cost": round(total_cost, 2),
        "total_current_value": round(total_current_value, 2),
        "total_unrealized_pnl": round(total_unrealized_pnl, 2),
        "total_pnl_percent": round(total_pnl_percent, 2)
    }


if __name__ == "__main__":
    import uvicorn
    import os
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)