import { useState } from 'react'
import { createJob } from '../api.js'
import Spinner from '../components/Spinner.jsx'

const STRUCTURES = [
  { id: 'bone', label: 'Bone' },
  { id: 'cortical_bone', label: 'Cortical' },
  { id: 'trabecular_bone', label: 'Trabecular' },
  { id: 'soft_tissue', label: 'Soft Tissue' },
]

const SLIDERS = [
  { key: 'threshold', label: 'HU Threshold', min: 100, max: 600, step: 1, unit: 'HU', tooltip: 'Foot/wrist: 200–250 · Spine/femur: 400' },
  { key: 'sigma', label: 'XY Sigma', min: 0.0, max: 3.0, step: 0.1, unit: '', tooltip: 'Gaussian blur in the XY plane' },
  { key: 'sigma_z', label: 'Z Sigma', min: 0.0, max: 4.0, step: 0.1, unit: '', tooltip: 'Use 2.0 for 3mm slice CT (bridges inter-slice gaps)' },
  { key: 'smooth', label: 'Smooth Iterations', min: 0, max: 10, step: 1, unit: 'iters', tooltip: 'Laplacian smoothing. Hard limit: 10' },
  { key: 'min_component_ratio', label: 'Min Component Ratio', min: 0.01, max: 0.20, step: 0.01, unit: '', tooltip: 'Filters small fragments. Use 0.05 for foot.' },
  { key: 'bridge', label: 'Bridge Gap', min: 0, max: 10, step: 1, unit: 'mm', tooltip: 'Fuses adjacent bones. Use 4 for foot.' },
  { key: 'max_bodies', label: 'Max Bodies', min: 0, max: 10, step: 1, unit: '', tooltip: '0 = off. 1 = keep only largest component.' },
]

const DEFAULTS = {
  structure: 'bone',
  threshold: 400,
  sigma: 0.5,
  sigma_z: 0.0,
  smooth: 5,
  min_component_ratio: 0.01,
  bridge: 0,
  max_bodies: 0,
  reorient: true,
  step_size: 1,
}

function Slider({ def, value, onChange, dark }) {
  const border = dark ? '#1e3355' : '#c8d6e8'
  const text = dark ? '#ddeaf8' : '#152033'
  const sub = dark ? '#8aaacb' : '#4d6a8a'
  const [tip, setTip] = useState(false)
  // Raw text while the user is typing in the number input
  const [inputText, setInputText] = useState(null)

  const isEditable = def.key === 'threshold'

  const handleSliderChange = (e) => {
    const v = def.step < 1 ? parseFloat(e.target.value) : parseInt(e.target.value)
    onChange(def.key, v)
    setInputText(null)
  }

  const handleNumberInput = (e) => {
    setInputText(e.target.value)
    const raw = e.target.value.trim()
    if (raw === '' || raw === '-') return
    const num = def.step < 1 ? parseFloat(raw) : parseInt(raw)
    if (!isNaN(num)) {
      const clamped = Math.min(def.max, Math.max(def.min, num))
      onChange(def.key, clamped)
    }
  }

  const handleNumberBlur = () => {
    setInputText(null)
  }

  const displayValue = typeof value === 'number'
    ? (def.step < 1 ? value.toFixed(2) : value)
    : value

  return (
    <div style={{ marginBottom: 18 }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 4 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          <label style={{ fontSize: 13, fontWeight: 500, color: text }}>{def.label}</label>
          {def.tooltip && (
            <span
              onMouseEnter={() => setTip(true)}
              onMouseLeave={() => setTip(false)}
              style={{ fontSize: 11, color: sub, cursor: 'help', position: 'relative' }}
            >
              ⓘ
              {tip && (
                <span style={{
                  position: 'absolute',
                  left: '100%',
                  top: -2,
                  marginLeft: 6,
                  backgroundColor: dark ? '#111d30' : '#152033',
                  color: '#fff',
                  fontSize: 11,
                  padding: '4px 8px',
                  borderRadius: 6,
                  whiteSpace: 'nowrap',
                  zIndex: 10,
                  pointerEvents: 'none',
                }}>
                  {def.tooltip}
                </span>
              )}
            </span>
          )}
        </div>

        {isEditable ? (
          <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
            <input
              type="number"
              min={def.min}
              max={def.max}
              step={def.step}
              value={inputText !== null ? inputText : value}
              onChange={handleNumberInput}
              onBlur={handleNumberBlur}
              style={{
                width: 68,
                padding: '3px 6px',
                borderRadius: 6,
                border: `1.5px solid ${border}`,
                backgroundColor: dark ? '#0b1220' : '#fff',
                color: '#4d82bc',
                fontSize: 13,
                fontWeight: 700,
                textAlign: 'right',
                outline: 'none',
              }}
            />
            {def.unit && <span style={{ fontSize: 12, color: sub }}>{def.unit}</span>}
          </div>
        ) : (
          <span style={{ fontSize: 13, fontWeight: 600, color: '#4d82bc', minWidth: 60, textAlign: 'right' }}>
            {displayValue}{def.unit ? ` ${def.unit}` : ''}
          </span>
        )}
      </div>
      <input
        type="range"
        min={def.min}
        max={def.max}
        step={def.step}
        value={value}
        onChange={handleSliderChange}
        style={{ width: '100%' }}
      />
      <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 11, color: sub, marginTop: 1 }}>
        <span>{def.min}{def.unit ? ` ${def.unit}` : ''}</span>
        <span>{def.max}{def.unit ? ` ${def.unit}` : ''}</span>
      </div>
    </div>
  )
}

export default function ConfigureScreen({ dark, uploadId, fileCount, onBack, onDone }) {
  const [params, setParams] = useState(DEFAULTS)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  const card = dark ? '#111d30' : '#ffffff'
  const border = dark ? '#1e3355' : '#c8d6e8'
  const text = dark ? '#ddeaf8' : '#152033'
  const sub = dark ? '#8aaacb' : '#4d6a8a'

  const set = (key, val) => setParams(prev => ({ ...prev, [key]: val }))

  const handleRun = async () => {
    setError(null)
    setLoading(true)
    try {
      const body = {
        upload_id: uploadId,
        structure: params.structure,
        threshold: params.threshold,
        sigma: params.sigma,
        sigma_z: params.sigma_z > 0 ? params.sigma_z : null,
        smooth: params.smooth,
        step_size: params.step_size,
        min_component_ratio: params.min_component_ratio,
        max_bodies: params.max_bodies > 0 ? params.max_bodies : null,
        reorient: params.reorient,
        bridge: params.bridge,
      }
      const result = await createJob(body)
      onDone(result.job_id)
    } catch (err) {
      setError(err?.response?.data?.detail || err.message || 'Failed to start job')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div style={{ display: 'grid', gridTemplateColumns: '1fr 340px', gap: 24, alignItems: 'start' }}>
      {/* Left column */}
      <div>
        <h2 style={{ fontSize: 22, fontWeight: 600, marginBottom: 6, color: text }}>Configure Pipeline</h2>
        <p style={{ fontSize: 14, color: sub, marginBottom: 20 }}>
          Adjust parameters for your anatomy type and scan resolution.
        </p>

        {/* Structure pills */}
        <div style={{ marginBottom: 24 }}>
          <label style={{ fontSize: 13, fontWeight: 500, color: text, display: 'block', marginBottom: 8 }}>
            Structure Type
          </label>
          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
            {STRUCTURES.map(s => (
              <button
                key={s.id}
                onClick={() => set('structure', s.id)}
                style={{
                  padding: '7px 16px',
                  borderRadius: 20,
                  border: `1.5px solid ${params.structure === s.id ? '#4d82bc' : border}`,
                  backgroundColor: params.structure === s.id ? '#4d82bc' : 'transparent',
                  color: params.structure === s.id ? '#fff' : text,
                  fontWeight: params.structure === s.id ? 600 : 400,
                  cursor: 'pointer',
                  fontSize: 13,
                  transition: 'all 0.15s',
                }}
              >
                {s.label}
              </button>
            ))}
          </div>
        </div>

        {/* Sliders */}
        <div
          style={{
            backgroundColor: card,
            border: `1px solid ${border}`,
            borderRadius: 12,
            padding: '20px 20px 4px',
            marginBottom: 20,
          }}
        >
          {SLIDERS.map(def => (
            <Slider key={def.key} def={def} value={params[def.key]} onChange={set} dark={dark} />
          ))}
        </div>

        {/* Checkboxes */}
        <div
          style={{
            backgroundColor: card,
            border: `1px solid ${border}`,
            borderRadius: 12,
            padding: '16px 20px',
            marginBottom: 20,
            display: 'flex',
            gap: 24,
            flexWrap: 'wrap',
          }}
        >
          <label style={{ display: 'flex', alignItems: 'center', gap: 8, cursor: 'pointer', fontSize: 13, color: text }}>
            <input
              type="checkbox"
              checked={params.reorient}
              onChange={(e) => set('reorient', e.target.checked)}
              style={{ accentColor: '#4d82bc', width: 16, height: 16 }}
            />
            Reorient for printing
          </label>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <span style={{ fontSize: 13, color: text }}>Step size:</span>
            {[1, 2].map(v => (
              <label key={v} style={{ display: 'flex', alignItems: 'center', gap: 4, cursor: 'pointer', fontSize: 13, color: text }}>
                <input
                  type="radio"
                  name="step_size"
                  value={v}
                  checked={params.step_size === v}
                  onChange={() => set('step_size', v)}
                  style={{ accentColor: '#4d82bc' }}
                />
                {v === 1 ? '1 (full res)' : '2 (half res, faster)'}
              </label>
            ))}
          </div>
        </div>

        {error && (
          <div style={{ backgroundColor: dark ? '#1a1020' : '#fef2f2', border: '1px solid #fca5a5', borderRadius: 8, padding: '10px 14px', marginBottom: 12, fontSize: 13, color: '#991b1b' }}>
            Error: {error}
          </div>
        )}

        {/* Action buttons */}
        <div style={{ display: 'flex', gap: 10 }}>
          <button
            onClick={onBack}
            disabled={loading}
            style={{
              padding: '12px 20px',
              borderRadius: 10,
              border: '1.5px solid #6a8fae',
              background: 'transparent',
              color: dark ? '#ddeaf8' : '#152033',
              fontWeight: 600,
              fontSize: 14,
              cursor: loading ? 'not-allowed' : 'pointer',
            }}
          >
            ← Back
          </button>
          <button
            onClick={handleRun}
            disabled={loading}
            style={{
              flex: 1,
              padding: '12px',
              backgroundColor: loading ? (dark ? '#1e3355' : '#c8d6e8') : '#4d82bc',
              color: loading ? sub : '#fff',
              border: 'none',
              borderRadius: 10,
              fontWeight: 600,
              fontSize: 14,
              cursor: loading ? 'not-allowed' : 'pointer',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              gap: 8,
            }}
          >
            {loading ? <><Spinner size={18} color="#fff" /> Starting…</> : 'Run Pipeline →'}
          </button>
        </div>
      </div>

      {/* Right column — Series Info */}
      <div
        style={{
          backgroundColor: card,
          border: `1px solid ${border}`,
          borderRadius: 12,
          padding: 20,
          position: 'sticky',
          top: 72,
        }}
      >
        <h3 style={{ fontSize: 15, fontWeight: 600, color: text, marginBottom: 16 }}>Series Info</h3>
        {[
          ['Upload ID', uploadId ? `${uploadId.slice(0, 8)}…` : '—'],
          ['Files', fileCount || '—'],
          ['Pixel Spacing', '—'],
          ['Slice Thickness', '—'],
          ['Modality', '—'],
        ].map(([label, val]) => (
          <div
            key={label}
            style={{
              display: 'flex',
              justifyContent: 'space-between',
              padding: '8px 0',
              borderBottom: `1px solid ${border}`,
              fontSize: 13,
            }}
          >
            <span style={{ color: sub }}>{label}</span>
            <span style={{ color: text, fontWeight: 500 }}>{val}</span>
          </div>
        ))}

        <div style={{ marginTop: 20 }}>
          <p style={{ fontSize: 12, color: sub, marginBottom: 8 }}>Current threshold</p>
          <div style={{ fontSize: 28, fontWeight: 700, color: '#4d82bc' }}>
            {params.threshold} <span style={{ fontSize: 14, fontWeight: 400, color: sub }}>HU</span>
          </div>
          <p style={{ fontSize: 11, color: sub, marginTop: 4 }}>
            {params.threshold >= 350 ? 'Cortical bone range' :
             params.threshold >= 200 ? 'Trabecular + cortical range' :
             'Full trabecular range'}
          </p>
        </div>
      </div>
    </div>
  )
}
