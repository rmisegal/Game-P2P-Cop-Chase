"""Tests for local system spec collection (book section 6 declaration)."""

from police_thief.shared.sysinfo import collect_spec

REQUIRED_KEYS = {
    "os", "cpu_type", "cpu_cores", "cpu_freq_mhz",
    "ram_gb", "gpu_type", "gpu_cores_or_cuda", "vram_gb",
}


class TestCollectSpec:
    def test_returns_all_required_keys(self):
        spec = collect_spec()
        assert spec.keys() >= REQUIRED_KEYS

    def test_cpu_cores_positive_int(self):
        assert isinstance(collect_spec()["cpu_cores"], int)
        assert collect_spec()["cpu_cores"] >= 1

    def test_cached_single_probe(self):
        assert collect_spec() is collect_spec()  # same dict object: probed once

    def test_values_are_json_serializable(self):
        import json

        json.dumps(collect_spec())
