"""Windows Process Management module."""

import os
import subprocess
import time
from typing import List, Sequence, Union
import psutil

from storage.logger import logger


class ProcessManager:
    """Handles process inspection, graceful termination, launching, and verification."""

    @staticmethod
    def _normalize_names(process_names: Union[str, Sequence[str]]) -> List[str]:
        if isinstance(process_names, str):
            return [process_names.lower()]
        return [name.lower() for name in process_names]

    @classmethod
    def find_processes(cls, process_names: Union[str, Sequence[str]]) -> List[psutil.Process]:
        """Finds all running processes matching any of the given process names."""
        targets = cls._normalize_names(process_names)
        target_stems = {t.removesuffix(".exe") for t in targets if t}
        target_full = {t if t.endswith(".exe") else f"{t}.exe" for t in targets if t}

        matches: List[psutil.Process] = []
        for proc in psutil.process_iter(["pid", "name"]):
            try:
                raw_name = proc.info.get("name")
                if not raw_name or not raw_name.strip():
                    continue
                name = raw_name.lower().strip()
                name_stem = name.removesuffix(".exe")

                if name in target_full or name_stem in target_stems:
                    matches.append(proc)
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                continue
        return matches

    @classmethod
    def is_running(cls, process_names: Union[str, Sequence[str]]) -> bool:
        """Returns True if at least one matching process is actively running."""
        return len(cls.find_processes(process_names)) > 0

    @classmethod
    def terminate(
        cls,
        process_names: Union[str, Sequence[str]],
        grace_period: float = 3.5,
        force_timeout: float = 1.5,
    ) -> bool:
        """
        Gracefully terminates matching processes, waiting up to grace_period seconds.
        If any process remains alive after grace_period, forcefully kills it.
        Returns True if all matching processes have terminated.
        """
        procs = cls.find_processes(process_names)
        if not procs:
            return True

        logger.info("Attempting graceful termination of %d process(es) matching %s", len(procs), process_names)

        # Step 1: Send terminate signal
        for p in procs:
            try:
                p.terminate()
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass

        # Step 2: Wait for processes to exit
        try:
            gone, alive = psutil.wait_procs(procs, timeout=grace_period)
        except Exception as ex:
            logger.debug("wait_procs exception: %s", ex)
            alive = [p for p in procs if p.is_running()]

        # Step 3: Force kill any still running
        if alive:
            logger.warning("%d process(es) still alive after grace period. Sending kill...", len(alive))
            for p in alive:
                try:
                    p.kill()
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass
            try:
                gone_forced, still_alive = psutil.wait_procs(alive, timeout=force_timeout)
            except Exception:
                still_alive = [p for p in alive if p.is_running()]

            if still_alive:
                logger.error("Failed to terminate %d process(es).", len(still_alive))
                return False

        logger.info("Successfully terminated all processes matching %s.", process_names)
        return True

    @classmethod
    def launch(
        cls,
        launch_command: Union[str, List[str]],
        verify_process_names: Union[str, Sequence[str], None] = None,
        verify_timeout: float = 5.0,
    ) -> bool:
        """
        Launches an application and optionally verifies that the process starts within verify_timeout.
        """
        logger.info("Launching application: %s", launch_command)
        try:
            if isinstance(launch_command, str) and (
                os.path.isabs(launch_command) or launch_command.endswith((".exe", ".cmd", ".bat"))
            ):
                try:
                    os.startfile(launch_command)
                except Exception as ex:
                    logger.debug("os.startfile failed, falling back to subprocess.Popen: %s", ex)
                    subprocess.Popen(
                        launch_command,
                        shell=True,
                        creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP,
                    )
            elif isinstance(launch_command, str):
                subprocess.Popen(
                    launch_command,
                    shell=True,
                    creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP,
                )
            else:
                subprocess.Popen(
                    launch_command,
                    creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP,
                )

            if not verify_process_names:
                return True

            # Verify process actually started
            start_time = time.time()
            while time.time() - start_time < verify_timeout:
                if cls.is_running(verify_process_names):
                    logger.info("Verified process is running: %s", verify_process_names)
                    return True
                time.sleep(0.3)

            logger.error("Process launch verification timed out for %s", verify_process_names)
            return False

        except Exception as e:
            logger.error("Failed to launch application (%s): %s", launch_command, e)
            return False
