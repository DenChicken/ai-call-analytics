FROM nvidia/cuda:12.6.3-cudnn-runtime-ubuntu24.04 AS base

ENV DEBIAN_FRONTEND=noninteractive
ENV PIP_BREAK_SYSTEM_PACKAGES=1
ENV PYTHONDONTWRITEBYTECODE=1

RUN apt-get update && apt-get install -y --no-install-recommends \
        python3 python3-pip \
    && rm -rf /var/lib/apt/lists/*

COPY pipeline/requirements.txt /tmp/requirements.txt
RUN pip3 install --no-cache-dir \
        --extra-index-url https://abetlen.github.io/llama-cpp-python/whl/cu124 \
        -r /tmp/requirements.txt \
    && rm /tmp/requirements.txt


FROM base AS build

RUN apt-get update && apt-get install -y --no-install-recommends \
        python3-dev build-essential patchelf \
    && rm -rf /var/lib/apt/lists/* \
    && pip3 install --no-cache-dir nuitka

WORKDIR /build

COPY licensing ./licensing
COPY pipeline/main.py pipeline/
COPY pipeline/src pipeline/src

RUN cd pipeline && PYTHONPATH=/build python3 -m nuitka \
        --assume-yes-for-downloads \
        --remove-output \
        --nofollow-imports \
        --no-deployment-flag=self-execution \
        --follow-import-to=src \
        --include-package=licensing \
        --output-dir=/out \
        --output-filename=pipeline \
        --company-name=ai-call-analytics \
        --product-name=pipeline \
        main.py

RUN /out/pipeline --help > /dev/null


FROM base

ENV HF_HUB_OFFLINE=1

COPY --from=build /out/pipeline /app/pipeline

ENTRYPOINT ["/app/pipeline", "--config", "/configs/config.toml"]
