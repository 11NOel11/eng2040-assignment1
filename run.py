"""Rebuild every pipeline output from supplied/data/raw.sql and check it, or fail loudly.
uv run --locked python run.py            everything, 5-10 min
uv run --locked python run.py --fast     reuse the last engine comparison
uv run --locked python run.py --update   accept the current outputs as the new expected.sha256"""
import hashlib, json, resource, shutil, subprocess, sys, time
from pathlib import Path
import nbformat
from nbclient import NotebookClient

ROOT = Path(__file__).resolve().parent
DATA, DB = ROOT / "data", ROOT / "data" / "marketplace.sqlite"
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()

# check 1: same python as the lock file (uv run --locked already refuses an outdated uv.lock)
assert sys.version_info[:2] == (3, 12), f"python 3.12 expected, got {sys.version.split()[0]}"

# check 2: supplied files unchanged
for line in (ROOT / "supplied.sha256").read_text().splitlines():
    digest, name = line.split(maxsplit=1)
    assert sha(ROOT / name) == digest, f"{name} differs from supplied.sha256"
print("supplied files match supplied.sha256")

# start clean: no output from an earlier run can survive into this one (--fast keeps only the engine comparison)
keep = {p.name: p.read_bytes() for p in (DATA / "01_load").glob("bench*.csv")} if "--fast" in sys.argv else {}
shutil.rmtree(DATA, ignore_errors=True)
DATA.mkdir()
if keep:
    (DATA / "01_load").mkdir()
    for name, b in keep.items():
        (DATA / "01_load" / name).write_bytes(b)

# step 0: fresh working db from raw.sql with the supplied loader
t = time.perf_counter()
subprocess.run([sys.executable, ROOT / "supplied" / "setup_db.py", "--db", DB], check=True)
peak = resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss / (1e6 if sys.platform == "darwin" else 1e3)
raw = (ROOT / "supplied" / "data" / "raw.sql").stat().st_size / 1e6
# its own process, so peak is the whole process. estimate: python ~15 MB + the sql text read whole + sqlite cache
res = {"step": "00_setup_db", "seconds": round(time.perf_counter() - t, 2), "rss_peak_MB": round(peak, 2), "in_memory_MB": {"raw.sql text": round(raw, 2)},
       "estimate_peak_MB": f"{15 + raw:.0f}-{15 + 2 * raw:.0f}", "saved_MB": {DB.name: round(DB.stat().st_size / 1e6, 2)}}
(DATA / "00_setup_db").mkdir()
(DATA / "00_setup_db" / "resources.json").write_text(json.dumps(res, indent=1))
print(res)

# engine comparison for step 1, 3-8 min
if not keep:
    t = time.perf_counter()
    subprocess.run([sys.executable, ROOT / "bench.py"], check=True, stdout=subprocess.DEVNULL)
    print(f"bench.py  {time.perf_counter() - t:.1f} s")

# kernel lives inside .venv so the notebook always runs on this project's env
subprocess.run([sys.executable, "-m", "ipykernel", "install", "--sys-prefix", "--name", "eng2040-a1"], check=True, capture_output=True)
path = ROOT / "pipeline.ipynb"
nb = nbformat.read(path, as_version=4)
t = time.perf_counter()
NotebookClient(nb, timeout=1800, kernel_name="eng2040-a1", resources={"metadata": {"path": str(ROOT)}}).execute()  # stops at the first failing assert
nbformat.write(nb, path)
print(f"pipeline.ipynb  {time.perf_counter() - t:.1f} s (incl kernel start)")

# check 3: one clean top to bottom pass, no error output anywhere
cells = [c for c in nb.cells if c.cell_type == "code"]
assert [c.execution_count for c in cells] == list(range(1, len(cells) + 1)), "cells did not run once, in order"
assert not any(o.output_type == "error" for c in cells for o in c.outputs), "a cell has an error output"

# check 4: every output byte for byte against expected.sha256 (committed). timing files always differ, so they are left out.
# charts are compared too, but only warned on: font rendering can differ between machines while the data behind them does not
skip = {"resources.json", "bench.csv", "bench_raw.csv", "engine_comparison.png", "resources_summary.csv", "environment.json"}
files = sorted(p for p in DATA.rglob("*") if p.is_file() and p.name not in skip and p.suffix != ".sqlite")
now = {str(p.relative_to(ROOT)): sha(p) for p in files}
(DATA / "manifest.sha256").write_text("".join(f"{h}  {n}\n" for n, h in now.items()))
expected_path = ROOT / "expected.sha256"
if "--update" in sys.argv:
    expected_path.write_text((DATA / "manifest.sha256").read_text())
    print(f"expected.sha256 updated, {len(now)} files")
    sys.exit()
expected = dict(reversed(l.split("  ", 1)) for l in expected_path.read_text().splitlines())
missing, extra = sorted(set(expected) - set(now)), sorted(set(now) - set(expected))
differ = sorted(n for n in set(now) & set(expected) if now[n] != expected[n])
charts = [n for n in differ if n.endswith(".png")]
data = [n for n in differ if not n.endswith(".png")]
for n in charts:
    print("warning, chart differs (rendering):", n)
assert not (missing or extra or data), f"outputs differ from expected.sha256\n missing {missing}\n extra {extra}\n differ {data}"
print(f"all {len(now)} outputs match expected.sha256" + (f" ({len(charts)} charts only warned)" if charts else ""))
