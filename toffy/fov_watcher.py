import os
from pathlib import Path
import time
import json
from datetime import datetime
from typing import Callable, List, Tuple
from watchdog.events import FileCreatedEvent, FileSystemEventHandler
from watchdog.observers import Observer


class RunStructure:
    """Expected bin and json files

    Attributes:
        fov_progress (dict): Whether or not an expected file has been created
    """
    def __init__(self, run_folder: str, timeout: int = 10 * 60):
        """ initializes RunStructure by parsing run json within provided run folder

        Args:
            run_folder (str):
                path to run folder
            timeout (int):
                number of seconds to wait for non-null filesize before raising an error
        """
        self.timeout = timeout
        self.fov_progress = {}
        self.processed_fovs = []

        # find run .json and get parameters
        run_name = Path(run_folder).parts[-1]
        with open(os.path.join(run_folder, f'{run_name}.json'), 'r') as f:
            run_metadata = json.load(f)

        # parse run_metadata and populate expected structure
        for fov in run_metadata.get('fovs', ()):
            run_order = fov.get('runOrder', -1)
            scan = fov.get('scanCount', -1)
            if run_order * scan < 0:
                raise KeyError(f"Could not locate keys in {run_folder}.json")

            fov_name = f'fov-{run_order}-scan-{scan}'
            self.fov_progress[fov_name] = {
                'json': False,
                'bin': False,
            }

    def check_run_condition(self, path: str, check_interval: int = 10) -> Tuple[bool, str]:
        """Checks if all requisite files exist and are complete

        Args:
            path (str):
                path to expected file
            check_interval (int):
                number of seconds to wait before re-checking filesize

        Raises:
            TimeoutError

        Returns:
            (bool, str):
                whether or not both json and bin files exist, as well as the name of the point
        """

        if not os.path.exists(path):
            raise FileNotFoundError(f"{path} doesn't exist but was recently created. "
                                    "This should be unreachable...")

        filename = Path(path).parts[-1]

        if len(filename.split('.')) != 2:
            return False, ''

        fov_name, extension = filename.split('.')

        # avoids repeated processing in case of duplicated events
        if fov_name in self.processed_fovs:
            return False, fov_name

        wait_time = 0
        if fov_name in self.fov_progress:
            if extension in self.fov_progress[fov_name]:
                while os.path.getsize(path) == 0:
                    # consider timed out fovs complete
                    if wait_time >= self.timeout:
                        del self.fov_progress[fov_name]
                        raise TimeoutError(f'timed out waiting for {path}...')

                    time.sleep(check_interval)
                    wait_time += check_interval

                self.fov_progress[fov_name][extension] = True

            if all(self.fov_progress[fov_name].values()):
                return True, fov_name

        elif extension == 'bin':
            raise KeyError(f'Found unexpected bin file, {path}...')

        return False, fov_name

    def processed(self, fov_name: str):
        """Notifies run structure that fov has been processed

        Args:
            fov_name (str):
                Name of FoV
        """
        self.processed_fovs.append(fov_name)

    def check_fov_progress(self) -> dict:
        """Condenses internal dictionary to show which fovs have finished

        Returns:
            dict
        """
        return {k: all(self.fov_progress[k].values()) for k in self.fov_progress}


class FOV_EventHandler(FileSystemEventHandler):
    """File event handler for FOV files

    Attributes:
        run_folder (str):
            path to run folder
        watcher_out (str):
            folder to save all callback results + log file
        run_structure (RunStructure):
            expected run file structure + fov_progress status
        per_fov (list):
            callbacks to run on each fov
        per_run (list):
            callbacks to run over the entire run
    """
    def __init__(self, run_folder: str, log_folder: str,
                 per_fov: List[Callable[[str, str], None]],
                 per_run: List[Callable[[str], None]], timeout: int = 1.03 * 60 * 60):
        """Initializes FOV_EventHandler

        Args:
            run_folder (str):
                path to run folder
            log_folder (str):
                path to save outputs to
            per_fov (list):
                callbacks to run on each fov
            per_run (list):
                callbacks to run over the entire run
            timeout (int):
                number of seconds to wait for non-null filesize before raising an error
        """
        super().__init__()
        self.run_folder = run_folder

        self.log_path = os.path.join(log_folder, f'{Path(run_folder).parts[-1]}_log.txt')

        # create run structure
        self.run_structure = RunStructure(run_folder, timeout=timeout)

        self.per_fov = per_fov
        self.per_run = per_run

        for root, dirs, files in os.walk(run_folder):
            for name in files:
                self.on_created(FileCreatedEvent(os.path.join(root, name)))

    def on_created(self, event: FileCreatedEvent):
        """Handles file creation events

        If FOV structure is completed, all callbacks in `per_fov` will be run over the data.
        This function is automatically called; users generally shouldn't call this function

        Args:
            event (FileCreatedEvent):
                file creation event
        """
        super().on_created(event)

        # check if what's created is in the run structure
        try:
            fov_ready, point_name = self.run_structure.check_run_condition(event.src_path)
        except TimeoutError as timeout_error:
            print(f'Encountered TimeoutError error: {timeout_error}')
            logf = open(self.log_path, 'a')
            logf.write(
                f'{datetime.now().strftime("%d/%m/%Y %H:%M:%S")} -- '
                f'{event.src_path} never reached non-zero file size...\n'
            )
            self.check_complete()
            return

        if fov_ready:
            print(f'Discovered {point_name}, begining per-fov callbacks...')
            logf = open(self.log_path, 'a')

            logf.write(
                f'{datetime.now().strftime("%d/%m/%Y %H:%M:%S")} -- '
                f'Extracting {point_name}\n'
            )

            # run per_fov callbacks
            for fov_func in self.per_fov:
                logf.write(
                    f'{datetime.now().strftime("%d/%m/%Y %H:%M:%S")} -- '
                    f'Running {fov_func.__name__} on {point_name}\n'
                )

                fov_func(self.run_folder, point_name)
            self.run_structure.processed(point_name)

            logf.close()
            self.check_complete()

    def check_complete(self):
        """Checks run structure fov_progress status

        If run is complete, all calbacks in `per_run` will be run over the whole run.
        """
        if all(self.run_structure.check_fov_progress().values()):
            logf = open(self.log_path, 'a')

            logf.write(
                f'{datetime.now().strftime("%d/%m/%Y %H:%M:%S")} -- '
                f'All FOVs finished\n'
            )

            # run per_runs
            for run_func in self.per_run:
                logf.write(
                    f'{datetime.now().strftime("%d/%m/%Y %H:%M:%S")} -- '
                    f'Running {run_func.__name__} on whole run\n'
                )

                run_func(self.run_folder)


def start_watcher(run_folder: str, log_folder: str, per_fov: List[Callable[[str, str], None]],
                  per_run: List[Callable[[str, str], None]],
                  completion_check_time: int = 30, zero_size_timeout: int = 1.03 * 60 * 60):
    """ Passes bin files to provided callback functions as they're created

    Args:
        run_folder (str):
            path to run folder
        log_folder (str):
            where to create log file
        per_fov (list):
            list of functions to pass bin files
        per_run (list):
            list of functions to pass whole run
        completion_check_time (int):
            how long to wait before checking watcher completion, in seconds.
            note, this doesn't effect the watcher itself, just when this wrapper function exits.
        zero_size_timeout (int):
            number of seconds to wait for non-zero file size
    """
    observer = Observer()
    event_handler = FOV_EventHandler(run_folder, log_folder, per_fov, per_run, zero_size_timeout)
    observer.schedule(event_handler, run_folder, recursive=True)
    observer.start()

    try:
        while not all(event_handler.run_structure.check_fov_progress().values()):
            time.sleep(completion_check_time)
    except KeyboardInterrupt:
        observer.stop()

    observer.stop()
    observer.join()
