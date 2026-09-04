FROM python:3.11-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    TZ=UTC \
    WAKE_PDI_BROWSER=firefox \
    HOME=/tmp \
    XDG_CACHE_HOME=/tmp/.cache \
    XDG_CONFIG_HOME=/tmp/.config

ARG GECKODRIVER_VERSION=0.37.1
ARG GECKODRIVER_SHA256=e815130ea95983e162ae91843b48d3a3ce991735635fce83a647afde21e09f7e

RUN apt-get update \
    && apt-get install --yes --no-install-recommends \
        ca-certificates \
        curl \
        firefox-esr \
        xvfb \
        tar \
        tini \
    && curl --fail --silent --show-error --location --proto '=https' --tlsv1.2 \
        "https://github.com/mozilla/geckodriver/releases/download/v${GECKODRIVER_VERSION}/geckodriver-v${GECKODRIVER_VERSION}-linux64.tar.gz" \
        --output /tmp/geckodriver.tar.gz \
    && echo "${GECKODRIVER_SHA256}  /tmp/geckodriver.tar.gz" | sha256sum --check --status \
    && tar --extract --gzip --file /tmp/geckodriver.tar.gz --directory /usr/local/bin geckodriver \
    && chmod 0755 /usr/local/bin/geckodriver \
    && rm -f /tmp/geckodriver.tar.gz \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

RUN groupadd --gid 5678 appuser \
    && useradd --uid 5678 --gid 5678 --create-home --home-dir /app --shell /usr/sbin/nologin appuser \
    && install --directory --owner=appuser --group=appuser --mode=0750 /app/logs /var/lib/wake-pdi

COPY requirements-scheduler.txt ./
RUN pip install --no-cache-dir -r requirements-scheduler.txt

COPY --chown=appuser:appuser \
    auth.py \
    auth_requests.py \
    auth_utils.py \
    browser_utils.py \
    config.py \
    firefox_utils.py \
    instance.py \
    logger.py \
    mfa_vault.py \
    scheduler.py \
    session_store.py \
    totp.py \
    utils.py \
    wake.py \
    ./

USER 5678:5678

ENTRYPOINT ["/usr/bin/tini", "--"]
# A bare image is deliberately inert. A scheduled workload must choose
# --reconcile and explicitly opt into Portal mutation with --allow-wake.
CMD ["python", "wake.py", "--help"]
