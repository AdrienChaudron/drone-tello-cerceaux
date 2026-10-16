import { STALE_MS } from './config.js'
import { useNow, useTelloMqtt } from './hooks/useTelloMqtt.js'
import Header from './components/Header.jsx'
import VideoPanel from './components/VideoPanel.jsx'
import DronePanel from './components/DronePanel.jsx'
import VisionPanel from './components/VisionPanel.jsx'
import LandButton from './components/LandButton.jsx'
import Drone3DPanel from './components/Drone3DPanel.jsx'
import ArchivePanel from './components/ArchivePanel.jsx'
import ErreurXPanel from './components/ErreurXPanel.jsx'

export default function App() {
  const { connected, fps, vision, status, lastSeen, publish, archive, erreurX } = useTelloMqtt()
  const now = useNow()
  const fresh = (t) => connected && now - t < STALE_MS // donnees du serveur Node (PC de controle)
  const freshVision = (t) => now - t < STALE_MS // vision : flux direct depuis le PC vision

  return (
    <div className="app">
      <Header connected={connected} visionOk={freshVision(lastSeen.state)} statusOk={fresh(lastSeen.status)} />
      <main className="layout">
        <div className="layout__left">
          <VideoPanel fps={fps} stale={!freshVision(lastSeen.view)} test={vision?.test} />
          <Drone3DPanel status={status} stale={!fresh(lastSeen.status)} />
        </div>
        <div className="layout__center">
          <ArchivePanel archive={archive} />
          <ErreurXPanel erreurX={erreurX} stale={!freshVision(lastSeen.state)} />
        </div>
        <aside className="layout__side">
          <DronePanel status={status} stale={!fresh(lastSeen.status)} />
          <VisionPanel vision={vision} stale={!freshVision(lastSeen.state)} />
          <LandButton connected={connected} publish={publish} />
        </aside>
      </main>
    </div>
  )
}
