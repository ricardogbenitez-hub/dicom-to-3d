import { useEffect, useRef, useState } from 'react'
import { wsUrl } from '../api.js'

const STAGE_LABELS = {
  loading: 'Loading DICOM files',
  preprocessing: 'Preprocessing volume',
  segmenting: 'Segmenting anatomy',
  mesh: 'Building mesh',
  completed: 'Complete',
  failed: 'Failed',
  error: 'Error',
}

export default function ProcessingScreen({ dark, jobId, onDone, onError }) {
  const [messages, setMessages] = useState([])
  const [percent, setPercent] = useState(0)
  const [stage, setStage] = useState('pending')
  const [errMsg, setErrMsg] = useState(null)
  const wsRef = useRef(null)
  const logRef = useRef(null)
  // completedRef: avoids stale-closure bug in ws.onclose
  const completedRef = useRef(false)

  const card = dark ? '#111d30' : '#ffffff'
  const border = dark ? '#1e3355' : '#c8d6e8'
  const text = dark ? '#ddeaf8' : '#152033'
  const sub = dark ? '#8aaacb' : '#4d6a8a'

  useEffect(() => {
    if (!jobId) return
    completedRef.current = false
    // cleanedUp is local to this effect instance — immune to StrictMode's
    // double-mount because each closure gets its own independent variable
    let cleanedUp = false
    const startTime = Date.now()

    const url = wsUrl(jobId)
    const ws = new WebSocket(url)
    wsRef.current = ws

    ws.onopen = () => {
      setMessages([{ stage: 'connecting', message: `Connected — job ${jobId}`, active: false, done: false }])
    }

    ws.onmessage = (evt) => {
      try {
        const msg = JSON.parse(evt.data)
        const { stage: s, percent: p, message, metrics, error } = msg

        setStage(s)
        if (p !== undefined) setPercent(p)

        const isFailed = s === 'failed' || s === 'error'
        const isDone = s === 'completed'

        setMessages(prev => {
          const updated = prev.map(m => ({ ...m, active: false }))
          if (isDone) {
            updated.push({ stage: s, message: 'Pipeline complete', done: true, active: false })
            return updated
          }
          if (isFailed) {
            updated.push({ stage: s, message: error || message || 'Pipeline failed', done: false, active: false, isError: true })
            return updated
          }
          updated.push({ stage: s, message: message || STAGE_LABELS[s] || s, done: false, active: true })
          return updated
        })

        if (isDone) {
          completedRef.current = true
          const elapsed = ((Date.now() - startTime) / 1000).toFixed(1)
          setTimeout(() => onDone({ ...metrics, processing_time_s: parseFloat(elapsed) }), 800)
        }
        if (isFailed) {
          setErrMsg(error || message || 'Pipeline failed')
        }
      } catch (_) {}
    }

    ws.onerror = () => {
      if (!cleanedUp && !completedRef.current) {
        setErrMsg('WebSocket connection failed — is the backend running on port 8000?')
        setStage('error')
      }
    }

    ws.onclose = (evt) => {
      // cleanedUp = we closed it ourselves (StrictMode teardown or unmount) → ignore
      if (cleanedUp) return
      // code 1000 = normal server close after job completion
      if (!completedRef.current && evt.code !== 1000) {
        setErrMsg(`WebSocket closed unexpectedly (code ${evt.code})`)
        setStage('error')
      }
    }

    return () => {
      cleanedUp = true
      ws.close()
    }
  }, [jobId])

  useEffect(() => {
    if (logRef.current) {
      logRef.current.scrollTop = logRef.current.scrollHeight
    }
  }, [messages])

  const stageColor = (m) => {
    if (m.isError) return '#ef4444'
    if (m.done) return '#22c98a'
    if (m.active) return '#4d82bc'
    return sub
  }

  const stageIcon = (m) => {
    if (m.isError) return '✗'
    if (m.done) return '✓'
    if (m.active) return '●'
    return '○'
  }

  if (errMsg) {
    return (
      <div style={{ maxWidth: 560, margin: '0 auto' }}>
        <div style={{ backgroundColor: dark ? '#1a1020' : '#fef2f2', border: '1px solid #fca5a5', borderRadius: 12, padding: 28, textAlign: 'center' }}>
          <div style={{ fontSize: 36, marginBottom: 12 }}>⚠</div>
          <h3 style={{ fontWeight: 600, color: '#991b1b', marginBottom: 8 }}>Pipeline Failed</h3>
          <p style={{ fontSize: 13, color: dark ? '#fca5a5' : '#991b1b', marginBottom: 20 }}>{errMsg}</p>
          <button
            onClick={onError}
            style={{
              padding: '10px 24px',
              backgroundColor: '#4d82bc',
              color: '#fff',
              border: 'none',
              borderRadius: 8,
              fontWeight: 600,
              cursor: 'pointer',
            }}
          >
            Try Again
          </button>
        </div>
      </div>
    )
  }

  return (
    <div style={{ maxWidth: 600, margin: '0 auto' }}>
      <h2 style={{ fontSize: 22, fontWeight: 600, marginBottom: 6, color: text }}>Processing</h2>
      <p style={{ fontSize: 14, color: sub, marginBottom: 24 }}>
        Running pipeline on job {jobId?.slice(0, 8)}…
      </p>

      {/* Progress bar */}
      <div
        style={{
          backgroundColor: card,
          border: `1px solid ${border}`,
          borderRadius: 12,
          padding: '20px 24px',
          marginBottom: 16,
        }}
      >
        <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 8 }}>
          <span style={{ fontSize: 14, fontWeight: 600, color: text }}>
            {STAGE_LABELS[stage] || stage}
          </span>
          <span style={{ fontSize: 14, fontWeight: 700, color: '#4d82bc' }}>{percent}%</span>
        </div>
        <div
          style={{
            height: 10,
            backgroundColor: dark ? '#1e3355' : '#e2ecf7',
            borderRadius: 5,
            overflow: 'hidden',
          }}
        >
          <div
            className={stage !== 'completed' ? 'progress-bar-animated' : ''}
            style={{
              height: '100%',
              width: `${percent}%`,
              backgroundColor: stage === 'completed' ? '#22c98a' : '#4d82bc',
              borderRadius: 5,
              transition: 'width 0.4s ease',
            }}
          />
        </div>
      </div>

      {/* Log */}
      <div
        ref={logRef}
        style={{
          backgroundColor: dark ? '#080f1c' : '#f8fafc',
          border: `1px solid ${border}`,
          borderRadius: 10,
          padding: '14px 16px',
          fontFamily: 'ui-monospace, Consolas, monospace',
          fontSize: 13,
          maxHeight: 220,
          overflowY: 'auto',
        }}
      >
        {messages.length === 0 ? (
          <span style={{ color: sub }}>Connecting to pipeline…</span>
        ) : (
          messages.map((m, i) => (
            <div key={i} style={{ display: 'flex', alignItems: 'flex-start', gap: 8, marginBottom: 5 }}>
              <span style={{ color: stageColor(m), fontWeight: 700, minWidth: 14, marginTop: 1 }}>
                {stageIcon(m)}
              </span>
              <span style={{ color: stageColor(m) }}>
                [{m.stage}] {m.message}
              </span>
            </div>
          ))
        )}
      </div>
    </div>
  )
}
