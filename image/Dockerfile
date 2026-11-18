# emkay-home: hivemind-core and the house page, in one small image.
# OVOS itself runs from ovos-docker's own images (see compose/).
#
#   podman build -f image/Dockerfile -t emkay-home .
ARG PYTHON_IMAGE=docker.io/library/python:3.12-slim
FROM ${PYTHON_IMAGE}

LABEL org.opencontainers.image.title="Emkay Home" \
      org.opencontainers.image.description="The OpenVoiceOS for the house that Emkays are satellites of: hivemind-core and the pairing page" \
      org.opencontainers.image.source="https://github.com/emkay-voice/emkay-home" \
      org.opencontainers.image.url="https://emkay.ai" \
      org.opencontainers.image.licenses="Apache-2.0"

ENV PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1 PIP_ROOT_USER_ACTION=ignore

# the same uid as ovos-docker's ovos user, so the shared OVOS config is writable
RUN groupadd --gid 1000 emkay && useradd --uid 1000 --gid 1000 -m emkay \
 && mkdir -p /data /requests /speech /home/emkay/.config/mycroft /ovos-config /emkay-site /home/emkay/.local/share/hivemind-core /home/emkay/.config/hivemind-core \
 && chown -R emkay:emkay /data /requests /speech /ovos-config /emkay-site /home/emkay

COPY image/requirements.txt /tmp/requirements.txt
RUN pip install -r /tmp/requirements.txt && rm /tmp/requirements.txt
# Piper's list of voices (voices.json), for the house's voice on the house
# page – the plugin itself runs in emkay_home_tts; only its list is read here
RUN pip install --no-deps --pre ovos-tts-plugin-piper

COPY pyproject.toml README.md LICENSE /src/
COPY emkay_home /src/emkay_home
RUN pip install --no-deps /src && rm -rf /src

USER emkay
WORKDIR /home/emkay
VOLUME ["/data", "/emkay-site", "/home/emkay/.local/share/hivemind-core", "/home/emkay/.config/hivemind-core"]

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8099/api/info', timeout=4)" || exit 1

ENTRYPOINT ["emkay-home"]
