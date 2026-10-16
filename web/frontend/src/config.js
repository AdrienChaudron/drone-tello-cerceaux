export const API_URL = import.meta.env?.VITE_API_URL || 'http://192.168.20.1:3000'

// Vision (PC vision, vision_node.py) : video annotee en MJPEG + etat de la vision en SSE, servis en direct
// (la video ne passe pas par le broker ni par le serveur Node). Simulation : VITE_VISION_URL=http://localhost:8080
export const VISION_URL = import.meta.env?.VITE_VISION_URL || 'http://192.168.20.2:8080'
export const VIDEO_URL = `${VISION_URL}/video.mjpeg`

export const TOPICS = {
  view: 'tello/vision/view', // NOTRE PC : image annotee par le CNN (JPEG brut)
  state: 'tello/vision/state', // NOTRE PC : etat de la vision (JSON)
  status: 'tello/status', // PC de controle : batterie, hauteur, cap... (JSON)
  safety: 'tello/safety', // IHM -> PC de controle : atterrissage force
  archive: 'tello/archive/+', // PC de controle : boucles d'asservissement (une par axe)
}

// Courbes des asservissements (tello/archive/<axe>) : {timestamp, reference, command, measure}
export const ARCHIVE_AXES = ['X', 'Y', 'Z', 'YAW']
export const ARCHIVE_KEEP_S = 120 // duree gardee en memoire dans le navigateur
export const ARCHIVE_WINDOWS_S = [15, 30, 60, 120] // fenetres proposees a l'affichage

// Au-dela de ce delai sans message, la donnee est consideree comme perimee.
export const STALE_MS = 2000
