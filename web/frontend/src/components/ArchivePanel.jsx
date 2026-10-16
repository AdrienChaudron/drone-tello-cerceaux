import { useEffect, useRef, useState } from 'react'
import uPlot from 'uplot'
import 'uplot/dist/uPlot.min.css'
import Panel from './Panel.jsx'
import { ARCHIVE_AXES, ARCHIVE_WINDOWS_S } from '../config.js'

// Couleurs des series (palette validee sur le fond sombre des panneaux)
const C = { reference: '#3987e5', measure: '#d95926', command: '#199e70', grid: '#232a36', axis: '#8a93a3' }
const UNITS = { X: 'cm', Y: 'cm', Z: 'cm', YAW: '°' }
const REFRESH_MS = 100 // les courbes se redessinent 10 fois par seconde

const axisStyle = (size = 46) => ({
  stroke: C.axis,
  grid: { stroke: C.grid, width: 1 },
  ticks: { stroke: C.grid, width: 1 },
  font: '11px system-ui',
  size,
})

const timeAxis = () => ({
  ...axisStyle(28),
  values: (u, ticks) => ticks.map((t) => new Date(t * 1000).toLocaleTimeString('fr-FR')),
})

/** Un axe d'asservissement : consigne + mesure (meme unite), puis la commande dans sa propre bande. */
function AxisChart({ axis, buffers, windowS }) {
  const boxRef = useRef(null)
  const mainRef = useRef(null)
  const stripRef = useRef(null)
  const [empty, setEmpty] = useState(true)

  useEffect(() => {
    const width = boxRef.current.clientWidth
    const cursor = { show: false, drag: { x: false, y: false } }
    const hasReference = !['X', 'Y'].includes(axis)
    const hasCommand = true
    const main = new uPlot(
      {
        width,
        height: 150,
        cursor,
        legend: { show: true, live: false },
        scales: { x: { time: true } },
        series: [
          { label: 'Temps', value: (u, t) => (t == null ? '—' : new Date(t * 1000).toLocaleTimeString('fr-FR')) },
          ...(hasReference ? [{ label: `Consigne (${UNITS[axis]})`, stroke: C.reference, width: 2, points: { show: false }, value: (u, v) => (v == null ? '—' : v.toFixed(1)) }] : []),
          { label: `Mesure (${UNITS[axis]})`, stroke: C.measure, width: 2, dash: [6, 4], points: { show: false }, value: (u, v) => (v == null ? '—' : v.toFixed(1)) },
        ],
        axes: [{ ...timeAxis(), show: false }, axisStyle()],
      },
      [[], ...(hasReference ? [[], []] : [[]]),],
      mainRef.current,
    )
    const strip = new uPlot(
      {
        width,
        height: 90,
        cursor,
        legend: { show: true, live: false },
        scales: { x: { time: true }, y: { range: [-100, 100] } },
        series: [
          { label: 'Temps', show: false },
          ...(hasCommand ? [{ label: 'Commande (rc, %)', stroke: C.command, width: 2, points: { show: false }, value: (u, v) => (v == null ? '—' : v.toFixed(0)) }] : []),
        ],
        axes: [timeAxis(), { ...axisStyle(), splits: () => [-100, 0, 100] }],
      },
      [[], ...(hasCommand ? [[]] : [])],
      stripRef.current,
    )

    // Redessin periodique depuis les tampons (sans passer par l'etat React)
    const timer = setInterval(() => {
      const b = buffers.current[axis]
      const n = b.t.length
      setEmpty(n === 0)
      if (n === 0) return
      const tEnd = b.t[n - 1]
      let i0 = 0
      while (i0 < n && b.t[i0] < tEnd - windowS) i0 += 1
      const t = b.t.slice(i0)
      main.setData([t, ...(hasReference ? [b.reference.slice(i0)] : []), b.measure.slice(i0)])
      strip.setData([t, ...(hasCommand ? [b.command.slice(i0)] : [])])
      main.setScale('x', { min: tEnd - windowS, max: tEnd }) // fenetre fixe qui defile
      strip.setScale('x', { min: tEnd - windowS, max: tEnd })
    }, REFRESH_MS)

    // Largeur suivie quand la page change de taille
    const ro = new ResizeObserver(([entry]) => {
      const w = Math.floor(entry.contentRect.width)
      main.setSize({ width: w, height: 150 })
      strip.setSize({ width: w, height: 90 })
    })
    ro.observe(boxRef.current)

    return () => {
      clearInterval(timer)
      ro.disconnect()
      main.destroy()
      strip.destroy()
    }
  }, [axis, buffers, windowS])

  return (
    <div className="axis-chart" ref={boxRef}>
      <h3 className="axis-chart__title">Archive {axis}</h3>
      <div className="axis-chart__plots">
        <div ref={mainRef} />
        <div ref={stripRef} className="axis-chart__strip" />
        {empty && <div className="axis-chart__empty">Pas de données (tello/archive/{axis})</div>}
      </div>
    </div>
  )
}

/** Courbes des asservissements du PC de controle (comme dans MQTT Explorer). */
export default function ArchivePanel({ archive, stale }) {
  const [windowS, setWindowS] = useState(30)
  return (
    <Panel title="Asservissements" source="PC de contrôle · tello/archive/+" stale={stale} className="archive">
      <div className="archive__toolbar" role="group" aria-label="Fenêtre de temps affichée">
        {ARCHIVE_WINDOWS_S.map((s) => (
          <button
            key={s}
            type="button"
            className={`seg ${s === windowS ? 'seg--on' : ''}`}
            onClick={() => setWindowS(s)}
          >
            {s} s
          </button>
        ))}
      </div>
      <div className="archive__grid">
        {ARCHIVE_AXES.map((a) => (
          <AxisChart key={a} axis={a} buffers={archive} windowS={windowS} />
        ))}
      </div>
    </Panel>
  )
}
