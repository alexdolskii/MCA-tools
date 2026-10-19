"""Supervise command resources and retain evidence after abnormal exits."""

import os
import shutil
import signal
import subprocess
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

import psutil

from .files import write_json
from .run import utc_now


def process_gone(pid, created):
    try:
        process = psutil.Process(pid)
        return (
            process.create_time() != created
            or process.status() == psutil.STATUS_ZOMBIE
        )
    except psutil.NoSuchProcess:
        return True
    except psutil.Error:
        return False


def run_command(command, arguments):
    root = Path(
        os.environ.get("MCA_RUNTIME_HOME", str(Path.home() / ".mca-tools"))
    ).expanduser()
    if not root.is_absolute():
        raise ValueError("MCA_RUNTIME_HOME must be an absolute path")
    run_id = (
        datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ_")
        + uuid.uuid4().hex[:12]
    )
    directory, temporary = root / "runs" / run_id, root / "tmp" / run_id
    directory.mkdir(parents=True)
    temporary.mkdir(parents=True)
    owner = {"run_id": run_id, "path": str(temporary.resolve())}
    write_json(temporary / ".mca-owner.json", owner)
    record = {
        "run_id": run_id,
        "command": command,
        "arguments": list(arguments),
        "started_utc": utc_now(),
        "temporary_directory": str(temporary),
        "process_status": "STARTING",
        "cleanup": "PENDING",
    }
    write_json(directory / "run.json", record)
    print(f"Run resources: {directory}", flush=True)
    env = dict(os.environ)
    env.update(
        MCA_WORKER="1",
        MCA_RUN_DIR=str(directory),
        MCA_RUN_TMP=str(temporary),
        TMPDIR=str(temporary),
        TMP=str(temporary),
        TEMP=str(temporary),
    )
    processes = {}
    observed = True
    interrupted = None
    child = None
    try:
        child = subprocess.Popen(
            [sys.executable, "-m", "mca_tools.cli", command, *arguments],
            env=env,
            start_new_session=os.name != "nt",
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP
            if os.name == "nt"
            else 0,
        )
        record.update(process_status="RUNNING", pid=child.pid)
        write_json(directory / "run.json", record)
        while child.poll() is None:
            try:
                process = psutil.Process(child.pid)
                for member in [process, *process.children(recursive=True)]:
                    processes[member.pid] = member.create_time()
            except psutil.NoSuchProcess:
                pass
            except psutil.Error:
                observed = False
            try:
                child.wait(timeout=0.2)
            except subprocess.TimeoutExpired:
                pass
            except KeyboardInterrupt:
                if interrupted is None:
                    interrupted = time.monotonic()
                    child.send_signal(
                        signal.CTRL_BREAK_EVENT
                        if os.name == "nt"
                        else signal.SIGINT
                    )
            if (
                interrupted
                and time.monotonic() - interrupted > 15
                and child.poll() is None
            ):
                child.terminate()
                try:
                    child.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    child.kill()
                    child.wait()
        code = 130 if interrupted else child.returncode
        exited = (
            observed
            and bool(processes)
            and all(
                process_gone(pid, created)
                for pid, created in processes.items()
            )
        )
        record.update(
            process_status="EXITED",
            exit_code=code,
            observed_processes=processes,
            process_observation="COMPLETE"
            if observed and processes
            else "INCOMPLETE",
            all_observed_processes_exited=exited,
        )
        if code in (0, 130) and exited and not temporary.is_symlink():
            import json

            marker = json.loads((temporary / ".mca-owner.json").read_text())
            if marker == owner and str(temporary.resolve()) == owner["path"]:
                shutil.rmtree(temporary)
                record["cleanup"] = "COMPLETE"
            else:
                record["cleanup"] = "RETAINED_OWNER_MISMATCH"
        else:
            record["cleanup"] = "RETAINED_FOR_INSPECTION"
        return code
    except BaseException as error:
        record.update(error=str(error), cleanup="RETAINED_FOR_INSPECTION")
        if child is not None and child.poll() is None:
            child.terminate()
            try:
                child.wait(timeout=5)
            except subprocess.TimeoutExpired:
                child.kill()
                child.wait()
        raise
    finally:
        record["finished_utc"] = utc_now()
        write_json(directory / "run.json", record)
        (directory / "runtime.log").write_text(
            f"{record['started_utc']} START {command}\n"
            f"{record['finished_utc']} {record['process_status']} "
            f"exit={record.get('exit_code')} cleanup={record['cleanup']}\n",
            encoding="utf-8",
        )
