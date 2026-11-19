
from pathlib import Path
from datetime import datetime
import subprocess
import shutil
import csv
import time
import pandas as pd
import yaml

# ============================================================
# 1. CONFIGURACIÓN DEL PROYECTO
# ============================================================

ROOT = Path(__file__).resolve().parents[1]

with open(ROOT / "config" / "config.yaml", encoding="utf-8") as f:
    config = yaml.safe_load(f)

N_RUNS = int(config["download"]["n_runs"])
MAX_SIZE = str(config["download"].get("max_size", "u"))
STRATEGY = config["download"].get("strategy", "sequential")

METADATA_FILE = ROOT / config["paths"]["metadata"] / "SraRunInfo.csv"
SRA_DIR = ROOT / config["paths"]["sra"]
BENCHMARK_DIR = ROOT / config["paths"]["benchmarks"]

SRA_DIR.mkdir(parents=True, exist_ok=True)
BENCHMARK_DIR.mkdir(parents=True, exist_ok=True)

BENCHMARK_FILE = BENCHMARK_DIR / "download_times_sequential.csv"


# ============================================================
# 2. COMPROBAR QUE SRA TOOLKIT ESTÉ DISPONIBLE
# ============================================================

prefetch = shutil.which("prefetch")

if prefetch is None:
    raise RuntimeError(
        "No se encontró prefetch. Comprobá que SRA Toolkit "
        "esté agregado al PATH de esta terminal."
    )


# ============================================================
# 3. LEER LOS METADATOS Y SELECCIONAR CORRIDAS
# ============================================================

if not METADATA_FILE.exists():
    raise FileNotFoundError(
        f"No se encontró el archivo: {METADATA_FILE}"
    )

metadata = pd.read_csv(METADATA_FILE)

if "Run" not in metadata.columns:
    raise ValueError("El archivo SraRunInfo.csv no contiene Run.")

runs = metadata["Run"].dropna().astype(str).tolist()
selected_runs = runs[:N_RUNS]

print(f"Corridas seleccionadas: {len(selected_runs)}")
print(f"Estrategia: {STRATEGY}")
print(f"Directorio de destino: {SRA_DIR}")


# ============================================================
# 4. PREPARAR EL REGISTRO DE BENCHMARKS
# ============================================================

fields = [
    "timestamp",
    "run",
    "strategy",
    "status",
    "elapsed_seconds",
    "size_bytes",
    "size_MB",
    "throughput_MB_s"
]

# ============================================================
# 5. DESCARGAR O RECONOCER CADA CORRIDA
# ============================================================

for i, accession in enumerate(selected_runs, start=1):

    print(f"\n[{i}/{len(selected_runs)}] Procesando {accession}")

    run_dir = SRA_DIR / accession
    sra_file = run_dir / f"{accession}.sra"

    # Buscar también una descarga manual en la raíz del proyecto.
    manual_file = ROOT / accession / f"{accession}.sra"

    # Si existe en la raíz, incorporarla a la estructura definitiva.
    if not sra_file.exists() and manual_file.exists():

        print("Archivo encontrado en la raíz del proyecto.")
        print("Moviendo a data/raw/sra/...")

        run_dir.parent.mkdir(parents=True, exist_ok=True)

        if run_dir.exists():
            print("La carpeta de destino ya existe. No se mueve.")
        else:
            shutil.move(str(manual_file.parent), str(run_dir))

    # --------------------------------------------------------
    # CASO A: LA CORRIDA YA ESTÁ DESCARGADA
    # --------------------------------------------------------

    if sra_file.exists():

        size_bytes = sra_file.stat().st_size
        size_mb = size_bytes / (1024 ** 2)

        status = "already_present"
        elapsed = ""
        throughput = ""

        print("La corrida ya está disponible.")
        print(f"Tamaño: {size_mb:.2f} MB")
        print("No se realizará otra descarga.")

    # --------------------------------------------------------
    # CASO B: LA CORRIDA TODAVÍA NO EXISTE
    # --------------------------------------------------------

    else:

        run_dir.mkdir(parents=True, exist_ok=True)

        command = [
            prefetch,
            accession,
            "-O", str(run_dir),
            "--max-size", MAX_SIZE,
            "--progress"
        ]

        print("Iniciando descarga...")
        start = time.perf_counter()

        try:
            result = subprocess.run(command, check=False)
            elapsed = time.perf_counter() - start

            if result.returncode == 0 and sra_file.exists():

                status = "downloaded"
                size_bytes = sra_file.stat().st_size
                size_mb = size_bytes / (1024 ** 2)
                throughput = size_mb / elapsed if elapsed > 0 else ""

                print("Descarga completada.")
                print(f"Tiempo: {elapsed:.2f} segundos")
                print(f"Tamaño: {size_mb:.2f} MB")
                print(f"Velocidad: {throughput:.2f} MB/s")

            else:

                status = f"failed_{result.returncode}"
                size_bytes = (
                    sra_file.stat().st_size if sra_file.exists() else 0
                )
                size_mb = size_bytes / (1024 ** 2)
                throughput = ""

                print(f"Descarga fallida. Código: {result.returncode}")

        except Exception as error:

            elapsed = time.perf_counter() - start
            status = "error"
            size_bytes = 0
            size_mb = 0
            throughput = ""

            print(f"Error: {error}")

    # --------------------------------------------------------
    # GUARDAR RESULTADO DE ESTA CORRIDA
    # --------------------------------------------------------

    record = {
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "run": accession,
        "strategy": STRATEGY,
        "status": status,
        "elapsed_seconds": elapsed,
        "size_bytes": size_bytes,
        "size_MB": round(size_mb, 2),
        "throughput_MB_s": (
            round(throughput, 2) if throughput != "" else ""
        )
    }

    write_header = not BENCHMARK_FILE.exists()

    with open(BENCHMARK_FILE, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)

        if write_header:
            writer.writeheader()

        writer.writerow(record)


# ============================================================
# 6. FINALIZACIÓN
# ============================================================

print("\nProceso finalizado.")
print(f"Resultados guardados en: {BENCHMARK_FILE}")
