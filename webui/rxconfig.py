import reflex as rx
from reflex_base.plugins.sitemap import SitemapPlugin
from reflex_components_radix.plugin import RadixThemesPlugin

APP_NAME = "webui"
APP_MODULE_IMPORT = "src.app"

APPEARANCE = "light"
ACCENT_COLOR = "indigo"
GRAY_COLOR = "slate"
RADIUS = "medium"

CORS_ALLOWED_ORIGINS = ["*"]

config = rx.Config(
    app_name=APP_NAME,
    app_module_import=APP_MODULE_IMPORT,
    cors_allowed_origins=CORS_ALLOWED_ORIGINS,
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
