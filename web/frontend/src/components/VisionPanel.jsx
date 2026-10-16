import Panel from './Panel.jsx'

const PHASES = {
  RECHERCHE: 'warn',
  APPROCHE: 'info',
  ALIGNEMENT: 'accent',
  TRAVERSEE: 'violet',
  PERTE: 'danger',
  FIN: 'ok',
}

// Valeur avec son signe ; une valeur arrondie a zero s'affiche sans signe (pas de « -0 »)
const signed = (v, digits = 2) => {
  if (v == null) return '—'
  const txt = Math.abs(v).toFixed(digits)
  if (Number(txt) === 0) return txt
  return `${v > 0 ? '+' : '-'}${txt}`
}

/** Etat de la vision et commande envoyee (tello/vision/state). */
export default function VisionPanel({ vision, stale }) {
  if (!vision) {
    return (
      <Panel title="Vision" source="PC vision · tello/vision/state" stale>
        <p className="muted">En attente de vision_node…</p>
      </Panel>
    )
  }
  console.log(vision)
  const { phase, mode, present, p, ambigu, distance_m: dist, centre, axe, commande: cmd } = vision
  return (
    <Panel title="Vision" source="PC vision · tello/vision/state" stale={stale}>
      <div className="vision__head">
        <span className={`phase phase--${PHASES[phase] ?? 'info'}`}>{phase}</span>
        <span className="muted">{mode}</span>
      </div>

      <div className="confidence">
        <span>{present ? 'Cerceau détecté' : 'Pas de cerceau'}</span>
        <div className="confidence__bar"><div style={{ width: `${Math.round(p * 100)}%` }} /></div>
        <span className="mono">p = {p.toFixed(2)}{ambigu ? ' · ambigu' : ''}</span>
      </div>

      <dl className="stats">
        <div><dt>Distance</dt><dd>{dist != null ? `${dist.toFixed(2)} m` : '—'}</dd></div>
        <div><dt>Avant</dt><dd>{centre ? `${centre.avant.toFixed(2)} m` : '—'}</dd></div>
        <div><dt>Droite</dt><dd>{centre ? `${signed(centre.droite)} m` : '—'}</dd></div>
        <div><dt>Haut</dt><dd>{centre ? `${signed(centre.haut)} m` : '—'}</dd></div>
        <div><dt>Écart à l'axe</dt><dd>{axe ? `${signed(axe.ecart_lateral_m * 100, 0)} cm` : '—'}</dd></div>
        <div><dt>Cap de l'axe</dt><dd>{axe ? `${signed(axe.cap_deg, 0)}°` : '—'}</dd></div>
      </dl>

      <h3 className="subhead">Commande envoyée</h3>
      <div className="command">
        <div><span>X</span><b>{signed(cmd.X, 0)}</b><small>px droite</small></div>
        <div><span>Y</span><b>{signed(cmd.Y, 0)}</b><small>cm distance</small></div>
        <div><span>Z</span><b>{cmd.Z.toFixed(0)}</b><small>cm absolu</small></div>
        <div><span>YAW</span><b>{signed(cmd.YAW, 0)}</b><small>° absolu</small></div>
      </div>

      <p className="footnote mono">
        calcul {vision.calcul_ms} ms · reçues {vision.recues} · sautées {vision.sautees}
      </p>
    </Panel>
  )
}
