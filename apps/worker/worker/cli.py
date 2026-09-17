import argparse

from worker.adapters.dof import DofAdapter
from worker.adapters.gobierno import GobiernoMxAdapter
from worker.adapters.leyesbiblio import LeyesBiblioAdapter
from worker.runner import IngestionRunner, dump_result

ADAPTERS = {
    "gobierno": GobiernoMxAdapter,
    "leyesbiblio": LeyesBiblioAdapter,
    "dof": DofAdapter,
}


def main() -> None:
    parser = argparse.ArgumentParser(description="Ejecuta una fuente oficial y genera candidatos para revisión.")
    parser.add_argument("adapter", choices=sorted(ADAPTERS))
    args = parser.parse_args()
    print(dump_result(IngestionRunner(ADAPTERS[args.adapter]()).run()))


if __name__ == "__main__":
    main()
