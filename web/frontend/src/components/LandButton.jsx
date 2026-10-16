import { useEffect, useState } from 'react'
import Panel from './Panel.jsx'
import { API_URL } from '../config.js'

/**
 * Atterrissage force : envoie {"cmd": "land"} sur tello/safety, que le PC de controle traite.
 * Deux clics pour eviter un appui accidentel : le premier arme le bouton pendant 3 s.
 * Le deadman principal reste la barre espace du PC de controle.
 */
export default function LandButton({ connected, publish }) {
  const [armed, setArmed] = useState(false)
  const [sentAt, setSentAt] = useState(null)

  useEffect(() => {
    if (!armed) return undefined
    const t = setTimeout(() => setArmed(false), 3000)
    return () => clearTimeout(t)
  }, [armed])

  const onClick = async () => {
    if (!armed) {
      setArmed(true);
      return;
    }

    try {
      // Send landing / deadman command via server.js route
      const response = await fetch(`${API_URL}/api/deadman`, {
        method: 'POST',
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      setArmed(false);
      setSentAt(new Date());
    } catch (error) {
      console.error('Failed to trigger land/deadman procedure:', error);
      setArmed(false);
      setSentAt(null);
    }
  };

  return (
    <Panel title="Sécurité" source="IHM → PC de contrôle · tello/safety">
      <button
        type="button"
        className={`land ${armed ? 'land--armed' : ''}`}
        onClick={onClick}
        disabled={!connected}
      >
        {armed ? 'Confirmer l’atterrissage' : 'Atterrissage forcé'}
      </button>
      <p className="footnote">
        {sentAt
          ? `Demande envoyée à ${sentAt.toLocaleTimeString('fr-FR')}`
          : 'Deadman principal : barre espace du PC de contrôle.'}
      </p>
    </Panel>
  )
}
