# Deployment Guide

## Quick Deployment Options

### Option 1: Render.com (Recommended for Free Tier)

**Steps:**

1. **Create Render Account**: Sign up at [render.com](https://render.com)

2. **Deploy Backend**:
   - Click "New +" → "Web Service"
   - Connect your GitHub repo
   - Configure:
     - **Name**: `athletes-backend`
     - **Root Directory**: `backend`
     - **Runtime**: `Python 3`
     - **Build Command**: `pip install -r requirements.txt`
     - **Start Command**: `python main.py`
     - **Instance Type**: `Free`
   - Add Environment Variable:
     - `PORT` = `8000`
   - Click "Create Web Service"
   - Wait for deployment (~5 minutes)
   - Copy the backend URL (e.g., `https://athletes-backend-xyz.onrender.com`)

3. **Deploy Frontend**:
   - Click "New +" → "Static Site"
   - Connect your GitHub repo
   - Configure:
     - **Name**: `athletes-frontend`
     - **Root Directory**: `frontend`
     - **Build Command**: `npm install && npm run build`
     - **Publish Directory**: `dist`
   - Add Environment Variable:
     - `VITE_BACKEND_URL` = `<your-backend-url-from-step-2>`
   - Click "Create Static Site"
   - Wait for deployment (~3 minutes)
   - Your app is live!

**Limitations**:
- Free tier sleeps after 15 minutes of inactivity
- First request after sleep takes ~30 seconds to wake up
- 750 hours/month free

---

### Option 2: Railway.app

**Steps:**

1. **Create Railway Account**: Sign up at [railway.app](https://railway.app)

2. **Deploy from GitHub**:
   - Click "New Project" → "Deploy from GitHub repo"
   - Select your repository
   - Railway will detect both backend and frontend

3. **Configure Backend Service**:
   - Click on the backend service
   - Settings → Environment:
     - Add `PORT=8000`
   - Settings → Domain: Generate domain
   - Copy the backend URL

4. **Configure Frontend Service**:
   - Click on the frontend service
   - Settings → Environment:
     - Add `VITE_BACKEND_URL=<backend-url>`
   - Settings → Domain: Generate domain
   - Redeploy if needed

**Limitations**:
- Free tier: 500 hours/month shared across all projects
- $5/month for usage beyond free tier

---

### Option 3: Local Network (For Home Use)

If you just want to use it with friends on the same network:

1. **Find your local IP**:
   ```bash
   # Windows
   ipconfig
   # Look for IPv4 Address (e.g., 192.168.1.100)
   
   # Mac/Linux
   ifconfig
   ```

2. **Start backend** (from `backend/` directory):
   ```bash
   python main.py
   ```

3. **Start frontend** (from `frontend/` directory):
   Update `vite.config.js`:
   ```js
   server: {
     host: '0.0.0.0',  // Expose to network
     port: 3000,
     proxy: {
       '/socket.io': {
         target: 'http://192.168.1.100:8000',  // Your local IP
         ws: true
       },
       '/api': {
         target: 'http://192.168.1.100:8000'
       }
     }
   }
   ```
   
   Then run:
   ```bash
   npm run dev
   ```

4. **Share with friends**:
   - Give them: `http://192.168.1.100:3000`
   - They must be on the same Wi-Fi network

---

## Environment Variables

### Backend
- `PORT` - Port to run on (default: 8000)

### Frontend
- `VITE_BACKEND_URL` - Backend API URL (e.g., `https://your-backend.onrender.com`)

---

## Troubleshooting

### Backend won't start
- Check Python version (need 3.9+): `python --version`
- Install dependencies: `pip install -r requirements.txt`
- Check port not in use: `netstat -ano | findstr :8000`

### Frontend can't connect to backend
- Check CORS is enabled (should be by default in `main.py`)
- Verify `VITE_BACKEND_URL` is set correctly
- Check browser console for errors (F12)

### WebSocket connection fails
- Ensure your hosting platform supports WebSockets
- Render and Railway both support it
- Some proxies/firewalls block WebSocket connections

### Athletes not validating
- Wikidata API may be slow or rate-limited
- Check backend logs for validation errors
- Athletes will be marked as "unvalidated" on API failure

### Session lost after server restart
- Sessions are stored in memory (by design for MVP)
- Server restart clears all sessions
- Consider adding Redis/database for production persistence

---

## Production Recommendations

If you want to use this beyond tonight:

1. **Add Database**: Replace in-memory storage with PostgreSQL/MongoDB
2. **Add Redis**: For session management and caching
3. **Better Validation**: Pre-populate athlete database for faster validation
4. **Rate Limiting**: Prevent abuse of submission endpoints
5. **Analytics**: Track session statistics
6. **Better Error Handling**: More detailed error messages
7. **Testing**: Add unit and integration tests

---

## Monitoring

### Check Backend Health
```bash
curl https://your-backend-url.com/
# Should return: {"message":"2000 Athletes Challenge API","status":"running"}
```

### Check Session Creation
```bash
curl -X POST https://your-backend-url.com/api/session/create
# Should return: {"code":"ABC123","created_at":"..."}
```

---

## Scaling Considerations

Current architecture supports:
- **5-10 concurrent users per session**: Comfortable
- **Multiple sessions**: Limited by server memory
- **100+ athletes per session**: No issues
- **2000 athletes**: Tested and working

For larger scale:
- Move to database storage
- Add caching layer (Redis)
- Load balancer for multiple backend instances
- CDN for frontend assets

---

## Cost Estimate

**Free Tier (Render)**:
- Backend: Free (with cold starts)
- Frontend: Free
- Total: **$0/month**

**Paid Tier (Render)**:
- Backend: $7/month (always on)
- Frontend: Free
- Total: **$7/month**

**Railway**:
- $5/month for execution time beyond free tier
- Typically **$5-10/month** for this app

---

## Support

Need help deploying? Common issues:

1. **"Module not found" errors**: Run `pip install -r requirements.txt` or `npm install`
2. **"Port already in use"**: Change port or kill process using it
3. **"CORS error"**: Check CORS settings in `main.py`
4. **"Cannot connect to WebSocket"**: Check hosting platform supports WebSockets

Still stuck? Check the logs on your hosting platform's dashboard.
