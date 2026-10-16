#!/usr/bin/env bash
# deux_vues.sh : lance EN MEME TEMPS les deux fenetres de comparaison du retard
#   1. camera recue SANS CNN      (tools/view_stream.py --no-detect)
#   2. camera traitee par le CNN  (tools/vision_node.py --no-commande : aucun ordre envoye au drone)
# Comparer les numeros d'image (#...) des deux fenetres. Ctrl+C (ou q dans une fenetre) arrete les deux.
# Usage : tools/deux_vues.sh                (ajouter --avec-ordres pour que vision_node envoie les ordres)

cd "$(dirname "$0")/.." || exit 1
PY=venv/bin/python
OPT_VISION="--no-commande"
[ "$1" = "--avec-ordres" ] && OPT_VISION=""

$PY tools/view_stream.py --no-detect &
PID_BRUT=$!
$PY tools/vision_node.py $OPT_VISION &
PID_CNN=$!

trap 'kill $PID_BRUT $PID_CNN 2>/dev/null' INT TERM EXIT
wait -n $PID_BRUT $PID_CNN          # une des deux fenetres fermee : on arrete l'autre
