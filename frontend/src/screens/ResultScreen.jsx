import { useEffect, useRef, useState } from 'react'
import * as THREE from 'three'
import { STLLoader } from 'three/examples/jsm/loaders/STLLoader.js'
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js'
import { downloadStl } from '../api.js'
import Spinner from '../components/Spinner.jsx'

function StlViewer({ jobId, dark }) {
  const mountRef = useRef(null)
  const [loading, setLoading] = useState(true)
  const [err, setErr] = useState(null)
  const [wireframe, setWireframe] = useState(false)
  const meshRef = useRef(null)
  const rendererRef = useRef(null)
  const autoRotateRef = useRef(true)
  const controlsRef = useRef(null)

  useEffect(() => {
    if (!mountRef.current) return
    const el = mountRef.current
    const w = el.clientWidth
    const h = el.clientHeight

    // Scene
    const scene = new THREE.Scene()
    scene.background = new THREE.Color('#060d1a')

    // Camera — 3/4 elevated view: slightly to the right and above the model
    const camera = new THREE.PerspectiveCamera(45, w / h, 0.1, 5000)
    camera.position.set(220, 160, 300)

    // Renderer
    const renderer = new THREE.WebGLRenderer({ antialias: true })
    renderer.setSize(w, h)
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2))
    el.appendChild(renderer.domElement)
    rendererRef.current = renderer

    // Lights
    scene.add(new THREE.AmbientLight(0xffffff, 0.6))
    const dir = new THREE.DirectionalLight(0xffffff, 0.9)
    dir.position.set(200, 300, 200)
    scene.add(dir)
    const dir2 = new THREE.DirectionalLight(0x8aafdf, 0.3)
    dir2.position.set(-200, -100, -200)
    scene.add(dir2)

    // Controls
    const controls = new OrbitControls(camera, renderer.domElement)
    controls.enableDamping = true
    controls.dampingFactor = 0.07
    controls.autoRotate = true
    controls.autoRotateSpeed = 0.6
    controlsRef.current = controls

    // Stop auto-rotate on first user interaction
    const stopAutoRotate = () => { autoRotateRef.current = false; controls.autoRotate = false }
    renderer.domElement.addEventListener('pointerdown', stopAutoRotate, { once: true })

    // Load STL
    const loader = new STLLoader()
    downloadStl(jobId)
      .then(blob => {
        const url = URL.createObjectURL(blob)
        loader.load(url, (geometry) => {
          URL.revokeObjectURL(url)
          geometry.computeVertexNormals()
          // reorient_for_printing sets Z=up (print-bed convention); Three.js uses Y=up.
          geometry.rotateX(-Math.PI / 2)
          geometry.center()

          // Scale to fit
          geometry.computeBoundingBox()
          const box = geometry.boundingBox
          const size = new THREE.Vector3()
          box.getSize(size)
          const maxDim = Math.max(size.x, size.y, size.z)
          const scale = 260 / maxDim
          geometry.scale(scale, scale, scale)

          const material = new THREE.MeshPhongMaterial({
            color: new THREE.Color('#8faabf'),
            specular: new THREE.Color('#2a4a6a'),
            shininess: 40,
            side: THREE.DoubleSide,
          })
          const mesh = new THREE.Mesh(geometry, material)
          scene.add(mesh)
          meshRef.current = mesh

          // Position camera
          camera.position.set(0, 0, 400)
          controls.update()
          setLoading(false)
        },
        undefined,
        (e) => { setErr('Failed to parse STL'); setLoading(false) })
      })
      .catch(() => { setErr('Failed to download STL'); setLoading(false) })

    // Animate
    let animId
    const animate = () => {
      animId = requestAnimationFrame(animate)
      controls.update()
      renderer.render(scene, camera)
    }
    animate()

    // Resize
    const onResize = () => {
      const nw = el.clientWidth
      const nh = el.clientHeight
      camera.aspect = nw / nh
      camera.updateProjectionMatrix()
      renderer.setSize(nw, nh)
    }
    window.addEventListener('resize', onResize)

    return () => {
      cancelAnimationFrame(animId)
      window.removeEventListener('resize', onResize)
      renderer.dispose()
      if (el.contains(renderer.domElement)) el.removeChild(renderer.domElement)
    }
  }, [jobId])

  // Toggle wireframe
  useEffect(() => {
    if (meshRef.current) {
      meshRef.current.material.wireframe = wireframe
    }
  }, [wireframe])

  return (
    <div style={{ position: 'relative', width: '100%', height: '100%', borderRadius: 12, overflow: 'hidden', backgroundColor: '#060d1a' }}>
      <div ref={mountRef} style={{ width: '100%', height: '100%' }} />
      {loading && (
        <div style={{ position: 'absolute', inset: 0, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: 12, backgroundColor: '#060d1a' }}>
          <Spinner size={40} color="#4d82bc" />
          <span style={{ fontSize: 13, color: '#8aaacb' }}>Loading 3D model…</span>
        </div>
      )}
      {err && (
        <div style={{ position: 'absolute', inset: 0, display: 'flex', alignItems: 'center', justifyContent: 'center', backgroundColor: '#060d1a' }}>
          <span style={{ fontSize: 13, color: '#ef4444' }}>{err}</span>
        </div>
      )}
      {!loading && !err && (
        <button
          onClick={() => setWireframe(w => !w)}
          style={{
            position: 'absolute',
            top: 12,
            right: 12,
            padding: '5px 12px',
            backgroundColor: 'rgba(0,0,0,0.5)',
            color: '#ddeaf8',
            border: '1px solid #1e3355',
            borderRadius: 6,
            fontSize: 12,
            cursor: 'pointer',
          }}
        >
          {wireframe ? 'Solid' : 'Wireframe'}
        </button>
      )}
    </div>
  )
}

function MetricCard({ label, value, unit, ok, dark }) {
  const card = dark ? '#111d30' : '#ffffff'
  const border = dark ? '#1e3355' : '#c8d6e8'
  const text = dark ? '#ddeaf8' : '#152033'
  const sub = dark ? '#8aaacb' : '#4d6a8a'

  return (
    <div style={{ backgroundColor: card, border: `1px solid ${border}`, borderRadius: 10, padding: '12px 16px' }}>
      <div style={{ fontSize: 11, color: sub, marginBottom: 4, textTransform: 'uppercase', letterSpacing: '0.05em' }}>{label}</div>
      <div style={{ fontSize: 18, fontWeight: 700, color: ok === true ? '#22c98a' : ok === false ? '#ef4444' : text }}>
        {value !== null && value !== undefined ? (
          <>
            {typeof value === 'number' ? value.toLocaleString() : String(value)}
            {unit && <span style={{ fontSize: 13, fontWeight: 400, color: sub, marginLeft: 3 }}>{unit}</span>}
          </>
        ) : '—'}
      </div>
    </div>
  )
}

export default function ResultScreen({ dark, jobId, metrics, onReset }) {
  const border = dark ? '#1e3355' : '#c8d6e8'
  const text = dark ? '#ddeaf8' : '#152033'
  const sub = dark ? '#8aaacb' : '#4d6a8a'

  const handleDownload = async () => {
    try {
      const blob = await downloadStl(jobId)
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `dicomto3d_${jobId?.slice(0, 8)}.stl`
      document.body.appendChild(a)
      a.click()
      document.body.removeChild(a)
      URL.revokeObjectURL(url)
    } catch (e) {
      alert('Download failed: ' + e.message)
    }
  }

  const bbox = metrics?.bounding_box_mm
  const params = metrics?.params_used

  return (
    <div>
      <h2 style={{ fontSize: 22, fontWeight: 600, marginBottom: 6, color: text }}>Result</h2>
      <p style={{ fontSize: 14, color: sub, marginBottom: 20 }}>Your 3D model is ready.</p>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 340px', gap: 24, alignItems: 'start' }}>
        {/* Three.js viewer */}
        <div style={{ height: 460, borderRadius: 12, overflow: 'hidden', border: `1px solid ${border}` }}>
          <StlViewer jobId={jobId} dark={dark} />
        </div>

        {/* Metrics + buttons */}
        <div>
          {/* Metric cards */}
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10, marginBottom: 16 }}>
            <MetricCard
              dark={dark}
              label="Watertight"
              value={metrics?.is_watertight ? '✓ Yes' : '✗ No'}
              ok={metrics?.is_watertight}
            />
            <MetricCard
              dark={dark}
              label="Faces"
              value={metrics?.face_count}
            />
            <MetricCard
              dark={dark}
              label="Volume"
              value={metrics?.volume_cm3 != null ? parseFloat(metrics.volume_cm3).toFixed(1) : null}
              unit="cm³"
            />
            <MetricCard
              dark={dark}
              label="Time"
              value={metrics?.processing_time_s != null ? parseFloat(metrics.processing_time_s).toFixed(1) : null}
              unit="s"
            />
          </div>

          {/* Bounding box — bbox is [[xmin,ymin,zmin],[xmax,ymax,zmax]] */}
          {bbox && Array.isArray(bbox) && bbox.length === 2 && (
            <div
              style={{
                backgroundColor: dark ? '#111d30' : '#ffffff',
                border: `1px solid ${border}`,
                borderRadius: 10,
                padding: '12px 16px',
                marginBottom: 12,
              }}
            >
              <div style={{ fontSize: 11, color: sub, textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: 8 }}>Bounding Box</div>
              <div style={{ display: 'flex', gap: 16 }}>
                {['X', 'Y', 'Z'].map((ax, i) => {
                  const size = bbox[1][i] - bbox[0][i]
                  return (
                    <div key={ax}>
                      <div style={{ fontSize: 10, color: sub, textTransform: 'uppercase' }}>{ax}</div>
                      <div style={{ fontSize: 15, fontWeight: 600, color: text }}>
                        {Math.round(size)}
                        <span style={{ fontSize: 11, color: sub, marginLeft: 2 }}>mm</span>
                      </div>
                    </div>
                  )
                })}
              </div>
            </div>
          )}

          {/* Params used */}
          {params && (
            <div
              style={{
                backgroundColor: dark ? '#111d30' : '#ffffff',
                border: `1px solid ${border}`,
                borderRadius: 10,
                padding: '12px 16px',
                marginBottom: 16,
                fontSize: 12,
              }}
            >
              <div style={{ fontSize: 11, color: sub, textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: 8 }}>Parameters Used</div>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '4px 12px' }}>
                {Object.entries(params).filter(([k, v]) => v !== null && v !== undefined).map(([k, v]) => (
                  <div key={k} style={{ display: 'flex', justifyContent: 'space-between' }}>
                    <span style={{ color: sub }}>{k}</span>
                    <span style={{ color: text, fontWeight: 500 }}>{String(v)}</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Buttons */}
          <button
            onClick={handleDownload}
            style={{
              width: '100%',
              padding: '13px',
              backgroundColor: '#4d82bc',
              color: '#fff',
              border: 'none',
              borderRadius: 10,
              fontWeight: 600,
              fontSize: 15,
              cursor: 'pointer',
              marginBottom: 10,
            }}
          >
            ⬇ Download STL
          </button>
          <button
            onClick={onReset}
            style={{
              width: '100%',
              padding: '12px',
              backgroundColor: 'transparent',
              color: dark ? '#ddeaf8' : '#152033',
              border: '1.5px solid #6a8fae',
              borderRadius: 10,
              fontWeight: 600,
              fontSize: 15,
              cursor: 'pointer',
            }}
          >
            + New Conversion
          </button>
        </div>
      </div>
    </div>
  )
}
