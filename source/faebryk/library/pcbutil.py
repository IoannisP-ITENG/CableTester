import itertools
import logging
import random
from typing import Any, List, Tuple, TypeVar
from faebryk.library.util import get_all_components
from faebryk.library.core import Component
from faebryk.library.traits.component import has_overriden_name, has_footprint, has_footprint_pinmap
from faebryk.library.kicad import has_kicad_footprint
from faebryk.library.core import ComponentTrait, Interface

from library.kicadpcb import At, Footprint, PCB, Line, Text, Via

logger = logging.getLogger(__name__)


class PCB_Transformer:
    class has_linked_kicad_footprint(ComponentTrait):
        def get_fp(self) -> Footprint:
            raise NotImplementedError()

    class has_linked_kicad_footprint_defined(has_linked_kicad_footprint.impl()):
        def __init__(self, fp: Footprint) -> None:
            super().__init__()
            self.fp = fp

        def get_fp(self):
            return self.fp

    def __init__(self, pcb: PCB, graph: Component) -> None:
        self.pcb = pcb
        self.graph = graph

        self.dimensions = None

        FONT_SCALE = 8
        FONT = (1 / FONT_SCALE, 1 / FONT_SCALE, 0.15 / FONT_SCALE)
        self.font = FONT
        self.via_size_drill = (0.55, 0.25)

        self.tstamp_i = itertools.count()

        self.attach()
        self.cleanup()

    def attach(self):
        footprints = {(f.reference.text, f.name): f for f in self.pcb.footprints}

        for cmp in get_all_components(self.graph):
            if not cmp.has_trait(has_overriden_name):
                continue
            if not cmp.has_trait(has_footprint):
                continue
            g_fp = cmp.get_trait(has_footprint).get_footprint()
            if not g_fp.has_trait(has_kicad_footprint):
                continue

            # TODO changed faebryk for this
            fp_ref = cmp.get_trait(has_overriden_name).get_name()
            fp_name = g_fp.get_trait(has_kicad_footprint).get_kicad_footprint()

            fp = footprints[(fp_ref, fp_name)]

            cmp.add_trait(self.has_linked_kicad_footprint_defined(fp))

    def set_dimensions(self, width_mm: float, height_mm: float):
        for line_node in self.pcb.get_prop("gr_line"):
            line = Line.from_node(line_node)
            if line.layer.node[1] != "Edge.Cuts":
                continue
            line.delete()

        points = [
            (0, 0),
            (0, height_mm),
            (width_mm, height_mm),
            (width_mm, 0),
            (0, 0),
        ]

        for start, end in zip(points[:-1], points[1:]):
            self.pcb.append(
                Line.factory(
                    start,
                    end,
                    stroke=Line.Stroke.factory(0.05, "default"),
                    layer="Edge.Cuts",
                    tstamp=str(int(random.random() * 100000)),
                )
            )

        self.dimensions = (width_mm, height_mm)

    def move_fp(self, fp: Footprint, coord: At.Coord):
        if any(filter(lambda x: x.text == "FBRK:notouch", fp.user_text)):
            logger.warning(f"Skipped no touch component: {fp.name}")
            return

        fp.at.coord = coord

        if any(filter(lambda x: x.text == "FBRK:autoplaced", fp.user_text)):
            return
        fp.append(
            Text.factory(
                text="FBRK:autoplaced",
                at=At.factory((0, 0, 0)),
                font=self.font,
                tstamp=str(next(self.tstamp_i)),
                layer="User.5",
            )
        )

    def cleanup(self):
        # delete auto-placed vias
        # determined by their size_drill values
        for via in self.pcb.vias:
            if via.size_drill == self.via_size_drill:
                via.delete()

    @staticmethod
    def get_fp(cmp) -> Footprint:
        return cmp.get_trait(PCB_Transformer.has_linked_kicad_footprint).get_fp()

    T = TypeVar("T")

    @staticmethod
    def flipped(l: List[Tuple[T, int]]) -> List[Tuple[T, int]]:
        return [(x, (y + 180) % 360) for x, y in reversed(l)]

    # TODO
    def insert_plane(self, layer: str, net: Any):
        raise NotImplementedError()

    def insert_via(self, coord: Tuple[float, float], intf: Interface):
        cmp : Component = intf.parent[0]
        pin_map = cmp.get_trait(has_footprint_pinmap).get_pin_map()
        pin_name = [k for k,v in pin_map.items() if v == intf][0]
        fp = self.get_fp(cmp)
        pad = fp.get_pad(pin_name)
        net = pad.get_prop("net")[0].node[1]
        #print("Inserting via for", ".".join([y for x,y in intf.get_hierarchy()]), "at:", coord, "in net:", net)

        self.pcb.append(
            Via.factory(
                at=At.factory(coord),
                size_drill=self.via_size_drill,
                layers=("F.Cu", "B.Cu"),
                net=net,
                tstamp=str(next(self.tstamp_i))
            )
        )
