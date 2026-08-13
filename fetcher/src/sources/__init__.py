from src.config import ConfigError, FetchConfig, NetworkConfig, SourceConfig
from src.source import Source
from src.sources.bitrix import BitrixSource

SOURCE_KINDS = {
    "bitrix24": BitrixSource,
}


def create_source(
    source_config: SourceConfig, network: NetworkConfig, fetch: FetchConfig
) -> Source:
    factory = SOURCE_KINDS.get(source_config.kind)
    if factory is None:
        known = ", ".join(sorted(SOURCE_KINDS))
        raise ConfigError(
            f"unknown source kind '{source_config.kind}' in [[source]] "
            f"'{source_config.name}', known kinds: {known}"
        )
    return factory(source_config, network, fetch)
