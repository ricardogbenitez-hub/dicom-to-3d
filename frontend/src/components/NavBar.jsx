export default function NavBar({ dark, onToggleDark }) {
  const navBg = dark ? '#111d30' : '#ffffff'
  const border = dark ? '#1e3355' : '#c8d6e8'
  const text = dark ? '#ddeaf8' : '#152033'
  const sub = dark ? '#8aaacb' : '#4d6a8a'

  return (
    <nav
      style={{
        backgroundColor: navBg,
        borderBottom: `1px solid ${border}`,
        padding: '0 24px',
        height: 56,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        position: 'sticky',
        top: 0,
        zIndex: 100,
      }}
    >
      <span style={{ fontWeight: 700, fontSize: 20, color: '#4d82bc', letterSpacing: '-0.5px' }}>
        Dicomto3D
      </span>

      <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
        <span style={{ fontSize: 13, color: sub, display: 'none' }} className="credit-text">
          built and designed by Ricardo Garza Benítez
        </span>
        <span
          style={{
            fontSize: 12,
            color: sub,
            display: 'block',
          }}
        >
          built and designed by Ricardo Garza Benítez
        </span>
        <button
          onClick={onToggleDark}
          aria-label="Toggle dark mode"
          style={{
            background: 'none',
            border: `1.5px solid ${border}`,
            borderRadius: 8,
            padding: '5px 10px',
            cursor: 'pointer',
            color: text,
            fontSize: 16,
            lineHeight: 1,
            display: 'flex',
            alignItems: 'center',
          }}
        >
          {dark ? '☀' : '🌙'}
        </button>
      </div>
    </nav>
  )
}
