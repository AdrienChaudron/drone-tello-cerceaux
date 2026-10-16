// Broker MQTT de SIMULATION pour l'IHM web (le Mosquitto du systeme est limite a /etc/mosquitto par AppArmor).
//   TCP 1885       : Python (vision_node.py, simulate_hil.py) avec configs/reseau_sim.yaml
//   WebSocket 9001 : navigateur (web/frontend)
// En vol reel, c'est le Mosquitto du PC de controle qui joue ce role (il faudra y ouvrir un port WebSocket).
import net from 'node:net'
import { Aedes } from 'aedes'
import { createServer } from 'aedes-server-factory'

const TCP_PORT = 1885
const WS_PORT = 9001

const broker = await Aedes.createBroker()
net.createServer(broker.handle).listen(TCP_PORT, '127.0.0.1', () =>
  console.log(`[broker] MQTT     mqtt://127.0.0.1:${TCP_PORT}`))
createServer(broker, { ws: true }).listen(WS_PORT, '127.0.0.1', () =>
  console.log(`[broker] WebSocket ws://127.0.0.1:${WS_PORT}`))

broker.on('client', (c) => console.log(`[broker] + ${c.id}`))
broker.on('clientDisconnect', (c) => console.log(`[broker] - ${c.id}`))
