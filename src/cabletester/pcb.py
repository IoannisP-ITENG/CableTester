import logging
from typing import List, Optional, Tuple, cast

from cabletester.cable_tester import Cable_Tester, PairTester
from faebryk.core.core import Module
from faebryk.core.util import get_all_nodes
from faebryk.exporters.pcb.kicad.transformer import PCB_Transformer
from faebryk.library.MOSFET import MOSFET
from faebryk.libs.kicad.pcb import At

# logging settings
logger = logging.getLogger(__name__)


def transform_pcb(transformer: PCB_Transformer):
    FONT_SCALE = 8
    FONT = (1 / FONT_SCALE, 1 / FONT_SCALE, 0.15 / FONT_SCALE)
    PLACE_VIAS = False

    LED_FP = "lcsc:LED0805-R-RD"
    MOSFET_FPS = [
        "lcsc:SOT-23-3_L2.9-W1.3-P1.90-LS2.4-BR",
        "lcsc:SOT-23_L2.9-W1.3-P1.90-LS2.4-BR",
    ]
    RESISTOR_FP = "lcsc:R0402"

    footprints = [
        cmp.get_trait(PCB_Transformer.has_linked_kicad_footprint).get_fp()
        for cmp in get_all_nodes(transformer.app)
        if cmp.has_trait(PCB_Transformer.has_linked_kicad_footprint)
    ]

    assert isinstance(transformer.app, Cable_Tester)
    app: Cable_Tester = transformer.app

    transformer.set_dimensions(50, 50)

    # positioning -------------------------------------------------------------
    t = app.NODEs.tester.NODEs
    matrix: List[Tuple[Optional[PairTester], PairTester]] = [
        (t.cc1, t.cc2),
        (t.sbu1, t.sbu2),
        tuple(t.d1),
        tuple(t.d2),
        tuple(t.pair1_rx1),
        tuple(t.pair2_rx2),
        tuple(t.pair3_tx1),
        tuple(t.pair4_tx2),
        (t.vbus[0], t.gnd[0]),
        (t.vbus[1], t.gnd[1]),
        (t.vbus[2], t.gnd[2]),
        (t.vbus[3], t.gnd[3]),
        (None, t.shield),
    ]
    base = (13, 2.5)
    for i, (le, ri) in enumerate(matrix):
        for j, x in enumerate([le, ri]):
            if x is None:
                continue
            flip = j == 1
            alt = x in t.gnd + [t.shield]

            ind = x.NODEs.indicator.NODEs
            led = ind.led.NODEs.led
            clr = ind.led.NODEs.current_limiting_resistor
            mos = ind.power_switch.NODEs.mosfet
            pr = ind.power_switch.NODEs.pull_resistor

            layout: List[Tuple[Module, int]] = [
                (pr, 270),
                (mos, 180),
                (clr, 270),
                (led, 0),
            ]
            if alt:
                layout = [(pr, 270), (mos, 180), (led, 180), (clr, 270)]
            if flip:
                layout = PCB_Transformer.flipped(layout)

            # left, up, right, down
            clearances = {
                LED_FP: (2.25, 1, 2, 1),
                RESISTOR_FP: (1, 0.5, 1, 0.5),
                MOSFET_FPS[0]: (2, 3.25, 2, 3.25),
                MOSFET_FPS[1]: (2, 3.25, 2, 3.25),
            }

            group_x_ptr = 0
            for j2, (cmp, rot) in enumerate(layout):
                fp = PCB_Transformer.get_fp(cmp)
                clearance = clearances.get(fp.name, tuple([3] * 4))
                # rotate
                clearance = tuple(clearance[rot // 90 :] + clearance[: rot // 90])

                group_x_ptr += clearance[0]

                target = (
                    base[0] + j * 11 + group_x_ptr,  # x row length
                    base[1] + i * 3.25,  # y mosfet clearance
                    rot,
                )
                transformer.move_fp(fp, target)
                group_x_ptr += clearance[2]

                # mosfet vias
                if PLACE_VIAS:
                    if isinstance(cmp, MOSFET):
                        # source via to power plane
                        if ind.power_switch.lowside:
                            transformer.insert_via_next_to(
                                intf=cmp.IFs.drain, clearance=(-1.5, 0)
                            )
                        # gate via to signal plane
                        transformer.insert_via_next_to(
                            intf=cmp.IFs.gate, clearance=(1.5, 0.5)
                        )

    # Done, and moved manually, so disabling now
    # USB VIA
    # usb_pm = t.usb_c[1].get_trait(has_footprint_pinmap).get_pin_map()
    # for side in ["A", "B"]:
    #    intfs = [usb_pm[f"{side}{i}"] for i in range(1, 13)]
    #    if side == "B":
    #        transformer.insert_via_triangle(
    #            intfs,
    #            depth=5 if side == "A" else -5.5,
    #            clearance=0.75 if side == "A" else -0.75,
    #        )
    #    if side == "A":
    #        transformer.insert_via_line2(intfs[:6], (6, 0), (0, -0.75))
    #        transformer.insert_via_line2(list(reversed(intfs[6:])), (6, 0), (0, -0.75))

    # --------------------------------------------------------------------------
    def place_label(cmp: PairTester):
        fp = PCB_Transformer.get_fp(cmp.NODEs.indicator.NODEs.led.NODEs.led)
        assert len(fp.at.coord) == 3
        parent = cmp.get_parent()
        assert parent is not None
        name = parent[1]
        # TODO move a bit
        c = fp.at.coord
        at = At.factory(
            (
                c[0],
                c[1] - 1.5,
                0,
            )
        )

        transformer.insert_text(
            text=name, at=at, font=(1 / 4, 1 / 4, 0.15 / 4), permanent=True
        )

    for cmp in t.get_all():
        if isinstance(cmp, list):
            for cmp_ in cmp:
                place_label(cmp_)
        if isinstance(cmp, PairTester):
            place_label(cmp)

    # --------------------------------------------------------------------------
    # rename, resize, relayer text
    for f in footprints:
        # ref
        f.reference.layer = "User.8"
        f.reference.at.coord = (0, 0, 0)
        f.reference.font = (0.5, 0.5, 0.075)

        # user
        name = f.reference.text.split(".")
        user_text = next(filter(lambda x: not x.text.startswith("FBRK:"), f.user_text))
        user_text.text = f"{name[1]}.{name[-1].split('[')[0]}"
        # user_text.layer = "F.Silkscreen"
        user_text.layer = "User.7"
        user_text.font = FONT

    # reposition silkscreen text
    for f in footprints:
        assert len(f.at.coord) > 2
        rot = cast(tuple[float, float, float], f.at.coord)[2]
        if f.name in [*MOSFET_FPS, RESISTOR_FP, LED_FP]:
            user_text = next(
                filter(lambda x: not x.text.startswith("FBRK:"), f.user_text)
            )
            user_text.at.coord = (0, -2 if rot in [180, 270] else 2, rot)
