# Changelog

## [1.1.0] - 2026-11-24
### Added
- **Linux support** (X11 and Wayland): MPRIS media control, PulseAudio/PipeWire mixer, clipboard (wl-clipboard/xclip),
  Discord keybinds (xdotool/ydotool/wtype), systemd power menu, Steam/Proton/Heroic/Lutris game detection, kernel CPU temperature,
  Discord IPC for native/Flatpak/Snap installs, tray app with XDG autostart.
- `install.sh` / `uninstall.sh` (per-user, installs missing packages on apt/dnf/pacman/zypper) and a Linux release archive.
- CI on every push: Linux smoke test against a real MPRIS player, PulseAudio and X11 (Python 3.10 and 3.12), Windows import check.

### Fixed
- GitHub showed the license as "Other"; LICENSE is now the plain MIT text.

## [1.0.1] - 2026-11-24
### Added
- **English user interface** for the tablet, admin panel, tray app and server messages, with automatic selection from the Windows display language and a *Language / Dil* switch in the admin panel.
- iPad (iPadOS) and HarmonyOS: device names when pairing, home-screen (web app) support, platform instructions in the admin panel.
- English README with screenshots, social preview, contributing guide, issue templates.

### Changed
- English file names: `build.bat`, `bridge/build-bridge.bat`, `bridge/sdk/PUT_SDK_HERE.txt`; Claude Code settings backup is now `settings.json.minidesktop-backup`.

### Fixed
- When Discord was closed, the Discord connection reported a generic error instead of "Discord is not running".
- The Unix time tool in Developer mode could fail to show its result.

## [1.0.0] - 2026-11-23
First public release.
- Tablet web app: media player, Discord, performance gauges, volume mixer, weather, lock screen.
- Modes: Normal, Developer (Claude Code, git/GitHub, commands, ports & processes, clipboard, dev tools), Game (auto-detect), Night.
- Discord: Social SDK bridge (friends, unread DMs), keybind mode and full RPC control.
- Windows tray app with QR pairing, firewall check, start with Windows; per-user installer.
