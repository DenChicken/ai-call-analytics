FROM nvidia/cuda:12.6.3-runtime-ubuntu24.04 AS build

ENV DEBIAN_FRONTEND=noninteractive
ENV PIP_BREAK_SYSTEM_PACKAGES=1
ENV PYTHONDONTWRITEBYTECODE=1

RUN apt-get update && apt-get install -y --no-install-recommends \
        python3 python3-dev python3-pip \
        build-essential patchelf ccache \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /build

COPY pipeline/requirements.txt ./
RUN pip3 install --no-cache-dir -r requirements.txt nuitka

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


FROM nvidia/cuda:12.6.3-runtime-ubuntu24.04

ENV DEBIAN_FRONTEND=noninteractive
ENV PIP_BREAK_SYSTEM_PACKAGES=1
ENV HF_HUB_OFFLINE=1

RUN apt-get update && apt-get install -y --no-install-recommends \
        python3 python3-pip \
    && rm -rf /var/lib/apt/lists/*

COPY pipeline/requirements.txt /tmp/requirements.txt
RUN pip3 install --no-cache-dir -r /tmp/requirements.txt && rm /tmp/requirements.txt

COPY --from=build /out/pipeline /app/pipeline

ENTRYPOINT ["/app/pipeline", "--config", "/configs/config.toml"]
