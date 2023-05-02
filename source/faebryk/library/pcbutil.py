import itertools
import logging
import math
import random
from operator import add
from typing import Any, Dict, List, Tuple, TypeVar

import numpy as np
from faebryk.library.core import Component, ComponentTrait, FaebrykLibObject, Interface
from faebryk.library.kicad import has_kicad_footprint
from faebryk.library.traits.component import (
    has_footprint,
    has_footprint_pinmap,
    has_overriden_name,
)
from faebryk.library.util import get_all_components
from library.kicadpcb import PCB, At, Footprint, Line, Pad, Text, Via

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

    def __init__(self, pcb: PCB, graph: Component, cleanup: bool = True) -> None:
        self.pcb = pcb
        self.graph = graph

        self.dimensions = None

        FONT_SCALE = 8
        FONT = (1 / FONT_SCALE, 1 / FONT_SCALE, 0.15 / FONT_SCALE)
        self.font = FONT

        # After finalized, vias get changed to 0.45
        self.via_size_drill = (0.46, 0.2)

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

    def insert_via(self, coord: Tuple[float, float], net: str):
        self.pcb.append(
            Via.factory(
                at=At.factory(coord),
                size_drill=self.via_size_drill,
                layers=("F.Cu", "B.Cu"),
                net=net,
                tstamp=str(next(self.tstamp_i)),
            )
        )

    @staticmethod
    def get_any_fp_map(intf: Interface) -> Tuple[Dict[str, Interface], Component]:
        obj: FaebrykLibObject = intf

        while not obj.has_trait(has_footprint_pinmap):
            if obj.parent is None:
                raise Exception
            obj = obj.parent[0]

        assert isinstance(obj, Component)
        pin_map = obj.get_trait(has_footprint_pinmap).get_pin_map()
        return pin_map, obj

    @staticmethod
    def get_pad(intf: Interface) -> Tuple[Footprint, Pad]:
        pin_map, cmp = PCB_Transformer.get_any_fp_map(intf)
        pin_name = [k for k, v in pin_map.items() if v == intf][0]

        fp = PCB_Transformer.get_fp(cmp)
        pad = fp.get_pad(pin_name)

        return fp, pad

    def insert_via_next_to(self, intf: Interface, clearance: Tuple[float, float]):
        fp, pad = self.get_pad(intf)

        rel_target = tuple(map(add, pad.at.coord, clearance))
        coord = self.Geometry.abs_pos(fp.at.coord, rel_target)

        self.insert_via(coord[:2], pad.net)

        # print("Inserting via for", ".".join([y for x,y in intf.get_hierarchy()]), "at:", coord, "in net:", net)
        ...

    def insert_via_triangle(
        self, intfs: List[Interface], depth: float, clearance: float
    ):
        # get pcb pads
        fp_pads = list(map(self.get_pad, intfs))
        pads = [x[1] for x in fp_pads]
        fp = fp_pads[0][0]

        # from first & last pad
        rect = [pads[-1].at.coord[i] - pads[0].at.coord[i] for i in range(2)]
        assert 0 in rect
        width = [p for p in rect if p != 0][0]
        start = pads[0].at.coord

        # construct triangle
        shape = self.Geometry.triangle(
            self.Geometry.abs_pos(fp.at.coord, start),
            width=width,
            depth=depth,
            count=len(pads),
        )

        # clearance
        shape = self.Geometry.translate(
            tuple([clearance if x != 0 else 0 for x in rect]), shape
        )

        # place vias
        for pad, point in zip(pads, shape):
            self.insert_via(point, pad.net)

    def insert_via_line(
        self, intfs: List[Interface], length: float, clearance: float, angle_deg: float
    ):
        raise NotImplementedError()
        # get pcb pads
        fp_pads = list(map(self.get_pad, intfs))
        pads = [x[1] for x in fp_pads]
        fp = fp_pads[0][0]

        # from first & last pad
        start = pads[0].at.coord
        abs_start = self.Geometry.abs_pos(fp.at.coord, start)

        shape = self.Geometry.line(
            start=abs_start,
            length=length,
            count=len(pads),
        )

        shape = self.Geometry.rotate(
            axis=abs_start[:2],
            structure=shape,
            angle_deg=angle_deg,
        )

        # clearance
        shape = self.Geometry.translate((clearance, 0), shape)

        # place vias
        for pad, point in zip(pads, shape):
            self.insert_via(point, pad.net)

    def insert_via_line2(
        self,
        intfs: List[Interface],
        length: Tuple[float, float],
        clearance: Tuple[float, float],
    ):
        # get pcb pads
        fp_pads = list(map(self.get_pad, intfs))
        pads = [x[1] for x in fp_pads]
        fp = fp_pads[0][0]

        # from first & last pad
        start = tuple(map(add, pads[0].at.coord, clearance))
        abs_start = self.Geometry.abs_pos(fp.at.coord, start)

        shape = self.Geometry.line2(
            start=abs_start,
            end=self.Geometry.abs_pos(abs_start, length),
            count=len(pads),
        )

        # place vias
        for pad, point in zip(pads, shape):
            self.insert_via(point, pad.net)

    # Geometry ----------------------------------------------------------------
    class Geometry:
        Point = Tuple[float, float]

        @staticmethod
        def abs_pos(parent: At.Coord, child: At.Coord) -> At.Coord:
            x, y = parent[:2]
            rot = 0
            if len(parent) > 2:
                rot = parent[2] / 360 * 2 * math.pi

            cx, cy = child[:2]

            rx = round(cx * math.cos(rot) + cy * math.sin(rot), 2)
            ry = round(-cx * math.sin(rot) + cy * math.cos(rot), 2)

            # print(f"Rotate {round(cx,2),round(cy,2)}, by {round(rot,2),parent[2]} to {rx,ry}")

            return x + rx, y + ry, 0

        @staticmethod
        def translate(vec: Point, structure: List[Point]):
            return [tuple(map(add, vec, point)) for point in structure]

        @classmethod
        def rotate(
            cls, axis: Point, structure: List[Point], angle_deg: float
        ) -> List[Point]:
            theta = np.radians(angle_deg)
            c, s = np.cos(theta), np.sin(theta)
            R = np.array(((c, -s), (s, c)))

            return cls.translate(
                (-axis[0], -axis[1]),
                [
                    tuple(R @ np.array(point))
                    for point in cls.translate(axis, structure)
                ],
            )

        @staticmethod
        def triangle(start: At.Coord, width: float, depth: float, count: int):
            x1, y1 = start[:2]

            n = count - 1
            cy = width / n

            ys = [round(y1 + cy * i, 2) for i in range(count)]
            xs = [
                round(x1 + depth * (1 - abs(1 - 1 / n * i * 2)), 2)
                for i in range(count)
            ]

            return list(zip(xs, ys))

        @staticmethod
        def line(start: At.Coord, length: float, count: int):
            x1, y1 = start[:2]

            n = count - 1
            cy = length / n

            ys = [round(y1 + cy * i, 2) for i in range(count)]
            xs = [x1] * count

            return list(zip(xs, ys))

        @staticmethod
        def line2(start: At.Coord, end: At.Coord, count: int):
            x1, y1 = start[:2]
            x2, y2 = end[:2]

            n = count - 1
            cx = (x2 - x1) / n
            cy = (y2 - y1) / n

            ys = [round(y1 + cy * i, 2) for i in range(count)]
            xs = [round(x1 + cx * i, 2) for i in range(count)]

            return list(zip(xs, ys))
