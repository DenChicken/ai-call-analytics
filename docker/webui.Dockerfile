FROM ubuntu:24.04 AS base

ENV DEBIAN_FRONTEND=noninteractive
ENV PIP_BREAK_SYSTEM_PACKAGES=1
ENV PYTHONDONTWRITEBYTECODE=1

RUN apt-get update && apt-get install -y --no-install-recommends \
        python3 python3-pip curl unzip \
    && rm -rf /var/lib/apt/lists/*

COPY webui/requirements.txt /tmp/requirements.txt
RUN pip3 install --no-cache-dir -r /tmp/requirements.txt && rm /tmp/requirements.txt


FROM base AS build

RUN apt-get update && apt-get install -y --no-install-recommends \
        python3-dev build-essential patchelf \
    && rm -rf /var/lib/apt/lists/* \
    && pip3 install --no-cache-dir nuitka

WORKDIR /build

COPY licensing ./licensing
RUN python3 -m nuitka \
        --mode=package \
        --assume-yes-for-downloads \
        --remove-output \
        --output-dir=/out/webui \
        licensing \
    && rm -f /out/webui/licensing*.pyi

COPY webui/main.py webui/rxconfig.py /out/webui/
COPY webui/src /out/webui/src

RUN cd /out/webui && python3 -m compileall -q -b -o 2 src main.py rxconfig.py \
    && find . -name '*.py' ! -name 'rxconfig.py' ! -name 'app.py' -delete \
    && rm -f rxconfig.pyc src/app.pyc \
    && find . -name '__pycache__' -type d -exec rm -rf {} +

RUN cd /out/webui && python3 -c \
        "import licensing.license as l, licensing.verify_runtime as v; \
         assert l.PUBLIC_KEY, 'public key is empty'; \
         assert 'compiled' in type(v.load).__name__, 'not the compiled module'"

RUN cd /out/webui && python3 -m reflex export --frontend-only --no-zip \
    && rm -rf .web/node_modules


FROM base

COPY --from=build /out/webui /app

WORKDIR /app

ENTRYPOINT ["python3", "main.pyc", "--config", "/configs/config.toml"]
