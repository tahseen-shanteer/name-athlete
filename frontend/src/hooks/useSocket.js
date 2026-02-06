import { useEffect, useRef } from 'react'
import { io } from 'socket.io-client'
import { useGame } from '../context/GameContext'

const BACKEND_URL = import.meta.env.VITE_BACKEND_URL || 'http://localhost:8000'

export const useSocket = () => {
  const socketRef = useRef(null)
  const {
    sessionCode,
    username,
    setStatus,
    setAthletes,
    setCount,
    addAthlete,
    setTimeRemaining,
    setEndsAt,
    setError,
    setIsSubmitting,
    updateUsers,
    setYourSubmissions,
    showNotification,
    setRequiresHint,
    setPendingSubmission,
    setIsHost,
    setHostUsername,
    updateLeaderboard,
    setRejectedSubmissions,
    setRecentSubmissions,
    setIsPaused,
    resetGame,
  } = useGame()

  useEffect(() => {
    if (!sessionCode || !username) return

    // Create socket connection
    const socket = io(BACKEND_URL, {
      transports: ['websocket', 'polling'],
      reconnection: true,
      reconnectionAttempts: 10,
      reconnectionDelay: 1000,
      reconnectionDelayMax: 5000,
    })

    socketRef.current = socket

    // Connection events
    socket.on('connect', () => {
      console.log('Connected to server')
      socket.emit('join_session', { code: sessionCode, username })
    })

    socket.on('disconnect', () => {
      console.log('Disconnected from server')
      showNotification('Connection lost. Reconnecting...', 'warning')
    })

    // Session events
    socket.on('session_joined', (data) => {
      console.log('Session joined:', data)
      setError(null)  // Clear any stale errors from reconnection
      setStatus(data.status)
      const athleteList = data.athletes || []
      setAthletes(athleteList)
      setCount(data.count || 0)
      // Rebuild recent submissions from server data so they persist across reconnects
      // Athletes are ordered chronologically; take the last 10 reversed (most recent first)
      setRecentSubmissions(athleteList.slice(-10).reverse())
      updateUsers(data.users || [])
      setYourSubmissions(data.your_submissions || 0)
      setIsHost(data.is_host || false)
      setHostUsername(data.host_username || null)
      
      // Set initial leaderboard
      if (data.leaderboard) {
        updateLeaderboard(data.leaderboard)
      }

      // Set pause state from server
      if (data.is_paused) {
        setIsPaused(true)
        if (data.time_remaining_at_pause != null) {
          setTimeRemaining(data.time_remaining_at_pause)
        }
      } else {
        setIsPaused(false)
      }

      if (data.ends_at) {
        setEndsAt(data.ends_at)
        const remaining = Math.floor((new Date(data.ends_at) - new Date()) / 1000)
        setTimeRemaining(Math.max(0, remaining))
      }

      if (data.reconnected) {
        showNotification("You're back in the game!", 'success')
      } else {
        showNotification(`Joined session ${sessionCode}`, 'success')
      }
    })

    socket.on('user_joined', (data) => {
      showNotification(`${data.username} joined${data.reconnected ? ' (reconnected)' : ''}`, 'info')
      // Update user list with full data from server
      if (data.users) {
        updateUsers(data.users)
      }
    })

    socket.on('user_left', (data) => {
      showNotification(`${data.username} disconnected`, 'info')
      // Update user list with full data from server
      if (data.users) {
        updateUsers(data.users)
      }
    })

    // Game events
    socket.on('game_started', (data) => {
      console.log('Game started:', data)
      setError(null)  // Clear any stale errors
      setStatus('active')
      setEndsAt(data.ends_at)
      const remaining = Math.floor((new Date(data.ends_at) - new Date()) / 1000)
      setTimeRemaining(Math.max(0, remaining))
      showNotification('Game started! Start submitting athletes!', 'success')
    })

    socket.on('athlete_added', (data) => {
      console.log('Athlete added:', data)
      addAthlete(data.athlete)
      setIsSubmitting(false)
      
      if (data.athlete.submitted_by === username) {
        // Use canonical name if available for display
        const displayName = data.athlete.canonical_name || data.athlete.name
        showNotification(`${displayName} added!`, 'success')
      }
    })

    // Leaderboard update event
    socket.on('leaderboard_update', (data) => {
      console.log('Leaderboard update:', data)
      if (data.leaderboard) {
        updateLeaderboard(data.leaderboard)
      }
    })

    socket.on('submission_error', (data) => {
      console.log('Submission error:', data)
      setIsSubmitting(false)
      setError(data.message || 'Submission failed')
      
      // Check if disambiguation is required
      if (data.requires_hint) {
        setRequiresHint(true)
        showNotification('Multiple athletes found - please add a hint', 'warning')
      } else {
        showNotification(data.message || 'Submission failed', 'error')
      }
    })

    socket.on('timer_tick', (data) => {
      setTimeRemaining(data.remaining)
    })

    socket.on('game_ended', (data) => {
      console.log('Game ended:', data)
      setStatus('completed')
      setTimeRemaining(0)
      
      // Store final leaderboard and rejected submissions
      if (data.leaderboard) {
        updateLeaderboard(data.leaderboard)
      }
      if (data.rejected_submissions) {
        setRejectedSubmissions(data.rejected_submissions)
      }
      
      showNotification(
        `Game over! Final count: ${data.final_count}/2000${data.goal_reached ? ' - GOAL REACHED!' : ''}`,
        data.goal_reached ? 'success' : 'info'
      )
    })

    socket.on('error', (data) => {
      console.error('Socket error:', data)
      setError(data.message || 'An error occurred')
      showNotification(data.message || 'An error occurred', 'error')
    })

    // Host control events
    socket.on('game_paused', (data) => {
      console.log('Game paused:', data)
      setIsPaused(true)
      setTimeRemaining(data.time_remaining)
      showNotification('Game paused by host', 'warning')
    })

    socket.on('game_resumed', (data) => {
      console.log('Game resumed:', data)
      setIsPaused(false)
      setEndsAt(data.ends_at)
      const remaining = Math.floor((new Date(data.ends_at) - new Date()) / 1000)
      setTimeRemaining(Math.max(0, remaining))
      showNotification('Game resumed!', 'success')
    })

    socket.on('player_removed', (data) => {
      console.log('Player removed:', data)
      showNotification(data.message || 'You have been removed from the session.', 'error')
      // Reset game state - kicked back to idle
      resetGame()
    })

    socket.on('user_removed', (data) => {
      console.log('User removed:', data)
      if (data.users) {
        updateUsers(data.users)
      }
      if (data.leaderboard) {
        updateLeaderboard(data.leaderboard)
      }
      showNotification(`${data.username} was removed from the session`, 'info')
    })

    return () => {
      socket.disconnect()
    }
    // Note: showNotification, setAthletes, etc. are stable functions from context
    // Only sessionCode and username changes should trigger reconnection
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sessionCode, username])

  const startGame = () => {
    if (socketRef.current && sessionCode) {
      // Include username so server can verify host
      socketRef.current.emit('start_game', { code: sessionCode, username })
    }
  }

  const submitAthlete = (athleteName, sport, hint = null, sportLabel = null) => {
    if (socketRef.current && sessionCode && username) {
      setIsSubmitting(true)
      setError(null)
      
      // Store for potential resubmission with hint (include label for display)
      setPendingSubmission({ name: athleteName, sport, sportLabel: sportLabel || sport })
      
      const payload = {
        session_code: sessionCode,
        athlete_name: athleteName,
        sport,
        username,
      }
      
      // Include hint if provided
      if (hint) {
        payload.hint = hint
      }
      
      socketRef.current.emit('submit_athlete', payload)
    }
  }

  const pauseGame = () => {
    if (socketRef.current && sessionCode) {
      socketRef.current.emit('pause_game', { code: sessionCode, username })
    }
  }

  const resumeGame = () => {
    if (socketRef.current && sessionCode) {
      socketRef.current.emit('resume_game', { code: sessionCode, username })
    }
  }

  const endGameEarly = () => {
    if (socketRef.current && sessionCode) {
      socketRef.current.emit('end_game_early', { code: sessionCode, username })
    }
  }

  const removePlayer = (targetUsername) => {
    if (socketRef.current && sessionCode) {
      socketRef.current.emit('remove_player', { code: sessionCode, username, target_username: targetUsername })
    }
  }

  return {
    startGame,
    submitAthlete,
    pauseGame,
    resumeGame,
    endGameEarly,
    removePlayer,
    isConnected: socketRef.current?.connected,
  }
}
