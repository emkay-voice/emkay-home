#!/usr/bin/env bash
# Start one of the house's speech servers – or wait, if speech is on the
# phones. emkay_home (emkay_home/speech.py) writes the choice and the
# plugins' settings to ~/.config/mycroft here (the emkay_home_speech volume)
# and asks for this container to be restarted when they change.
#
#   run.sh stt    ovos-stt-server, onnx-asr, on 127.0.0.1:${STT_PORT:-8590}
#   run.sh tts    ovos-tts-server, Piper,   on 127.0.0.1:${TTS_PORT:-8591}
#
# Both listen on localhost only: Caddy is the way in (/speech/…), and lets
# only the paired Emkays through.
set -euo pipefail
what="${1:-stt}"
conf="$HOME/.config/mycroft"

if [ ! -f "$conf/in-the-house" ]; then
  echo "speech is on the phones – $what waits here until the house page says otherwise"
  trap 'exit 0' TERM INT
  while :; do sleep 3600 & wait $!; done
fi

# the language, and the plugin for stt / tts, from the config emkay_home wrote
read -r lang stt tts < <(python -c "
import json; c = json.load(open('$conf/mycroft.conf'))
print(c.get('lang', 'en-us'), c['stt'].get('module', 'ovos-stt-plugin-onnx-asr'),
      c['tts'].get('module', 'ovos-tts-plugin-piper'))" 2>/dev/null || echo "en-us ovos-stt-plugin-onnx-asr ovos-tts-plugin-piper")

case "$what" in
  stt) exec ovos-stt-server --engine "$stt" --host 127.0.0.1 --port "${STT_PORT:-8590}" ;;
  tts) exec ovos-tts-server --engine "$tts" --lang "$lang" \
         --host 127.0.0.1 --port "${TTS_PORT:-8591}" ;;
  *)   echo "run.sh: stt or tts, not $what" >&2; exit 2 ;;
esac
