# Contributing to MiniDesktop

Thanks for helping! Issues and pull requests are welcome.

## Good first contributions
- **New languages** (see below). English and Turkish are included.
- **New widgets / modes** for the tablet.
- **Hardware support:** AMD/Intel GPU stats, more game launchers in game detection (`server/modes.py`).
- Testing on **iPad** and **HarmonyOS** tablets and reporting what works.

## Adding a language
Texts are written in Turkish in the code and wrapped in `t("…")`; each language is a dictionary from the Turkish text to the translation:

| Component | Dictionary |
|---|---|
| Tablet web app | `I18N_EN` / `I18N_EN_HTML` in `web/i18n.js` |
| Admin panel | `EN` / `EN_HTML` in the `<script>` of `server/admin.html` |
| Server + tray app | `EN` in `server/i18n.py` |

To add a language, add a dictionary next to the English one, extend the language lists (`LANGS` in `server/i18n.py`, the `<select>` in the admin panel) and pick the dictionary by language code in the three `t()` functions. Keep `{placeholders}` unchanged.

## Development setup
```powershell
powershell -ExecutionPolicy Bypass -File tools\setup.ps1
.venv\Scripts\python app\launcher.py
```
The tablet web app has no build step: edit files in `web/` and reload the page. When running from source, data is stored in `data/` inside the project.

## Guidelines
- Keep everything local-first: no telemetry, no new cloud services without a clear opt-in.
- Never commit secrets, tokens or the Discord Social SDK files (`bridge/sdk/*/`).
- Describe how you tested (PC OS, tablet + browser) in the pull request.
