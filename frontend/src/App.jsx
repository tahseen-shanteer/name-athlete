import React from 'react'
import { GameProvider, useGame } from './context/GameContext'
import { useSocket } from './hooks/useSocket'
import { CreateSession, JoinSession } from './components/SessionSetup'
import {
  Timer,
  Counter,
  SessionInfo,
  SubmitForm,
  AthleteList,
  RecentSubmissions,
  Notification,
  GameOverSummary,
  HostControls,
} from './components/GameComponents'
import { Leaderboard } from './components/Leaderboard'

const GameContent = () => {
  const { status, sessionCode, setSessionCode, setUsername, setStatus, count } = useGame()
  useSocket()

  const handleSessionCreated = (code, hostUsername) => {
    // Set username and session code, then move to joining state
    setUsername(hostUsername)
    setSessionCode(code)
    setStatus('joining')
  }

  const handleJoin = () => {
    setStatus('joining')
  }

  if (status === 'idle') {
    return (
      <div className="landing-page">
        <div className="hero">
          <h1>2000 Athletes Challenge</h1>
          <p>Can your team name 2000 unique athletes in 2 hours?</p>
        </div>
        
        <div className="actions">
          <div className="action-card">
            <h2>Create New Session</h2>
            <p>Start a new challenge and invite your friends</p>
            <CreateSession onCreated={handleSessionCreated} />
          </div>
          
          <div className="divider">OR</div>
          
          <div className="action-card">
            <h2>Join Existing Session</h2>
            <p>Enter the session code to join your friends</p>
            <JoinSession onJoin={handleJoin} />
          </div>
        </div>
      </div>
    )
  }

  if (status === 'joining' && sessionCode) {
    return (
      <div className="joining-page">
        <h1>Join Session: {sessionCode}</h1>
        <JoinSession onJoin={handleJoin} initialCode={sessionCode} />
      </div>
    )
  }

  // Game completed - show summary overlay
  if (status === 'completed') {
    return (
      <div className="game-page">
        <Notification />
        
        <header className="game-header">
          <h1>2000 Athletes Challenge</h1>
          <SessionInfo />
        </header>

        <div className="game-over-container">
          <GameOverSummary />
          <button onClick={() => window.location.reload()} className="btn btn-primary new-game-btn">
            Start New Game
          </button>
        </div>
      </div>
    )
  }

  return (
    <div className="game-page">
      <Notification />
      
      <header className="game-header">
        <h1>2000 Athletes Challenge</h1>
        <SessionInfo />
      </header>

      <div className="game-stats">
        <Counter />
        <Timer />
      </div>

      <div className="game-layout">
        {/* Main game area */}
        <div className="game-main">
          <SubmitForm />
          <HostControls />
          
          <div className="game-columns">
            <div className="column">
              <RecentSubmissions />
            </div>
            <div className="column column-wide">
              <AthleteList />
            </div>
          </div>
        </div>

        {/* Sidebar with users and leaderboard */}
        <Leaderboard />
      </div>
    </div>
  )
}

function App() {
  return (
    <GameProvider>
      <GameContent />
    </GameProvider>
  )
}

export default App
