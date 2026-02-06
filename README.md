# 2000 Athletes Challenge

A real-time collaborative web app where friends compete to name 2000 unique athletes in 2 hours!

## Features

- 🎮 Real-time collaboration with Socket.IO
- ⏱️ Server-side 2-hour countdown timer
- ✅ Athlete validation via Wikidata API
- 🔄 Automatic reconnection support
- 📱 Mobile-responsive design
- 🏆 Live leaderboard and statistics
- 🔍 Duplicate detection
- 🌐 Late join support

## Tech Stack

**Backend:**
- FastAPI (Python)
- Socket.IO for real-time communication
- Wikidata SPARQL API for athlete validation
- In-memory session storage

**Frontend:**
- React 18
- Vite
- Socket.IO Client
- CSS3 with responsive design

## Quick Start

### Prerequisites

- Python 3.9+
- Node.js 18+
- npm or yarn

### Installation

1. **Clone the repository**
```bash
git clone <your-repo>
cd name_athletes
```

2. **Set up the backend**
```bash
cd backend
pip install -r requirements.txt
```

3. **Set up the frontend**
```bash
cd ../frontend
npm install
```

### Running Locally

1. **Start the backend** (from `/backend` directory):
```bash
python main.py
```
The backend will run on `http://localhost:8000`

2. **Start the frontend** (from `/frontend` directory):
```bash
npm run dev
```
The frontend will run on `http://localhost:3000`

3. **Open your browser** to `http://localhost:3000`

## How to Play

1. **Create a Session:** One player creates a new session and receives a 6-character code
2. **Share the Code:** Share the code with your friends
3. **Join:** Friends enter the code and their username to join
4. **Start:** The creator starts the 2-hour timer
5. **Submit Athletes:** Everyone submits athlete names and their sport
6. **Win:** Reach 2000 unique athletes before time runs out!

## Key Features Explained

### Athlete Validation
- Athletes are validated against Wikidata's database
- Name variations and aliases are handled automatically
- If Wikidata API fails, submissions are accepted but marked as "unvalidated"

### Reconnection Support
- Users can close the tab and rejoin using the same username
- Session state is preserved for 5 minutes after disconnect
- Full game state is synced on reconnect

### Late Join
- Friends can join even after the game has started
- They receive the full current state immediately

## Deployment

### Deploy to Railway

1. Create a new project on [Railway.app](https://railway.app)
2. Connect your GitHub repository
3. Add two services:
   - **Backend:** Python service pointing to `/backend`
   - **Frontend:** Static site pointing to `/frontend`
4. Set environment variables:
   - Backend: `PORT=8000`
   - Frontend: `VITE_BACKEND_URL=<your-backend-url>`
5. Deploy!

### Deploy to Render

1. Create a new Web Service on [Render.com](https://render.com)
2. Connect your repository
3. Configure:
   - **Backend:**
     - Build: `pip install -r requirements.txt`
     - Start: `python main.py`
   - **Frontend:**
     - Build: `npm install && npm run build`
     - Static site from `dist` folder
4. Deploy!

## Project Structure

```
name_athletes/
├── backend/
│   ├── main.py              # FastAPI app entry point
│   ├── models.py            # Pydantic data models
│   ├── session_manager.py   # Session state management
│   ├── validation.py        # Wikidata athlete validation
│   ├── events.py            # Socket.IO event handlers
│   ├── sports_config.py     # Sport definitions
│   └── requirements.txt     # Python dependencies
│
└── frontend/
    ├── src/
    │   ├── App.jsx          # Main app component
    │   ├── main.jsx         # React entry point
    │   ├── components/      # React components
    │   ├── hooks/           # Custom hooks (useSocket)
    │   ├── context/         # Game context provider
    │   └── styles/          # CSS styling
    ├── index.html
    ├── package.json
    └── vite.config.js
```

## API Documentation

### REST Endpoints

- `POST /api/session/create` - Create a new session
- `GET /api/session/{code}` - Get session details
- `GET /api/sports` - Get list of available sports

### Socket.IO Events

**Client → Server:**
- `join_session` - Join a game session
- `start_game` - Start the timer
- `submit_athlete` - Submit an athlete

**Server → Client:**
- `session_joined` - Session state on join
- `game_started` - Timer has begun
- `athlete_added` - New valid athlete added
- `submission_error` - Invalid submission
- `timer_tick` - Timer update (every second)
- `game_ended` - Game over

## Known Limitations

- Sessions are stored in-memory (lost on server restart)
- Wikidata API may have rate limits
- No user authentication
- Maximum 2-hour session duration

## Future Enhancements

- Persistent storage (database)
- User authentication
- Session history and replays
- Export results to CSV
- Sound effects
- More sports and better sport matching
- Fuzzy name matching for typos

## License

MIT

## Contributing

Pull requests welcome! Please open an issue first to discuss changes.

## Support

For issues, please open a GitHub issue or contact the maintainers.
