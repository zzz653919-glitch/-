from pyatnitsa import health


def snap(**kw):
    base = dict(taken=0, cpu_percent=10, cpu_count=4, cpu_freq_mhz=None, cpu_temp=None, cpu_temp_note="n/a",
                ram_total=16 * 1024**3, ram_used=4 * 1024**3, ram_available=12 * 1024**3, ram_percent=25,
                disks=[health.DiskInfo("C:\\", 500 * 1024**3, 100 * 1024**3, 400 * 1024**3, 20)],
                disk_read_bps=None, disk_write_bps=None, gpus=None, battery=None, os_name="Windows 11",
                uptime_s=3600, events=None)
    base.update(kw)
    return health.Snapshot(**base)


def test_good():
    a = health.assess(snap())
    assert health.overall(a) == "good" and a["gpu"].level == "na" and a["battery"].level == "na"


def test_levels_and_reasons():
    a = health.assess(snap(cpu_percent=95, ram_percent=80, cpu_temp=92,
                           disks=[health.DiskInfo("C:\\", 500 * 1024**3, 497 * 1024**3, 3 * 1024**3, 99)]))
    assert a["cpu"].level == "high" and a["ram"].level == "warn" and a["disk"].level == "high"
    assert any("mumkin" in r for r in a["cpu"].reasons)       # tashxis emas, ehtimol
    assert health.overall(a) == "high"


def test_unavailable_values_are_not_invented():
    txt = health.full_report(snap())
    assert "Batareya mavjud emas" in txt and health.NA in txt
    assert "°C" not in txt.split("Eslatma")[0]
    assert "GPU — Ma'lumot mavjud emas" in txt


def test_battery_states():
    s = snap(battery=health.BatteryInfo(15, False, None))
    assert health.assess(s)["battery"].level == "warn"
    assert "quvvat olmoqda" in health._batt_text(snap(battery=health.BatteryInfo(80, True, None)))


def test_gpu_partial_metrics():
    s = snap(gpus=[health.GpuInfo("NVIDIA X", util=50, temp=None)])
    assert health.NA in health._gpu_text(s) and "50%" in health._gpu_text(s)


def test_real_sample_and_history():
    m = health.HealthMonitor()
    s = m.sample()
    assert 0 <= s.cpu_percent <= 100 and 0 <= s.ram_percent <= 100 and s.ram_total > 0 and s.uptime_s > 0
    assert len(m.cpu_history) == 1
