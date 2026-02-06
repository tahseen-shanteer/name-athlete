import React, { useState } from 'react'
import { useGame } from '../context/GameContext'
import { BACKEND_URL } from '../config'

export const CreateSession = ({ onCreated }) => {
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [password, setPassword] = useState('')
  const [hostUsername, setHostUsername] = useState('')

  const handleCreate = async (e) => {
    e.preventDefault()
    
    if (!password.trim()) {
      setError('Admin password is required')
      return
    }
    
    if (!hostUsername.trim()) {
      setError('Username is required')
      return
    }
    
    setLoading(true)
    setError(null)

    try {
      const response = await fetch(BACKEND_URL + '/api/session/create', { 
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          password: password.trim(),
          host_username: hostUsername.trim()
        })
      })
      
      if (response.status === 403) {
        throw new Error('Invalid admin password')
      }
      
      if (!response.ok) {
        const data = await response.json()
        throw new Error(data.detail || 'Failed to create session')
      }
      
      const data = await response.json()
      onCreated(data.code, hostUsername.trim())
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <form onSubmit={handleCreate} className="create-session">
      <div className="form-group">
        <input
          type="text"
          placeholder="Your Username"
          value={hostUsername}
          onChange={(e) => setHostUsername(e.target.value)}
          maxLength={20}
          required
        />
      </div>
      <div className="form-group">
        <input
          type="password"
          placeholder="Admin Password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          required
        />
      </div>
      <button type="submit" disabled={loading} className="btn btn-primary">
        {loading ? 'Creating...' : 'Create New Session'}
      </button>
      {error && <p className="error">{error}</p>}
    </form>
  )
}

export const JoinSession = ({ onJoin, initialCode = '' }) => {
  const [code, setCode] = useState(initialCode)
  const [username, setUsername] = useState('')
  const [error, setError] = useState(null)
  const { setUsername: setGameUsername, setSessionCode } = useGame()

  const handleJoin = (e) => {
    e.preventDefault()
    
    if (!code.trim() || !username.trim()) {
      setError('Please enter both session code and username')
      return
    }

    setGameUsername(username.trim())
    setSessionCode(code.trim().toUpperCase())
    onJoin()
  }

  return (
    <form onSubmit={handleJoin} className="join-session">
      <div className="form-group">
        <input
          type="text"
          placeholder="Session Code (e.g., ABC123)"
          value={code}
          onChange={(e) => setCode(e.target.value.toUpperCase())}
          maxLength={6}
          required
        />
      </div>
      <div className="form-group">
        <input
          type="text"
          placeholder="Your Username"
          value={username}
          onChange={(e) => setUsername(e.target.value)}
          maxLength={20}
          required
        />
      </div>
      <button type="submit" className="btn btn-primary">
        Join Session
      </button>
      {error && <p className="error">{error}</p>}
    </form>
  )
}
