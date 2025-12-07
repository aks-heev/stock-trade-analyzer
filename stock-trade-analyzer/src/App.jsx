import React, { useState } from 'react';
import axios from 'axios';
import './App.css';

const TradeAnalyzer = () => {
  const [activeTab, setActiveTab] = useState('upload');
  const [file, setFile] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [analysisData, setAnalysisData] = useState(null);
  const [singleTrade, setSingleTrade] = useState({
    entry_price: '',
    exit_price: '',
    quantity: 1,
    commission: 0
  });
  const [singleTradeResult, setSingleTradeResult] = useState(null);

  const API_BASE_URL = 'http://localhost:8000';

  // File Upload Handler
  const handleFileChange = (e) => {
    const selectedFile = e.target.files;
    if (selectedFile && selectedFile.name.endsWith('.xlsx')) {
      setFile(selectedFile);
      setError(null);
    } else {
      setError('Please select a valid Excel (.xlsx) file');
    }
  };

  // Upload and Analyze
  const handleUpload = async () => {
    if (!file) {
      setError('Please select a file');
      return;
    }

    setLoading(true);
    setError(null);

    try {
      const formData = new FormData();
      formData.append('file', file);

      const response = await axios.post(
        `${API_BASE_URL}/analyze-xlsx`,
        formData,
        { headers: { 'Content-Type': 'multipart/form-data' } }
      );

      setAnalysisData(response.data);
      setActiveTab('results');
      setFile(null);
    } catch (err) {
      setError(err.response?.data?.detail || 'Error analyzing file. Check console for details.');
      console.error('Upload error:', err);
    } finally {
      setLoading(false);
    }
  };

  // Single Trade Analysis
  const handleSingleTradeChange = (e) => {
    const { name, value } = e.target;
    setSingleTrade(prev => ({
      ...prev,
      [name]: name === 'quantity' ? parseInt(value) : parseFloat(value) || ''
    }));
  };

  const analyzeSingleTrade = async () => {
    try {
      const response = await axios.post(
        `${API_BASE_URL}/single-trade`,
        singleTrade
      );
      setSingleTradeResult(response.data);
    } catch (err) {
      setError('Error analyzing trade');
      console.error('Single trade error:', err);
    }
  };

  // Render Upload Tab
  const renderUploadTab = () => (
    <div className="card">
      <h2>📁 Upload Order History</h2>
      
      <div className="upload-area" onClick={() => document.getElementById('csv-upload').click()}>
        <label htmlFor="csv-upload" className="upload-label">
          📤 Drag & Drop your Excel file here or click to browse
        </label>
        <input
          id="csv-upload"
          type="file"
          accept=".xlsx,.xls"
          onChange={handleFileChange}
        />
      </div>

      {file && (
        <div style={{ marginTop: '20px' }}>
          <p style={{ color: '#22c55e' }}>✓ File selected: {file.name}</p>
        </div>
      )}

      <div className="help-text">
        Required columns: Symbol, Date, Order Type (BUY/SELL), Price, Quantity
      </div>

      {error && (
        <div className="alert alert-error">
          ⚠️ {error}
        </div>
      )}

      <button 
        className="btn btn-primary" 
        onClick={handleUpload} 
        disabled={!file || loading}
        style={{ marginTop: '20px', width: '100%' }}
      >
        {loading ? '⏳ Analyzing...' : '🚀 Analyze Trades'}
      </button>

      <div className="sample-text">
        <strong>Sample Excel Format:</strong>
        <code>
Symbol  | Date       | Order Type | Price | Quantity | Commission
--------|------------|-----------|-------|----------|----------
RELIANCE| 2024-01-15 | BUY       | 2500  | 10       | 25
RELIANCE| 2024-02-20 | SELL      | 2600  | 10       | 26
TCS     | 2024-01-20 | BUY       | 3500  | 5        | 17.5
        </code>
      </div>
    </div>
  );

  // Render Results Tab
  const renderResultsTab = () => {
    if (!analysisData) return <p>No analysis data available</p>;

    const { trades, metrics, summary } = analysisData;

    return (
      <div>
        {/* Summary Info */}
        <div className="card">
          <h2>📊 Analysis Summary</h2>
          <div className="metrics-grid">
            <div className="metric-card info">
              <div className="metric-value">{trades.length}</div>
              <div className="metric-label">Total Trades</div>
            </div>
            <div className="metric-card success">
              <div className="metric-value">{metrics.winning_trades || 0}</div>
              <div className="metric-label">Winning Trades</div>
            </div>
            <div className="metric-card danger">
              <div className="metric-value">{metrics.losing_trades || 0}</div>
              <div className="metric-label">Losing Trades</div>
            </div>
            <div className="metric-card primary">
              <div className="metric-value">{metrics.win_rate || 0}%</div>
              <div className="metric-label">Win Rate</div>
            </div>
          </div>
        </div>

        {/* Key Metrics */}
        <div className="card">
          <h2>💹 Key Metrics</h2>
          <div className="metrics-grid">
            <div className="metric-card">
              <div className="metric-value" style={{ color: metrics.total_pnl > 0 ? '#22c55e' : '#ef4444' }}>
                ₹{metrics.total_pnl}
              </div>
              <div className="metric-label">Total P&L</div>
            </div>
            <div className="metric-card">
              <div className="metric-value">₹{metrics.best_trade}</div>
              <div className="metric-label">Best Trade</div>
            </div>
            <div className="metric-card">
              <div className="metric-value" style={{ color: '#ef4444' }}>
                ₹{metrics.worst_trade}
              </div>
              <div className="metric-label">Worst Trade</div>
            </div>
            <div className="metric-card">
              <div className="metric-value">₹{metrics.avg_win}</div>
              <div className="metric-label">Avg Win</div>
            </div>
            <div className="metric-card">
              <div className="metric-value" style={{ color: '#ef4444' }}>
                ₹{metrics.avg_loss}
              </div>
              <div className="metric-label">Avg Loss</div>
            </div>
            <div className="metric-card">
              <div className="metric-value">{metrics.profit_factor}</div>
              <div className="metric-label">Profit Factor</div>
            </div>
          </div>
        </div>

        {/* Trades Table */}
        <div className="card">
          <h2>📋 Trade Details</h2>
          <div className="table-container">
            <table className="trades-table">
              <thead>
                <tr>
                  <th>Symbol</th>
                  <th>Entry Date</th>
                  <th>Entry Price</th>
                  <th>Exit Date</th>
                  <th>Exit Price</th>
                  <th>Qty</th>
                  <th>P&L</th>
                  <th>P&L %</th>
                  <th>Commission</th>
                  <th>Status</th>
                </tr>
              </thead>
              <tbody>
                {trades.map((trade, idx) => (
                  <tr 
                    key={idx}
                    className={`status-${trade.status.toLowerCase()}`}
                  >
                    <td className="bold">{trade.symbol}</td>
                    <td>{trade.entry_date}</td>
                    <td>₹{trade.entry_price.toFixed(2)}</td>
                    <td>{trade.exit_date || '—'}</td>
                    <td>{trade.exit_price ? `₹${trade.exit_price.toFixed(2)}` : '—'}</td>
                    <td>{trade.quantity}</td>
                    <td className={trade.pnl > 0 ? 'positive' : trade.pnl < 0 ? 'negative' : ''}>
                      ₹{trade.pnl.toFixed(2)}
                    </td>
                    <td className={trade.pnl_percent > 0 ? 'positive' : trade.pnl_percent < 0 ? 'negative' : ''}>
                      {trade.pnl_percent.toFixed(2)}%
                    </td>
                    <td>₹{trade.commission.toFixed(2)}</td>
                    <td>
                      <span className={`status-badge status-${trade.status.toLowerCase()}`}>
                        {trade.status}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    );
  };

  // Render Single Trade Tab
  const renderSingleTradeTab = () => (
    <div className="card">
      <h2>🔄 Analyze Single Trade</h2>
      
      <div className="form-grid">
        <div className="form-group">
          <label>Entry Price (₹)</label>
          <input 
            type="number" 
            className="form-input"
            name="entry_price"
            value={singleTrade.entry_price}
            onChange={handleSingleTradeChange}
            placeholder="e.g., 2500"
          />
        </div>
        <div className="form-group">
          <label>Exit Price (₹)</label>
          <input 
            type="number" 
            className="form-input"
            name="exit_price"
            value={singleTrade.exit_price}
            onChange={handleSingleTradeChange}
            placeholder="e.g., 2600"
          />
        </div>
        <div className="form-group">
          <label>Quantity</label>
          <input 
            type="number" 
            className="form-input"
            name="quantity"
            value={singleTrade.quantity}
            onChange={handleSingleTradeChange}
            placeholder="e.g., 10"
          />
        </div>
        <div className="form-group">
          <label>Commission (₹)</label>
          <input 
            type="number" 
            className="form-input"
            name="commission"
            value={singleTrade.commission}
            onChange={handleSingleTradeChange}
            placeholder="e.g., 25"
          />
        </div>
      </div>

      <button 
        className="btn btn-primary" 
        onClick={analyzeSingleTrade}
        style={{ width: '100%', marginTop: '20px' }}
      >
        📊 Analyze Trade
      </button>

      {singleTradeResult && (
        <div className="metrics-grid" style={{ marginTop: '30px' }}>
          <div className="metric-card success">
            <div className="metric-value" style={{ color: singleTradeResult.pnl > 0 ? '#22c55e' : '#ef4444' }}>
              ₹{singleTradeResult.pnl.toFixed(2)}
            </div>
            <div className="metric-label">P&L</div>
          </div>
          <div className="metric-card primary">
            <div className="metric-value">
              {singleTradeResult.pnl_percent.toFixed(2)}%
            </div>
            <div className="metric-label">Return %</div>
          </div>
          <div className="metric-card">
            <div className="metric-value">
              <span className={`status-badge status-${singleTradeResult.status.toLowerCase()}`}>
                {singleTradeResult.status}
              </span>
            </div>
            <div className="metric-label">Status</div>
          </div>
        </div>
      )}
    </div>
  );

  return (
    <div className="container">
      <div className="header">
        <h1>📈 Stock Trade Analyzer</h1>
        <p>Analyze your trading performance with FIFO algorithm</p>
      </div>

      {/* Tabs */}
      <div className="tabs">
        <button 
          className={`tab ${activeTab === 'upload' ? 'active' : ''}`}
          onClick={() => setActiveTab('upload')}
        >
          📤 Upload File
        </button>
        <button 
          className={`tab ${activeTab === 'results' ? 'active' : ''}`}
          onClick={() => setActiveTab('results')}
          disabled={!analysisData}
        >
          📊 Results
        </button>
        <button 
          className={`tab ${activeTab === 'single' ? 'active' : ''}`}
          onClick={() => setActiveTab('single')}
        >
          🔄 Single Trade
        </button>
      </div>

      {/* Tab Content */}
      {activeTab === 'upload' && renderUploadTab()}
      {activeTab === 'results' && renderResultsTab()}
      {activeTab === 'single' && renderSingleTradeTab()}
    </div>
  );
};

export default TradeAnalyzer;
