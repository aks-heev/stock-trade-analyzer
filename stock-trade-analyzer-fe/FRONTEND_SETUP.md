# Frontend Setup Guide

## Overview

The frontend is a React application that connects to the deployed backend on Render.

## Recent Updates

### ✅ Fixed Issues:
1. **File Selection Bug** - Fixed `e.target.files` to `e.target.files[0]`
2. **API URL** - Now uses environment variable with Render URL as default
3. **Positions Display** - Added Current Positions table showing open holdings
4. **Error Handling** - Improved error messages and network error detection
5. **Dependencies** - Added axios to package.json

## Configuration

### API URL Configuration

The app uses environment variables for API URL configuration:

**Default (Production)**: `https://stock-trade-analyzer-k7k4.onrender.com`

**For Local Development**:
1. Create a `.env.local` file in `stock-trade-analyzer/stock-trade-analyzer/` directory
2. Add: `REACT_APP_API_URL=http://localhost:8000`
3. Restart the React dev server

**Environment Variable Priority**:
1. `.env.local` (for local development, ignored by git)
2. `.env` (for production, committed to git)
3. Default Render URL (hardcoded fallback)

## Installation

```bash
cd stock-trade-analyzer/stock-trade-analyzer
npm install
```

## Running Locally

```bash
# Start development server
npm start

# The app will open at http://localhost:3000
```

## Features

### 1. Upload File Tab
- Upload Excel (.xlsx) files with trade history
- Supports drag & drop or click to browse
- Validates file format
- Shows loading state during analysis

### 2. Results Tab
- **Analysis Summary**: Total trades, winning/losing trades, win rate
- **Key Metrics**: Total P&L, best/worst trade, averages, profit factor
- **Current Positions**: Shows open positions with average price and total cost
- **Trade Details**: Complete table of all trades with P&L breakdown

### 3. Single Trade Tab
- Calculate P&L for individual trades
- Enter entry price, exit price, quantity, and commission
- Shows P&L amount, percentage return, and status

## Backend Connection

The frontend connects to:
- **Production**: `https://stock-trade-analyzer-k7k4.onrender.com`
- **Local**: `http://localhost:8000` (when using `.env.local`)

### API Endpoints Used:
- `POST /analyze-xlsx` - Upload and analyze Excel file
- `POST /single-trade` - Analyze single trade
- `GET /health` - Health check (not used in UI, but available)

## Troubleshooting

### Cannot Connect to Backend
- Check if backend is running (for local development)
- Verify API URL in browser console
- Check Render dashboard if using production backend
- Free tier Render services spin down after 15 min inactivity

### File Upload Not Working
- Ensure file is `.xlsx` format
- Check browser console for errors
- Verify backend is accessible

### Positions Not Showing
- Positions only appear if there are open positions (unmatched BUY orders)
- Check backend response in browser DevTools → Network tab

## Building for Production

```bash
npm run build
```

This creates an optimized production build in the `build/` folder.

## Dependencies

- **React** 19.2.1
- **axios** 1.13.2 - HTTP client for API calls
- **react-scripts** 5.0.1 - Create React App tooling

## Notes

- The app uses dark theme with modern UI
- All API calls include error handling
- Loading states are shown during API requests
- Error messages are user-friendly

