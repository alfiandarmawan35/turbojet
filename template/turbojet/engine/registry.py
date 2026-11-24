"""Registri operasi engine (tetap di Python; bukan target port).

Fungsi dicari lewat ``getattr`` setiap kali dipanggil, sehingga ``rust-anything enable``
(yang mengikat ulang nama fungsi di modulnya ke versi Rust) langsung berlaku.
"""

from importlib import import_module

OPERATIONS = {
    "group_sum": ("turbojet.engine.ops.group_sum", "aggregate_chunk"),
}


def resolve(name):
    if name not in OPERATIONS:
        raise KeyError(name)
    module_name, func_name = OPERATIONS[name]
    return getattr(import_module(module_name), func_name)


def engine_path(func):
    """``python`` bila fungsi masih rujukan Python, ``rust`` bila sudah diganti port Rust."""
    module = getattr(func, "__module__", "") or ""
    return "python" if module.startswith("turbojet.engine.") else "rust"


def describe():
    from turbojet.engine.split import records

    out = {name: {"path": engine_path(resolve(name))} for name in OPERATIONS}
    out["_split_records"] = {"path": engine_path(records.split_records)}
    return out
