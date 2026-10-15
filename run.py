"""Rebuild every pipeline output from supplied/data/raw.sql: uv run python run.py  (--fast skips the engine comparison)"""
import hashlib, resource, subprocess, sys, time
from pathlib import Path
import nbformat
from nbclient import NotebookClient

ROOT = Path(__file__).resolve().parent
DB = ROOT / "data" / "marketplace.sqlite"

# supplied files must be unchanged
for line in (ROOT / "supplied.sha256").read_text().splitlines():
    digest, name = line.split(maxsplit=1)
    assert hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == digest, f"{name} changed"
print("supplied files match supplied.sha256")

# step 0: fresh working db from raw.sql with the supplied loader
DB.parent.mkdir(exist_ok=True)
DB.unlink(missing_ok=True)
t = time.perf_counter()
subprocess.run([sys.executable, ROOT / "supplied" / "setup_db.py", "--db", DB], check=True)
peak = resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss / (1e6 if sys.platform == "darwin" else 1e3)
print(f"00_setup_db  {time.perf_counter() - t:.1f} s  peak {peak:.0f} MB  db {DB.stat().st_size / 1e6:.1f} MB")

# engine comparison for step 1, about 3 min. --fast reuses the last result
if "--fast" not in sys.argv or not (ROOT / "data" / "01_load" / "bench.csv").exists():
    t = time.perf_counter()
    subprocess.run([sys.executable, ROOT / "bench.py"], check=True, stdout=subprocess.DEVNULL)
    print(f"bench.py  {time.perf_counter() - t:.1f} s")

# kernel lives inside .venv so notebooks always run on this project's env
subprocess.run([sys.executable, "-m", "ipykernel", "install", "--sys-prefix", "--name", "eng2040-a1"], check=True, capture_output=True)

path = ROOT / "pipeline.ipynb"
nb = nbformat.read(path, as_version=4)
t = time.perf_counter()
NotebookClient(nb, timeout=1800, kernel_name="eng2040-a1", resources={"metadata": {"path": str(ROOT)}}).execute()
nbformat.write(nb, path)
print(f"pipeline.ipynb  {time.perf_counter() - t:.1f} s (incl kernel start), per step numbers in data/<step>/resources.json")

# hash every output so two runs can be compared byte for byte. timing files always differ, so they are left out
skip = {"resources.json", "bench.csv", "bench_raw.csv", "engine_comparison.png", "resources_summary.csv", "environment.json", "manifest.sha256"}
files = sorted(p for p in (ROOT / "data").rglob("*") if p.is_file() and p.name not in skip and p.suffix != ".sqlite")
lines = [f"{hashlib.sha256(p.read_bytes()).hexdigest()}  {p.relative_to(ROOT)}" for p in files]
(ROOT / "data" / "manifest.sha256").write_text("\n".join(lines) + "\n")
print(f"data/manifest.sha256  {len(lines)} output files hashed")
