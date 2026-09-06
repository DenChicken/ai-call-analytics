FROM python:3.14.7-slim AS base

ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONDONTWRITEBYTECODE=1

RUN apt-get update && apt-get install -y --no-install-recommends \
        curl unzip \
    && rm -rf /var/lib/apt/lists/*

COPY webui/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt && rm /tmp/requirements.txt


FROM base AS build

RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential patchelf \
    && rm -rf /var/lib/apt/lists/* \
    && pip install --no-cache-dir nuitka

WORKDIR /build

COPY licensing ./licensing
RUN python -m nuitka \
        --mode=package \
        --assume-yes-for-downloads \
        --remove-output \
        --output-dir=/out/webui \
        licensing \
    && rm -f /out/webui/licensing*.pyi

COPY webui/main.py webui/rxconfig.py /out/webui/
COPY webui/src /out/webui/src

RUN cd /out/webui && python -m compileall -q -b -o 2 src main.py rxconfig.py \
    && find . -name '*.py' ! -name 'rxconfig.py' ! -name 'app.py' -delete \
    && rm -f rxconfig.pyc src/app.pyc \
    && find . -name '__pycache__' -type d -exec rm -rf {} +

RUN cd /out/webui && python -c \
        "import licensing.license as l, licensing.verify_runtime as v; \
         assert l.PUBLIC_KEY, 'public key is empty'; \
         assert 'compiled' in type(v.load).__name__, 'not the compiled module'"

RUN cd /out/webui && python -m reflex export --frontend-only --no-zip \
    && rm -rf .web/node_modules


FROM base

COPY --from=build /out/webui /app

WORKDIR /app

ENTRYPOINT ["python", "main.pyc", "--config", "/configs/config.toml"]
