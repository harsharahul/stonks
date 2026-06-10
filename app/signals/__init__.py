"""Signal source plugins.

Importing this package registers every bundled plugin with the global
``signal_registry`` (each module uses the ``@register_signal_source``
decorator). Community contributions: add your module here and follow
CONTRIBUTING-SIGNALS.md.
"""
from app.signals import wsb_momentum  # noqa: F401
from app.signals import capitol_trades  # noqa: F401
from app.signals import public_figure_mentions  # noqa: F401
