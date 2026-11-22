# emkay-home-panel: the stock OpenVoiceOS control panel (ovos-control-panel),
# for the OVOS in the house, as it is: Emkay's look, the house's guide and
# what the house leaves out come from its own system layer (panel/system.conf). It talks to
# OVOS over the message bus and edits the same config the ovos_core container
# uses (the shared ovos_config volume); installing skills and plugins it asks ovos-core to do
# (ovos.pip.install), so they land where they run.
#
# Caddy serves it at https://<house>:8500/, behind Emkay Home's own sign-in
# (forward_auth), with the panel's token added on the way (see
# emkay_home/panel.py) – one password for the whole house.
#
#   podman build -f panel/Dockerfile -t emkay-home-panel .
ARG PYTHON_IMAGE=docker.io/library/python:3.12-slim
FROM ${PYTHON_IMAGE}

LABEL org.opencontainers.image.title="Emkay Home – control panel" \
      org.opencontainers.image.description="The stock OpenVoiceOS control panel for the house's OVOS, as Emkay Home runs it" \
      org.opencontainers.image.source="https://github.com/emkay-voice/emkay-home" \
      org.opencontainers.image.url="https://emkay.ai" \
      org.opencontainers.image.licenses="Apache-2.0" \
      org.opencontainers.image.vendor="emkay-voice"

ENV PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1 PIP_ROOT_USER_ACTION=ignore

# the same uid as ovos-docker's ovos user: the config volume is theirs
RUN groupadd --gid 1000 ovos && useradd --uid 1000 --gid 1000 -m ovos \
 && mkdir -p /home/ovos/.config/mycroft /home/ovos/.config/ovos_persona /home/ovos/.local/share/mycroft \
 && chown -R ovos:ovos /home/ovos

# the alpha channel, as the panel and Emkay follow it
ARG OVOS_RELEASES_REF=main
RUN pip install --pre "ovos-control-panel>=0.0.1a92" \
      -c "https://raw.githubusercontent.com/OpenVoiceOS/ovos-releases/${OVOS_RELEASES_REF}/constraints-alpha.txt"

# Emkay Home as a distribution of the panel: its system layer of
# mycroft.conf (name, eyes and colours as in Emkay, a dark theme, no
# ovos-audio in the house, Emkay may show it in a frame, the house's setup
# guide). Only the panel reads it (MYCROFT_SYSTEM_CONFIG); what is chosen on
# the panel's own Control panel page goes in the user layer and wins.
# emkay_home itself, for its page (the Emkays in the house): only its
# controlpanel.json is read here; the page talks to emkay_home over the bus
COPY pyproject.toml README.md LICENSE /src/
COPY emkay_home /src/emkay_home
RUN pip install --no-deps /src && rm -rf /src
COPY panel/system.conf /opt/emkay/system.conf
COPY panel/emkay-logo.svg /opt/emkay/emkay-logo.svg
ENV MYCROFT_SYSTEM_CONFIG=/opt/emkay/system.conf

USER ovos
WORKDIR /home/ovos

# on localhost only: Caddy is the way in
ENV OVOS_WEBUI_HOST=127.0.0.1 OVOS_WEBUI_PORT=8599
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8599/healthz', timeout=4)" || exit 1

ENTRYPOINT ["ovos-control-panel"]
