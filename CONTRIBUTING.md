# Contributing to MiniDesktop

Thanks for helping! Issues and pull requests are welcome.

## Good first contributions
- **Translations:** the tablet UI (`web/`), the admin panel (`server/admin.html`) and the tray app (`app/control.py`) are currently in Turkish. An English UI (and a simple language switch) would help the most.
- **New widgets / modes** for the tablet.
- **Hardware support:** AMD/Intel GPU stats, more game launchers in game detection (`server/modes.py`).
- Testing on **iPad** and **HarmonyOS** tablets and reporting what works.

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
