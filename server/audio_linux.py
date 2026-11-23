"""Linux ses mikseri: PulseAudio / PipeWire (pipewire-pulse) üzerinden, pulsectl ile."""
import asyncio
from concurrent.futures import ThreadPoolExecutor

import pulsectl


def _app_key(si) -> str:
    p = si.proplist
    return (p.get("application.process.binary") or p.get("application.name") or f"stream-{si.index}").lower()


def _app_name(si) -> str:
    p = si.proplist
    name = p.get("application.name") or p.get("application.process.binary") or "?"
    return name[:1].upper() + name[1:]


class Audio:
    def __init__(self):
        # pulsectl iş parçacığı güvenli değil: tüm çağrılar tek bir thread'de
        self._ex = ThreadPoolExecutor(1, thread_name_prefix="pulse")
        self._pulse: pulsectl.Pulse | None = None

    def _p(self) -> pulsectl.Pulse:
        if self._pulse is None or not self._pulse.connected:
            self._pulse = pulsectl.Pulse("MiniDesktop")
        return self._pulse

    def _run(self, fn, *args):
        try:
            return fn(*args)
        except pulsectl.PulseError:
            self._pulse = None  # bağlantı koptu: bir dahaki çağrıda yeniden bağlan
            raise

    async def snapshot(self) -> dict:
        return await asyncio.get_running_loop().run_in_executor(self._ex, self._run, self._snapshot)

    async def command(self, action: str, key=None, value=None):
        await asyncio.get_running_loop().run_in_executor(self._ex, self._run, self._command, action, key, value)

    def _sink(self):
        p = self._p()
        name = p.server_info().default_sink_name
        return p.get_sink_by_name(name)

    def _snapshot(self) -> dict:
        p = self._p()
        sink = self._sink()
        master = {"volume": round(min(1.0, sink.volume.value_flat), 3), "muted": bool(sink.mute), "device": sink.description or sink.name}
        apps: dict[str, dict] = {}
        for si in p.sink_input_list():
            key = _app_key(si)
            entry = apps.get(key)
            active = not si.corked
            if entry is None:
                apps[key] = {"key": key, "name": _app_name(si), "volume": round(min(1.0, si.volume.value_flat), 3),
                             "muted": bool(si.mute), "active": active}
            elif active:
                entry["active"] = True
        ordered = sorted(apps.values(), key=lambda a: (not a["active"], a["name"].lower()))
        return {"master": master, "apps": ordered}

    def _command(self, action, key, value):
        p = self._p()
        if action in ("master_volume", "master_mute"):
            sink = self._sink()
            if action == "master_volume":
                p.volume_set_all_chans(sink, max(0.0, min(1.0, float(value))))
                if sink.mute:
                    p.mute(sink, False)
            else:
                p.mute(sink, not sink.mute)
            return
        targets = [si for si in p.sink_input_list() if _app_key(si) == key]
        if not targets:
            return
        if action == "app_volume":
            v = max(0.0, min(1.0, float(value)))
            for si in targets:
                p.volume_set_all_chans(si, v)
        elif action == "app_mute":
            mute = not targets[0].mute
            for si in targets:
                p.mute(si, mute)

