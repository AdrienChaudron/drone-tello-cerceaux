import { useEffect, useState } from 'react'
import Panel from './Panel.jsx'
import { VIDEO_URL } from '../config.js'

/**
 * Image annotee par le CNN (la meme que la fenetre OpenCV de vision_node), en MJPEG :
 * le navigateur affiche le flux tout seul dans une balise <img>. Si le PC vision ne repond pas
 * (vision_node arrete ou redemarre), on retente toutes les 3 s.
 */
export default function VideoPanel({ fps, stale, test }) {
  const [attempt, setAttempt] = useState(0)
  const [failed, setFailed] = useState(false)

  useEffect(() => {
    if (!failed) return undefined
    const t = setTimeout(() => {
      setFailed(false)
      setAttempt((a) => a + 1)
    }, 3000)
    return () => clearTimeout(t)
  }, [failed])

  return (
    <Panel title="Caméra · détection CNN" source="PC vision · /video.mjpeg" stale={stale} className="video">
      <div className="video__frame">
        {!failed && (
          <img
            key={attempt}
            src={`${VIDEO_URL}?n=${attempt}`}
            alt="Image du drone annotée par le CNN"
            onError={() => setFailed(true)}
          />
        )}
        {(failed || stale) && (
          <div className={failed ? 'video__empty' : 'video__overlay'}>
            {failed ? 'En attente du PC vision…' : 'Flux interrompu'}
          </div>
        )}
        <div className="video__badges">
          <span className="badge">{fps} i/s</span>
          {test && <span className="badge badge--warn">{test}</span>}
        </div>
      </div>
    </Panel>
  )
}
