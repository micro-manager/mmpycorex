[![License](https://img.shields.io/pypi/l/mmpycorex.svg)](https://github.com/micro-manager/mmpycorex/raw/master/LICENSE)
[![PyPI](https://img.shields.io/pypi/v/mmpycorex.svg)](https://pypi.org/project/mmpycorex)

# mmpycorex

This package contains modules for downloading and installing MM through python, and for accessing the Java core of
a running micro-manager instance, creating a headless java core object for access through python, or creating and instance of
the python wrapper of the core (pymmcore)

### Installation

`pip install mmpycorex`

## Programatically installing Micro-Manager
- Python utility functions for downloading and installing Micro-Manager
```python
from mmpycorex import download_and_install_mm, find_existing_mm_install

# this automatically installs the latest nightly build
# specify destination="your/custom/path", otherwise it will default to 'C:/Program files/Micro-Manager/'
# on windows or the home directory on mac
installed_path = download_and_install_mm()
```

## Accessing the Java core through python
```python
### Java Core example
from mmpycorex import create_core_instance, terminate_core_instances, get_default_install_location

# If micro-manager is alread running, you can get access to the core directly
# (just make sure the "run server" in the tools options dialog is checked)

# Otherwise you must create an instance of the Core in headless mode
mm_location = get_default_install_location() # 'C:/Program files/Micro-Manager/'
config_file = 'MMConfig_demo.cfg'
create_core_instance(mm_location, config_file, python_backend=False) # Create a remote MMCoreJ object

# Now that a core is running (either through the MM App or headless mode), create an object to access it
core = Core()

#### use the core

terminate_core_instances() 
```

## Accessing the python core (pymmcore)
```python
### pymmcore example
from mmpycorex import create_core_instance, terminate_core_instances

# Otherwise you must create an instance of the Core in headless mode
mm_location = get_default_install_location() # 'C:/Program files/Micro-Manager/'
config_file = 'MMConfig_demo.cfg'
create_core_instance(mm_location, config_file, python_backend=True) # Create pymmcore instance

# Now that a core is running (either through the MM App or headless mode), create an object to access it
core = Core()

#### use the core

terminate_core_instances() 
```

## Install issues on M1 Macs

https://github.com/conda-forge/miniforge/issues/165#issuecomment-860233092

   
