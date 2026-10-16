import Panel from './Panel.jsx'

function batteryLevel(pct) {
  if (pct <= 20) return 'danger'
  if (pct <= 40) return 'warn'
  return 'ok'
}

function formatDuration(s) {
  const m = Math.floor(s / 60)
  return `${m}:${String(Math.floor(s % 60)).padStart(2, '0')}`
}

/** Etat du drone, fourni par le PC de controle (tello/status). */
export default function DronePanel({ status, stale }) {
  if (!status) {
    return (
      <Panel title="Drone" source="PC de contrôle · tello/status" stale>
        <p className="muted">En attente du PC de contrôle (batterie, hauteur, cap…).</p>
      </Panel>
    )
  }
  const bat = status.battery ?? 0

  return (
    <Panel title="Drone" source="PC de contrôle · tello/status" stale={stale}>
      <div className={`battery battery--${batteryLevel(bat)}`}>
        <div className="battery__bar">
          <div className="battery__fill" style={{ width: `${bat}%` }} />
        </div>
        <span className="battery__value">{bat} %</span>
      </div>
      <dl className="stats">
        <div><dt>Hauteur (ToF)</dt><dd>{status.tof ?? '—'} cm</dd></div>
        <div><dt>Cap</dt><dd>{status.yaw != null ? `${status.yaw > 0 ? '+' : ''}${status.yaw}°` : '—'}</dd></div>
        <div><dt>Température</dt><dd>{status.temperature ?? '—'} °C</dd></div>
        <div><dt>Temps de vol</dt><dd>{status.flight_time != null ? formatDuration(status.flight_time) : '—'}</dd></div>
      </dl>
    </Panel>
  )
}
