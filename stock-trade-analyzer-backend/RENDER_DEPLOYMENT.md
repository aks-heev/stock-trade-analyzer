# Render Deployment Guide

## Files Required for Render Deployment

1. ✅ **Procfile** - Tells Render how to start the server
2. ✅ **requirements.txt** - Python dependencies
3. ✅ **runtime.txt** - Python version specification

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

### 3. Environment Variables (Optional)

No environment variables required for basic deployment. The PORT is automatically set by Render.

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

**Solution**: 
1. **Manually set Python version in Render Dashboard**:
   - Go to your service → Settings → Environment
   - Set "Python Version" to `3.11.9` or `3.11`
   - Save and redeploy
   
2. **Why this happens**: 
   - pandas 2.2.0 doesn't have pre-built wheels for Python 3.13
   - Building from source fails due to Cython/C++ compilation issues
   - Python 3.11 has pre-built wheels available

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

