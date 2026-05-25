export default function Spinner({ size = 32, color = '#4d82bc' }) {
  return (
    <div
      style={{
        width: size,
        height: size,
        border: `3px solid ${color}33`,
        borderTop: `3px solid ${color}`,
        borderRadius: '50%',
        animation: 'spin 0.8s linear infinite',
        display: 'inline-block',
      }}
    >
      <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
    </div>
  )
}
