"""Run a bounded subprocess and clean up its process group on timeout/cancellation."""
import asyncio
import os
import signal
import time


async def run_process(args, workspace, timeout=600, progress=None):
    proc = await asyncio.create_subprocess_exec(
        *args, cwd=workspace, stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE, start_new_session=(os.name != "nt"),
    )
    communication = asyncio.create_task(proc.communicate())
    started = time.monotonic()
    try:
        while True:
            remaining = timeout - (time.monotonic() - started)
            if remaining <= 0:
                raise TimeoutError(f"Execution timed out after {timeout:g} seconds")
            done, _ = await asyncio.wait({communication}, timeout=min(10, remaining))
            if done:
                stdout, stderr = communication.result()
                return {"exit_code": proc.returncode,
                        "stdout": stdout.decode("utf-8", errors="replace"),
                        "stderr": stderr.decode("utf-8", errors="replace")}
            if progress:
                await progress(time.monotonic() - started)
    finally:
        if not communication.done():
            try:
                if os.name != "nt":
                    os.killpg(proc.pid, signal.SIGKILL)
                else:
                    proc.kill()
            except ProcessLookupError:
                pass
            await proc.wait()
            communication.cancel()
            await asyncio.gather(communication, return_exceptions=True)
