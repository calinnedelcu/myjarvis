"""Claude Code integration — uses shared persistent process + real-time dashboard streaming."""

from loguru import logger

_SHORT_LIMIT = 400
_last_response = {"prompt": "", "summary": "", "full": ""}


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
    """Run Claude Code via shared persistent process, stream to dashboard in real-time."""
    try:
        from ui.claude_session import get_claude
        from ui.dashboard import _handle_claude_event

        logger.info(f"Claude Code: {prompt[:100]}")
        _push("user", prompt)
        _push("claude_working", "true")

        output_parts = []

        def on_event(event):
            _handle_claude_event(event, output_parts)

        claude = get_claude()
        completed = claude.send(prompt, on_event=on_event, timeout=120)

        output = "".join(output_parts).strip()
        _push("claude_working", "false")

        if not completed and not output:
            error = "Claude Code timed out."
            _push("error", error)
            return error

        if not output:
            _push("assistant", "Claude Code finished but produced no output.")
            _push("claude_done", "")
            _last_response["prompt"] = prompt
            _last_response["summary"] = "Finished but produced no output."
            _last_response["full"] = ""
            return "Claude Code finished but produced no output."

        lines = output.count("\n") + 1
        logger.info(f"Claude Code: {lines} lines, {len(output)} chars")

        _push("assistant", output)
        _push("claude_done", output)

        # Store last response so Jarvis brain can reference it
        _last_response["prompt"] = prompt
        _last_response["full"] = output
        if len(output) <= _SHORT_LIMIT:
            _last_response["summary"] = output
        else:
            # Build a meaningful summary from first and last few lines
            out_lines = output.strip().split("\n")
            head = "\n".join(out_lines[:5])
            tail = "\n".join(out_lines[-3:]) if len(out_lines) > 8 else ""
            _last_response["summary"] = (
                f"{head}\n{'...\n' + tail if tail else ''}"
                f"\n[{lines} lines total]"
            )

        if len(output) <= _SHORT_LIMIT:
            return output

        first_lines = "\n".join(output.split("\n")[:3])
        return (
            f"Done. Claude Code responded with {lines} lines. "
            f"Here's the start:\n{first_lines}\n\n"
            f"Full response visible on the dashboard."
        )

    except FileNotFoundError:
        return "Claude Code CLI is not installed or not on PATH."
    except Exception as exc:
        logger.error(f"Claude Code error: {exc}")
        _push("error", str(exc))
        return f"Error running Claude Code: {exc}"


def get_last_claude_response() -> str:
    """Return Claude Code's last response summary for Jarvis to read back."""
    if not _last_response["summary"]:
        return "Claude Code hasn't responded to anything yet in this session."
    return (
        f"Last prompt sent to Claude: {_last_response['prompt'][:200]}\n\n"
        f"Claude's response:\n{_last_response['summary']}"
    )


TOOLS = [
    {
        "name": "get_last_claude_response",
        "description": (
            "Get Claude Code's last response/answer. Use when the user asks "
            "'what did Claude say?', 'what was Claude's response?', "
            "'what did Claude do?', 'read Claude's answer', 'tell me what Claude replied', "
            "or any question about Claude Code's most recent output."
        ),
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    {
        "name": "run_claude_code",
        "description": (
            "Run a prompt through Claude Code CLI (Anthropic's coding assistant). "
            "Use when the user says 'tell Claude to...', 'ask Claude Code to...', "
            "'use Claude to fix/build/write/refactor...', etc. "
            "Claude Code can read/write files, run commands, and make code changes. "
            "Results stream live on the dashboard terminal and Jarvis speaks a summary. "
            "IMPORTANT: The prompt must be plain natural language, NOT code. "
            "Do NOT wrap it in print(), code blocks, or any programming syntax. "
            "Example: if the user says 'tell Claude hello', the prompt is 'hello', NOT 'print(\"hello\")'."
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
    "get_last_claude_response": lambda: get_last_claude_response(),
}
