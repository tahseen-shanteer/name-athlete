import React, { createContext, useContext, useState, useRef } from 'react'

const GameContext = createContext(null)

export const GameProvider = ({ children }) => {
  const [sessionCode, setSessionCode] = useState(null)
  const [username, setUsername] = useState('')
  const [status, setStatus] = useState('idle') // 'idle' | 'joining' | 'waiting' | 'active' | 'completed'
  const [athletes, setAthletes] = useState([])
  const [count, setCount] = useState(0)
  const [timeRemaining, setTimeRemaining] = useState(0) // seconds
  const [endsAt, setEndsAt] = useState(null)
  const [recentSubmissions, setRecentSubmissions] = useState([])
  const [error, setError] = useState(null)
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [connectedUsers, setConnectedUsers] = useState([]) // Now contains {username, is_connected, is_host}
  const [yourSubmissions, setYourSubmissions] = useState(0)
  const [notification, setNotification] = useState(null)
  
  // Host tracking
  const [isHost, setIsHost] = useState(false)
  const [hostUsername, setHostUsername] = useState(null)
  
  // Leaderboard state
  const [leaderboard, setLeaderboard] = useState([])
  const previousRanks = useRef({}) // Track previous ranks for animation
  
  // Rejected submissions (shown at game end)
  const [rejectedSubmissions, setRejectedSubmissions] = useState([])
  
  // Disambiguation state - when multiple athletes match
  const [requiresHint, setRequiresHint] = useState(false)
  const [pendingSubmission, setPendingSubmission] = useState(null) // {name, sport} to retry with hint
  
  // Pause state
  const [isPaused, setIsPaused] = useState(false)

  const addAthlete = (athlete) => {
    setAthletes(prev => [...prev, athlete])
    setCount(prev => prev + 1)
    
    // Update recent submissions (keep last 10)
    setRecentSubmissions(prev => [athlete, ...prev].slice(0, 10))
    
    // Update your submissions count if it's yours
    if (athlete.submitted_by === username) {
      setYourSubmissions(prev => prev + 1)
    }
    
    // Clear disambiguation state on successful submission
    setRequiresHint(false)
    setPendingSubmission(null)
  }

  const updateLeaderboard = (newLeaderboard) => {
    // Store previous ranks for animation detection
    const prevRanks = {}
    leaderboard.forEach(entry => {
      prevRanks[entry.username] = entry.rank
    })
    previousRanks.current = prevRanks
    
    // Update leaderboard with rank change info
    const enrichedLeaderboard = newLeaderboard.map(entry => ({
      ...entry,
      previousRank: prevRanks[entry.username] || null,
      rankChange: prevRanks[entry.username] 
        ? prevRanks[entry.username] - entry.rank 
        : 0
    }))
    
    setLeaderboard(enrichedLeaderboard)
  }

  const updateUsers = (users) => {
    setConnectedUsers(users)
  }

  const showNotification = (message, type = 'info') => {
    setNotification({ message, type })
    setTimeout(() => setNotification(null), 3000)
  }

  const resetGame = () => {
    setSessionCode(null)
    setStatus('idle')
    setAthletes([])
    setCount(0)
    setTimeRemaining(0)
    setEndsAt(null)
    setRecentSubmissions([])
    setError(null)
    setConnectedUsers([])
    setYourSubmissions(0)
    setRequiresHint(false)
    setPendingSubmission(null)
    setIsHost(false)
    setHostUsername(null)
    setLeaderboard([])
    setRejectedSubmissions([])
    setIsPaused(false)
    previousRanks.current = {}
  }
  
  const clearDisambiguation = () => {
    setRequiresHint(false)
    setPendingSubmission(null)
    setError(null)
  }

  const value = {
    sessionCode, setSessionCode,
    username, setUsername,
    status, setStatus,
    athletes, setAthletes, addAthlete,
    count, setCount,
    timeRemaining, setTimeRemaining,
    endsAt, setEndsAt,
    recentSubmissions, setRecentSubmissions,
    error, setError,
    isSubmitting, setIsSubmitting,
    connectedUsers, setConnectedUsers, updateUsers,
    yourSubmissions, setYourSubmissions,
    notification, showNotification,
    requiresHint, setRequiresHint,
    pendingSubmission, setPendingSubmission,
    clearDisambiguation,
    resetGame,
    // New state
    isHost, setIsHost,
    hostUsername, setHostUsername,
    leaderboard, updateLeaderboard,
    rejectedSubmissions, setRejectedSubmissions,
    isPaused, setIsPaused,
  }

  return <GameContext.Provider value={value}>{children}</GameContext.Provider>
}

export const useGame = () => {
  const context = useContext(GameContext)
  if (!context) {
    throw new Error('useGame must be used within GameProvider')
  }
  return context
}
