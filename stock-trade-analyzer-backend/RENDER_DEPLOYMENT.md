# Render Deployment Guide

## Files Required for Render Deployment

1. ✅ **Procfile** - Tells Render how to start the server
2. ✅ **requirements.txt** - Python dependencies
3. ✅ **runtime.txt** - Python version specification (may be ignored by Render)
4. ✅ **.python-version** - Alternative Python version specification

## Render Setup Steps

### 1. Create a New Web Service on Render

1. Go to [Render Dashboard](https://dashboard.render.com)
2. Click "New +" → "Web Service"
3. Connect your Git repository

### 2. Configure Build Settings

- **Name**: `stock-trade-analyzer-backend` (or your preferred name)
- **Environment**: `Python 3`
- **Python Version**: **IMPORTANT** - Set to `3.11.9` (or 3.11.x) in Render dashboard
  - Go to: Settings → Environment → Python Version
  - Select: `3.11.9` or `3.11`
  - **Why?** pandas 2.2.0 doesn't have pre-built wheels for Python 3.13, causing build failures
- **Build Command**: `pip install -r requirements.txt`
- **Start Command**: (Leave empty - Procfile will be used automatically)
  - Or manually: `uvicorn stock_analyzer_backend_v2:app --host 0.0.0.0 --port $PORT`

### 3. Environment Variables (CRITICAL)

**REQUIRED**: Set Python version via environment variable:

1. Go to: Settings → Environment
2. Click "Add Environment Variable"
3. Add:
   - **Key**: `PYTHON_VERSION`
   - **Value**: `3.11.9`
4. Save

**Why?** Render may ignore `runtime.txt`. Setting `PYTHON_VERSION` environment variable forces Python 3.11, which has pre-built pandas wheels.

**Note**: The PORT environment variable is automatically set by Render (no need to add it manually).

### 4. Deploy

Click "Create Web Service" and Render will:
- Install dependencies from `requirements.txt`
- Start the server using the `Procfile`
- Make it available at `https://your-app-name.onrender.com`

## Important Notes

- **Port**: The app now uses the `PORT` environment variable (set by Render automatically)
- **CORS**: Currently set to allow all origins (`*`). For production, consider restricting to your frontend domain
- **File Uploads**: Make sure your Render plan supports file uploads (free tier has limitations)

## Testing the Deployment

Once deployed, test the endpoints:

```bash
# Health check
curl https://your-app-name.onrender.com/health

# API info
curl https://your-app-name.onrender.com/
```

## Troubleshooting

### Build Fails

#### Python Version Issue (pandas build failure)
**Error**: `error: metadata-generation-failed` when building pandas  
**Error**: `==> Using Python version 3.13.4 (default)` (Render ignoring runtime.txt)

**Solution**: 
1. **Set PYTHON_VERSION environment variable** (MOST RELIABLE):
   - Go to your service → Settings → Environment
   - Click "Add Environment Variable"
   - Key: `PYTHON_VERSION`
   - Value: `3.11.9`
   - Save and redeploy
   
2. **Alternative - Set Python Version in Settings**:
   - Go to: Settings → Environment → Python Version dropdown
   - Select: `3.11.9` or `3.11`
   - Save and redeploy
   
3. **Why this happens**: 
   - Render may ignore `runtime.txt` file
   - pandas 2.2.0 doesn't have pre-built wheels for Python 3.13
   - Building from source fails due to Cython/C++ compilation issues
   - Python 3.11 has pre-built wheels available
   - Setting `PYTHON_VERSION` environment variable forces the correct version

#### Other Build Issues
- Check that `requirements.txt` has all dependencies
- Verify Python version in `runtime.txt` is `3.11.9` (format: just the version number)
- Ensure `Procfile` exists and has correct format (no trailing newlines)

### App Crashes
- Check Render logs: Dashboard → Your Service → Logs
- Verify the Procfile command is correct
- Ensure all imports are available in requirements.txt

### Port Issues
- The app now uses `$PORT` environment variable automatically
- No need to hardcode port numbers

## Update Frontend

After deployment, update your frontend `App.js` to use the Render URL:

```javascript
const API_BASE_URL = 'https://your-app-name.onrender.com';
```

