# Intercom Bridge Project Mandates

This project is a Python-based audio router and Bluetooth manager with direct hardware interaction (GPIO/OLED).

## Engineering Standards

- **State Machine Architecture:** All core state transitions (audio routing, Bluetooth pairing, LED states) MUST be handled within `state_machine.py`.
- **Typing:** Use Python type hinting for all new functions and classes to maintain consistency.
- **Hardware Abstraction:** Business logic should interact with hardware through the established manager classes (`led_manager`, `gpio_handler`) to ensure clean dependency injection.
- **Testing:** New features MUST include unit tests using `pytest` and `pytest-mock` to simulate hardware signals.

## AI Collaboration Protocol

- **Claude & Gemini CLI:** Claude should utilize Gemini CLI as a dedicated research assistant and code reviewer for this codebase.
- **Cross-Review System:** All logic changes (especially state machine updates) must be reviewed by the second AI.
- **Verification:** Use Gemini CLI to run `pytest` or `ruff` to verify changes before finalizing.
- **Strengths:** Use Gemini CLI for searching DBus/udev dependencies and running validation commands. Use Claude for drafting complex state transitions and high-level reasoning.

## Copilot Team Manager Skill (Gemini CLI)

Gemini CLI acts as the **Copilot Team Manager** for this project, orchestrating a team of specialized agents and local specialists.

### The Team
- **High-Power Agents:** `claude` (Claude Code CLI), `architect`, `developer`, `reviewer`, `security` (Copilot).
- **No-Cost Specialists:** `python-expert` (Ruff), `json-architect` (JQ), `package-manager` (Pip), `historian` (Git), `search` (Grep/Find).

### Workflow Protocol
1. **GitHub Context:** Use `gh repo view` and `gh pr list` to sync with the project state.
2. **Dispatching:** Use `/Users/andyherbein/gemini-skills/copilot-team-manager/bin/dispatch-copilot.sh` to assign tasks.
3. **Selection Strategy:** Prioritize No-Cost Specialists for gathering data/linting; use Copilot for boilerplate; use Claude for complex logic.

## Pending AI Review (Gemini -> Claude)

- **Vulnerability Found:** `src/config.py:Config._load` uses `json.load()` without error handling. A malformed `config.json` will crash the entire application on startup.
- **Proposed Fix:**
    ```python
    def _load(self):
        on_disk = {}
        if os.path.exists(self._path):
            try:
                with open(self._path) as f:
                    on_disk = json.load(f)
            except (json.JSONDecodeError, IOError):
                # Fallback to empty dict, which merges with DEFAULTS below
                on_disk = {}
        
        self._data = {**DEFAULTS, **on_disk}
        self._data["profiles"] = {**DEFAULTS["profiles"], **on_disk.get("profiles", {})}
        self._data["sidetone"] = {**DEFAULTS["sidetone"], **on_disk.get("sidetone", {})}
        self.save()
    ```
- **Task for Claude:** Review the proposed try/except block. Does `self.save()` immediately overwriting a corrupt config align with our recovery strategy, or should we rename the corrupt file first (e.g., `config.json.bak`)?

## Pending AI Review: Audio Routing & Performance (Gemini -> Claude)

- **Performance Concern:** `audio_router.py` currently executes `pw-dump` and parses a large JSON blob on every state transition. On low-power target hardware (e.g., Pi Zero), this may cause audible latency or CPU spikes.
- **Fragility Warning:** `_unlink_all()` relies on parsing the string output of `pw-link --list`. This is highly dependent on specific PipeWire versions and CLI formatting.
- **Optimization Strategy:** 
    1.  **Caching:** Cache PipeWire node IDs and only refresh them when a hardware change is detected (via `udev` or DBus signals).
    2.  **Tooling:** Evaluate if `wpctl` (WirePlumber CLI) provides a more stable and performant interface for routing and volume control than the combination of `pw-dump`/`pw-link`/`pw-metadata`.
    3.  **Error Handling:** Implement a fallback if the primary "XLR" or "BT" nodes are missing, perhaps by displaying a specific error state on the OLED.
