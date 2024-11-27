import os
import sys

def get_resource_path(filename):
    if getattr(sys, 'frozen', False):
        # Running from a bundled executable
        base_path = sys._MEIPASS
    else:
        # Running as a script
        base_path = os.path.dirname(__file__)

    return os.path.join(base_path, filename)

def get_restic_path():
    if getattr(sys, 'frozen', False):
        # Running from a bundled executable
        return get_resource_path('restic')
    else:
        # Running as a script
        return './restic'

def get_static_directory():
    if getattr(sys, 'frozen', False):
        # Running from a bundled executable
        return get_resource_path('static')
    else:
        # Running as a script
        return './static'