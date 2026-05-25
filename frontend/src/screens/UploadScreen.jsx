import { useState, useRef, useCallback } from 'react'
import { uploadDicoms } from '../api.js'
import Spinner from '../components/Spinner.jsx'

export default function UploadScreen({ dark, onDone }) {
  const [files, setFiles] = useState([])
  const [dragging, setDragging] = useState(false)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const inputRef = useRef()

  const card = dark ? '#111d30' : '#ffffff'
  const border = dark ? '#1e3355' : '#c8d6e8'
  const text = dark ? '#ddeaf8' : '#152033'
  const sub = dark ? '#8aaacb' : '#4d6a8a'
  const dragBg = dragging ? (dark ? '#162840' : '#e8f0f9') : card

  const addFiles = useCallback((incoming) => {
    const all = Array.from(incoming)
    setFiles(prev => {
      const existing = new Set(prev.map(f => f.name + f.size))
      const next = all.filter(f => !existing.has(f.name + f.size))
      return [...prev, ...next]
    })
  }, [])

  const onDrop = (e) => {
    e.preventDefault()
    setDragging(false)
    addFiles(e.dataTransfer.files)
  }

  const onInputChange = (e) => {
    addFiles(e.target.files)
    e.target.value = ''
  }

  const removeFile = (idx) => setFiles(prev => prev.filter((_, i) => i !== idx))

  const fmt = (bytes) => {
    if (bytes < 1024) return `${bytes} B`
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
    return `${(bytes / 1024 / 1024).toFixed(2)} MB`
  }

  const nonDcm = files.filter(f => !f.name.toLowerCase().endsWith('.dcm')).length
  const canContinue = files.length >= 10

  const handleUpload = async () => {
    setError(null)
    setLoading(true)
    try {
      const result = await uploadDicoms(files)
      onDone(result.upload_id, files.length)
    } catch (err) {
      setError(err?.response?.data?.detail || err.message || 'Upload failed')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div style={{ maxWidth: 680, margin: '0 auto' }}>
      <h2 style={{ fontSize: 22, fontWeight: 600, marginBottom: 6, color: text }}>Upload DICOM Files</h2>
      <p style={{ fontSize: 14, color: sub, marginBottom: 20 }}>
        Drop your .dcm files or click to browse. Minimum 10 files required.
      </p>

      {/* Drop zone */}
      <div
        onDragOver={(e) => { e.preventDefault(); setDragging(true) }}
        onDragLeave={() => setDragging(false)}
        onDrop={onDrop}
        onClick={() => inputRef.current?.click()}
        style={{
          backgroundColor: dragBg,
          border: `2px dashed ${dragging ? '#4d82bc' : border}`,
          borderRadius: 12,
          padding: '48px 24px',
          textAlign: 'center',
          cursor: 'pointer',
          transition: 'all 0.15s',
          marginBottom: 16,
        }}
      >
        <div style={{ fontSize: 40, marginBottom: 12 }}>📂</div>
        <p style={{ fontWeight: 600, color: text, marginBottom: 4 }}>
          Drag & drop DICOM files here
        </p>
        <p style={{ fontSize: 13, color: sub }}>or click to browse</p>
        <input
          ref={inputRef}
          type="file"
          multiple
          accept=".dcm"
          onChange={onInputChange}
          style={{ display: 'none' }}
        />
      </div>

      {/* File list */}
      {files.length > 0 && (
        <div
          style={{
            backgroundColor: card,
            border: `1px solid ${border}`,
            borderRadius: 10,
            marginBottom: 16,
            overflow: 'hidden',
          }}
        >
          <div
            style={{
              padding: '10px 16px',
              borderBottom: `1px solid ${border}`,
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
            }}
          >
            <span style={{ fontWeight: 600, fontSize: 14, color: text }}>
              {files.length} file{files.length !== 1 ? 's' : ''} selected
            </span>
            <button
              onClick={() => setFiles([])}
              style={{ fontSize: 12, color: sub, background: 'none', border: 'none', cursor: 'pointer' }}
            >
              Clear all
            </button>
          </div>
          <div style={{ maxHeight: 220, overflowY: 'auto' }}>
            {files.map((f, i) => (
              <div
                key={i}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  padding: '7px 16px',
                  borderBottom: i < files.length - 1 ? `1px solid ${border}` : 'none',
                  gap: 10,
                }}
              >
                <span style={{ fontSize: 13, color: text, flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                  {f.name}
                </span>
                <span style={{ fontSize: 12, color: sub, whiteSpace: 'nowrap' }}>{fmt(f.size)}</span>
                {!f.name.toLowerCase().endsWith('.dcm') && (
                  <span style={{ fontSize: 11, backgroundColor: '#fef3c7', color: '#92400e', borderRadius: 4, padding: '1px 5px' }}>
                    non-dcm
                  </span>
                )}
                <button
                  onClick={(e) => { e.stopPropagation(); removeFile(i) }}
                  style={{ color: sub, background: 'none', border: 'none', cursor: 'pointer', fontSize: 16, lineHeight: 1, padding: 0 }}
                >
                  ×
                </button>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Warnings */}
      {nonDcm > 0 && (
        <div style={{ backgroundColor: '#fef3c7', border: '1px solid #fcd34d', borderRadius: 8, padding: '8px 14px', marginBottom: 12, fontSize: 13, color: '#92400e' }}>
          ⚠ {nonDcm} file{nonDcm > 1 ? 's are' : ' is'} not .dcm — will be included but may cause errors
        </div>
      )}
      {files.length > 0 && files.length < 10 && (
        <div style={{ backgroundColor: dark ? '#1a1020' : '#fef2f2', border: '1px solid #fca5a5', borderRadius: 8, padding: '8px 14px', marginBottom: 12, fontSize: 13, color: '#991b1b' }}>
          Need at least 10 files ({10 - files.length} more needed)
        </div>
      )}

      {/* Error */}
      {error && (
        <div style={{ backgroundColor: dark ? '#1a1020' : '#fef2f2', border: '1px solid #fca5a5', borderRadius: 8, padding: '10px 14px', marginBottom: 12, fontSize: 13, color: '#991b1b' }}>
          Error: {error}
        </div>
      )}

      {/* Continue button */}
      <button
        onClick={handleUpload}
        disabled={!canContinue || loading}
        style={{
          width: '100%',
          padding: '13px',
          backgroundColor: canContinue && !loading ? '#4d82bc' : (dark ? '#1e3355' : '#c8d6e8'),
          color: canContinue && !loading ? '#fff' : sub,
          border: 'none',
          borderRadius: 10,
          fontWeight: 600,
          fontSize: 15,
          cursor: canContinue && !loading ? 'pointer' : 'not-allowed',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          gap: 8,
          transition: 'background-color 0.15s',
        }}
      >
        {loading ? <><Spinner size={20} color="#fff" /> Uploading…</> : `Continue → (${files.length} files)`}
      </button>
    </div>
  )
}
