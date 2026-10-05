"""
Strop Core — Shared utilities, hardware detection, theme engine, and preset management.
"""

import os
# Set default OpenGL renderer for GTK4 (suppresses RADV non-conformant warning)
if "GSK_RENDERER" not in os.environ:
    os.environ["GSK_RENDERER"] = "gl"


__version__ = "1.0.0"




