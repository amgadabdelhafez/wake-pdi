FROM debian:bookworm-slim

RUN apt-get update \
    && apt-get install --yes --no-install-recommends ca-certificates firefox-esr \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --gid 5678 probe \
    && useradd --uid 5678 --gid 5678 --create-home --shell /usr/sbin/nologin probe

USER 5678:5678
ENV HOME=/tmp \
    XDG_CACHE_HOME=/tmp/.cache \
    XDG_CONFIG_HOME=/tmp/.config

ENTRYPOINT ["firefox-esr", "--headless", "--screenshot", "/tmp/firefox-probe.png", "about:blank"]
