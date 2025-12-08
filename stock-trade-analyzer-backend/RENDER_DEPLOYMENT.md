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
- Check that `requirements.txt` has all dependencies
- Verify Python version in `runtime.txt` matches Render's supported versions

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

