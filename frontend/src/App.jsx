import { useState } from 'react'
import NavBar from './components/NavBar.jsx'
import Stepper from './components/Stepper.jsx'
import UploadScreen from './screens/UploadScreen.jsx'
import ConfigureScreen from './screens/ConfigureScreen.jsx'
import ProcessingScreen from './screens/ProcessingScreen.jsx'
import ResultScreen from './screens/ResultScreen.jsx'

export default function App() {
  const [step, setStep] = useState('upload')
  const [uploadId, setUploadId] = useState(null)
  const [fileCount, setFileCount] = useState(0)
  const [jobId, setJobId] = useState(null)
  const [metrics, setMetrics] = useState(null)
  const [dicomMeta, setDicomMeta] = useState(null)
  const [dark, setDark] = useState(false)

  const reset = () => {
    setStep('upload')
    setUploadId(null)
    setFileCount(0)
    setJobId(null)
    setMetrics(null)
    setDicomMeta(null)
  }

  const stepIndex = { upload: 0, configure: 1, processing: 1, result: 2 }

  const bg = dark ? '#0b1220' : '#f0f4f9'
  const text = dark ? '#ddeaf8' : '#152033'

  return (
    <div style={{ minHeight: '100vh', backgroundColor: bg, color: text, transition: 'background-color 0.2s, color 0.2s' }}>
      <NavBar dark={dark} onToggleDark={() => setDark(!dark)} />
      <div style={{ maxWidth: 1100, margin: '0 auto', padding: '0 24px 40px' }}>
        <Stepper current={stepIndex[step]} dark={dark} />

        {step === 'upload' && (
          <UploadScreen
            dark={dark}
            onDone={(id, count, meta) => {
              setUploadId(id)
              setFileCount(count)
              setDicomMeta(meta)
              setStep('configure')
            }}
          />
        )}
        {step === 'configure' && (
          <ConfigureScreen
            dark={dark}
            uploadId={uploadId}
            fileCount={fileCount}
            dicomMeta={dicomMeta}
            onBack={() => setStep('upload')}
            onDone={(jid) => {
              setJobId(jid)
              setStep('processing')
            }}
          />
        )}
        {step === 'processing' && (
          <ProcessingScreen
            dark={dark}
            jobId={jobId}
            onDone={(m) => {
              setMetrics(m)
              setStep('result')
            }}
            onError={() => reset()}
          />
        )}
        {step === 'result' && (
          <ResultScreen
            dark={dark}
            jobId={jobId}
            metrics={metrics}
            onReset={reset}
          />
        )}
      </div>
    </div>
  )
}
