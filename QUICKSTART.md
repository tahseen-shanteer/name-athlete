# Quick Start Guide - 2000 Athletes Challenge

## Get Running in 5 Minutes

### Prerequisites
- Python 3.9+ installed
- Node.js 18+ installed
- Two terminal windows

---

## Step 1: Start the Backend (Terminal 1)

```bash
# Navigate to backend directory
cd backend

# Install Python dependencies
pip install -r requirements.txt

# Start the server
python main.py
```

**Expected output:**
```
INFO:     Started server process [...]
INFO:     Waiting for application startup.
INFO:     Application startup complete.
INFO:     Uvicorn running on http://0.0.0.0:8000
```

✅ Backend is running on **http://localhost:8000**

---

## Step 2: Start the Frontend (Terminal 2)

```bash
# Navigate to frontend directory (from project root)
cd frontend

# Install Node dependencies
npm install

# Start development server
npm run dev
```

**Expected output:**
```
  VITE v5.0.12  ready in 423 ms

  ➜  Local:   http://localhost:3000/
  ➜  Network: use --host to expose
```

✅ Frontend is running on **http://localhost:3000**

---

## Step 3: Play the Game!

1. **Open your browser** to `http://localhost:3000`

2. **Create a Session**:
   - Click "Create New Session"
   - You'll get a 6-character code (e.g., "ABC123")

3. **Share the Code** with friends on the same network

4. **Join the Session**:
   - Others enter the code and their username
   - Click "Join Session"

5. **Start the Game**:
   - Creator clicks "Start Game"
   - 2-hour timer begins!

6. **Submit Athletes**:
   - Enter athlete name
   - Select sport
   - Click "Submit"
   - Watch the counter go up in real-time!

7. **Win**:
   - Reach 2000 athletes before time runs out!

---

## Testing It Out (Solo)

Want to test it yourself?

1. Open `http://localhost:3000` in your browser
2. Create a session
3. Open a **second browser tab** (or incognito window)
4. Join the same session with a different username
5. Submit athletes from both tabs and watch them sync!

---

## Sample Athletes to Try

**Basketball:**
- LeBron James
- Michael Jordan
- Kobe Bryant

**Soccer:**
- Lionel Messi
- Cristiano Ronaldo
- Pelé

**Tennis:**
- Serena Williams
- Roger Federer
- Rafael Nadal

**Baseball:**
- Babe Ruth
- Jackie Robinson
- Derek Jeter

---

## Common Issues

### "Port 8000 already in use"
```bash
# Find and kill the process
# Windows:
netstat -ano | findstr :8000
taskkill /PID <PID> /F

# Mac/Linux:
lsof -ti:8000 | xargs kill -9
```

### "Port 3000 already in use"
```bash
# Vite will offer to use 3001 instead - just say yes!
```

### "Cannot connect to server"
- Make sure backend is running (check terminal 1)
- Check `http://localhost:8000` shows: `{"message":"2000 Athletes Challenge API","status":"running"}`

### "Athletes not validating"
- Wikidata API may be slow (first query takes ~5-10 seconds)
- Subsequent queries are cached and fast
- Athletes will be marked "unvalidated" if API fails

---

## Next Steps

### For Production Use
See `DEPLOYMENT.md` for deploying to Render/Railway

### For Development
- Backend code is in `/backend`
- Frontend code is in `/frontend/src`
- API docs available at `http://localhost:8000/docs` (FastAPI auto-generated)

---

## Features Implemented

✅ Real-time collaboration (Socket.IO)
✅ 2-hour server-side timer
✅ Athlete validation (Wikidata API)
✅ Duplicate detection
✅ Reconnection support
✅ Late join support
✅ Mobile responsive design
✅ Unvalidated athlete marking
✅ Live counter and athlete list
✅ Recent submissions feed
✅ User tracking

---

## Need Help?

1. Check backend logs (Terminal 1)
2. Check frontend console (F12 in browser)
3. Review `README.md` for detailed info
4. Check `DEPLOYMENT.md` for hosting options

---

**Have fun reaching 2000 athletes!** 🏆
