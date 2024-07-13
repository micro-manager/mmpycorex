[![License](https://img.shields.io/pypi/l/mmpycorex.svg)](https://github.com/micro-manager/mmpycorex/raw/master/LICENSE)
[![PyPI](https://img.shields.io/pypi/v/mmpycorex.svg)](https://pypi.org/project/mmpycorex)

# mmpycorex

This package contains:
- A unified `Core` for using MMCore through python, either using `pymmcore` or using the ZMQ-remote MMCoreJ.
- functions for launching MMCore instances
- Python utility functions for downloading and installing Micro-Manager
```python
from mmpycorex import download_and_install_mm, find_existing_mm_install
```
   
