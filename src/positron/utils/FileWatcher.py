import logging
import os
import time
from typing import Callable

from watchdog.events import FileSystemEvent, FileSystemEventHandler
from watchdog.observers import Observer

from positron.util import acall, create_task


########################## FileWatcher #############################
class FileWatcher(FileSystemEventHandler):
    """
    A FileWatcher is really just a watchdog Eventhandler that holds a set of files to be watched.

    Add a file to be watched with the add_file function
    """

    def __init__(self):
        self.last_hit = time.monotonic()  # this doesn't need to be extremely accurate
        self.files = set[str]()
        self.dirs = set[str]()
        self.callbacks: dict[str, Callable] = {}

    def add_file(self, file: str, callback: Callable):
        file = os.path.abspath(file)
        self.files.add(file)
        self.callbacks[file] = callback
        new_dir = os.path.dirname(file)
        if not new_dir in self.dirs:
            self.dirs.add(new_dir)
            ob = Observer()
            ob.schedule(self, new_dir)
            ob.start()

    def on_modified(self, event: FileSystemEvent):
        path: str = event.src_path
        logging.debug(f"File modified: {path}")
        if path in self.files and (t := time.monotonic()) - self.last_hit > 1:
            create_task(
                acall(self.callbacks[path]),
                sync=True,
            )
            self.last_hit = t


####################################################################
