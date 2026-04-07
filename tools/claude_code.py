"""Claude Code integration — headless CLI + real-time dashboard streaming."""

import json
import re
import subprocess
from datetime import datetime
from pathlib import Path
from loguru import logger

_DEFAULT_DIR = r"C:\Projects\jarvis"
_TIMEOUT = 120
_SHORT_LIMIT = 400
_ANSI_RE = re.compile(r'\x1b\[[0-9;]*[a-zA-Z]|\x1b\].*?\x07')


def _push(msg_type: str, content, *, raw_msg: dict = None):
    """Push a message to dashboard WebSocket + history."""
    try:
        from ui.dashboard import _add_to_history, broadcast_to_clients
        if msg_type in ("user", "assistant", "error"):
            _add_to_history(msg_type, content)
        if raw_msg:
            broadcast_to_clients(raw_msg)
        else:
            broadcast_to_clients({"type": msg_type, "content": content})
    except Exception:
        pass


def run_claude_code(prompt: str, directory: str = "") -> str:
    """Run Claude Code with --continue for context, stream to dashboard in real-time."""
    cwd = directory or _DEFAULT_DIR
    try:
        logger.info(f"Claude Code: {prompt[:100]}")
        _push("user", prompt)

        _push("claude_working", "true")

        cmd = ["claude", "-p", prompt]
        try:
            from ui.dashboard import should_skip_continue
            if not should_skip_continue():
                cmd.append("--continue")
        except ImportError:
            cmd.append("--continue")
        cmd += ["--output-format", "stream-json", "--verbose",
                "--include-partial-messages",
                "--dangerously-skip-permissions"]
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, cwd=cwd,
        )

        output_parts = []
        while True:
            line = proc.stdout.readline()
            if not line:
                break
            line = line.strip()
            if not line:
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                clean = _ANSI_RE.sub('', line)
                output_parts.append(clean + "\n")
                _push("claude_stream", clean + "\n")
                continue

            evt_type = event.get("type")
            if evt_type == "stream_event":
                inner = event.get("event", {})
                if inner.get("type") == "content_block_delta":
                    delta = inner.get("delta", {})
                    if delta.get("type") == "text_delta":
                        text = delta.get("text", "")
                        if text:
                            output_parts.append(text)
                            _push("claude_stream", text)
            elif evt_type == "rate_limit_event":
                info = event.get("rate_limit_info", {})
                if info:
                    try:
                        import ui.dashboard as _dash
                        _dash._rate_limit_info = info
                    except Exception:
                        pass
                    _push("rate_limit", "", raw_msg={"type": "rate_limit", "info": info})
            elif evt_type == "result":
                if not output_parts and event.get("result"):
                    output_parts.append(event["result"])
                    _push("claude_stream", event["result"])

        proc.wait(timeout=_TIMEOUT)
        output = "".join(output_parts).strip()
        stderr = (proc.stderr.read() or "").strip()
        _push("claude_working", "false")

        if proc.returncode != 0 and not output:
            error = f"Claude Code hit an error: {stderr[:200]}"
            logger.error(error)
            _push("error", error)
            return error

        if not output:
            _push("assistant", "Claude Code finished but produced no output.")
            _push("claude_done", "")
            return "Claude Code finished but produced no output."

        lines = output.count("\n") + 1
        logger.info(f"Claude Code: {lines} lines, {len(output)} chars")

        _push("assistant", output)
        _push("claude_done", output)

        if len(output) <= _SHORT_LIMIT:
            return output

        first_lines = "\n".join(output.split("\n")[:3])
        return (
            f"Done. Claude Code responded with {lines} lines. "
            f"Here's the start:\n{first_lines}\n\n"
            f"Full response visible on the dashboard."
        )

    except subprocess.TimeoutExpired:
        _push("error", f"Timed out after {_TIMEOUT}s")
        return f"Claude Code timed out after {_TIMEOUT} seconds."
    except FileNotFoundError:
        return "Claude Code CLI is not installed or not on PATH."
    except Exception as exc:
        logger.error(f"Claude Code error: {exc}")
        _push("error", str(exc))
        return f"Error running Claude Code: {exc}"


TOOLS = [
    {
        "name": "run_claude_code",
        "description": (
            "Run a prompt through Claude Code CLI (Anthropic's coding assistant). "
            "Use when the user says 'tell Claude to...', 'ask Claude Code to...', "
            "'use Claude to fix/build/write/refactor...', etc. "
            "Claude Code can read/write files, run commands, and make code changes. "
            "Uses --continue to maintain conversation context across calls. "
            "Results stream live on the dashboard terminal and Jarvis speaks a summary."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "prompt": {
                    "type": "string",
                    "description": "The instruction for Claude Code",
                },
                "directory": {
                    "type": "string",
                    "description": "Working directory (default: C:\\Projects\\jarvis)",
                },
            },
            "required": ["prompt"],
        },
    },
]

HANDLERS = {
    "run_claude_code": run_claude_code,
}
