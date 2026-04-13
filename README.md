# Browser v1 (Python)

A long-term educational browser project implemented from scratch in Python 3.11+.

## Vision

This repository builds a modular browser architecture where each subsystem can be upgraded independently over time.

Current goals:
- Custom URL parsing (without `urllib` URL parsing helpers)
- Raw HTTP/HTTPS networking via sockets
- HTML tokenizer + parser to DOM tree
- CSS parser + selector matching + specificity
- Render tree, layout, and paint pipeline
- Tkinter desktop UI with navigation controls and tabs
- Foundational storage, security, and JS runtime modules

## Project Structure

- `main.py` – app entry point
- `network/` – URL parsing, HTTP client, SSL handling
- `parser/` – HTML/CSS parsing and DOM structures
- `renderer/` – render tree, layout engine, paint engine
- `engine/` – pipeline coordinator and event loop
- `ui/` – main window, address bar, tab manager
- `storage/` – cookies, history, bookmarks persistence
- `security/` – CSP checker and sandbox policy
- `js_engine/` – basic JavaScript interpreter
- `utils/` – shared configuration and logging

## How It Works (Pipeline)

1. Parse URL (`network/url_parser.py`)
2. Fetch resource over HTTP/HTTPS (`network/http_client.py`)
3. Parse HTML into DOM (`parser/html_parser.py` + `parser/dom_tree.py`)
4. Parse CSS into rules (`parser/css_parser.py`)
5. Build Render Tree (`renderer/render_tree.py`)
6. Compute layout boxes (`renderer/layout_engine.py`)
7. Paint on Tk canvas (`renderer/paint_engine.py`)

## Run

1. Ensure Python 3.11+ is installed.
2. Open terminal in project root (`Browser/`).
3. Run:

```powershell
python main.py
```

## Logging

Logs are written to:
- Console
- `browser.log`

The code logs network requests, parser activity, layout steps, and paint calls.

## Module Notes

### Networking
- Socket-based HTTP client with GET/POST support
- HTTPS support through custom SSL wrapper
- Redirect handling (up to configured max)
- Basic response parsing, chunked transfer decoding

### Parsing
- HTML tokenizer emits: DOCTYPE, StartTag, EndTag, SelfClosingTag, Text, Comment
- Fault-tolerant DOM construction for malformed HTML
- CSS parser supports tag/class/id selectors and basic combinators (` ` and `>`)
- Specificity calculation and inherited style support

### Rendering
- Render nodes merge DOM + computed styles
- `display: none` nodes are omitted
- Simplified block/inline layout with box model fields
- Canvas painting supports text, backgrounds, and borders

### UI
- Main window with back/forward/refresh controls
- Address bar with Enter navigation and loading state
- Tab manager supports open/switch/close; each tab has its own `BrowserEngine`

### Storage and Security
- Cookie manager supports domain/path scoping and expiration
- History manager supports back/forward movement
- Bookmarks persisted to JSON
- CSP checker supports `default-src` and `<type>-src` evaluation
- Sandbox restricts JS runtime global access

### JavaScript Engine
Current interpreter supports:
- `var`, `let`, `const` declarations
- Variable assignment
- Arithmetic expressions
- Comparisons
- `console.log(...)`
- Basic `if (...) { ... } else { ... }`

## Roadmap (Next Upgrades)

- Full CSS cascade improvements and external stylesheet loading
- Better inline layout/text wrapping
- Script tag extraction and JS-DOM integration
- Cookie header integration with networking
- Tabs UI controls (new/close buttons and session restore)
- Bookmarks/history UI pages
- Dev tools inspector and network panel
- Security hardening: richer CSP and sandbox boundaries
- Async networking + incremental painting

## Engineering Standards

- Python 3.11+
- Type hints across modules
- Dataclasses for core models
- Module-level docstrings and class/method docstrings
- Custom exception classes where needed
- PEP 8 style
- Modular architecture designed for independent testing
