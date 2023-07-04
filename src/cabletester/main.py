"""
TODO: Explain file
"""

import logging
import subprocess
from pathlib import Path

import typer
from cabletester.cable_tester import Cable_Tester
from cabletester.pcb import transform_pcb
from faebryk.core.graph import Graph
from faebryk.exporters.netlist.graph import make_t1_netlist_from_graph
from faebryk.exporters.netlist.kicad.netlist_kicad import from_faebryk_t2_netlist
from faebryk.exporters.netlist.netlist import make_t2_netlist_from_t1
from faebryk.exporters.pcb.kicad.transformer import PCB_Transformer
from faebryk.exporters.visualize.graph import render_matrix
from faebryk.libs.kicad.pcb import PCB
from faebryk.libs.logging import setup_basic_logging

# logging settings
logger = logging.getLogger(__name__)


def write_netlist(graph: Graph, path: Path) -> bool:
    logger.info("Making T1")
    t1 = make_t1_netlist_from_graph(graph)
    logger.info("Making T2")
    t2 = make_t2_netlist_from_t1(t1)
    logger.info("Making Netlist")
    netlist = from_faebryk_t2_netlist(t2)

    if path.exists():
        old_netlist = path.read_text()
        # TODO this does not work!
        if old_netlist == netlist:
            return False
        backup_path = path.with_suffix(path.suffix + ".bak")
        logger.info(f"Backup old netlist at {backup_path}")
        backup_path.write_text(old_netlist)

    assert isinstance(netlist, str)
    logger.info("Writing Experiment netlist to {}".format(path.resolve()))
    path.write_text(netlist, encoding="utf-8")

    # TODO faebryk/kicad bug: net names cant be too long -> pcb file can't save

    return True


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

    # visualize
    if False:
        render_matrix(
            G.G,
            nodes_rows=[],
            depth=1,
            show_full=True,
            show_non_sum=False,
        ).show()

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
        # input()

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
    # main()
