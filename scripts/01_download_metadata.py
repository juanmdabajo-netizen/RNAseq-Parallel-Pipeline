
from pathlib import Path
from io import StringIO
import requests
import pandas as pd
import yaml
import time

# Ubicación principal del proyecto
ROOT = Path(__file__).resolve().parents[1]

# Leer la configuración
with open(ROOT / "config" / "config.yaml", encoding="utf-8") as f:
    config = yaml.safe_load(f)

SRA_STUDY = config["project"]["sra_study"]

# Crear carpeta para guardar los resultados
METADATA_DIR = ROOT / config["paths"]["metadata"]
METADATA_DIR.mkdir(parents=True, exist_ok=True)

OUTPUT = METADATA_DIR / "SraRunInfo.csv"
ACCESSIONS = METADATA_DIR / "run_accessions.txt"

# Servicio de metadatos de NCBI
URL = "https://trace.ncbi.nlm.nih.gov/Traces/sra-db-be/runinfo"

params = {
    "acc": SRA_STUDY
}

print(f"Consultando NCBI: {SRA_STUDY}")

start = time.perf_counter()

try:
    response = requests.get(URL, params=params, timeout=120)
    response.raise_for_status()

    elapsed = time.perf_counter() - start

    if not response.text.strip():
        raise ValueError("NCBI devolvió una respuesta vacía.")

    # Interpretar la respuesta como tabla
    metadata = pd.read_csv(
        StringIO(response.text),
        sep=None,
        engine="python"
    )

    if "Run" not in metadata.columns:
        raise ValueError(
            "La respuesta no contiene la columna Run. "
            "Respuesta recibida:\n" + response.text[:1000]
        )

    metadata = metadata.dropna(subset=["Run"]).copy()
    metadata["Run"] = metadata["Run"].astype(str)

    if metadata.empty:
        raise ValueError("No se encontraron corridas SRA.")

    # Guardar archivos
    metadata.to_csv(OUTPUT, index=False)
    metadata["Run"].to_csv(
        ACCESSIONS,
        index=False,
        header=False
    )

    print("\n¡Consulta completada!")
    print(f"Estudio: {SRA_STUDY}")
    print(f"Corridas encontradas: {len(metadata)}")
    print(f"Tiempo de consulta: {elapsed:.2f} segundos")
    print(f"Archivo CSV: {OUTPUT}")
    print(f"Lista de corridas: {ACCESSIONS}")

    columns = [
        c for c in [
            "Run",
            "SampleName",
            "BioSample",
            "LibraryLayout",
            "LibraryStrategy",
            "size_MB"
        ]
        if c in metadata.columns
    ]

    print("\nResumen de corridas:")
    print(metadata[columns].to_string(index=False))

except requests.exceptions.RequestException as error:
    print("\nERROR de conexión con NCBI:")
    print(error)

except Exception as error:
    print("\nERROR al procesar los metadatos:")
    print(error)
