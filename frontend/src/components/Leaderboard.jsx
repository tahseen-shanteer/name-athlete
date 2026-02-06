import React, { useEffect, useState } from 'react'
import { useGame } from '../context/GameContext'

export const Leaderboard = () => {
  const { 
    connectedUsers, 
    leaderboard, 
    username, 
    status,
    hostUsername 
  } = useGame()
  
  // Track animations for rank changes
  const [animatingEntries, setAnimatingEntries] = useState({})

  // Trigger animations when leaderboard changes
  useEffect(() => {
    const newAnimations = {}
    leaderboard.forEach(entry => {
      if (entry.rankChange && entry.rankChange !== 0) {
        newAnimations[entry.username] = entry.rankChange > 0 ? 'rank-up' : 'rank-down'
      }
    })
    
    if (Object.keys(newAnimations).length > 0) {
      setAnimatingEntries(newAnimations)
      // Clear animations after they complete
      setTimeout(() => setAnimatingEntries({}), 600)
    }
  }, [leaderboard])

  // Don't show during idle/joining
  if (status === 'idle' || status === 'joining') return null

  return (
    <div className="leaderboard-sidebar">
      {/* Users Section */}
      <div className="sidebar-section">
        <h3 className="sidebar-title">
          <span className="sidebar-icon">👥</span>
          Players ({connectedUsers.length})
        </h3>
        <ul className="user-list">
          {connectedUsers.map((user) => (
            <li 
              key={user.username} 
              className={`user-item ${user.username === username ? 'current-user' : ''}`}
            >
              <span className={`status-dot ${user.is_connected ? 'online' : 'offline'}`}></span>
              <span className="user-name">
                {user.username}
                {user.is_host && <span className="host-badge">Host</span>}
                {user.username === username && <span className="you-badge">You</span>}
              </span>
            </li>
          ))}
        </ul>
      </div>

      {/* Leaderboard Section - only show during active/completed */}
      {(status === 'active' || status === 'completed') && (
        <div className="sidebar-section">
          <h3 className="sidebar-title">
            <span className="sidebar-icon">🏆</span>
            Leaderboard
          </h3>
          <ul className="leaderboard-list">
            {leaderboard.map((entry) => (
              <li 
                key={entry.username}
                className={`leaderboard-item ${entry.username === username ? 'current-user' : ''} ${animatingEntries[entry.username] || ''}`}
              >
                <span className="rank">
                  {entry.rank <= 3 ? ['🥇', '🥈', '🥉'][entry.rank - 1] : `${entry.rank}.`}
                </span>
                <span className="leaderboard-name">
                  {entry.username}
                  {entry.username === username && <span className="you-indicator">(You)</span>}
                </span>
                <span className="score">{entry.score} pts</span>
                {animatingEntries[entry.username] === 'rank-up' && (
                  <span className="rank-change up">▲</span>
                )}
                {animatingEntries[entry.username] === 'rank-down' && (
                  <span className="rank-change down">▼</span>
                )}
              </li>
            ))}
            {leaderboard.length === 0 && (
              <li className="empty-message">No submissions yet</li>
            )}
          </ul>
        </div>
      )}
    </div>
  )
}

export default Leaderboard
