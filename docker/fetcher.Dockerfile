FROM ubuntu:24.04 AS base

ENV DEBIAN_FRONTEND=noninteractive
ENV PIP_BREAK_SYSTEM_PACKAGES=1
ENV PYTHONDONTWRITEBYTECODE=1

RUN apt-get update && apt-get install -y --no-install-recommends \
        python3 python3-pip \
    && rm -rf /var/lib/apt/lists/*

COPY fetcher/requirements.txt /tmp/requirements.txt
RUN pip3 install --no-cache-dir -r /tmp/requirements.txt && rm /tmp/requirements.txt


FROM base AS build

RUN apt-get update && apt-get install -y --no-install-recommends \
        python3-dev build-essential patchelf \
    && rm -rf /var/lib/apt/lists/* \
    && pip3 install --no-cache-dir nuitka

WORKDIR /build

COPY licensing ./licensing
COPY fetcher/main.py fetcher/
COPY fetcher/src fetcher/src

RUN cd fetcher && PYTHONPATH=/build python3 -m nuitka \
        --assume-yes-for-downloads \
        --remove-output \
        --nofollow-imports \
        --no-deployment-flag=self-execution \
        --follow-import-to=src \
        --include-package=licensing \
        --output-dir=/out \
        --output-filename=fetcher \
        --company-name=ai-call-analytics \
        --product-name=fetcher \
        main.py

RUN /out/fetcher --help > /dev/null


FROM base

COPY --from=build /out/fetcher /app/fetcher

ENTRYPOINT ["/app/fetcher", "--config", "/configs/config.toml"]
