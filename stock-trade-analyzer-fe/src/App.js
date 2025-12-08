import React, { useState, useEffect } from 'react';
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
  
  // Upstox state
  const [upstoxConnected, setUpstoxConnected] = useState(false);
  const [upstoxUser, setUpstoxUser] = useState(null);
  const [upstoxLoading, setUpstoxLoading] = useState(false);
  const [upstoxHoldings, setUpstoxHoldings] = useState(null);
  const [sessionId, setSessionId] = useState(() => {
    return localStorage.getItem('upstox_session') || `session_${Date.now()}`;
  });

  // API Base URL - uses environment variable or defaults to Render URL
  const API_BASE_URL = process.env.REACT_APP_API_URL || 'https://stock-trade-analyzer-k7k4.onrender.com';

  // Check Upstox connection on mount and URL params
  useEffect(() => {
    // Save session to localStorage
    localStorage.setItem('upstox_session', sessionId);
    
    // Check URL params for Upstox callback
    const urlParams = new URLSearchParams(window.location.search);
    const connected = urlParams.get('upstox_connected');
    const session = urlParams.get('session');
    
    if (connected === 'true' && session) {
      setSessionId(session);
      localStorage.setItem('upstox_session', session);
      setActiveTab('upstox'); // Switch to Upstox tab after connection
      // Clean URL
      window.history.replaceState({}, document.title, window.location.pathname);
    }
    
    // Check connection status
    checkUpstoxStatus();
  }, []);

  // Check Upstox connection status
  const checkUpstoxStatus = async () => {
    try {
      const response = await axios.get(`${API_BASE_URL}/upstox/status?session=${sessionId}`);
      if (response.data.connected) {
        setUpstoxConnected(true);
        setUpstoxUser(response.data);
      } else {
        setUpstoxConnected(false);
        setUpstoxUser(null);
      }
    } catch (err) {
      console.log('Upstox not connected');
      setUpstoxConnected(false);
    }
  };

  // Connect to Upstox
  const connectUpstox = async () => {
    try {
      setUpstoxLoading(true);
      const response = await axios.get(`${API_BASE_URL}/upstox/auth-url?state=${sessionId}`);
      // Redirect to Upstox login
      window.location.href = response.data.auth_url;
    } catch (err) {
      setError('Failed to get Upstox auth URL: ' + (err.response?.data?.detail || err.message));
      setUpstoxLoading(false);
    }
  };

  // Fetch trades from Upstox
  const fetchUpstoxTrades = async () => {
    try {
      setLoading(true);
      setError(null);
      const response = await axios.get(`${API_BASE_URL}/upstox/trades?session=${sessionId}`);
      setAnalysisData(response.data);
      setActiveTab('results');
    } catch (err) {
      const errorMessage = err.response?.data?.detail || err.message;
      setError('Failed to fetch Upstox trades: ' + errorMessage);
    } finally {
      setLoading(false);
    }
  };

  // Fetch holdings from Upstox
  const fetchUpstoxHoldings = async () => {
    try {
      setUpstoxLoading(true);
      setError(null);
      const response = await axios.get(`${API_BASE_URL}/upstox/holdings?session=${sessionId}`);
      setUpstoxHoldings(response.data.holdings);
    } catch (err) {
      const errorMessage = err.response?.data?.detail || err.message;
      setError('Failed to fetch holdings: ' + errorMessage);
    } finally {
      setUpstoxLoading(false);
    }
  };

  // Disconnect Upstox (clear local session)
  const disconnectUpstox = () => {
    localStorage.removeItem('upstox_session');
    setSessionId(`session_${Date.now()}`);
    setUpstoxConnected(false);
    setUpstoxUser(null);
    setUpstoxHoldings(null);
  };

  // File Upload Handler
  const handleFileChange = (e) => {
    const selectedFile = e.target.files[0]; // Fix: Get first file from FileList
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
      const errorMessage = err.response?.data?.detail || err.message || 'Error analyzing file. Please check the file format and try again.';
      setError(errorMessage);
      console.error('Upload error:', err);
      if (err.response?.status === 0 || err.code === 'ERR_NETWORK') {
        setError('Cannot connect to server. Please check if the backend is running and try again.');
      }
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
    if (!singleTrade.entry_price || !singleTrade.exit_price || !singleTrade.quantity) {
      setError('Please fill in all required fields (Entry Price, Exit Price, Quantity)');
      return;
    }

    try {
      setError(null);
      const response = await axios.post(
        `${API_BASE_URL}/single-trade`,
        singleTrade
      );
      setSingleTradeResult(response.data);
    } catch (err) {
      const errorMessage = err.response?.data?.detail || err.message || 'Error analyzing trade';
      setError(errorMessage);
      console.error('Single trade error:', err);
      if (err.response?.status === 0 || err.code === 'ERR_NETWORK') {
        setError('Cannot connect to server. Please check if the backend is running.');
      }
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

    const { trades, metrics, summary, positions } = analysisData;

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

        {/* Current Positions */}
        {positions && positions.length > 0 && (
          <div className="card">
            <h2>📈 Current Positions ({positions.length})</h2>
            <div className="table-container">
              <table className="trades-table">
                <thead>
                  <tr>
                    <th>Symbol</th>
                    <th>Quantity</th>
                    <th>Avg Price</th>
                    <th>Total Cost</th>
                  </tr>
                </thead>
                <tbody>
                  {positions.map((position, idx) => (
                    <tr key={idx}>
                      <td className="bold">{position.symbol}</td>
                      <td>{position.quantity}</td>
                      <td>₹{position.avg_price.toFixed(2)}</td>
                      <td>₹{position.total_cost.toFixed(2)}</td>
                    </tr>
                  ))}
                </tbody>
                <tfoot>
                  <tr style={{ fontWeight: 'bold', borderTop: '2px solid var(--border)' }}>
                    <td>Total Investment</td>
                    <td colSpan="2"></td>
                    <td>₹{positions.reduce((sum, pos) => sum + pos.total_cost, 0).toFixed(2)}</td>
                  </tr>
                </tfoot>
              </table>
            </div>
          </div>
        )}

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

  // Render Upstox Tab
  const renderUpstoxTab = () => (
    <div className="card">
      <h2>🔗 Upstox Integration</h2>
      
      {!upstoxConnected ? (
        <div className="upstox-connect">
          <p style={{ color: 'var(--text-secondary)', marginBottom: '20px' }}>
            Connect your Upstox account to automatically import and analyze your trades.
          </p>
          <button 
            className="btn btn-upstox" 
            onClick={connectUpstox}
            disabled={upstoxLoading}
          >
            {upstoxLoading ? '⏳ Connecting...' : '🔐 Connect Upstox Account'}
          </button>
          <div className="help-text" style={{ marginTop: '20px' }}>
            <strong>What you'll get:</strong>
            <ul style={{ marginTop: '10px', paddingLeft: '20px' }}>
              <li>Automatic trade history import</li>
              <li>Real-time holdings with P&L</li>
              <li>FIFO-based trade analysis</li>
            </ul>
          </div>
        </div>
      ) : (
        <div className="upstox-connected">
          <div className="connection-status">
            <span className="status-indicator connected"></span>
            <span>Connected to Upstox</span>
            {upstoxUser?.email && <span className="user-email">({upstoxUser.email})</span>}
          </div>
          
          <div className="upstox-actions">
            <button 
              className="btn btn-primary" 
              onClick={fetchUpstoxTrades}
              disabled={loading}
              style={{ marginRight: '10px' }}
            >
              {loading ? '⏳ Loading...' : '📊 Analyze My Trades'}
            </button>
            <button 
              className="btn btn-secondary" 
              onClick={fetchUpstoxHoldings}
              disabled={upstoxLoading}
              style={{ marginRight: '10px' }}
            >
              {upstoxLoading ? '⏳ Loading...' : '📈 View Holdings'}
            </button>
            <button 
              className="btn btn-danger" 
              onClick={disconnectUpstox}
            >
              🔓 Disconnect
            </button>
          </div>

          {/* Holdings Display */}
          {upstoxHoldings && upstoxHoldings.length > 0 && (
            <div style={{ marginTop: '30px' }}>
              <h3 style={{ color: 'var(--primary)', marginBottom: '15px' }}>📈 Current Holdings</h3>
              <div className="table-container">
                <table className="trades-table">
                  <thead>
                    <tr>
                      <th>Symbol</th>
                      <th>Quantity</th>
                      <th>Avg Price</th>
                      <th>Current Price</th>
                      <th>Total Cost</th>
                      <th>P&L</th>
                      <th>Day Change</th>
                    </tr>
                  </thead>
                  <tbody>
                    {upstoxHoldings.map((holding, idx) => (
                      <tr key={idx}>
                        <td className="bold">{holding.symbol}</td>
                        <td>{holding.quantity}</td>
                        <td>₹{holding.avg_price?.toFixed(2)}</td>
                        <td>₹{holding.current_price?.toFixed(2)}</td>
                        <td>₹{holding.total_cost?.toFixed(2)}</td>
                        <td className={holding.pnl > 0 ? 'positive' : holding.pnl < 0 ? 'negative' : ''}>
                          ₹{holding.pnl?.toFixed(2)}
                        </td>
                        <td className={holding.day_change > 0 ? 'positive' : holding.day_change < 0 ? 'negative' : ''}>
                          {holding.day_change?.toFixed(2)}%
                        </td>
                      </tr>
                    ))}
                  </tbody>
                  <tfoot>
                    <tr>
                      <td>Total</td>
                      <td></td>
                      <td></td>
                      <td></td>
                      <td>₹{upstoxHoldings.reduce((sum, h) => sum + (h.total_cost || 0), 0).toFixed(2)}</td>
                      <td className={upstoxHoldings.reduce((sum, h) => sum + (h.pnl || 0), 0) > 0 ? 'positive' : 'negative'}>
                        ₹{upstoxHoldings.reduce((sum, h) => sum + (h.pnl || 0), 0).toFixed(2)}
                      </td>
                      <td></td>
                    </tr>
                  </tfoot>
                </table>
              </div>
            </div>
          )}

          {upstoxHoldings && upstoxHoldings.length === 0 && (
            <div className="alert" style={{ marginTop: '20px', background: 'rgba(100,150,200,0.1)', borderLeft: '4px solid var(--text-secondary)' }}>
              No holdings found in your Upstox account.
            </div>
          )}
        </div>
      )}

      {error && (
        <div className="alert alert-error" style={{ marginTop: '20px' }}>
          ⚠️ {error}
        </div>
      )}
    </div>
  );

  return (
    <div className="container">
      <div className="header">
        <h1>📈 Stock Trade Analyzer</h1>
        <p>Analyze your trading performance with FIFO algorithm</p>
        {upstoxConnected && (
          <div className="header-status">
            <span className="status-indicator connected"></span>
            <span>Upstox Connected</span>
          </div>
        )}
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
          className={`tab ${activeTab === 'upstox' ? 'active' : ''}`}
          onClick={() => setActiveTab('upstox')}
        >
          🔗 Upstox {upstoxConnected && '✓'}
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
      {activeTab === 'upstox' && renderUpstoxTab()}
      {activeTab === 'results' && renderResultsTab()}
      {activeTab === 'single' && renderSingleTradeTab()}
    </div>
  );
};

export default TradeAnalyzer;
