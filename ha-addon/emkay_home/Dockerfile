# Emkay Home as a Home Assistant add-on: the whole house in one container,
# kept running by s6 – what compose/docker-compose.yml runs as eight:
#
#   ovos_messagebus, ovos_core   OpenVoiceOS (ovos-docker's ovos-core image)
#   emkay_home                   hivemind-core and the house page (image/)
#   emkay_home_panel             the OVOS control panel (panel/)
#   emkay_home_stt, _tts         speech in the house (speech/)
#   caddy                        one https address (caddy/Caddyfile)
#   restarter                    restarts ovos_core and speech when asked
#
# The same code and the same pins as the normal images; only how they are
# started differs. Everything the house keeps is under /data (the add-on's
# own storage, in Home Assistant's backups).
#
# Built from the repository root (.github/workflows/image.yml):
#   docker build -f ha-addon/emkay_home/Dockerfile .
ARG OVOS_IMAGE=docker.io/smartgic/ovos-core:alpha
FROM caddy:2 AS caddy
FROM ${OVOS_IMAGE}

ARG TARGETARCH
ARG S6_OVERLAY_VERSION=3.2.0.2
ARG OVOS_RELEASES_REF=main
USER root
SHELL ["/bin/bash", "-c"]

LABEL org.opencontainers.image.title="Emkay Home – Home Assistant add-on" \
      org.opencontainers.image.description="The OpenVoiceOS for the house that Emkays are satellites of, as a Home Assistant add-on" \
      org.opencontainers.image.source="https://github.com/emkay-voice/emkay-home" \
      org.opencontainers.image.url="https://emkay.ai" \
      org.opencontainers.image.licenses="Apache-2.0" \
      io.hass.type="addon" \
      io.hass.name="Emkay Home"

# s6-overlay keeps the services running; espeak-ng for Piper; xz for s6
RUN apt-get update \
 && apt-get install -y --no-install-recommends xz-utils espeak-ng \
 && rm -rf /var/lib/apt/lists/* \
 && case "$TARGETARCH" in amd64) a=x86_64 ;; arm64) a=aarch64 ;; *) echo "no s6 for $TARGETARCH" >&2; exit 1 ;; esac \
 && for t in noarch "$a"; do \
      curl -fsSL "https://github.com/just-containers/s6-overlay/releases/download/v${S6_OVERLAY_VERSION}/s6-overlay-${t}.tar.xz" | tar -C / -Jxp; \
    done

COPY --from=caddy /usr/bin/caddy /usr/local/bin/caddy

ADD https://raw.githubusercontent.com/OpenVoiceOS/ovos-releases/${OVOS_RELEASES_REF}/constraints-alpha.txt /tmp/constraints.txt

# the message bus, in OVOS' own venv (as ovos-docker's messagebus image)
RUN source /home/ovos/.venv/bin/activate \
 && uv pip install --prerelease=allow ovos-messagebus -c /tmp/constraints.txt

# emkay_home and hivemind-core (image/Dockerfile)
COPY image/requirements.txt /tmp/emkay-requirements.txt
COPY pyproject.toml README.md LICENSE /src/
COPY emkay_home /src/emkay_home
RUN python -m venv /opt/emkay \
 && /opt/emkay/bin/pip install --no-cache-dir -r /tmp/emkay-requirements.txt \
 && /opt/emkay/bin/pip install --no-cache-dir --no-deps --pre ovos-tts-plugin-piper \
 && /opt/emkay/bin/pip install --no-cache-dir --no-deps /src

# the control panel (panel/Dockerfile), with emkay_home for its page (the
# Emkays in the house: only its controlpanel.json is read there)
COPY panel/system.conf /opt/emkay/system.conf
COPY panel/emkay-logo.svg /opt/emkay/emkay-logo.svg
RUN python -m venv /opt/panel \
 && /opt/panel/bin/pip install --no-cache-dir --pre "ovos-control-panel>=0.0.1a92" -c /tmp/constraints.txt \
 && /opt/panel/bin/pip install --no-cache-dir --no-deps /src \
 && rm -rf /src

# speech in the house (speech/Dockerfile)
COPY speech/run.sh /opt/emkay/speech.sh
RUN python -m venv /opt/speech \
 && /opt/speech/bin/pip install --no-cache-dir --pre ovos-stt-http-server ovos-tts-server \
      ovos-stt-plugin-onnx-asr "onnx-asr[hub]" ovos-tts-plugin-piper -c /tmp/constraints.txt \
 && rm -f /tmp/constraints.txt /tmp/emkay-requirements.txt

COPY caddy/Caddyfile /etc/caddy/Caddyfile
COPY ha-addon/emkay_home/rootfs/ /
RUN chmod +x /etc/cont-init.d/* /etc/services.d/*/run /usr/local/bin/wait-for-house \
 && ln -s /data/emkay-site /emkay-site

ENV S6_BEHAVIOUR_IF_STAGE2_FAILS=2 S6_CMD_WAIT_FOR_SERVICES_MAXTIME=0
WORKDIR /
ENTRYPOINT ["/init"]
