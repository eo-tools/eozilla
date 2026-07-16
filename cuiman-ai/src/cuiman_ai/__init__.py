from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("cuiman-ai")
except PackageNotFoundError:  # pragma: no cover - useful while running from source
    __version__ = "0.0.0+unknown"

__all__ = ["__version__"]
