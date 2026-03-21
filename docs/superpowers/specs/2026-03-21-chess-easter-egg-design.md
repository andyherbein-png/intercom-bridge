# Chess Easter Egg — Design Specification
**Date:** 2026-03-21
**Status:** Draft v1.0
**Parent Project:** Intercom-to-Wireless Audio Bridge
**Spec Location:** `docs/superpowers/specs/2026-03-21-chess-easter-egg-design.md`

---

## 1. Overview

A hidden chess game accessible through the intercom bridge web UI via a secret gesture. The game presents as an authentic Commodore 64 BASIC program — complete with boot header, READY prompt, and BASIC-style move log — running entirely in the browser. The Raspberry Pi Zero 2W acts only as a web server; all game logic runs client-side.

**Aesthetic target:** Looks exactly like a BASIC chess program typed into a C64 in 1984.
**Platform:** Browser-only (iPhone-first, also desktop). No OLED display involvement.
**Access:** Secret menu hidden in the web UI's ABOUT section.
**Exit:** Browser "back", explicit QUIT button, or a server-sent event when audio activity fires.

---

## 2. Research Summary

### 2.1 ROM Emulation — Investigated and Rejected

C64 chess ROMs were evaluated (Chess Master 1983, Colossus Chess 4.0 1985, Chessmaster 2100). Running them via EmulatorJS (VICE vice_x64sc core) is technically possible but rejected for the following reasons:

- C64 chess games require keyboard input (type `E2 E4` to move). No touch equivalent on iPhone.
- EmulatorJS data bundles are large (~15–30MB) — inappropriate for a Pi Zero 2W serving over a local WiFi hotspot.
- VICE.js is archived and unmaintained.
- ROM copyright is ambiguous (abandonware, but not cleanly open-source).
- No way to receive the "exit on audio event" signal from Flask inside an emulator.

**Verdict:** ROM emulation is not suitable for an iPhone-friendly Easter egg.

### 2.2 JavaScript Chess Engine Options

| Engine | Size | AI | Mobile | Notes |
|--------|------|----|--------|-------|
| chess.js | ~50KB min | No | Yes | Move validation only; widely tested |
| js-chess-engine | Small | Yes (5 levels) | Yes | Zero deps; all-in-one; pure JS |
| Lozza | ~200–250KB | Yes (UCI ~ELO 2340) | Limited | Needs web worker; single file |
| Stockfish WASM lite | ~7MB | Yes (strong) | Yes (iOS 16+) | Too heavy for Easter egg |
| Sunfish (JS port) | ~131 lines | Yes (~ELO 2000) | Yes | Extremely small; good for embedding |
| Kilobyte's Gambit | 1KB | Yes (weak) | Yes | Fun but blunders frequently |

### 2.3 Visual Rendering

Unicode chess pieces (♔♕♖♗♘♙♚♛♜♝♞♟, U+2654–U+265F) render reliably in modern mobile browsers including Safari on iPhone. The C64 Pro Mono font from cdnfonts.com is already used by the main web UI; fallback to `'Courier New'` is sufficient for the BASIC aesthetic.

---

## 3. Architecture Decision

### 3.1 Approach: Single Self-Contained HTML File

**Rationale:** The device serves at `192.168.4.1` over a local WiFi hotspot with no guaranteed internet access. All dependencies must be self-hosted or embedded. A single HTML file with all JavaScript inline means:

- One file for Flask to serve at `/chess`
- No CDN dependencies at runtime
- No npm, no build tools, no Node.js on the Pi
- Trivially portable — copy one file to update

**Rejected alternatives:**
- CDN for chess.js: fails on air-gapped hotspot
- Web worker for Lozza: requires a second file; adds deployment complexity
- EmulatorJS: too large, keyboard-only, no audio event integration

### 3.2 Stack

| Layer | Technology | Why |
|-------|-----------|-----|
| Server | Flask (existing) | Already running; just add one route |
| Game logic | chess.js (embedded inline, minified) | Battle-tested, ~50KB, MIT license |
| AI engine | Custom minimax + alpha-beta pruning (inline, ~150 lines) | Authentic "BASIC program" simplicity; ~5KB; zero deps; appropriate for Easter egg |
| Rendering | HTML table + CSS grid, Unicode pieces | Touch-friendly 44px cells; no canvas needed |
| Styling | C64 design system (established project CSS) | Consistent with main web UI |
| Exit signaling | Flask SSE endpoint `/chess/events` | Pushes "EXIT" event when PTT fires |
| Font | C64 Pro Mono via CDN with Courier New fallback | Matches existing project; works offline |

### 3.3 AI Strength Decision

The inline minimax AI (depth 3–5) is intentionally at ~1500–1800 ELO — similar to the original C64 chess games' strength. This is:
- Appropriate for a hidden Easter egg (beatable but not trivially so)
- Authentic to the "running on a C64" fiction
- Fast enough on an iPhone with no lag

A "HARD" mode option uses depth 5 (slower but meaningfully stronger).

---

## 4. User Experience

### 4.1 Secret Access Mechanism

In the existing web UI (`/`), navigate to **SETTINGS → ABOUT**. A hidden touch target (the "★" in the footer Easter egg credit line) starts a 3-tap detection timer. Three taps within 2 seconds navigates to `/chess`.

This preserves the "secret" nature while being discoverable on an iPhone.

### 4.2 Chess Page Layout (Phone-First)

```
┌─────────────────────────────────────┐
│  **** CHESS BASIC V1.0 ****         │
│  64K RAM SYSTEM  38911 BASIC BYTES  │
│  FREE                               │
│                                     │
│  10 REM EASTER EGG - CHESS          │
│  20 REM (C) INTERCOM BRIDGE         │
│  READY.█                            │
├─────────────────────────────────────┤
│  CHESS          [FLIP] [QUIT]       │  ← title bar
├─────────────────────────────────────┤
│  ● YOUR TURN · HUMAN VS COMPUTER   │  ← status strip
├─────────────────────────────────────┤
│    A  B  C  D  E  F  G  H          │
│  8 ♜  ♞  ♝  ♛  ♚  ♝  ♞  ♜         │
│  7 ♟  ♟  ♟  ♟  ♟  ♟  ♟  ♟         │
│  6 ·  ·  ·  ·  ·  ·  ·  ·         │
│  5 ·  ·  ·  ·  ·  ·  ·  ·         │
│  4 ·  ·  ·  ·  ·  ·  ·  ·         │
│  3 ·  ·  ·  ·  ·  ·  ·  ·         │
│  2 ♙  ♙  ♙  ♙  ♙  ♙  ♙  ♙         │
│  1 ♖  ♘  ♗  ♕  ♔  ♗  ♘  ♖         │
├─────────────────────────────────────┤
│  ▶ MOVE HISTORY                     │  ← BASIC-style log
│  10 E2-E4                           │
│  20 E7-E5                           │
│  30 G1-F3                           │
├─────────────────────────────────────┤
│  ▶ DIFFICULTY                       │
│  [NOVICE]  [ADVANCED]  [MASTER]     │
│  ★ IN HONOR OF OPEN SOURCE DEVS ★  │
└─────────────────────────────────────┘
```

### 4.3 Interaction Model (Touch)

1. **Select piece**: Tap any square containing your piece → square highlights in cyan (`#AAFFEE`)
2. **See legal moves**: Highlighted squares show small green dots (`#AAFF66`, `--lgreen`)
3. **Move**: Tap a highlighted legal-move square → piece moves; status updates
4. **Cancel**: Tap elsewhere or tap the same square again → deselect
5. **CPU response**: Status shows "COMPUTER THINKING..." → move plays after ~0.5–2s

6. **Undo**: Tap UNDO button → reverts both the CPU's last move and the player's last move (2 half-moves). Only available when there are moves to undo and CPU is not thinking. Unavailable after game over.

No drag-and-drop. No gestures beyond tap. iPhone-friendly.

### 4.4 BASIC-Style Messaging

All system messages display in BASIC program style:

| Event | Display |
|-------|---------|
| Game start | `RUN` then board appears |
| Your turn | `● YOUR TURN` |
| CPU thinking | `COMPUTER THINKING...` with blinking cursor |
| Illegal move | `?SYNTAX ERROR: ILLEGAL MOVE` |
| Check | `WARNING: CHECK!` |
| Checkmate (you lose) | `GAME OVER. COMPUTER WINS. READY.` |
| Checkmate (you win) | `CONGRATULATIONS! YOU WIN! READY.` |
| Stalemate | `PROGRAM FINISHED. DRAW. READY.` |
| Audio event exit | `AUDIO EVENT DETECTED. PROGRAM ENDED.` |

### 4.5 Audio Event Exit

The Flask server exposes a Server-Sent Events endpoint:

```
GET /chess/events
```

When the audio state machine fires any of: PTT press, headset connect, headset disconnect — Flask sends:
```
data: EXIT
```

The chess page listens with `EventSource` and immediately redirects to `/` when `EXIT` is received. This ensures the Easter egg never interferes with show-critical audio operations.

### 4.6 Move History Format

The move log uses BASIC line numbers (increments of 10, cycling at 990→10):
```
10 E2-E4    (WHITE)
20 E7-E5    (BLACK)
30 G1-F3    (WHITE)
40 B8-C6    (BLACK)
```

Displayed in a scrollable panel, newest at bottom. Max 20 lines shown (scrollable).

---

## 5. Visual Design

### 5.1 Color Scheme

Inherits the established C64 design system:

| Element | Color | Value |
|---------|-------|-------|
| Screen background | c64-bg | `#20398D` |
| Board light square | c64-bg | `#20398D` |
| Board dark square | c64-dark | `#10206d` |
| Board border/grid | c64-border | `#6076C5` |
| White pieces | White | `#FFFFFF` |
| Black pieces | Yellow | `#EEEE77` (visibility on dark blue) |
| Selected square | Cyan bg | `#AAFFEE` |
| Legal move dot (empty square) | Light green | `#AAFF66` (`--lgreen`) — small centered circle |
| Legal move (capture) | Light green | `#AAFF66` — thin border ring on cell |
| Status text | Light green | `#AAFF66` |
| Move history | Cyan | `#AAFFEE` |
| Error messages | Light red | `#FF7777` |
| CPU thinking | Orange | `#DD8855` |

**Note:** Using yellow for "black" pieces (rather than actual black) ensures visibility against the dark blue board — same technique used in many original C64 games.

### 5.2 Board Dimensions (iPhone Safe)

```
Board: 8 × 8 cells
Cell size: min(44px, floor(90vw / 8)) → ~42px on 375px iPhone
Board width: ~336px on iPhone, fills available width
Rank/file labels: 18px gutter on left, 8px top
Touch target: 44px minimum (matches Apple HIG)
```

### 5.3 Boot Sequence Animation

On page load, simulate a BASIC boot sequence (1.5 seconds total):

1. Screen fades in black → `#20398D`
2. Boot text types character-by-character: `**** CHESS BASIC V1.0 ****`
3. Next line: `64K RAM SYSTEM  38911 BASIC BYTES FREE`
4. Blank line
5. `10 REM EASTER EGG - CHESS`
6. `20 REM (C) INTERCOM BRIDGE`
7. `READY.` with blinking cursor
8. After 0.8s: `RUN` types itself
9. Board appears with slide-in animation

Total: ~2 seconds. Can be skipped by tapping.

### 5.4 C64 Font

```css
font-family: 'C64 Pro Mono', 'C64_Pro_Mono-STYLE', 'Courier New', monospace;
text-transform: uppercase;
```

The CDN import (`https://fonts.cdnfonts.com/css/c64-pro-mono`) will load if device has internet access. Falls back to Courier New, which is installed on all iPhones and looks excellent for the retro aesthetic.

---

## 6. Technical Design

### 6.1 Flask Integration

Add to `web_server.py`:

```python
from flask import render_template, Response, stream_with_context
import queue, threading

chess_exit_queue = queue.SimpleQueue()

@app.route('/chess')
def chess_page():
    return render_template('chess.html')

@app.route('/chess/events')
def chess_events():
    def generate():
        q = queue.SimpleQueue()
        _chess_event_listeners.append(q)
        try:
            while True:
                msg = q.get(timeout=30)
                yield f"data: {msg}\n\n"
        except:
            yield "data: KEEPALIVE\n\n"
        finally:
            _chess_event_listeners.remove(q)
    return Response(stream_with_context(generate()),
                    mimetype='text/event-stream',
                    headers={'Cache-Control': 'no-cache'})

# Call this from state_machine.py on audio events:
def notify_chess_exit():
    for q in _chess_event_listeners:
        q.put("EXIT")

_chess_event_listeners = []
```

### 6.2 chess.html Structure

```
chess.html (self-contained, ~80–120KB total)
├── <style>          C64 CSS (from design system, ~8KB)
├── <script>         chess.js minified (embedded, ~50KB)
├── <script>         Minimax AI (~5KB, ~150 lines)
├── <script>         Game UI controller (~10KB)
└── <body>           HTML structure
```

### 6.3 Minimax AI Specification

A depth-limited minimax with alpha-beta pruning:

```
Difficulty  Depth  Approx Time (iPhone)  Approx ELO
NOVICE      1      <50ms                 ~1000
ADVANCED    3      ~200–500ms            ~1400
MASTER      5      ~1–3s                 ~1700–1800
```

Piece-square tables for positional evaluation (same tables used in classic BASIC chess programs from 1980s magazines). No opening book. Captures and checks prioritized in move ordering.

**Note:** These ELO estimates are for the inline minimax. For a future "GRANDMASTER" mode, swap the AI for Lozza served as a second static file. Design supports this without UI changes.

### 6.4 State Management

```javascript
const gameState = {
    chess: null,          // chess.js instance
    selectedSquare: null, // currently selected square ('e2' format)
    legalMoves: [],       // legal moves for selected piece
    isPlayerTurn: true,   // true = white (player)
    difficulty: 3,        // minimax depth (1-5)
    moveNumber: 10,       // BASIC line number counter
    history: [],          // move history [{from, to, san, side}]
    flipped: false        // board flip state
};
```

### 6.5 Promotion Handling

When a pawn reaches the back rank, a modal appears:
```
┌───────────────────────┐
│  PROMOTE PAWN TO:     │
│  [♕ QUEEN] [♖ ROOK]  │
│  [♗ BISHOP][♘ KNIGHT] │
└───────────────────────┘
```
C64-styled. Auto-promotes to queen for CPU.

### 6.6 New Game / Reset

"NEW GAME" button shows a BASIC-style confirmation:
```
RUN NEW GAME? [Y] [N]
```
Confirms, then plays boot sequence animation again.

---

## 7. File Layout

```
intercom-bridge/
└── web_server/
    ├── templates/
    │   └── chess.html          ← new file (~100KB self-contained)
    └── web_server.py           ← add /chess and /chess/events routes
```

OR if Flask uses static files:

```
intercom-bridge/
└── static/
    └── chess.html              ← served directly
```

The exact path follows whatever convention `web_server.py` uses (to be determined when implementation begins).

---

## 8. Out of Scope

- **OLED chess**: The user's original hardware OLED chess (128×64 + encoders) remains a future task per the project memory. This spec covers only the browser chess.
- **Multiplayer**: Human vs CPU only. No two-player mode.
- **Game save/load**: No persistence. Games are ephemeral.
- **Network play**: Not applicable.
- **Stockfish-level strength**: The Easter egg is intentionally beatable. A "GRANDMASTER" mode using Lozza can be added later without redesign.
- **Sound effects**: The Pi Zero 2W's audio is show-critical; the chess page produces no sound.

---

## 9. Open Questions for User Review

1. **Secret access mechanism**: Triple-tap on the footer ★ symbol in ABOUT page OK, or prefer a different gesture (e.g., hold back button 3 seconds)?
2. **Font offline**: The existing web UI already uses CDN font import — should the chess page use the same CDN call and accept that it degrades to Courier New when offline?
3. **AI difficulty default**: Start on ADVANCED (depth 3) or NOVICE (depth 2)?
4. **Board flip**: Should the board always show white at bottom, or should it respect which color the player is? (Currently: player always plays white.)
5. **Future Lozza integration**: Is a stronger "GRANDMASTER" mode wanted from the start, or is the built-in minimax sufficient?

---

## 10. Implementation Readiness

Research complete. Architecture decided. Ready to proceed to implementation plan.

**Estimated deliverables:**
- `chess.html` — single self-contained file, ~100KB
- Web server modifications — ~20 lines of Python
- State machine hook — ~5 lines of Python (call `notify_chess_exit()` on audio events)

**Dependencies:** None new. Uses chess.js (MIT, embedded), existing C64 CSS, existing Flask app.

---

*Spec drafted autonomously during scheduled research session (user sleeping). All architectural decisions documented above. User should review section 9 (Open Questions) before implementation begins.*
