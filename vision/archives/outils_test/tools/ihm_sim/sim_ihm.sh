#!/usr/bin/env bash
# Simulation complete de l'IHM web, sans drone ni PC du collegue :
#   broker local Node/aedes (1885 + WebSocket 9001)  <-  simulate_hil.py (role du PC de controle : video + batterie)
#                                         <-> vision_node.py  (notre PC : CNN, image annotee, etat, ordres)
#                                         ->  navigateur      (web/frontend, http://localhost:5173)
# Usage : bash tools/ihm_sim/sim_ihm.sh      (Ctrl+C pour tout arreter)
set -u
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"
source venv/bin/activate
export NVM_DIR="$HOME/.nvm"; [ -s "$NVM_DIR/nvm.sh" ] && . "$NVM_DIR/nvm.sh"
IMAGES="${IMAGES:-captures/hoop/*_17907529*.jpg}"      # sequence enregistree dans la cage

# Une simulation tourne deja (ports occupes) ? On refuse : deux vision_node se partageraient le CPU
# et s'ejecteraient du broker (meme identifiant MQTT).
for port in 1885 9001 5173; do
  if ss -ltn | grep -q ":$port "; then
    echo "Le port $port est deja utilise : une simulation tourne encore."
    echo "Arretez-la (Ctrl+C dans son terminal) ou :  pkill -f 'reseau_sim.yaml'; pkill -f ihm_sim/broker; pkill -f vite/bin"
    exit 1
  fi
done

pids=()
cleanup() { echo; echo "Arret de la simulation..."; kill "${pids[@]}" 2>/dev/null; wait 2>/dev/null; }
trap cleanup EXIT INT TERM

[ -d tools/ihm_sim/broker/node_modules ] || (cd tools/ihm_sim/broker && yarn install)
node tools/ihm_sim/broker/broker.js > /tmp/ihm_sim_broker.log 2>&1 & pids+=($!)
sleep 1
python tools/vision_node.py --reseau configs/reseau_sim.yaml --no-window > /tmp/ihm_sim_vision.log 2>&1 & pids+=($!)
sleep 6                                                # chargement du CNN
python tools/simulate_hil.py --reseau configs/reseau_sim.yaml --images "$IMAGES" --fps 12 --loop --status \
    > /tmp/ihm_sim_hil.log 2>&1 & pids+=($!)
echo "Simulation lancee. Journaux : /tmp/ihm_sim_*.log"
echo "IHM : http://localhost:5173   (Ctrl+C pour tout arreter)"
cd web/frontend && VITE_MQTT_URL="ws://localhost:9001" yarn dev
