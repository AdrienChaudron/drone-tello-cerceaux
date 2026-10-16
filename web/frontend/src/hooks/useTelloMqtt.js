import { useCallback, useEffect, useRef, useState } from 'react'
import { ARCHIVE_AXES, ARCHIVE_KEEP_S, API_URL, VISION_URL } from '../config.js'

// Base URL of your Express API server

/**
 * Initialise un buffer vide pour chaque axe surveille.
 */
const emptyArchive = () =>
  Object.fromEntries(
    ARCHIVE_AXES.map((a) => [a, { t: [], reference: [], command: [], measure: [] }])
  )

export function useTelloMqtt() {
  const [connected, setConnected] = useState(false)
  const [frameUrl, setFrameUrl] = useState(null)
  const [fps, setFps] = useState(0)
  const [vision, setVision] = useState(null)
  const [status, setStatus] = useState(null)
  const [lastSeen, setLastSeen] = useState({ view: 0, state: 0, status: 0 })

  const frameCount = useRef(0)
  const archive = useRef(emptyArchive())
  const eventSourceRef = useRef(null)

  useEffect(() => {
    // 1. Initialisation de la connexion SSE vers l'API Express
    const es = new EventSource(`${API_URL}/events`)
    eventSourceRef.current = es

    es.onopen = () => {
      console.log('[SSE] Connecté à l\'API Node.js')
      setConnected(true)
    }

    es.onerror = (err) => {
      console.warn('[SSE] Déconnexion / Erreur de flux :', err)
      setConnected(false)
    }

    es.onmessage = (event) => {
      const now = Date.now()
      try {
        const payload = JSON.parse(event.data)

        // Traitement de l'historique initial envoyé par Node (les 120 dernières secondes)
        if (payload.type === 'history' && Array.isArray(payload.data)) {
          const sorted = [...payload.data].sort((a, b) => (a.timestamp ?? 0) - (b.timestamp ?? 0))
          sorted.forEach((point) => {
            pushArchive(archive.current, point.axis, point)
          })
        }

        // Traitement d'un point télémétrie en temps réel
        else if (payload.type === 'live' && payload.data) {
          const pt = payload.data
          pushArchive(archive.current, pt.axis, pt)
        }

        // Traitement de l'état du drone (batterie, vol, etc.)
        else if (payload.type === 'status' && payload.data) {
          setStatus(payload.data)
          setLastSeen((s) => ({ ...s, status: now }))
        }

        // Traitement optionnel de l'état de la vision
        else if (payload.type === 'vision' && payload.data) {
          setVision(payload.data)
          setLastSeen((s) => ({ ...s, view: now }))
        }
      } catch (err) {
        console.warn('[SSE] Impossible de parser le message JSON', err)
      }
    }

    // Calculateur de FPS (si une source vidéo est diffusée)
    const timer = setInterval(() => {
      setFps(frameCount.current)
      frameCount.current = 0
    }, 1000)

    return () => {
      clearInterval(timer)
      es.close()
      setConnected(false)
    }
  }, [])

  // 2. Vision (PC vision) : etat de la vision en SSE, un message par image traitee, directement depuis
  //    vision_node.py (la video elle-meme est affichee en MJPEG par VideoPanel). Reconnexion automatique.
  useEffect(() => {
    const vs = new EventSource(`${VISION_URL}/events`)
    vs.onmessage = (event) => {
      try {
        setVision(JSON.parse(event.data))
        frameCount.current += 1 // un etat par image traitee : sert de compteur d'images/s
        const now = Date.now()
        setLastSeen((s) => ({ ...s, view: now, state: now }))
      } catch (err) {
        console.warn('[vision] message illisible', err)
      }
    }
    return () => vs.close()
  }, [])

  /**
   * Publication de commandes via l'API REST Express
   * Compatible avec les appels existants : publish('tello/commands', { x, y, z, yaw })
   * ou deadman switch.
   */
  const publish = useCallback(async (topic, obj) => {
    try {
      // Cas 1 : Deadman switch
      if (
        topic === 'tello/deadman' ||
        (obj?.x === -69 && obj?.y === -69 && obj?.z === -69 && obj?.yaw === -69)
      ) {
        const res = await fetch(`${API_URL}/api/deadman`, { method: 'POST' })
        return res.ok
      }

      // Cas 2 : Commande de pilotage normale
      if (topic === 'tello/commands' || (obj?.x !== undefined && obj?.y !== undefined)) {
        const res = await fetch(`${API_URL}/api/command`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            x: Number(obj.x ?? 0),
            y: Number(obj.y ?? 0),
            z: Number(obj.z ?? 0),
            yaw: Number(obj.yaw ?? 0),
          }),
        })
        return res.ok
      }

      // Fallback générique si d'autres routes sont ajoutées plus tard
      return false
    } catch (err) {
      console.error('[API] Échec de l\'envoi de la commande :', err)
      return false
    }
  }, [])

  return {
    connected,
    frameUrl,
    fps,
    vision,
    status,
    lastSeen,
    publish,
    archive,
  }
}

/** Ajoute un point à l'axe et purge ce qui dépasse ARCHIVE_KEEP_S secondes. */
function pushArchive(buffers, axis, d) {
  if (!axis) return
  const normAxis = axis.toUpperCase()
  const b = buffers[normAxis]
  if (!b) return

  var t = Number(d.timestamp ?? Date.now() / 1000)
  if (isNaN(t)) return;

  const len = b.t.length
  if (len > 0) {
    const lastT = b.t[len - 1]
    if (t <= lastT) {
      t = lastT + 0.001
    }
  }

  b.t.push(t)
  b.reference.push(Number(d.reference ?? d.axis_command_reference ?? NaN))
  b.command.push(Number(d.command ?? d.axis_corrected_command ?? NaN))
  b.measure.push(Number(d.measure ?? NaN))

  let drop = 0
  while (drop < b.t.length && b.t[drop] < t - ARCHIVE_KEEP_S) {
    drop += 1
  }
  if (drop > 0) {
    for (const k of ['t', 'reference', 'command', 'measure']) {
      b[k].splice(0, drop)
    }
  }
}

/** Horloge qui se met à jour régulièrement (pour savoir si une donnée est périmée). */
export function useNow(periodMs = 500) {
  const [now, setNow] = useState(() => Date.now())
  useEffect(() => {
    const t = setInterval(() => setNow(Date.now()), periodMs)
    return () => clearInterval(t)
  }, [periodMs])
  return now
}
