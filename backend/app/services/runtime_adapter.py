"""Provider boundary: one invocation, streaming, exact resume, and local probes."""
import os
from app.services.process_runner import run_process
from app.services.runtime_events import AntigravityStream


class AntigravityAdapter:
    def __init__(self, executable, executor=run_process):
        self.executable = executable
        self.executor = executor

    async def get_capabilities(self, workspace):
        help_result = await self.executor([self.executable, '--help'], workspace, 10)
        version = await self.executor([self.executable, '--version'], workspace, 10)
        text = help_result['stdout'] + help_result['stderr']
        return {'provider': 'antigravity-cli', 'version': version['stdout'].strip()[:120],
                'probe_status': 'PASSED' if help_result['exit_code'] == 0 else 'FAILED',
                'streaming': '--output-format' in text and 'stream-json' in text,
                'exact_session_resume': '--conversation' in text, 'sandbox': '--sandbox' in text,
                'live_instruction_injection': False}

    async def start_task(self, prompt, workspace, timeout, effort, readonly=False,
                         emit=None, progress=None, conversation_id=None, model=None):
        args = [self.executable, '--add-dir', workspace, '-p', prompt,
                '--effort', effort, '--print-timeout', f'{timeout:g}s',
                '--output-format', 'stream-json', '--disable-slash-commands',
                '--sandbox', '--mode', 'plan' if readonly else 'accept-edits']
        if conversation_id:
            args += ['--conversation', conversation_id]
        if model:
            args += ['--model', model]
        if os.name == 'nt' and self.executable.lower().endswith(('.cmd', '.bat')):
            args = ['cmd.exe', '/c', *args]
        stream = AntigravityStream(emit)
        result = await self.executor(args, workspace, timeout, progress, stream.feed)
        return stream.final_result(result), stream

    async def resume_task(self, conversation_id, **kwargs):
        if not conversation_id:
            raise ValueError('Exact conversation ID required for session resume')
        return await self.start_task(conversation_id=conversation_id, **kwargs)

    async def interrupt(self, invocation):
        # run_process owns process-group teardown; await it before claiming paused.
        invocation.cancel()
        import asyncio
        await asyncio.gather(invocation, return_exceptions=True)
