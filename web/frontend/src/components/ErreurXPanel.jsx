import { useEffect, useRef, useState } from 'react'
import uPlot from 'uplot'
import 'uplot/dist/uPlot.min.css'
import Panel from './Panel.jsx'
import { ARCHIVE_WINDOWS_S } from '../config.js'

// Memes couleurs que les courbes des asservissements
const C = { erreur: '#d95926', seuil: '#8a93a3', grid: '#232a36', axis: '#8a93a3' }
const SEUIL_PX = 40 // cerceau considere centre a +-40 px (bandeau vert de vision_node)
const REFRESH_MS = 100

const axisStyle = (size = 46) => ({
  stroke: C.axis,
  grid: { stroke: C.grid, width: 1 },
  ticks: { stroke: C.grid, width: 1 },
  font: '11px system-ui',
  size,
})

/**
 * Erreur en X : delta_x envoye par la vision (pixels, image 960x720, > 0 = cerceau a droite).
 * Un point par image traitee par vision_node ; trou dans la courbe quand le cerceau n'est pas vu.
 */
export default function ErreurXPanel({ erreurX, stale }) {
  const [windowS, setWindowS] = useState(30)
  const boxRef = useRef(null)
  const plotRef = useRef(null)
  const [empty, setEmpty] = useState(true)

  useEffect(() => {
    const width = boxRef.current.clientWidth
    const plot = new uPlot(
      {
        width,
        height: 180,
        cursor: { show: false, drag: { x: false, y: false } },
        legend: { show: true, live: false },
        scales: { x: { time: true }, y: { range: (u, min, max) => { const m = Math.max(100, Math.abs(min || 0), Math.abs(max || 0)); return [-m, m] } } },
        series: [
          { label: 'Temps', value: (u, t) => (t == null ? '—' : new Date(t * 1000).toLocaleTimeString('fr-FR')) },
          { label: 'Erreur X (px)', stroke: C.erreur, width: 2, points: { show: false }, spanGaps: false, value: (u, v) => (v == null ? '—' : v.toFixed(0)) },
          { label: `±${SEUIL_PX} px (centré)`, stroke: C.seuil, width: 1, dash: [4, 4], points: { show: false } },
          { label: '', stroke: C.seuil, width: 1, dash: [4, 4], points: { show: false } },
        ],
        axes: [
          { ...axisStyle(28), values: (u, ticks) => ticks.map((t) => new Date(t * 1000).toLocaleTimeString('fr-FR')) },
          axisStyle(),
        ],
      },
      [[], [], [], []],
      plotRef.current,
    )

    const timer = setInterval(() => {
      const b = erreurX.current
      const n = b.t.length
      setEmpty(n === 0)
      if (n === 0) return
      const tEnd = b.t[n - 1]
      let i0 = 0
      while (i0 < n && b.t[i0] < tEnd - windowS) i0 += 1
      const t = b.t.slice(i0)
      plot.setData([t, b.dx.slice(i0), t.map(() => SEUIL_PX), t.map(() => -SEUIL_PX)])
      plot.setScale('x', { min: tEnd - windowS, max: tEnd })
    }, REFRESH_MS)

    const ro = new ResizeObserver(([entry]) => plot.setSize({ width: Math.floor(entry.contentRect.width), height: 180 }))
    ro.observe(boxRef.current)

    return () => {
      clearInterval(timer)
      ro.disconnect()
      plot.destroy()
    }
  }, [erreurX, windowS])

  return (
    <Panel title="Erreur en X" source="PC vision · delta_x (pixels)" stale={stale} className="archive">
      <div className="archive__toolbar" role="group" aria-label="Fenêtre de temps affichée">
        {ARCHIVE_WINDOWS_S.map((s) => (
          <button key={s} type="button" className={`seg ${s === windowS ? 'seg--on' : ''}`} onClick={() => setWindowS(s)}>
            {s} s
          </button>
        ))}
      </div>
      <div className="axis-chart" ref={boxRef}>
        <div className="axis-chart__plots">
          <div ref={plotRef} />
          {empty && <div className="axis-chart__empty">Pas de données (vision_node)</div>}
        </div>
      </div>
    </Panel>
  )
}
