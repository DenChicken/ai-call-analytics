ARG LLAMA_VERSION
ARG LLAMA_CPU_INDEX
ARG LLAMA_CUDA_ARCHITECTURES
ARG LLAMA_CUDA_CMAKE_ARGS


FROM nvidia/cuda:12.6.3-cudnn-devel-ubuntu24.04 AS llama

ARG LLAMA_VERSION
ARG LLAMA_CUDA_ARCHITECTURES
ARG LLAMA_CUDA_CMAKE_ARGS

ENV DEBIAN_FRONTEND=noninteractive
ENV PIP_BREAK_SYSTEM_PACKAGES=1

RUN apt-get update && apt-get install -y --no-install-recommends \
        python3 python3-pip python3-dev build-essential cmake \
    && rm -rf /var/lib/apt/lists/*

RUN CMAKE_ARGS="${LLAMA_CUDA_CMAKE_ARGS} -DCMAKE_CUDA_ARCHITECTURES=${LLAMA_CUDA_ARCHITECTURES}" \
    pip3 wheel --no-cache-dir --no-deps -w /wheel \
        llama-cpp-python==${LLAMA_VERSION}


FROM nvidia/cuda:12.6.3-cudnn-runtime-ubuntu24.04 AS base

ARG LLAMA_VERSION
ARG LLAMA_CPU_INDEX

ENV DEBIAN_FRONTEND=noninteractive
ENV PIP_BREAK_SYSTEM_PACKAGES=1
ENV PYTHONDONTWRITEBYTECODE=1

RUN apt-get update && apt-get install -y --no-install-recommends \
        python3 python3-pip libgomp1 \
    && rm -rf /var/lib/apt/lists/*

COPY pipeline/requirements.txt /tmp/requirements.txt
RUN pip3 install --no-cache-dir -r /tmp/requirements.txt && rm /tmp/requirements.txt

RUN pip3 install --no-cache-dir --no-deps --only-binary :all: \
        --extra-index-url ${LLAMA_CPU_INDEX} \
        --target /opt/llama/cpu \
        llama-cpp-python==${LLAMA_VERSION}

COPY --from=llama /wheel /tmp/wheel
RUN pip3 install --no-cache-dir --no-deps --target /opt/llama/cuda /tmp/wheel/*.whl \
    && rm -rf /tmp/wheel


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
