"""
TODO: Explain file
"""

import click
import logging
from pathlib import Path
import sys
from typing import Dict, List
import subprocess
from collections import defaultdict


# local imports
from cable_tester import Cable_Tester
from library.kicadpcb import PCB, Footprint, Text, At
import library.lcsc


# function imports
from faebryk.exporters.netlist.kicad.netlist_kicad import from_faebryk_t2_netlist
from faebryk.exporters.netlist.netlist import make_t2_netlist_from_t1
from faebryk.exporters.netlist.graph import (
    make_graph_from_components,
    make_t1_netlist_from_graph,
)

from faebryk.library.core import Component

# logging settings
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)
logging.getLogger(library.lcsc.__name__).setLevel(logging.DEBUG)

def write_netlist(components: List[Component], path: Path) -> bool:
    t1_ = make_t1_netlist_from_graph(make_graph_from_components(components))
    netlist = from_faebryk_t2_netlist(make_t2_netlist_from_t1(t1_))


    if path.exists():
        old_netlist = path.read_text()
        #TODO this does not work!
        if old_netlist == netlist:
            return False
        backup_path = path.with_suffix(path.suffix + ".bak")
        logger.info(f"Backup old netlist at {backup_path}")
        backup_path.write_text(old_netlist)

    logger.info("Writing Experiment netlist to {}".format(path.resolve()))
    path.write_text(netlist, encoding="utf-8")

    # from faebryk.exporters.netlist.netlist import render_graph
    # plt = render_graph(t1_)
    # plt.show()

    # TODO faebryk/kicad bug: net names cant be too long -> pcb file can't save

    return True


def transform_pcb(pcb: PCB):
    # positioning -------------------------------------------------------------
    groups: Dict[str, List[Footprint]] = defaultdict(lambda: [])
    for f in pcb.footprints:
        name = f.reference.text.split(".")
        if name[0] != "tester":
            continue
        group_name = name[1]
        if "Receptacle" in group_name:
            continue
        groups[group_name].append(f)

    touched_fps : List[Footprint] = []
    for i, (name, g) in enumerate(sorted(groups.items(), key=lambda x: x[0])):
        fs = {f.reference.text.split(".")[-1].split("[")[0]: f for f in g}
        for j, (fref, f) in enumerate(
            [
                (k, fs[k])
                for k in [
                    "pull_resistor",
                    "mosfet",
                    "current_limiting_resistor",
                    "led",
                ]
            ]
        ):
            # print(i, j, fref)
            if any(filter(lambda x: x.text == "FBRK:notouch", f.user_text)):
                logger.warning(f"Skipped no touch component: {f.name}")
                continue
            touched_fps.append(f)
            f.at.coord = (50 + j * 4, 15 + i * 4, 0)

    # --------------------------------------------------------------------------

    # rename, resize, relayer text
    for f in pcb.footprints:
        # ref
        f.reference.layer = "User.8"
        f.reference.at.coord = (0, 0, 0)
        f.reference.font = (0.5, 0.5, 0.075)

        # user
        name = f.reference.text.split(".")
        user_text = next(filter(lambda x: not x.text.startswith("FBRK:"), f.user_text))
        user_text.text = f"{name[1]}.{name[-1].split('[')[0]}"
        # user_text.layer = "F.SilkS"
        user_text.layer = "User.7"
        user_text.font = (0.5, 0.5, 0.075)

    for i,f in enumerate(touched_fps):
        if any(filter(lambda x: x.text == "FBRK:autoplaced", f.user_text)):
            continue
        f.append(Text.factory(text="FBRK:autoplaced", at=At.factory((0,0,0)), font=(1,1,0.15), tstamp=str(i), layer="User.5"))

    # reposition silkscreen text
    for f in pcb.footprints:
        rot = f.at.coord[2]
        if f.name in [
            "lcsc:SOT-23-3_L2.9-W1.3-P1.90-LS2.4-BR",
            "lcsc:R0402",
            "lcsc:LED0805-R-RD",
        ]:
            user_text = next(filter(lambda x: not x.text.startswith("FBRK:"), f.user_text))
            user_text.at.coord = (0, -2 if rot == 180 else 2, rot)


@click.command()
@click.option("--nonetlist", "-p", is_flag=True, help="don't regenerate netlist")
def main(nonetlist: bool):
    # paths
    build_dir = Path("./build")
    faebryk_build_dir = build_dir.joinpath("faebryk")
    faebryk_build_dir.mkdir(parents=True, exist_ok=True)
    kicad_prj_path = Path(__file__).parent.parent.joinpath("kicad/main")
    netlist_path = kicad_prj_path.joinpath("main.net")
    pcbfile = kicad_prj_path.joinpath("main.kicad_pcb")
    pcbnew = lambda: subprocess.check_output(["pcbnew", pcbfile], stderr=subprocess.DEVNULL)

    # graph
    G = Cable_Tester()

    # netlist
    netlist_updated = not nonetlist and write_netlist([G], netlist_path)

    if netlist_updated:
        logger.info("Opening kicad to import new netlist")
        print(
            f"Import the netlist at {netlist_path.as_posix()}. Press 'Update PCB'. Place the components, save the file and exit kicad."
        )
        pcbnew()

    # pcb
    pcb = PCB.load(pcbfile)

    transform_pcb(pcb)

    # import pprint
    # pprint.pprint(pcb.node)
    logger.info(f"Writing pcbfile {pcbfile}")
    pcb.dump(pcbfile)

    pcbnew()


if __name__ == "__main__":
    main()
