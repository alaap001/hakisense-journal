# Coach visual preview

With the frontend development server running, open `/tests/ui/coach-preview.html`.
This mounts the real Coach component and styles inside a representative workspace shell.
All API requests are intercepted with synthetic data. It does not read customer trades,
call an AI provider, or charge credits. The fixture is not an entry point in the production build.

- Open **Ask HakiSense**, then the saved performance conversation, to inspect two financial tables.
- Start a conversation and send a question to inspect incremental reply rendering.
- At a 390 px viewport, use **History** to reopen a conversation and scroll the comparison sideways.
- **Recent reviews** exercises opening a completed review and displays a refunded failure.
- **Save to notebook** records the unmodified Markdown in the in-memory fixture and shows the usual confirmation.

The shared renderer uses [remark-gfm](https://github.com/remarkjs/remark-gfm) for standard table syntax.
It retains explicit column alignment, infers right alignment for numeric columns when omitted,
and leaves the source content unchanged. Raw HTML is not enabled.

# Shared motion preview

Open `/tests/ui/motion-preview.html` in the development server for isolated Select/SuggestInput, modal dropdown and smooth-anchor checks. It contains synthetic options only and makes no backend calls.

- Open the long list; Home/End should move the list without moving the document.
- Escape should restore the trigger, with a brief noninteractive closing transition.
- Type into Known setups and select a suggestion with the keyboard.
- Open the dialog and its dropdown to verify top-layer positioning.
- Reset the scroll measurements, then use Scroll to top/bottom. The fixed output records document scroll positions for checking reversals or duplicate jumps.
