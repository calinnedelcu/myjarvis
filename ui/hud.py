"""
Phase 8 — J.A.R.V.I.S. HUD Overlay
Iron Man-style semi-transparent always-on-top overlay for Windows.

States: STANDBY → LISTENING → THINKING → SPEAKING → STANDBY
Thread-safe: voice pipeline threads push updates via a queue;
             tkinter main thread polls every 50 ms.
"""

import queue
import tkinter as tk
from typing import Optional

# ── State constants ────────────────────────────────────────────────────────────
STANDBY   = "STANDBY"
LISTENING = "LISTENING"
THINKING  = "THINKING"
SPEAKING  = "SPEAKING"
PAUSED    = "PAUSED"

# ── Iron-Man palette ───────────────────────────────────────────────────────────
_BG           = "#050d1a"   # near-black navy
_ACCENT       = "#00c8e8"   # arc-reactor cyan
_BORDER       = "#0a2a3a"   # dim cyan border
_TEXT         = "#b0dcea"   # soft blue-white (response)
_TRANSCRIPT   = "#4a7a8a"   # muted teal (what user said)
_TITLE        = "#00c8e8"   # cyan title
_ALPHA        = 0.88        # window opacity

_STATUS_COLOR = {
    STANDBY:   "#1e3a4a",
    LISTENING: "#00e676",   # bright green
    THINKING:  "#ffa726",   # amber
    SPEAKING:  "#00c8e8",   # cyan
    PAUSED:    "#ff5252",   # red
}
_STATUS_LABEL = {
    STANDBY:   "●  STANDBY",
    LISTENING: "◎  LISTENING",
    THINKING:  "◈  THINKING",
    SPEAKING:  "◉  SPEAKING",
    PAUSED:    "⏸  PAUSED",
}

_HUD_W        = 480
_HUD_H        = 220
_FADE_MS      = 10_000   # clear text 10 s after going idle


class JarvisHUD:
    """
    Frameless, always-on-top overlay.  All public methods are thread-safe.
    Call `run()` from the *main thread* — it blocks (tkinter mainloop).
    """

    def __init__(self, on_pause_toggle=None) -> None:
        self._q: queue.Queue = queue.Queue()
        self._fade_id: Optional[str] = None
        self._paused = False
        self._on_pause_toggle = on_pause_toggle  # callback(paused: bool)

        # ── root window ───────────────────────────────────────────────
        self._root = tk.Tk()
        r = self._root
        r.title("J.A.R.V.I.S.")
        r.overrideredirect(True)            # no title bar / chrome
        r.attributes("-topmost", True)      # always on top
        r.attributes("-alpha", _ALPHA)      # semi-transparent
        r.configure(bg=_BG)

        # position: bottom-right, 20 px margin
        sw = r.winfo_screenwidth()
        sh = r.winfo_screenheight()
        x  = sw - _HUD_W - 20
        y  = sh - _HUD_H - 60             # above taskbar
        r.geometry(f"{_HUD_W}x{_HUD_H}+{x}+{y}")

        # close: Escape or right-click menu
        r.bind("<Escape>",     lambda _: r.destroy())
        r.bind("<Button-3>",   self._show_menu)

        # drag support
        r.bind("<Button-1>",   self._drag_start)
        r.bind("<B1-Motion>",  self._drag_move)
        self._dx = self._dy = 0
        self._menu = tk.Menu(r, tearoff=0, bg=_BG, fg=_ACCENT,
                             activebackground=_BORDER, activeforeground=_ACCENT)
        self._menu.add_command(label="Restart Jarvis", command=self._restart_jarvis)
        self._menu.add_separator()
        self._menu.add_command(label="Close HUD", command=r.destroy)

        self._build_widgets()
        self._poll()                        # start 50 ms poll loop

    # ── Widget layout ──────────────────────────────────────────────────────────

    def _build_widgets(self) -> None:
        r = self._root

        # top accent line
        tk.Frame(r, bg=_ACCENT, height=2).pack(fill="x")

        # ── header row ────────────────────────────────────────────────
        hdr = tk.Frame(r, bg=_BG, padx=10, pady=5)
        hdr.pack(fill="x")

        tk.Label(
            hdr, text="◆  J.A.R.V.I.S.",
            bg=_BG, fg=_TITLE,
            font=("Consolas", 11, "bold"), anchor="w",
        ).pack(side="left")

        self._status_lbl = tk.Label(
            hdr, text=_STATUS_LABEL[STANDBY],
            bg=_BG, fg=_STATUS_COLOR[STANDBY],
            font=("Consolas", 9, "bold"), anchor="e",
        )
        self._status_lbl.pack(side="right")

        # pause/resume button
        self._pause_btn = tk.Label(
            hdr, text="⏸", bg=_BG, fg="#607080",
            font=("Consolas", 12), cursor="hand2", padx=6,
        )
        self._pause_btn.pack(side="right")
        self._pause_btn.bind("<Button-1>", self._toggle_pause)

        # separator
        tk.Frame(r, bg=_BORDER, height=1).pack(fill="x")

        # ── transcript row ────────────────────────────────────────────
        self._transcript_var = tk.StringVar(value="")
        tk.Label(
            r, textvariable=self._transcript_var,
            bg=_BG, fg=_TRANSCRIPT,
            font=("Consolas", 9, "italic"),
            anchor="w", padx=12, pady=3,
            wraplength=_HUD_W - 24, justify="left",
        ).pack(fill="x")

        # thin inner separator
        tk.Frame(r, bg="#0a1828", height=1).pack(fill="x")

        # ── response text ─────────────────────────────────────────────
        self._resp = tk.Text(
            r,
            bg=_BG, fg=_TEXT,
            font=("Consolas", 10),
            relief="flat", bd=0, highlightthickness=0,
            wrap="word", padx=12, pady=8,
            height=5,
            state="disabled", cursor="arrow",
        )
        self._resp.pack(fill="both", expand=True)

        # bottom accent line
        tk.Frame(r, bg=_BORDER, height=2).pack(fill="x", side="bottom")

    # ── Thread-safe public API ─────────────────────────────────────────────────

    def set_state(self, state: str) -> None:
        """Change the status indicator (any thread)."""
        self._q.put(("state", state))

    def set_transcript(self, text: str) -> None:
        """Show what the user said (any thread)."""
        self._q.put(("transcript", text))

    def set_response(self, text: str) -> None:
        """Replace full response text (any thread)."""
        self._q.put(("resp_set", text))

    def append_response(self, chunk: str) -> None:
        """Append a streaming chunk to response text (any thread)."""
        self._q.put(("resp_append", chunk))

    def run(self) -> None:
        """Block — run tkinter mainloop (call from main thread)."""
        self._root.mainloop()

    def quit(self) -> None:
        """Destroy the window (safe to call from any thread)."""
        self._q.put(("quit", None))

    # ── Queue poll (main thread only) ──────────────────────────────────────────

    def _poll(self) -> None:
        try:
            while True:
                cmd, data = self._q.get_nowait()
                if   cmd == "state":       self._apply_state(data)
                elif cmd == "transcript":  self._set_transcript(data)
                elif cmd == "resp_set":    self._set_resp(data)
                elif cmd == "resp_append": self._append_resp(data)
                elif cmd == "quit":        self._root.destroy(); return
        except queue.Empty:
            pass
        self._root.after(50, self._poll)

    # ── Internal UI updates (main thread only) ─────────────────────────────────

    def _apply_state(self, state: str) -> None:
        color = _STATUS_COLOR.get(state, _STATUS_COLOR[STANDBY])
        label = _STATUS_LABEL.get(state, _STATUS_LABEL[STANDBY])
        self._status_lbl.configure(fg=color, text=label)

        # cancel any pending fade when activity resumes
        if self._fade_id:
            self._root.after_cancel(self._fade_id)
            self._fade_id = None

        if state == STANDBY:
            self._fade_id = self._root.after(_FADE_MS, self._fade_content)

    def _set_transcript(self, text: str) -> None:
        self._transcript_var.set(f'"{text}"' if text else "")

    def _set_resp(self, text: str) -> None:
        w = self._resp
        w.configure(state="normal")
        w.delete("1.0", "end")
        if text:
            w.insert("end", text)
        w.configure(state="disabled")

    def _append_resp(self, chunk: str) -> None:
        w = self._resp
        w.configure(state="normal")
        w.insert("end", chunk)
        w.see("end")
        w.configure(state="disabled")

    def _fade_content(self) -> None:
        """Clear text after idle timeout."""
        self._set_transcript("")
        self._set_resp("")

    # ── Drag ──────────────────────────────────────────────────────────────────

    def _toggle_pause(self, event=None) -> None:
        self._paused = not self._paused
        if self._paused:
            self._pause_btn.configure(text="▶", fg="#00e676")
            self._apply_state(PAUSED)
        else:
            self._pause_btn.configure(text="⏸", fg="#607080")
            self._apply_state(STANDBY)
        if self._on_pause_toggle:
            self._on_pause_toggle(self._paused)

    def _restart_jarvis(self) -> None:
        """Restart the entire Jarvis process."""
        import sys, os, subprocess
        python = sys.executable
        script = os.path.join(os.path.dirname(os.path.dirname(__file__)), "main.py")
        subprocess.Popen([python, script], cwd=os.path.dirname(script))
        self._root.destroy()
        os._exit(0)

    def _show_menu(self, event) -> None:
        self._menu.tk_popup(event.x_root, event.y_root)

    def _drag_start(self, event) -> None:
        self._dx = event.x
        self._dy = event.y

    def _drag_move(self, event) -> None:
        x = self._root.winfo_x() + (event.x - self._dx)
        y = self._root.winfo_y() + (event.y - self._dy)
        self._root.geometry(f"+{x}+{y}")
