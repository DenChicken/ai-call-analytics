# speech-analysis-engine

speech-analysis-engine automatically reviews sales calls. It takes call recordings from a CRM, converts them to text, and uses a language model to check how well the manager handled each conversation. The results are shown in a web interface.

The system runs entirely on your own server. Speech recognition and the language model work locally, so recordings and results are never sent anywhere.

It is made of three services that share one PostgreSQL database:

- **fetcher** downloads new calls from the CRM.
- **pipeline** transcribes each call and scores it against your criteria.
- **webui** shows the results by company, by manager, and by call.

Scoring criteria and other settings are stored in simple `.toml` files, so you can change what the system checks without changing the code. The services run in Docker, on a CPU or an NVIDIA GPU.

## Documentation

Installation, configuration, and usage guides are in [docs/](docs/). The documentation is currently available in [RU](docs/ru/README.md).
