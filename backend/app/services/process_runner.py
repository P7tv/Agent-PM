"""Run a bounded subprocess and clean up its process group on timeout/cancellation."""
import asyncio
import os
import signal
import time


async def run_process(args, workspace, timeout=600, progress=None, stdout_line=None, max_output_bytes=2_000_000):
    proc = await asyncio.create_subprocess_exec(
        *args, cwd=workspace, stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE, start_new_session=(os.name != "nt"),
    )
    async def drain(reader, callback=None):
        # Drain both pipes concurrently, even after the retained tail is full.
        tail = bytearray()
        pending = bytearray()
        while True:
            chunk = await reader.read(16384)
            if not chunk:
                break
            tail.extend(chunk)
            if len(tail) > max_output_bytes:
                del tail[:-max_output_bytes]
            if callback:
                pending.extend(chunk)
                while b"\n" in pending:
                    line, _, rest = pending.partition(b"\n")
                    pending = bytearray(rest)
                    if len(line) > max_output_bytes:
                        raise ValueError("Runtime event exceeds output limit")
                    await callback(line.decode("utf-8", errors="replace"))
                if len(pending) > max_output_bytes:
                    raise ValueError("Runtime event exceeds output limit")
        if callback and pending:
            await callback(pending.decode("utf-8", errors="replace"))
        return bytes(tail)

    readers = [asyncio.create_task(drain(proc.stdout, stdout_line)),
               asyncio.create_task(drain(proc.stderr))]
    async def collect():
        output = await asyncio.gather(*readers)
        await proc.wait()
        return output
    communication = asyncio.create_task(collect())
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
        if proc.returncode is None or not communication.done():
            try:
                if os.name != "nt":
                    os.killpg(proc.pid, signal.SIGKILL)
                else:
                    proc.kill()
            except ProcessLookupError:
                pass
            await proc.wait()
            communication.cancel()
            for reader in readers:
                reader.cancel()
            await asyncio.gather(communication, *readers, return_exceptions=True)
