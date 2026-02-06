import React, { useState, useEffect, useMemo } from 'react'
import Select from 'react-select'
import { useGame } from '../context/GameContext'
import { useSocket } from '../hooks/useSocket'
import { BACKEND_URL } from '../config'

export const Timer = () => {
  const { timeRemaining, status, isPaused } = useGame()

  const formatTime = (seconds) => {
    const h = Math.floor(seconds / 3600)
    const m = Math.floor((seconds % 3600) / 60)
    const s = seconds % 60
    return `${h}:${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`
  }

  if (status !== 'active' && status !== 'completed') return null

  return (
    <div className={`timer ${timeRemaining < 300 ? 'timer-warning' : ''} ${isPaused ? 'timer-paused' : ''}`}>
      <div className="timer-label">Time Remaining</div>
      <div className="timer-value">{formatTime(timeRemaining)}</div>
      {isPaused && <div className="timer-paused-label">PAUSED</div>}
    </div>
  )
}

export const Counter = () => {
  const { count, status } = useGame()

  if (status === 'idle' || status === 'joining') return null

  return (
    <div className="counter">
      <div className="counter-value">{count}</div>
      <div className="counter-label">/ 2000 Athletes</div>
      {count >= 2000 && <div className="counter-success">GOAL REACHED!</div>}
    </div>
  )
}

export const SessionInfo = () => {
  const { sessionCode, connectedUsers, yourSubmissions, status, isHost, hostUsername } = useGame()
  const { startGame } = useSocket()

  if (status === 'idle' || status === 'joining') return null

  const onlineCount = connectedUsers.filter(u => u.is_connected).length

  return (
    <div className="session-info">
      <div className="session-code">
        <span className="label">Session Code:</span>
        <span className="code">{sessionCode}</span>
      </div>
      <div className="session-stats">
        <span>{onlineCount} users online</span>
        <span>•</span>
        <span>You: {yourSubmissions} submissions</span>
        {isHost && <span className="host-indicator">• You are the host</span>}
      </div>
      {status === 'waiting' && (
        <div className="start-game-section">
          {isHost ? (
            <button onClick={startGame} className="btn btn-success">
              Start Game
            </button>
          ) : (
            <p className="waiting-message">Waiting for {hostUsername || 'host'} to start the game...</p>
          )}
        </div>
      )}
    </div>
  )
}

// Custom styles for react-select to match our design
const sportSelectStyles = {
  control: (base, state) => ({
    ...base,
    minHeight: '44px',
    borderWidth: '2px',
    borderColor: state.isFocused ? '#667eea' : '#ddd',
    borderRadius: '6px',
    boxShadow: 'none',
    fontSize: '1rem',
    '&:hover': { borderColor: '#667eea' },
  }),
  menu: (base) => ({
    ...base,
    zIndex: 20,
    borderRadius: '6px',
    boxShadow: '0 4px 12px rgba(0,0,0,0.15)',
  }),
  option: (base, state) => ({
    ...base,
    backgroundColor: state.isSelected ? '#667eea' : state.isFocused ? '#f0f4ff' : 'white',
    color: state.isSelected ? 'white' : '#333',
    fontSize: '0.95rem',
    padding: '10px 12px',
    '&:active': { backgroundColor: '#5568d3', color: 'white' },
  }),
  placeholder: (base) => ({
    ...base,
    color: '#999',
  }),
  singleValue: (base) => ({
    ...base,
    color: '#333',
  }),
  input: (base) => ({
    ...base,
    color: '#333',
  }),
}

export const SubmitForm = () => {
  const [athleteName, setAthleteName] = useState('')
  const [selectedSport, setSelectedSport] = useState(null)
  const [hint, setHint] = useState('')
  const [sportOptions, setSportOptions] = useState([])
  const { 
    status, 
    isSubmitting, 
    error, 
    setError,
    requiresHint,
    pendingSubmission,
    clearDisambiguation
  } = useGame()
  const { submitAthlete } = useSocket()

  useEffect(() => {
    // Fetch sports list and transform to react-select format
    fetch(BACKEND_URL + '/api/sports')
      .then(res => res.json())
      .then(data => {
        const options = (data.sports || []).map(s => ({
          value: s.value,       // Q-ID (e.g., "Q5372")
          label: s.label,       // Display name (e.g., "basketball")
        }))
        setSportOptions(options)
      })
      .catch(err => console.error('Failed to load sports:', err))
  }, [])

  const handleSubmit = (e) => {
    e.preventDefault()
    
    // If disambiguation is required, use pending submission with hint
    if (requiresHint && pendingSubmission) {
      if (!hint.trim()) {
        setError('Please enter a hint (team, country, or birth year) to identify the athlete')
        return
      }
      submitAthlete(pendingSubmission.name, pendingSubmission.sport, hint.trim(), pendingSubmission.sportLabel)
      setHint('')
      return
    }

    if (!athleteName.trim() || !selectedSport) {
      setError('Please enter athlete name and select a sport')
      return
    }

    // Send the Q-ID as the sport value, label for display
    submitAthlete(athleteName.trim(), selectedSport.value, null, selectedSport.label)
    setAthleteName('')
  }

  const handleCancelDisambiguation = () => {
    clearDisambiguation()
    setHint('')
  }

  if (status !== 'active') return null

  // Show disambiguation hint form when required
  if (requiresHint && pendingSubmission) {
    return (
      <form onSubmit={handleSubmit} className="submit-form disambiguation-form">
        <div className="disambiguation-header">
          <p className="disambiguation-message">
            Multiple athletes named <strong>"{pendingSubmission.name}"</strong> found in {pendingSubmission.sportLabel || pendingSubmission.sport}.
            <br />
            Please add a hint to identify the specific player.
          </p>
        </div>
        <div className="form-row">
          <input
            type="text"
            placeholder="Enter hint (e.g., team, country, birth year)"
            value={hint}
            onChange={(e) => {
              setHint(e.target.value)
              setError(null)
            }}
            disabled={isSubmitting}
            autoFocus
            autoComplete="off"
          />
          <button type="submit" disabled={isSubmitting} className="btn btn-primary">
            {isSubmitting ? 'Submitting...' : 'Submit with Hint'}
          </button>
          <button 
            type="button" 
            onClick={handleCancelDisambiguation} 
            className="btn btn-secondary"
            disabled={isSubmitting}
          >
            Cancel
          </button>
        </div>
        {error && <p className="error">{error}</p>}
      </form>
    )
  }

  // Normal submission form
  return (
    <form onSubmit={handleSubmit} className="submit-form">
      <div className="form-row">
        <input
          type="text"
          placeholder="Athlete Name"
          value={athleteName}
          onChange={(e) => {
            setAthleteName(e.target.value)
            setError(null)
          }}
          disabled={isSubmitting}
          required
          autoComplete="off"
        />
        <div className="sport-select-wrapper">
          <Select
            options={sportOptions}
            value={selectedSport}
            onChange={(option) => {
              setSelectedSport(option)
              setError(null)
            }}
            placeholder="Search sport..."
            isSearchable={true}
            isClearable={true}
            isDisabled={isSubmitting}
            styles={sportSelectStyles}
            noOptionsMessage={() => 'No sports found'}
            maxMenuHeight={250}
          />
        </div>
        <button type="submit" disabled={isSubmitting} className="btn btn-primary">
          {isSubmitting ? 'Submitting...' : 'Submit'}
        </button>
      </div>
      {error && <p className="error">{error}</p>}
    </form>
  )
}

export const AthleteList = () => {
  const { athletes, status } = useGame()
  const [searchTerm, setSearchTerm] = useState('')

  if (status === 'idle' || status === 'joining' || status === 'waiting') return null

  const filteredAthletes = athletes.filter(a =>
    a.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
    (a.canonical_name && a.canonical_name.toLowerCase().includes(searchTerm.toLowerCase())) ||
    a.sport.toLowerCase().includes(searchTerm.toLowerCase()) ||
    a.submitted_by.toLowerCase().includes(searchTerm.toLowerCase())
  )

  return (
    <div className="athlete-list">
      <div className="list-header">
        <h3>Athletes ({athletes.length})</h3>
        <input
          type="text"
          placeholder="Search athletes..."
          value={searchTerm}
          onChange={(e) => setSearchTerm(e.target.value)}
          className="search-input"
        />
      </div>
      <div className="list-content">
        {filteredAthletes.length === 0 ? (
          <p className="empty-message">
            {athletes.length === 0 ? 'No athletes yet. Start submitting!' : 'No matches found.'}
          </p>
        ) : (
          <ul>
            {filteredAthletes.map((athlete, index) => (
              <li key={`${athlete.name}-${index}`} className={!athlete.validated ? 'unvalidated' : ''}>
                <span className="athlete-name">{athlete.canonical_name || athlete.name}</span>
                <span className="athlete-sport">{athlete.sport}</span>
                <span className="athlete-user">by {athlete.submitted_by}</span>
                {!athlete.validated && <span className="validation-badge">⚠</span>}
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  )
}

export const RecentSubmissions = () => {
  const { recentSubmissions, status } = useGame()

  if (status !== 'active' && status !== 'completed') return null
  if (recentSubmissions.length === 0) return null

  return (
    <div className="recent-submissions">
      <h3>Recent Submissions</h3>
      <ul>
        {recentSubmissions.slice(0, 5).map((athlete, index) => (
          <li key={`${athlete.name}-${index}`}>
            <span className="athlete-name">{athlete.canonical_name || athlete.name}</span>
            <span className="athlete-sport">({athlete.sport})</span>
            <span className="athlete-user">by {athlete.submitted_by}</span>
          </li>
        ))}
      </ul>
    </div>
  )
}

export const Notification = () => {
  const { notification } = useGame()

  if (!notification) return null

  return (
    <div className={`notification notification-${notification.type}`}>
      {notification.message}
    </div>
  )
}

export const GameOverSummary = () => {
  const { status, count, leaderboard, rejectedSubmissions, athletes } = useGame()
  const [showRejected, setShowRejected] = useState(false)

  if (status !== 'completed') return null

  const goalReached = count >= 2000

  return (
    <div className="game-over-summary">
      <div className="game-over-header">
        <h2>{goalReached ? '🎉 GOAL REACHED!' : '⏱️ Time\'s Up!'}</h2>
        <div className="final-count">
          <span className="count-number">{count}</span>
          <span className="count-label">/ 2000 Athletes</span>
        </div>
      </div>

      {/* Final Leaderboard */}
      <div className="final-leaderboard">
        <h3>🏆 Final Standings</h3>
        <ul>
          {leaderboard.map((entry, index) => (
            <li key={entry.username} className={`rank-${entry.rank}`}>
              <span className="rank">
                {entry.rank <= 3 ? ['🥇', '🥈', '🥉'][entry.rank - 1] : `${entry.rank}.`}
              </span>
              <span className="name">{entry.username}</span>
              <span className="score">{entry.score} submissions</span>
            </li>
          ))}
        </ul>
      </div>

      {/* Rejected Submissions */}
      {rejectedSubmissions.length > 0 && (
        <div className="rejected-section">
          <button 
            className="btn btn-secondary toggle-rejected"
            onClick={() => setShowRejected(!showRejected)}
          >
            {showRejected ? 'Hide' : 'Show'} Rejected Submissions ({rejectedSubmissions.length})
          </button>
          
          {showRejected && (
            <div className="rejected-list">
              <table>
                <thead>
                  <tr>
                    <th>Athlete</th>
                    <th>Sport</th>
                    <th>Submitted By</th>
                  </tr>
                </thead>
                <tbody>
                  {rejectedSubmissions.map((submission, index) => (
                    <tr key={index}>
                      <td>{submission.name}</td>
                      <td>{submission.sport}</td>
                      <td>{submission.username}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

export const HostControls = () => {
  const { isHost, status, connectedUsers, username, isPaused } = useGame()
  const { pauseGame, resumeGame, endGameEarly, removePlayer } = useSocket()
  const [showControls, setShowControls] = useState(false)

  if (!isHost || status !== 'active') return null

  const handleEndGame = () => {
    if (window.confirm('Are you sure you want to end the game early?')) {
      endGameEarly()
    }
  }

  const handleRemovePlayer = (targetUsername) => {
    if (window.confirm(`Remove ${targetUsername} from the session?`)) {
      removePlayer(targetUsername)
    }
  }

  // Get non-host players that can be removed
  const removablePlayers = connectedUsers.filter(
    u => u.username !== username
  )

  return (
    <div className="host-controls">
      <button 
        className="btn btn-secondary host-controls-toggle"
        onClick={() => setShowControls(!showControls)}
      >
        Host Controls {showControls ? '▲' : '▼'}
      </button>
      
      {showControls && (
        <div className="host-controls-panel">
          <div className="host-controls-actions">
            {isPaused ? (
              <button onClick={resumeGame} className="btn btn-success">
                ▶ Resume
              </button>
            ) : (
              <button onClick={pauseGame} className="btn btn-warning">
                ⏸ Pause
              </button>
            )}
            <button onClick={handleEndGame} className="btn btn-danger">
              End Game
            </button>
          </div>

          {removablePlayers.length > 0 && (
            <div className="host-controls-players">
              <h4>Remove Player</h4>
              <ul className="removable-players-list">
                {removablePlayers.map(user => (
                  <li key={user.username} className="removable-player">
                    <span className={`status-dot ${user.is_connected ? 'online' : 'offline'}`}></span>
                    <span className="player-name">{user.username}</span>
                    <button 
                      onClick={() => handleRemovePlayer(user.username)}
                      className="btn-remove-player"
                      title={`Remove ${user.username}`}
                    >
                      ✕
                    </button>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
