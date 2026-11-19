
from pathlib import Path
import subprocess
import pandas as pd
import yaml
import time
from datetime import datetime, timezone

# --------------------------------------------------
# 1. CONFIGURACION
# --------------------------------------------------

ROOT = Path(__file__).resolve().parents[1]

with open(ROOT / "config" / "config.yaml", encoding="utf-8") as f:
    config = yaml.safe_load(f)

METADATA = ROOT / config["paths"]["metadata"] / "SraRunInfo.csv"
SRA_DIR = ROOT / config["paths"]["sra"]
BENCH_DIR = ROOT / config["paths"]["benchmarks"]

SRA_DIR.mkdir(parents=True, exist_ok=True)
BENCH_DIR.mkdir(parents=True, exist_ok=True)

N_RUNS = config["download"]["n_runs"]
MAX_SIZE = config["download"]["max_size"]

# --------------------------------------------------
# 2. CARGAR ACCESIONES
# --------------------------------------------------

if not METADATA.is_file():
    raise FileNotFoundError(
        "Primero debe ejecutarse 01_download_metadata.py"
    )

metadata = pd.read_csv(METADATA)

runs = metadata["Run"].dropna().astype(str).tolist()

if N_RUNS > 0:
    runs = runs[:N_RUNS]

print(f"Corridas seleccionadas: {len(runs)}")

# --------------------------------------------------
# 3. FUNCION PARA MEDIR TAMAÑO
# --------------------------------------------------

def directory_size(path):
    return sum(
        f.stat().st_size
        for f in path.rglob("*")
        if f.is_file()
    )

# --------------------------------------------------
# 4. DESCARGA SECUENCIAL
# --------------------------------------------------

records = []

for i, run in enumerate(runs, start=1):

    print(f"\n[{i}/{len(runs)}] Descargando {run}")

    output_dir = SRA_DIR / run
    sra_file = output_dir / f"{run}.sra"

    if sra_file.is_file():
        print("Archivo SRA ya existente. Se omite.")

        records.append({
            "Run": run,
            "status": "already_present",
            "start_time": None,
            "elapsed_seconds": 0,
            "size_bytes": sra_file.stat().st_size
        })

        continue

    output_dir.mkdir(parents=True, exist_ok=True)

    start_datetime = datetime.now(timezone.utc).isoformat()
    start = time.perf_counter()

    command = [
        "prefetch",
        run,
        "-O", str(output_dir),
        "--max-size", str(MAX_SIZE)
    ]

    try:
        subprocess.run(command, check=True)

        elapsed = time.perf_counter() - start
        size = directory_size(output_dir)

        status = "completed"

    except subprocess.CalledProcessError as error:

        elapsed = time.perf_counter() - start
        size = directory_size(output_dir)
        status = f"failed: {error.returncode}"

    records.append({
        "Run": run,
        "status": status,
        "start_time": start_datetime,
        "elapsed_seconds": round(elapsed, 3),
        "size_bytes": size
    })

    print(f"Estado: {status}")
    print(f"Tiempo: {elapsed:.2f} segundos")
    print(f"Tamaño: {size / 1e9:.3f} GB")

# --------------------------------------------------
# 5. GUARDAR BENCHMARK
# --------------------------------------------------

results = pd.DataFrame(records)

output_csv = BENCH_DIR / "download_times_sequential.csv"

if output_csv.exists():
    previous = pd.read_csv(output_csv)
    results = pd.concat(
        [previous, results],
        ignore_index=True
    )

results.to_csv(output_csv, index=False)

print("\nDescarga finalizada.")
print(f"Resultados guardados en: {output_csv}")
