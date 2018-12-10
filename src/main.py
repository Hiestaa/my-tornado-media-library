# An example of embedding CEF Python in PySide2 application.

import os, sys
import argparse
libcef_dll = os.path.join(os.path.dirname(os.path.abspath(__file__)),
        'libcef.dll')
if os.path.exists(libcef_dll):
    # Import a local module
    if (2,7) <= sys.version_info < (2,8):
        import cefpython_py27 as cefpython
    elif (3,4) <= sys.version_info < (3,4):
        import cefpython_py34 as cefpython
    else:
        raise Exception("Unsupported python version: %s" % sys.version)
else:
    # Import an installed package
    from cefpython3 import cefpython

import PySide2
from PySide2 import QtWidgets
from PySide2 import QtCore
import ctypes
from threading import Thread
import logging

from server_main import Server

def GetApplicationPath(file=None):
    import re, os, platform
    # On Windows after downloading file and calling Browser.GoForward(),
    # current working directory is set to %UserProfile%.
    # Calling os.path.dirname(os.path.realpath(__file__))
    # returns for eg. "C:\Users\user\Downloads". A solution
    # is to cache path on first call.
    if not hasattr(GetApplicationPath, "dir"):
        if hasattr(sys, "frozen"):
            dir = os.path.dirname(sys.executable)
        elif "__file__" in globals():
            dir = os.path.dirname(os.path.realpath(__file__))
        else:
            dir = os.getcwd()
        GetApplicationPath.dir = dir
    # If file is None return current directory without trailing slash.
    if file is None:
        file = ""
    # Only when relative path.
    if not file.startswith("/") and not file.startswith("\\") and (
            not re.search(r"^[\w-]+:", file)):
        path = GetApplicationPath.dir + os.sep + file
        if platform.system() == "Windows":
            path = re.sub(r"[/\\]+", re.escape(os.sep), path)
        path = re.sub(r"[/\\]+$", "", path)
        return path
    return str(file)

def ExceptHook(excType, excValue, traceObject):
    import traceback, os, time, codecs
    # This hook does the following: in case of exception write it to
    # the "error.log" file, display it to the console, shutdown CEF
    # and exit application immediately by ignoring "finally" (os._exit()).
    errorMsg = "\n".join(traceback.format_exception(excType, excValue,
            traceObject))
    errorFile = GetApplicationPath("error.log")
    try:
        appEncoding = cefpython.g_applicationSettings["string_encoding"]
    except:
        appEncoding = "utf-8"
    if type(errorMsg) == bytes:
        errorMsg = errorMsg.decode(encoding=appEncoding, errors="replace")
    try:
        with codecs.open(errorFile, mode="a", encoding=appEncoding) as fp:
            fp.write("\n[%s] %s\n" % (
                    time.strftime("%Y-%m-%d %H:%M:%S"), errorMsg))
    except:
        logging.warning("cefpython: WARNING: failed writing to error file: %s" % (
                errorFile))
    # Convert error message to ascii before printing, otherwise
    # you may get error like this:
    # | UnicodeEncodeError: 'charmap' codec can't encode characters
    errorMsg = errorMsg.encode("ascii", errors="replace")
    errorMsg = errorMsg.decode("ascii", errors="replace")
    logging.error("\n"+errorMsg+"\n")
    cefpython.QuitMessageLoop()
    cefpython.Shutdown()
    os._exit(1)

class MainWindow(QtWidgets.QMainWindow):
    mainFrame = None

    def __init__(self, url):
        super(MainWindow, self).__init__(None)
        self.mainFrame = MainFrame(self, url)
        self.setCentralWidget(self.mainFrame)
        self.resize(1024, 768)
        self.setWindowTitle('Welcome to tornado-vice!')
        self.setFocusPolicy(QtCore.Qt.StrongFocus)
        self.setWindowFlags(QtCore.Qt.FramelessWindowHint)

    def focusInEvent(self, event):
        cefpython.WindowUtils.OnSetFocus(int(self.centralWidget().winIdFixed()), 0, 0, 0)

    def closeEvent(self, event):
        self.mainFrame.browser.CloseBrowser()

class MainFrame(QtWidgets.QWidget):
    browser = None

    def __init__(self, parent=None, url="http://www.google.fr/"):
        super(MainFrame, self).__init__(parent)
        windowInfo = cefpython.WindowInfo()
        windowInfo.SetAsChild(int(self.winIdFixed()))
        self.browser = cefpython.CreateBrowserSync(windowInfo,
                browserSettings={},
                navigateUrl=GetApplicationPath(url))
        self.browser.SetClientCallback('OnPreKeyEvent', self.OnKeyEvent)
        self.show()

    def OnKeyEvent(self,  browser, event, eventHandle, isKeyboardShortcutOut):
        if event['windows_key_code'] == 122:
            if event['type'] == cefpython.KEYEVENT_KEYDOWN or \
                    event['type'] == cefpython.KEYEVENT_RAWKEYDOWN:
                if self.parent().isFullScreen():
                    self.parent().showNormal()
                else:
                    self.parent().showFullScreen()


    def winIdFixed(self):
        # PySide2 bug: QWidget.winId() returns <PyCObject object at 0x02FD8788>,
        # there is no easy way to convert it to int.
        try:
            return int(self.winId())
        except:
            if sys.version_info[0] == 2:
                ctypes.pythonapi.PyCObject_AsVoidPtr.restype = ctypes.c_void_p
                ctypes.pythonapi.PyCObject_AsVoidPtr.argtypes = [ctypes.py_object]
                return ctypes.pythonapi.PyCObject_AsVoidPtr(self.winId())
            elif sys.version_info[0] == 3:
                ctypes.pythonapi.PyCapsule_GetPointer.restype = ctypes.c_void_p
                ctypes.pythonapi.PyCapsule_GetPointer.argtypes = [ctypes.py_object]
                return ctypes.pythonapi.PyCapsule_GetPointer(self.winId(), None)

    def moveEvent(self, event):
        cefpython.WindowUtils.OnSize(int(self.winIdFixed()), 0, 0, 0)

    def resizeEvent(self, event):
        cefpython.WindowUtils.OnSize(int(self.winIdFixed()), 0, 0, 0)

class CefApplication(QtWidgets.QApplication):
    timer = None

    def __init__(self, args):
        super(CefApplication, self).__init__(args)
        self.createTimer()

    def createTimer(self):
        self.timer = QtCore.QTimer()
        self.timer.timeout.connect(self.onTimer)
        self.timer.start(10)

    def onTimer(self):
        # The proper way of doing message loop should be:
        # 1. In createTimer() call self.timer.start(0)
        # 2. In onTimer() call MessageLoopWork() only when
        #    QtWidgets.QApplication.instance()->hasPendingEvents() returns False.
        # But... there is a bug in Qt, hasPendingEvents() returns always true.
        cefpython.MessageLoopWork()

    def stopTimer(self):
        # Stop the timer after Qt message loop ended, calls to MessageLoopWork()
        # should not happen anymore.
        self.timer.stop()

class EmbeddedBrowser(Thread):
    """
    UI-Thread allowing to run the embedded browser.
    """
    def __init__(self, url):
        super(EmbeddedBrowser, self).__init__()
        self.url = url

    def run(self):
        logging.info("PySide2 version: %s" % PySide2.__version__)
        logging.info("QtCore version: %s" % QtCore.__version__)

        sys.excepthook = ExceptHook
        settings = {}
        settings["log_file"] = GetApplicationPath("debug.log")
        settings["log_severity"] = cefpython.LOGSEVERITY_INFO
        settings["release_dcheck_enabled"] = True # Enable only when debugging
        settings["browser_subprocess_path"] = "%s/%s" % (
                cefpython.GetModuleDirectory(), "subprocess")
        cefpython.Initialize(settings)

        app = CefApplication(sys.argv)
        mainWindow = MainWindow(self.url)
        mainWindow.show()
        app.exec_()
        app.stopTimer()

        # Need to destroy QApplication(), otherwise Shutdown() fails.
        # Unset main window also just to be safe.
        del mainWindow
        del app

        cefpython.Shutdown()


def parse_args():
    parser = argparse.ArgumentParser(
        description="Run the tornado-vice application",
        prog="embed")
    parser.add_argument('--verbose', '-v', action="count",
                        help="Set console logging verbosity level. Default \
displays only ERROR messages, -v enable WARNING messages, -vv enable INFO \
messages and -vvv enable DEBUG messages. Ignored if started using daemon.",
                        default=0)
    parser.add_argument('-q', '--quiet', action="store_true",
                        help="Remove ALL logging messages from the console.")
    return parser.parse_args()


import time
from conf import Conf
ready = False
browser = None
def onReady():
    global ready
    ready = True

def onKill():
    print ("Server asked to kill the client!")


if __name__ == '__main__':
    print("Starting server...")
    server = Server(parse_args(), onReady=onReady)
    server.start()
    browser = EmbeddedBrowser("http://localhost:%d" % Conf['server']['port'])
    while not ready:
        time.sleep(0.1)
        continue
    logging.info("Starting browser...")
    # browser can be run synchronously. When closed, the server
    # will be killed
    browser.run()
    # browser.join()
    logging.info("Browser closed, now stopping server.")
    server.stop()
    server.join()
    logging.info("Shutted down.")
