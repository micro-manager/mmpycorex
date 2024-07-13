"""
mmpycorex package

This package provides access to pymmcore and the ZeroMQ wrapper to MMCoreJ,
along with associated utilities for downloading and running headless.
"""
from ._version import __version__, version_info

from .headless import create_core_instance, terminate_core_instances
from .core import Core
from .install import download_and_install_mm, find_existing_mm_install
