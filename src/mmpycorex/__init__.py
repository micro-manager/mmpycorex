"""
mmpycorex package

This package provides access to pymmcore and the ZeroMQ wrapper to MMCoreJ,
along with associated utilities for downloading and running headless.
"""
from ._version import __version__, version_info

from .core import Core
from .install import download_and_install_mm, find_existing_mm_install, get_default_install_location
from .launcher import create_core_instance, terminate_core_instances, is_pymmcore_active