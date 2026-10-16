/** Cadre commun des panneaux : titre, source de la donnee, contenu. */
export default function Panel({ title, source, stale = false, className = '', children }) {
  return (
    <section className={`panel ${stale ? 'panel--stale' : ''} ${className}`}>
      <header className="panel__head">
        <h2>{title}</h2>
        {source && <span className="panel__source">{source}</span>}
      </header>
      <div className="panel__body">{children}</div>
    </section>
  )
}
