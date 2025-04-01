import logging
import subprocess
import platform
import atexit
import threading
import types
import os

from .install import find_existing_mm_install
from pymmcore import CMMCore
import pymmcore
from pyjavaz import DEFAULT_BRIDGE_PORT, server_terminated


import re

logger = logging.getLogger(__name__)


#### Some functions to normalize the API between the Java and Python backends

class TaggedImage:

    def __init__(self, tags, pix):
        self.tags = tags
        self.pix = pix

def pop_next_tagged_image(self):
    md = pymmcore.Metadata()
    pix = self.pop_next_image_md(0, 0, md)
    tags = {key: md.GetSingleTag(key).GetValue() for key in md.GetKeys()}
    return TaggedImage(tags, pix)

def get_tagged_image(core, cam_index, camera, height, width, binning=None, pixel_type=None, roi_x_start=None,
                     roi_y_start=None):
    """
    Different signature than the Java version because of difference in metadata handling in the swig layers
    """
    pix = core.get_image()
    md = pymmcore.Metadata()
    # most of the same tags from pop_next_tagged_image, which may not be the same as the MMCoreJ version of this function
    tags = {'Camera': camera, 'Height': height, 'Width': width, 'PixelType': pixel_type,
            'CameraChannelIndex': cam_index}
    # Could optionally add these for completeness but there might be a performance hit
    if binning is not None:
        tags['Binning'] = binning
    if roi_x_start is not None:
        tags['ROI-X-start'] = roi_x_start
    if roi_y_start is not None:
        tags['ROI-Y-start'] = roi_y_start

    return TaggedImage(tags, pix)

def _camel_to_snake(name):
    """
    Convert camelCase string to snake_case
    """
    s1 = re.sub('(.)([A-Z][a-z]+)', r'\1_\2', name)
    return re.sub('([a-z0-9])([A-Z])', r'\1_\2', s1).lower()

def _create_pymmcore_instance():
    """
    Make a subclass of CMMCore with all methods converted to snake_case
    """

    # Create a new dictionary for the class attributes
    new_attributes = {}

    # Iterate through the original attributes
    for attr_name, attr_value in vars(CMMCore).items():
        # If it's a dunder method, skip it (we don't want to override these)
        if attr_name.startswith("__") and attr_name.endswith("__"):
            continue
        # If the attribute is callable (i.e., a method), convert its name to snake_case and add it
        if callable(attr_value):
            new_attr_name = _camel_to_snake(attr_name)
            new_attributes[new_attr_name] = attr_value

    # Create and return a new class that subclasses the original class and has the new attributes
    clz = type(CMMCore.__name__ + "SnakeCase", (CMMCore,), new_attributes)

    instance = clz()

    return instance


_JAVA_HEADLESS_SUBPROCESSES : dict[int, subprocess.Popen] = {}
_PYMMCORES = []

def is_pymmcore_active():
    """
    Check if any Python headless instance of Micro-Manager core is active.
    """
    return len(_PYMMCORES) > 0

def is_java_active():
    """
    Check if any Java headless instance of Micro-Manager core is active.
    """
    return len(_JAVA_HEADLESS_SUBPROCESSES) > 0

def is_java_port_allocated(port: int):
    """
    Check if a port is already allocated for a Java headless instance of Micro-Manager core.
    """
    return port in _JAVA_HEADLESS_SUBPROCESSES

def active_java_ports():
    """
    Get the ports of active Java headless instances of Micro-Manager core.
    """
    return list(_JAVA_HEADLESS_SUBPROCESSES.keys())

def terminate_java_instances(debug=False, port: int = None):
    """
    Terminate headless instances of Micro-Manager core started with the Java backend.

    Parameters
    ----------
    debug : bool
        Print debug messages
    port : int
        Port of the server to terminate. If None, all servers will be terminated
    """
    if not is_java_active():
        logger.debug('No Java instances to stop')
        return

    for key in active_java_ports():
        if port and port != key:
            continue

        process = _JAVA_HEADLESS_SUBPROCESSES[key]
        if debug:
            logger.debug(f'Stopping headless process with pid {process.pid}')
        process.terminate()
        server_terminated(key)
        if debug:
            logger.debug(f'Waiting for process with pid {process.pid} to terminate')
        process.wait()  # wait for process to terminate
        if debug:
            logger.debug(f'Process with pid {process.pid} terminated')
        del _JAVA_HEADLESS_SUBPROCESSES[key]

def terminate_pymmcore_instances(debug=False):
    """
    Terminate headless instances of Micro-Manager core started with the Python backend.
    """
    if not is_pymmcore_active():
        logger.debug('No pymmcore instances to stop')
        return

    if debug:
        logger.debug('Stopping {} pymmcore instances'.format(len(_PYMMCORES)))
    for c in _PYMMCORES:
        if debug:
            logger.debug('Stopping pymmcore instance')
        c.unloadAllDevices()
        if debug:
            logger.debug('Unloaded all devices')
        if debug:
            logger.debug('Engine shut down')
    _PYMMCORES.clear()
    if debug:
        logger.debug('Headless stopped')

def terminate_core_instances(debug=False):
    """
    Terminate all headless instances of Micro-Manager core.
    """
    terminate_java_instances(debug)
    terminate_pymmcore_instances(debug)
    

# make sure any Java processes are cleaned up when Python exits
atexit.register(terminate_core_instances)

def create_core_instance(
    mm_app_path: str = 'auto', config_file: str='MMConfig_demo.cfg', java_loc: str=None,
        python_backend=True, core_log_path: str='',
        buffer_size_mb: int=1024, max_memory_mb: int=2000,
        port: int=DEFAULT_BRIDGE_PORT, debug=False):
    """
    Start an instance of the Micro-Manager core in headless mode. This can be either a Python (i.e. pymmcore)
    or Java (i.e. MMCoreJ) backend. If a Python backend is used, the core will be started in the same process.

    On windows plaforms, the Java Runtime Environment will be grabbed automatically
    as it is installed along with the Micro-Manager application.

    On non-windows platforms, it may need to be installed/specified manually in order to ensure compatibility.
    Installing Java 11 is the most likely version to work without issue

    Parameters
    ----------
    mm_app_path : str
        Path to top level folder of Micro-Manager installation (made with graphical installer). If 'auto', it will
        use the default install location for the current OS
    config_file : str
        Path to micro-manager config file, with which core will be initialized. If None then initialization
        is left to the user.
    java_loc: str
        Path to the java version that it should be run with (Java backend only)
    python_backend : bool
        Whether to use the python backend or the Java backend
    core_log_path : str
        Path to where core log files should be created
    buffer_size_mb : int
        Size of circular buffer in MB in MMCore
    max_memory_mb : int
        Maximum amount of memory to be allocated to JVM (Java backend only
    port : int
        Default port to use for ZMQServer (Java backend only)
    debug : bool
        Print debug messages
    """
    if mm_app_path == 'auto':
        mm_app_path = find_existing_mm_install()

    # if config file is not an absolute path, assume it is relative to the mm_app_path
    if config_file is not None and not os.path.isabs(config_file):
        config_file = os.path.join(mm_app_path, config_file)

    if python_backend:
        mmc = _create_pymmcore_instance()
        mmc.set_device_adapter_search_paths([mm_app_path])
        if config_file is not None and config_file != "":
            mmc.load_system_configuration(config_file)
        mmc.set_circular_buffer_memory_footprint(buffer_size_mb)
        _PYMMCORES.append(mmc) # Store so it doesn't get garbage collected

        ##  Some hacks to somewhat mimic the MMCoreJ API
        mmc.get_tagged_image = types.MethodType(get_tagged_image, mmc)
        mmc.pop_next_tagged_image = types.MethodType(pop_next_tagged_image, mmc)
        # attach TaggedImage class
        mmc.TaggedImage = TaggedImage
    else:
        if is_java_port_allocated(port):
            raise Exception(f'Port {port} already in use')

        classpath = mm_app_path + '/plugins/Micro-Manager/*'
        if java_loc is None:
            if platform.system() == "Windows":
                # windows comes with its own JRE
                java_loc = mm_app_path + "/jre/bin/javaw.exe"
            else:
                java_loc = "java"
        if debug:
            logger.debug(f'Java location: {java_loc}')
            #print classpath
            logger.debug(f'Classpath: {classpath}')
            # print stuff in the classpath directory
            logger.debug('Contents of classpath directory:')
            for f in os.listdir(classpath.split('*')[0]):
                logger.debug(f)

        # This starts Java process and instantiates essential objects (core,
        # acquisition engine, ZMQServer)
        process = subprocess.Popen(
                [
                    java_loc,
                    "-classpath",
                    classpath,
                    "-Dsun.java2d.dpiaware=false",
                    f"-Xmx{max_memory_mb}m",
                    # This is used by MM desktop app but breaks things on MacOS...Don't think its neccessary
                    # "-XX:MaxDirectMemorySize=1000",
                    # TODO: this code also launches the java acquisition engine, which is technically not needed
                    #  for headless mode, but is unlikely to cause issues
                    "org.micromanager.remote.HeadlessLauncher",
                    str(port),
                    config_file if config_file is not None else '',
                    str(buffer_size_mb),
                    core_log_path,
                ], cwd=mm_app_path, stdout=subprocess.PIPE
            )
        process.port = port
        _JAVA_HEADLESS_SUBPROCESSES[port] = process

        started = False
        output = True
        # Some drivers output various status messages which need to be skipped over to look for the STARTED token.
        while output and not started:
            output = process.stdout.readline()
            started = "STARTED" in output.decode('utf-8')
        if not started:
            raise Exception('Error starting headless mode')
        if debug:
            logger.debug('Headless mode started')
            def loggerFunction():
                while process in _JAVA_HEADLESS_SUBPROCESSES.values():
                    line = process.stdout.readline().decode('utf-8')
                    if line.strip() != '':
                        logger.debug(line)
            threading.Thread(target=loggerFunction).start()


