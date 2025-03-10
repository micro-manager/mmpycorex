import threading
from pyjavaz import JavaObject, PullSocket, DEFAULT_BRIDGE_PORT

from .launcher import  _PYMMCORES

class _CoreCallback:
    """
    A class for recieving callbacks from the core, which are mostly used
    for the case where some hardware has changed
    See (https://github.com/micro-manager/mmCoreAndDevices/blob/main/MMCore/CoreCallback.cpp)

    """

    def __init__(self, callback_fn=None, bridge_port=DEFAULT_BRIDGE_PORT):
        self._closed = False
        self._thread = threading.Thread(
            target=self._callback_recieving_fn,
            name="CoreCallback",
            args=(bridge_port, self),
        )
        self.callback_fn = callback_fn
        self._thread.start()

    def _callback_recieving_fn(self, bridge_port, core_callback):
        callback_java = JavaObject(
            "org.micromanager.remote.RemoteCoreCallback", args=(ZMQRemoteMMCoreJ(port=bridge_port),)
        )

        camel_case = hasattr(callback_java, "getPushPort")
        port = callback_java.getPushPort() if camel_case else callback_java.get_push_port()
        pull_socket = PullSocket(port)
        callback_java.startPush() if camel_case else callback_java.start_push()

        while True:
            message = pull_socket.receive(timeout=100)
            if message is not None:
                core_callback._set_value(message)
            if core_callback._closed:
                callback_java.shutdown()
                break

    def _set_value(self, value):
        """
        Call the callback function
        :return:

        """
        function_name = value["name"]
        function_args = value["arguments"] if "arguments" in value else tuple()

        if self.callback_fn is not None:
            self.callback_fn(function_name, *function_args)

    def __del__(self):
        self._closed = True
        self._thread.join()


class ZMQRemoteMMCoreJ(JavaObject):
    """
    Remote instance of Micro-Manager Core
    """

    def __new__(
        cls, convert_camel_case=True, port=DEFAULT_BRIDGE_PORT, new_socket=False, debug=False, timeout=1000,
    ):
        """
        Parameters
        ----------
        convert_camel_case: bool
            If True, methods for Java objects that are passed across the bridge
            will have their names converted from camel case to underscores. i.e. class.methodName()
            becomes class.method_name()
        port: int
            The port of the Bridge used to create the object
        new_socket: bool
            If True, will create new java object on a new port so that blocking calls will not interfere
            with the bridges main port
        debug:
            print debug messages
        timeout:
            timeout for underlying bridge
        """
        try:
            core = JavaObject("mmcorej.CMMCore", new_socket=new_socket,
                      port=port, timeout=timeout, convert_camel_case=convert_camel_case, debug=debug)
            
            def register_core_callback_wrapper(callback_fn=None, bridge_port=DEFAULT_BRIDGE_PORT):
                """
                Get a CoreCallback function that will fire callback_fn with (name, *args) each
                time MMCore emits a callback signal

                callback_fn: Callable
                    a function that takes (name, *args)
                bridge_port: int
                    port of the Core instance to get callbacks from
                """
                return _CoreCallback(callback_fn=callback_fn, bridge_port=bridge_port)
            
            core.register_core_callback = register_core_callback_wrapper
            return core
        except Exception as e:
            raise Exception(f"Couldn't create Core. Is Micro-Manager running and is the ZMQ server on {port} option enabled?")


class Core:
    """
    Return a remote Java ZMQ Core, or a local Python Core, if the start_headless has been called with a Python backend
    """

    def __new__(cls, **kwargs):
        if _PYMMCORES:
            return _PYMMCORES[0]
        else:
            return ZMQRemoteMMCoreJ(**kwargs)

