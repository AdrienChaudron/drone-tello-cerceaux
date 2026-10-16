import { Suspense, useEffect, useMemo, useRef } from 'react'
import { Canvas, useFrame, useLoader, useThree } from '@react-three/fiber'
import { GLTFLoader } from 'three/examples/jsm/loaders/GLTFLoader.js'
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js'
import Panel from './Panel.jsx'

const MODEL_URL = '/models/tello.glb' // export de ~/Documents/blender-claude/dji_tello.blend
const DEG = Math.PI / 180

// Sens de rotation des helices (quadricoptere en X) : avant-gauche et arriere-droite dans un sens,
// les deux autres dans l'autre (sinon le drone tournerait sur lui-meme).
const PROPS = { Prop_FL: 1, Prop_RR: 1, Prop_FR: -1, Prop_RL: -1 }
const PROP_SPEED = 40 // rad/s a l'affichage (une vraie helice tourne bien plus vite)

/**
 * Modele du Tello. Reperes apres export glTF : haut = +Y, AVANT du drone (camera) = -Z.
 * Le cap Tello est positif vers la droite (sens horaire vu de dessus), alors qu'une rotation three.js
 * positive autour de Y est anti-horaire : on applique donc -cap.
 */
function Tello({ yawDeg, flying }) {
  const gltf = useLoader(GLTFLoader, MODEL_URL)
  const group = useRef()
  const props = useMemo(
    () => Object.entries(PROPS).map(([name, dir]) => [gltf.scene.getObjectByName(name), dir]).filter(([o]) => o),
    [gltf],
  )

  useFrame((_, dt) => {
    if (!group.current) return
    // Cap : on rejoint la valeur recue en douceur, par le chemin le plus court
    const target = -yawDeg * DEG
    const diff = Math.atan2(Math.sin(target - group.current.rotation.y), Math.cos(target - group.current.rotation.y))
    group.current.rotation.y += diff * Math.min(1, dt * 8)
    if (flying) for (const [prop, dir] of props) prop.rotateY(dir * PROP_SPEED * dt)
  })

  return (
    <group ref={group}>
      {/* centre vertical du drone a y = 0 (l'origine du modele est au sol) */}
      <primitive object={gltf.scene} position={[0, -0.018, 0]} />
    </group>
  )
}

/** Rotation / zoom de la vue a la souris (OrbitControls de three.js). */
function Controls() {
  const { camera, gl } = useThree()
  const ctrl = useRef(null)
  useEffect(() => {
    const c = new OrbitControls(camera, gl.domElement)
    c.enableDamping = true
    c.enablePan = false
    c.minDistance = 0.18
    c.maxDistance = 1.2
    c.maxPolarAngle = 88 * DEG // pas sous le sol
    ctrl.current = c
    return () => {
      c.dispose()
      ctrl.current = null
    }
  }, [camera, gl])
  useFrame(() => ctrl.current?.update())
  return null
}

/** Etat du drone en 3D : cap reel, helices animees quand il vole. */
export default function Drone3DPanel({ status, stale }) {
  const yaw = status?.yaw ?? 0
  const flying = !stale && (status?.tof ?? 0) > 20 // en l'air : ToF > 20 cm et donnees a jour

  return (
    <Panel title="Modèle 3D" source="PC de contrôle · tello/status (cap)" className="drone3d">
      <div className="drone3d__view">
        <Canvas camera={{ position: [0.15, 0.13, 0.19], fov: 40, near: 0.01, far: 20 }} dpr={[1, 2]}>
          <hemisphereLight args={['#ffffff', '#5a6475', 2.2]} />
          <directionalLight position={[1, 2, 1.5]} intensity={2.8} />
          {/* contre-jour : detache les pieces noires du fond */}
          <directionalLight position={[-1.5, 1, -1]} intensity={1.4} />
          <gridHelper args={[0.8, 16, '#3b4555', '#262d38']} position={[0, -0.018, 0]} />
          <Suspense fallback={null}>
            <Tello yawDeg={yaw} flying={flying} />
          </Suspense>
          <Controls />
        </Canvas>
        <div className="drone3d__info">
          <span>cap {yaw > 0 ? '+' : ''}{Math.round(yaw)}°</span>
          <span>{flying ? 'en vol' : 'au sol'}</span>
        </div>
        <div className="drone3d__hint">glisser : tourner la vue · molette : zoom</div>
      </div>
    </Panel>
  )
}
