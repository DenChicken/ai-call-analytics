# speech-analysis-engine

**speech-analysis-engine** is a self-hosted AI system for transcription and analysis of recorded speech. It collects audio recordings from an external source such as a CRM, converts them to text, and uses a language model to evaluate each conversation against your own criteria. The results are shown in a web interface.

The system runs entirely on your own server. Speech recognition and the language model work locally, so recordings and results are never sent anywhere.

It is made of three services that share one PostgreSQL database:

- **fetcher** downloads new recordings from the source.
- **pipeline** transcribes each recording and evaluates it against your criteria.
- **webui** shows the results as an overview, per speaker, and per recording.

Evaluation criteria and other settings are stored in simple `.toml` files, so you can change what the system checks without changing the code. The services run in Docker, on a CPU or an NVIDIA GPU.

## Documentation

Installation, configuration, and usage guides are in [docs/](docs/). The documentation is currently available in [RU](docs/ru/README.md).
