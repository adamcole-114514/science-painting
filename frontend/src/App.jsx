import { useState, useEffect, useRef, useCallback } from 'react'

function generateId(prefix) {
  return prefix + '_' + Math.random().toString(36).substring(2, 10)
}

function App() {
  const [messages, setMessages] = useState([])
  const [inputText, setInputText] = useState('')
  const [showModal, setShowModal] = useState(false)
  const [userAge, setUserAge] = useState('')
  const [userGender, setUserGender] = useState('male')
  const [agentState, setAgentState] = useState('idle')
  const [canSend, setCanSend] = useState(false)
  const [isConnected, setIsConnected] = useState(false)
  const [cognitiveLevel, setCognitiveLevel] = useState(null)
  const [shouldPrint, setShouldPrint] = useState(null)
  const [currentMessageText, setCurrentMessageText] = useState('')
  const [sessionId, setSessionId] = useState(() => generateId('sess'))

  const messagesEndRef = useRef(null)
  const wsRef = useRef(null)
  const messageCounterRef = useRef(0)
  const streamAccumulatorRef = useRef('')

  useEffect(() => {
    connectWebSocket()
    return () => {
      if (wsRef.current) {
        wsRef.current.close()
      }
    }
  }, [])

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const connectWebSocket = () => {
    const websocket = new WebSocket('ws://localhost:8000/ws')

    websocket.onopen = () => {
      console.log('WebSocket connected')
      wsRef.current = websocket
      setIsConnected(true)
    }

    websocket.onmessage = (event) => {
      const data = JSON.parse(event.data)
      handleServerMessage(data)
    }

    websocket.onclose = () => {
      console.log('WebSocket disconnected')
      setIsConnected(false)
      wsRef.current = null
      setTimeout(connectWebSocket, 3000)
    }

    return websocket
  }

  const handleServerMessage = (data) => {
    console.log('[Backend JSON]', JSON.stringify(data, null, 2))
    if (data.payload && data.payload.state) {
      console.log('[Agent State]', data.payload.state)
    }
    
    // 安全检查 payload
    if (!data.payload) {
      console.error('[Error] 收到无效消息，缺少 payload')
      return
    }
    
    const { message_text, text_over, cognitive_level, should_print } = data.payload
    
    console.log('[Debug] message_text:', message_text)

    // 检测用户离开回复
    if (message_text === '[智能体]用户离开，对话结束') {
      console.log('[User Left] 收到用户离开消息，重置前端状态')
      setMessages([])
      setAgentState('idle')
      setCanSend(false)
      setCurrentMessageText('')
      setCognitiveLevel(null)
      setShouldPrint(null)
      setSessionId(generateId('sess'))
      return
    }

    if (cognitive_level) {
      setCognitiveLevel(cognitive_level)
    }
    if (should_print !== undefined && should_print !== null) {
      setShouldPrint(should_print)
    }

    if (text_over) {
      const fullText = message_text || streamAccumulatorRef.current
      streamAccumulatorRef.current = ''
      if (fullText) {
        setMessages(prev => [...prev, { type: 'agent', text: fullText }])
      }
      setCurrentMessageText('')
      setCanSend(true)
    } else if (message_text) {
      streamAccumulatorRef.current = message_text
      setCurrentMessageText(message_text)
      setCanSend(false)
    }
  }

  const sendWsMessage = useCallback((action, extra = {}) => {
    if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) return

    messageCounterRef.current += 1
    const messageId = generateId('msg')

    const payload = {
      has_person: agentState !== 'idle',
      age: userAge ? parseInt(userAge) : null,
      gender: userGender,
      message: extra.message || ''
    }

    wsRef.current.send(JSON.stringify({
      message_id: messageId,
      session_id: sessionId,
      timestamp: new Date().toISOString(),
      action: action,
      ...payload,
      ...extra
    }))
  }, [agentState, userAge, userGender, sessionId])

  const handleApproach = () => {
    setShowModal(true)
  }

  const submitUserInfo = () => {
    if (!userAge || !userGender) return
    setShowModal(false)

    if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) {
      connectWebSocket()
      setTimeout(() => {
        if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
          sendWsMessage('has_person_change', { has_person: true })
        }
      }, 500)
    } else {
      sendWsMessage('has_person_change', { has_person: true })
    }
  }

  const sendMessage = () => {
    if (!inputText.trim() || !canSend) return

    setMessages(prev => [...prev, { type: 'user', text: inputText }])
    sendWsMessage('has_person_change', {
      has_person: true,
      message: inputText
    })
    setInputText('')
    setCanSend(false)
  }

  const handleLeave = () => {
    console.log('===== [User Leave] 点击用户离开 =====')
    console.log('[User Leave] 当前 agentState:', agentState)
    console.log('[User Leave] WebSocket 状态:', wsRef.current?.readyState)
    console.log('[User Leave] WebSocket 是否存在:', !!wsRef.current)
    
    // 先发送离开消息，等后端回复后再重置
    sendWsMessage('has_person_change', { has_person: false })
    console.log('[User Leave] 已发送 has_person_change 消息')
    // 不在这里重置，等 handleServerMessage 收到后端回复后再重置
  }

  const getStatusText = () => {
    switch(agentState) {
      case 'idle': return '等待用户接近'
      case 'greeting': return '寒暄中'
      case 'icebreaking_question': return '破冰（主动提问）'
      case 'icebreaking_no_question': return '破冰（未主动提问）'
      case 'transition': return '引导提问'
      case 'qa': return '正式问答'
      case 'ending': return '结束对话'
      case 'waiting_for_draw': return '等待手绘回复'
      case 'chat': return '闲聊中'
      default: return agentState
    }
  }

  const getCognitiveText = () => {
    switch(cognitiveLevel) {
      case 'level_0': return '基础知识弱，不了解领域'
      case 'level_1': return '有基础知识，不了解领域'
      case 'level_2': return '了解领域，不了解当前问题'
      case 'level_3': return '精深于本领域'
      default: return '未评估'
    }
  }

  return (
    <div className="app-container">
      <div className="control-panel">
        <h2>环境控制面板</h2>

        <button
          className="btn btn-approach"
          onClick={handleApproach}
          disabled={agentState !== 'idle'}
        >
          用户接近
        </button>

        <button
          className="btn btn-leave"
          onClick={() => {
            console.log('===== [DEBUG] 用户离开按钮 onClick 触发 =====')
            console.log('[DEBUG] agentState:', agentState)
            console.log('[DEBUG] wsRef.current:', wsRef.current)
            console.log('[DEBUG] wsRef.current?.readyState:', wsRef.current?.readyState)
            handleLeave()
          }}
        >
          用户离开 (当前状态: {agentState})
        </button>

        <div className={`status-indicator status-${agentState === 'idle' ? 'idle' : 'active'}`}>
          状态: 智能体工作中
        </div>

        {cognitiveLevel && (
          <div className="cognitive-info">
            <strong>认知水平:</strong> {getCognitiveText()}
          </div>
        )}

        {shouldPrint !== null && (
          <div className={`print-info ${shouldPrint ? 'print-yes' : 'print-no'}`}>
            <strong>手绘需求:</strong> {shouldPrint ? '需要' : '不需要'}
          </div>
        )}

        <div style={{ fontSize: '12px', color: '#999', marginTop: '10px' }}>
          {isConnected ? 'WebSocket已连接' : 'WebSocket连接中...'}
        </div>
      </div>

      <div className="chat-container">
        <div className="chat-header">科普问答系统</div>

        <div className="chat-messages">
          {messages.map((msg, idx) => (
            <div key={idx} className={`message message-${msg.type}`}>
              {msg.text}
            </div>
          ))}
          {currentMessageText && (
            <div className="message message-agent streaming">
              {currentMessageText}
            </div>
          )}
          <div ref={messagesEndRef} />
        </div>

        <div className="chat-input-area">
          <input
            type="text"
            className="chat-input"
            value={inputText}
            onChange={(e) => setInputText(e.target.value)}
            onKeyPress={(e) => e.key === 'Enter' && sendMessage()}
            placeholder={canSend ? "输入您的问题..." : "等待智能体回复..."}
            disabled={!canSend}
          />
          <button
            className="send-btn"
            onClick={sendMessage}
            disabled={!canSend || !inputText.trim()}
          >
            发送
          </button>
        </div>
      </div>

      {showModal && (
        <div className="modal-overlay" onClick={() => setShowModal(false)}>
          <div className="modal" onClick={(e) => e.stopPropagation()}>
            <h3>用户信息</h3>
            <div className="form-group">
              <label>性别</label>
              <select value={userGender} onChange={(e) => setUserGender(e.target.value)}>
                <option value="male">男</option>
                <option value="female">女</option>
              </select>
            </div>
            <div className="form-group">
              <label>年龄</label>
              <input
                type="number"
                value={userAge}
                onChange={(e) => setUserAge(e.target.value)}
                placeholder="请输入年龄"
              />
            </div>
            <div className="modal-buttons">
              <button className="btn" onClick={() => setShowModal(false)}>取消</button>
              <button className="btn btn-approach" onClick={submitUserInfo}>确认</button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

export default App
