import { API_URL } from '../config.js'

function Pill({ ok, label }) {
  return <span className={`pill ${ok ? 'pill--ok' : 'pill--off'}`}>{label}</span>
}

/** Bandeau du haut : nom de l'IHM et etat des liaisons. */
export default function Header({ connected, visionOk, statusOk }) {
  return (
    <header className="topbar">
      <div className="topbar__title">
        <span className="topbar__logo" aria-hidden="true">◎</span>
        <h1>Tello · IHM de vol</h1>
      </div>
      <div className="topbar__links">
        <Pill ok={connected} label={connected ? `API ${API_URL}` : 'API déconnectée'} />
        <Pill ok={visionOk} label="PC vision" />
        <Pill ok={statusOk} label="Tello en vol" />
      </div>
    </header>
  )
}
