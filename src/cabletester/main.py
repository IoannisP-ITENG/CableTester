"""
TODO: Explain file
"""

import logging
import subprocess
from pathlib import Path

import typer
from cabletester.cable_tester import Cable_Tester
from cabletester.pcb import transform_pcb
from cabletester.util import write_netlist
from faebryk.exporters.pcb.kicad.transformer import PCB_Transformer
from faebryk.libs.kicad.pcb import PCB
from faebryk.libs.logging import setup_basic_logging

# logging settings
logger = logging.getLogger(__name__)


def main(nonetlist: bool = False, nopcb: bool = False):
    # paths
    build_dir = Path("./build")
    faebryk_build_dir = build_dir.joinpath("faebryk")
    faebryk_build_dir.mkdir(parents=True, exist_ok=True)
    kicad_prj_path = Path(__file__).parent.parent.joinpath("kicad/main")
    netlist_path = kicad_prj_path.joinpath("main.net")
    pcbfile = kicad_prj_path.joinpath("main.kicad_pcb")

    def pcbnew():
        return subprocess.check_output(["pcbnew", pcbfile], stderr=subprocess.DEVNULL)

    # graph
    logger.info("Make app")
    app = Cable_Tester()

    logger.info("Build graph")
    G = app.get_graph()

    # netlist
    logger.info("Make netlist")
    netlist_updated = not nonetlist and write_netlist(G, netlist_path)

    if netlist_updated:
        logger.info("Opening kicad to import new netlist")
        print(
            f"Import the netlist at {netlist_path.as_posix()}. Press 'Update PCB'. "
            "Place the components, save the file and exit kicad."
        )
        # pcbnew()
        if not nopcb:
            input()

    # pcb
    if nopcb:
        logger.info("Skipping PCB")
        return

    logger.info("Load PCB")
    pcb = PCB.load(pcbfile)

    transformer = PCB_Transformer(pcb, G, app)

    logger.info("Transform PCB")
    transform_pcb(transformer)

    # import pprint
    # pprint.pprint(pcb.node)
    logger.info(f"Writing pcbfile {pcbfile}")
    pcb.dump(pcbfile)

    # pcbnew()


if __name__ == "__main__":
    setup_basic_logging()
    typer.run(main)
