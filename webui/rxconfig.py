import reflex as rx
from reflex_base.plugins.sitemap import SitemapPlugin
from reflex_components_radix.plugin import RadixThemesPlugin

from src import context

APP_NAME = "webui"
APP_MODULE_IMPORT = "src.app"

APPEARANCE = "light"
ACCENT_COLOR = "indigo"
GRAY_COLOR = "slate"
RADIUS = "medium"

server = context.config().server

config = rx.Config(
    app_name=APP_NAME,
    app_module_import=APP_MODULE_IMPORT,
    frontend_port=server.frontend_port,
    backend_port=server.backend_port,
    api_url=server.api_url,
    plugins=[
        RadixThemesPlugin(
            theme=rx.theme(
                appearance=APPEARANCE,
                accent_color=ACCENT_COLOR,
                gray_color=GRAY_COLOR,
                radius=RADIUS,
            )
        )
    ],
    disable_plugins=[SitemapPlugin],
)
