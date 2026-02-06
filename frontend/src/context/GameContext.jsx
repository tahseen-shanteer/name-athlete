import React, { createContext, useContext, useState, useRef, useCallback } from 'react'

const GameContext = createContext(null)

export const GameProvider = ({ children }) => {
  const [sessionCode, setSessionCode] = useState(null)
  const [username, setUsername] = useState('')
  const [status, setStatus] = useState('idle') // 'idle' | 'joining' | 'waiting' | 'active' | 'completed'
  const [athletes, setAthletes] = useState([])
  const [timeRemaining, setTimeRemaining] = useState(0) // seconds
  const [endsAt, setEndsAt] = useState(null)
  const [recentSubmissions, setRecentSubmissions] = useState([])
  const [error, setError] = useState(null)
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [connectedUsers, setConnectedUsers] = useState([]) // Now contains {username, is_connected, is_host}
  const [yourSubmissions, setYourSubmissions] = useState(0)
  const [notification, setNotification] = useState(null)
  const notificationTimerRef = useRef(null)
  
  // Host tracking
  const [isHost, setIsHost] = useState(false)
  const [hostUsername, setHostUsername] = useState(null)
  
  // Leaderboard state
  const [leaderboard, setLeaderboard] = useState([])
  const previousRanksRef = useRef({}) // Track previous ranks for animation
  
  // Rejected submissions (shown at game end)
  const [rejectedSubmissions, setRejectedSubmissions] = useState([])
  
  // Disambiguation state - when multiple athletes match
  const [requiresHint, setRequiresHint] = useState(false)
  const [pendingSubmission, setPendingSubmission] = useState(null) // {name, sport} to retry with hint
  
  // Pause state
  const [isPaused, setIsPaused] = useState(false)

  // Socket action refs — populated by useSocket, consumed by any component via context
  const socketRef = useRef(null)

  // Derive count from athletes array length
  const count = athletes.length

  // Use refs for values needed inside addAthlete to avoid stale closures
  const usernameRef = useRef(username)
  usernameRef.current = username

  const addAthlete = useCallback((athlete) => {
    setAthletes(prev => [...prev, athlete])
    
    // Update recent submissions (keep last 10)
    setRecentSubmissions(prev => [athlete, ...prev].slice(0, 10))
    
    // Update your submissions count if it's yours
    if (athlete.submitted_by === usernameRef.current) {
      setYourSubmissions(prev => prev + 1)
    }
    
    // Only clear disambiguation state if this is the current user's submission
    if (athlete.submitted_by === usernameRef.current) {
      setRequiresHint(false)
      setPendingSubmission(null)
    }
  }, [])

  const updateLeaderboard = useCallback((newLeaderboard) => {
    const prevRanks = previousRanksRef.current
    
    // Update leaderboard with rank change info
    const enrichedLeaderboard = newLeaderboard.map(entry => ({
      ...entry,
      previousRank: prevRanks[entry.username] || null,
      rankChange: prevRanks[entry.username] 
        ? prevRanks[entry.username] - entry.rank 
        : 0
    }))
    
    // Store current ranks for next comparison
    const nextRanks = {}
    newLeaderboard.forEach(entry => {
      nextRanks[entry.username] = entry.rank
    })
    previousRanksRef.current = nextRanks
    
    setLeaderboard(enrichedLeaderboard)
  }, [])

  const updateUsers = useCallback((users) => {
    setConnectedUsers(users)
  }, [])

  const showNotification = useCallback((message, type = 'info') => {
    // Clear any existing timer to prevent premature clearing
    if (notificationTimerRef.current) {
      clearTimeout(notificationTimerRef.current)
    }
    setNotification({ message, type })
    notificationTimerRef.current = setTimeout(() => {
      setNotification(null)
      notificationTimerRef.current = null
    }, 3000)
  }, [])

  const resetGame = useCallback(() => {
    setSessionCode(null)
    setStatus('idle')
    setAthletes([])
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
    previousRanksRef.current = {}
  }, [])
  
  const clearDisambiguation = useCallback(() => {
    setRequiresHint(false)
    setPendingSubmission(null)
    setError(null)
  }, [])

  // Socket action functions — use socketRef populated by useSocket
  const startGame = useCallback(() => {
    if (socketRef.current && sessionCode) {
      socketRef.current.emit('start_game', { code: sessionCode, username: usernameRef.current })
    }
  }, [sessionCode])

  const submitAthlete = useCallback((athleteName, sport, hint = null, sportLabel = null) => {
    if (socketRef.current && sessionCode && usernameRef.current) {
      setIsSubmitting(true)
      setError(null)
      
      // Store for potential resubmission with hint (include label for display)
      setPendingSubmission({ name: athleteName, sport, sportLabel: sportLabel || sport })
      
      const payload = {
        session_code: sessionCode,
        athlete_name: athleteName,
        sport,
        username: usernameRef.current,
      }
      
      if (hint) {
        payload.hint = hint
      }
      
      socketRef.current.emit('submit_athlete', payload)
    }
  }, [sessionCode])

  const pauseGame = useCallback(() => {
    if (socketRef.current && sessionCode) {
      socketRef.current.emit('pause_game', { code: sessionCode, username: usernameRef.current })
    }
  }, [sessionCode])

  const resumeGame = useCallback(() => {
    if (socketRef.current && sessionCode) {
      socketRef.current.emit('resume_game', { code: sessionCode, username: usernameRef.current })
    }
  }, [sessionCode])

  const endGameEarly = useCallback(() => {
    if (socketRef.current && sessionCode) {
      socketRef.current.emit('end_game_early', { code: sessionCode, username: usernameRef.current })
    }
  }, [sessionCode])

  const removePlayer = useCallback((targetUsername) => {
    if (socketRef.current && sessionCode) {
      socketRef.current.emit('remove_player', { code: sessionCode, username: usernameRef.current, target_username: targetUsername })
    }
  }, [sessionCode])

  const value = {
    sessionCode, setSessionCode,
    username, setUsername,
    status, setStatus,
    athletes, setAthletes, addAthlete,
    count,
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
    isHost, setIsHost,
    hostUsername, setHostUsername,
    leaderboard, updateLeaderboard,
    rejectedSubmissions, setRejectedSubmissions,
    isPaused, setIsPaused,
    // Socket actions — populated by useSocket, callable from any component
    socketRef,
    startGame, submitAthlete, pauseGame, resumeGame, endGameEarly, removePlayer,
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
