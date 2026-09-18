import argparse
import os
from pathlib import Path

from dotenv import load_dotenv

from worker.adapters.apf import ApfCatalogAdapter
from worker.adapters.dof import DofAdapter
from worker.adapters.gobierno import GobiernoMxAdapter
from worker.adapters.leyesbiblio import LeyesBiblioAdapter
from worker.adapters.nomina import NominaTransparenteAdapter
from worker.publisher import ApprovedCandidatePublisher
from worker.runner import IngestionRunner, dump_result

ADAPTERS = {
    "apf": ApfCatalogAdapter,
    "gobierno": GobiernoMxAdapter,
    "leyesbiblio": LeyesBiblioAdapter,
    "nomina": NominaTransparenteAdapter,
    "dof": DofAdapter,
}


def main() -> None:
    # El worker se ejecuta desde apps/worker en Railway y desde la raíz en
    # desarrollo. Cargar explícitamente el .env del monorepo evita que una
    # ejecución local caiga silenciosamente en el almacenamiento temporal.
    load_dotenv(Path(__file__).resolve().parents[3] / ".env")
    parser = argparse.ArgumentParser(description="Ingiere fuentes oficiales o publica candidatos aprobados.")
    parser.add_argument("command", choices=[*sorted(ADAPTERS), "publish-approved"])
    parser.add_argument("--adapter", choices=sorted(ADAPTERS), help="Limita la publicación a un adaptador.")
    parser.add_argument("--limit", type=int, help="Publica como máximo este número de tareas aprobadas.")
    args = parser.parse_args()
    if args.command == "publish-approved":
        database_url = os.environ.get("DATABASE_URL")
        if not database_url:
            parser.error("DATABASE_URL is required to publish approved candidates")
        adapter_key = ADAPTERS[args.adapter]().key if args.adapter else None
        print(dump_result(ApprovedCandidatePublisher(database_url).publish(adapter_key, args.limit).as_dict()))
        return
    print(dump_result(IngestionRunner(ADAPTERS[args.command]()).run()))


if __name__ == "__main__":
    main()
