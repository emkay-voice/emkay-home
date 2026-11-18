# emkay-home-speech: speech in the house, for the Emkays that want it – the
# stock OpenVoiceOS speech servers with the house's plugins:
#
#   stt   ovos-stt-server  + ovos-stt-plugin-onnx-asr (a model per language;
#         NVIDIA's Danish Parakeet for Danish – docs/danish-speech.md)
#   tts   ovos-tts-server  + ovos-tts-plugin-piper (Piper voices)
#
# One image, two containers (compose: emkay_home_stt, emkay_home_tts). Each
# waits idle until "Speech" on the house page says "in the house" (see
# speech/run.sh and emkay_home/speech.py); Caddy serves them at /speech/stt/
# and /speech/tts/ for the paired Emkays only.
#
#   podman build -f speech/Dockerfile -t emkay-home-speech .
ARG PYTHON_IMAGE=docker.io/library/python:3.12-slim
FROM ${PYTHON_IMAGE}

LABEL org.opencontainers.image.title="Emkay Home – speech" \
      org.opencontainers.image.description="OpenVoiceOS' STT and TTS servers (onnx-asr, Piper) for the Emkays of the house" \
      org.opencontainers.image.source="https://github.com/emkay-voice/emkay-home" \
      org.opencontainers.image.url="https://emkay.ai" \
      org.opencontainers.image.licenses="Apache-2.0"

ENV PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1 PIP_ROOT_USER_ACTION=ignore

# espeak-ng: Piper turns text into phonemes with it
RUN apt-get update \
 && apt-get install -y --no-install-recommends espeak-ng \
 && rm -rf /var/lib/apt/lists/*

# the same uid as ovos-docker's ovos user
RUN groupadd --gid 1000 ovos && useradd --uid 1000 --gid 1000 -m ovos \
 && mkdir -p /home/ovos/.config/mycroft /home/ovos/.cache /home/ovos/.local/share \
 && chown -R ovos:ovos /home/ovos

# the alpha channel, as Emkay and the rest of the house follow it;
# onnx-asr[hub]: it fetches its models from Hugging Face
ARG OVOS_RELEASES_REF=main
RUN pip install --pre ovos-stt-http-server ovos-tts-server \
      ovos-stt-plugin-onnx-asr "onnx-asr[hub]" ovos-tts-plugin-piper \
      -c "https://raw.githubusercontent.com/OpenVoiceOS/ovos-releases/${OVOS_RELEASES_REF}/constraints-alpha.txt"

COPY speech/run.sh /opt/emkay/run.sh

USER ovos
WORKDIR /home/ovos
ENTRYPOINT ["bash", "/opt/emkay/run.sh"]
CMD ["stt"]
