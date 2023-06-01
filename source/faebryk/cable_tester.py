import logging
from typing import List

logger = logging.getLogger(__name__)

# local imports
import library.lcsc as lcsc

# library imports
from faebryk.library.core import Component
from faebryk.library.library.components import LED, Resistor
from faebryk.library.library.interfaces import Electrical, Power
from faebryk.library.library.parameters import Constant, Range
from faebryk.library.trait_impl.component import (
    has_defined_footprint_pinmap,
    has_defined_type_description,
    has_symmetric_footprint_pinmap,
)
from faebryk.library.traits.component import has_footprint, has_footprint_pinmap

# function imports
from faebryk.library.util import get_all_components, times

# Project library imports
from library.library.components import (
    MOSFET,
    DifferentialPair,
    PoweredLED,
    PowerSwitch,
    RJ45_Receptacle,
    USB_C_Receptacle,
)

K = 1000
M = 1000_000
G = 1000_000_000

n = 0.001 * 0.001 * 0.001
u = 0.001 * 0.001
m = 0.001


class USB_C_PSU(Component):
    def __init__(self) -> None:
        super().__init__()

        # interfaces
        class _IFs(Component.InterfacesCls()):
            power_out = Power()

        self.IFs = _IFs(self)

        # components
        class _CMPs(Component.ComponentsCls()):
            usb = USB_C_Receptacle()
            configuration_resistors = times(2, lambda: Resistor(Constant(5.1 * K)))

        self.CMPs = _CMPs(self)

        self.IFs.power_out.IFs.hv.connect_all(self.CMPs.usb.IFs.vbus)
        self.IFs.power_out.IFs.lv.connect_all(self.CMPs.usb.IFs.gnd)

        # configure as ufp with 5V@max3A
        self.CMPs.usb.IFs.cc1.connect_via(
            self.CMPs.configuration_resistors[0], self.IFs.power_out.IFs.lv
        )
        self.CMPs.usb.IFs.cc2.connect_via(
            self.CMPs.configuration_resistors[1], self.IFs.power_out.IFs.lv
        )


class LEDIndicator(Component):
    def __init__(self, logic_low: bool, normally_on: bool) -> None:
        super().__init__()

        # interfaces
        class _IFs(Component.InterfacesCls()):
            # hv = high #TODO replace with Logical
            logic_in = Electrical()
            power_in = Power()

        self.IFs = _IFs(self)

        # components
        class _CMPs(Component.ComponentsCls()):
            led = PoweredLED()
            power_switch = PowerSwitch(
                lowside=not logic_low, normally_closed=normally_on
            )

        self.CMPs = _CMPs(self)

        #
        self.IFs.power_in.connect_via(self.CMPs.power_switch, self.CMPs.led.IFs.power)
        self.CMPs.power_switch.IFs.logic_in.connect(self.IFs.logic_in)


class PairTester(Component):
    def __init__(self, logic_low: bool = False) -> None:
        super().__init__()

        # interfaces
        class _IFs(Component.InterfacesCls()):
            power_in = Power()
            # TODO logical?
            wires = times(2, Electrical)

        self.IFs = _IFs(self)

        # components
        class _CMPs(Component.ComponentsCls()):
            indicator = LEDIndicator(logic_low=logic_low, normally_on=False)

        self.CMPs = _CMPs(self)

        #
        self.CMPs.indicator.IFs.power_in.connect(self.IFs.power_in)

        # connect logic high to indicator through wire pair
        self.IFs.wires[0].connect(
            self.IFs.power_in.IFs.lv if logic_low else self.IFs.power_in.IFs.hv
        )
        self.IFs.wires[1].connect(self.CMPs.indicator.IFs.logic_in)


class Tester(Component):
    def __init__(self) -> None:
        super().__init__()

        # interfaces
        class _IFs(Component.InterfacesCls()):
            power_in = Power()

        self.IFs = _IFs(self)

        # components
        class _CMPs(Component.ComponentsCls()):
            cc1 = PairTester()
            cc2 = PairTester()
            sbu1 = PairTester()
            sbu2 = PairTester()
            shield = PairTester(logic_low=True)  # in-case connected to gnd
            # power
            gnd = times(
                4, lambda: PairTester(logic_low=True)
            )  # logic_low to give emarker power
            vbus = times(4, PairTester)
            # diffpairs: p, n
            pair1_rx1 = times(2, PairTester)
            pair2_rx2 = times(2, PairTester)
            pair3_tx1 = times(2, PairTester)
            pair4_tx2 = times(2, PairTester)
            d1 = times(2, PairTester)
            d2 = times(2, PairTester)
            # connectors -------
            usb_c = times(2, USB_C_Receptacle)
            rj45 = times(2, RJ45_Receptacle)

        self.CMPs = _CMPs(self)

        # connect power to testers
        for tester in self.CMPs.get_all():
            if not isinstance(tester, PairTester):
                continue

            tester.IFs.power_in.connect(self.IFs.power_in)

        # connect receptacles to testers
        for i in range(2):

            def connect_diffpair_to_tester_pair(
                diffpair: DifferentialPair, testerpair: List[PairTester]
            ):
                diffpair.IFs.p.connect(testerpair[0].IFs.wires[i])
                diffpair.IFs.n.connect(testerpair[1].IFs.wires[i])

            # usb ------
            usb_i = self.CMPs.usb_c[i].IFs

            usb_i.cc1.connect(self.CMPs.cc1.IFs.wires[i])
            usb_i.cc2.connect(self.CMPs.cc2.IFs.wires[i])
            usb_i.sbu1.connect(self.CMPs.sbu1.IFs.wires[i])
            usb_i.sbu2.connect(self.CMPs.sbu2.IFs.wires[i])
            usb_i.shield.connect(self.CMPs.shield.IFs.wires[i])
            # power
            for cable_if, tester in list(zip(usb_i.gnd, self.CMPs.gnd)) + list(
                zip(usb_i.vbus, self.CMPs.vbus)
            ):
                cable_if.connect(tester.IFs.wires[i])
            # diffpairs
            connect_diffpair_to_tester_pair(usb_i.rx1, self.CMPs.pair1_rx1)
            connect_diffpair_to_tester_pair(usb_i.rx2, self.CMPs.pair2_rx2)
            connect_diffpair_to_tester_pair(usb_i.tx1, self.CMPs.pair3_tx1)
            connect_diffpair_to_tester_pair(usb_i.tx2, self.CMPs.pair4_tx2)
            connect_diffpair_to_tester_pair(usb_i.d1, self.CMPs.d1)
            connect_diffpair_to_tester_pair(usb_i.d2, self.CMPs.d2)

            # rj45 -----
            for cable_pair, tester_pair in zip(
                self.CMPs.rj45[i].IFs.twisted_pairs,
                [
                    self.CMPs.pair1_rx1,
                    self.CMPs.pair2_rx2,
                    self.CMPs.pair3_tx1,
                    self.CMPs.pair4_tx2,
                ],
            ):
                connect_diffpair_to_tester_pair(cable_pair, tester_pair)


def pick_component(cmp: Component):
    def _find_partno() -> str | None:
        if isinstance(cmp, USB_C_Receptacle):
            return "C134092"

        if isinstance(cmp, RJ45_Receptacle):
            return "C138392"

        if isinstance(cmp, Resistor):
            cmp.add_trait(has_symmetric_footprint_pinmap())

            resistors = {
                "C137885": Constant(300),
                "C226726": Constant(5.1 * K),
                "C25741": Constant(100 * K),
                "C11702": Constant(1 * K),
            }

            for partno, resistance in resistors.items():
                if (
                    isinstance(cmp.resistance, Constant)
                    and cmp.resistance.value == resistance.value
                ):
                    return partno
                if (
                    isinstance(cmp.resistance, Range)
                    and resistance.value >= cmp.resistance.min
                    and resistance.value <= cmp.resistance.max
                ):
                    cmp.set_resistance(resistance)
                    return partno

            raise Exception(
                f"Could not find fitting resistor for value: {cmp.resistance}"
            )

        if isinstance(cmp, LED):
            cmp.add_trait(
                has_defined_footprint_pinmap(
                    {
                        "1": cmp.IFs.anode,
                        "2": cmp.IFs.cathode,
                    }
                )
            )

            return "C84256"

        if isinstance(cmp, MOSFET):
            cmp.add_trait(
                has_defined_footprint_pinmap(
                    {
                        "2": cmp.IFs.source,
                        "3": cmp.IFs.drain,
                        "1": cmp.IFs.gate,
                    }
                )
            )

            mosfets = {
                "C8545": (
                    MOSFET.ChannelType.N_CHANNEL,
                    MOSFET.SaturationType.ENHANCEMENT,
                ),
                "C8492": (
                    MOSFET.ChannelType.P_CHANNEL,
                    MOSFET.SaturationType.ENHANCEMENT,
                ),
            }

            for partno, (channel_type, sat_type) in mosfets.items():
                if cmp.channel_type == channel_type and cmp.saturation_type == sat_type:
                    return partno

            raise Exception(
                f"Could not find fitting mosfet for: {cmp.channel_type, cmp.saturation_type}"
            )

        return None

    partno = _find_partno()
    if partno is None:
        return
    lcsc.attach_footprint(cmp, partno)


class Cable_Tester(Component):
    def __init__(self) -> None:
        super().__init__()

        # interfaces
        class _IFs(Component.InterfacesCls()):
            pass

        self.IFs = _IFs(self)

        # components
        class _CMPs(Component.ComponentsCls()):
            tester = Tester()
            psu = USB_C_PSU()

        self.CMPs = _CMPs(self)

        # power
        self.CMPs.tester.IFs.power_in.connect(self.CMPs.psu.IFs.power_out)

        # function

        # fill parameters
        cmps = get_all_components(self)
        for cmp in cmps:
            if isinstance(cmp, PairTester):
                pairtester = cmp
                pairtester.CMPs.indicator.CMPs.power_switch.CMPs.pull_resistor.set_resistance(
                    Constant(100 * K)
                )
            if isinstance(cmp, PoweredLED):
                cmp.CMPs.led.set_forward_parameters(
                    voltage_V=Constant(2), current_A=Constant(10 * m)
                )
                R_led = cmp.CMPs.led.get_trait(
                    LED.has_calculatable_needed_series_resistance
                ).get_needed_series_resistance_ohm(5)
                # Take higher resistance for dimmer LED
                R_led_dim = Range(R_led.value * 2, R_led.value * 4)
                cmp.CMPs.current_limiting_resistor.set_resistance(R_led_dim)
            if isinstance(cmp, LED):
                cmp.add_trait(has_defined_type_description("D"))
            if isinstance(cmp, MOSFET):
                cmp.add_trait(has_defined_type_description("Q"))

        # footprints
        for cmp in cmps:
            pick_component(cmp)

        # hack footprints
        for r in get_all_components(self) + [self]:
            if not r.has_trait(has_footprint):
                assert type(r) in [
                    Cable_Tester,
                    USB_C_PSU,
                    Tester,
                    PairTester,
                    PoweredLED,
                    PowerSwitch,
                    LEDIndicator,
                ], f"{r}"
            if not r.has_trait(has_footprint_pinmap):
                r.add_trait(has_symmetric_footprint_pinmap())
