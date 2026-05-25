const STEPS = ['Upload', 'Configure', 'Result']

export default function Stepper({ current, dark }) {
  const lineColor = dark ? '#1e3355' : '#c8d6e8'
  const doneColor = '#4d82bc'
  const pendingText = dark ? '#4a6a8a' : '#9fb8d0'
  const activeText = dark ? '#ddeaf8' : '#152033'

  return (
    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '28px 0 20px', gap: 0 }}>
      {STEPS.map((label, i) => {
        const done = i < current
        const active = i === current
        const circleColor = done || active ? doneColor : (dark ? '#1e3355' : '#c8d6e8')
        const circleBorder = done || active ? doneColor : (dark ? '#1e3355' : '#c8d6e8')
        const circleText = done || active ? '#fff' : pendingText
        const labelColor = active ? doneColor : (done ? (dark ? '#8aaacb' : '#4d6a8a') : pendingText)

        return (
          <div key={label} style={{ display: 'flex', alignItems: 'center' }}>
            <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 6 }}>
              <div
                style={{
                  width: 32,
                  height: 32,
                  borderRadius: '50%',
                  backgroundColor: circleColor,
                  border: `2px solid ${circleBorder}`,
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  fontWeight: 700,
                  fontSize: 14,
                  color: circleText,
                  transition: 'all 0.2s',
                }}
              >
                {done ? '✓' : i + 1}
              </div>
              <span style={{ fontSize: 12, fontWeight: active ? 600 : 400, color: labelColor, transition: 'color 0.2s' }}>
                {label}
              </span>
            </div>
            {i < STEPS.length - 1 && (
              <div
                style={{
                  width: 80,
                  height: 2,
                  backgroundColor: i < current ? doneColor : lineColor,
                  margin: '0 4px',
                  marginBottom: 20,
                  transition: 'background-color 0.2s',
                }}
              />
            )}
          </div>
        )
      })}
    </div>
  )
}
