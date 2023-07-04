import logging
from typing import List

from cabletester.picker import pick_component
from faebryk.core.core import Module
from faebryk.core.util import get_all_nodes
from faebryk.library.Constant import Constant
from faebryk.library.DifferentialPair import DifferentialPair
from faebryk.library.Electrical import Electrical
from faebryk.library.ElectricPower import ElectricPower
from faebryk.library.LED import LED
from faebryk.library.LEDIndicator import LEDIndicator
from faebryk.library.PoweredLED import PoweredLED
from faebryk.library.Range import Range
from faebryk.library.RJ45_Receptacle import RJ45_Receptacle
from faebryk.library.USB_C_PSU import USB_C_PSU
from faebryk.library.USB_Type_C_Receptacle_24_pin import USB_Type_C_Receptacle_24_pin
from faebryk.libs.units import K, m
from faebryk.libs.util import times

logger = logging.getLogger(__name__)


class PairTester(Module):
    def __init__(self, logic_low: bool = False) -> None:
        super().__init__()

        # interfaces
        class _IFs(Module.IFS()):
            power_in = ElectricPower()
            # TODO logical?
            wires = times(2, Electrical)

        self.IFs = _IFs(self)

        # components
        class _NODEs(Module.NODES()):
            indicator = LEDIndicator(logic_low=logic_low, normally_on=False)

        self.NODEs = _NODEs(self)

        #
        self.NODEs.indicator.IFs.power_in.connect(self.IFs.power_in)

        # connect logic high to indicator through wire pair
        self.IFs.wires[0].connect(
            self.IFs.power_in.NODEs.lv if logic_low else self.IFs.power_in.NODEs.hv
        )

        self.NODEs.indicator.IFs.logic_in.connect_to_electric(
            self.IFs.wires[1], self.IFs.power_in
        )


class Tester(Module):
    def __init__(self) -> None:
        super().__init__()

        # interfaces
        class _IFs(Module.IFS()):
            power_in = ElectricPower()

        self.IFs = _IFs(self)

        # components
        class _NODEs(Module.NODES()):
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
            usb_c = times(2, USB_Type_C_Receptacle_24_pin)
            rj45 = times(2, RJ45_Receptacle)

        self.NODEs = _NODEs(self)

        # connect power to testers
        for tester in self.NODEs.get_all():
            if not isinstance(tester, PairTester):
                continue

            tester.IFs.power_in.connect(self.IFs.power_in)

        # connect receptacles to testers
        for i in range(2):

            def connect_diffpair_to_tester_pair(
                diffpair: DifferentialPair, testerpair: List[PairTester]
            ):
                diffpair.NODEs.p.connect(testerpair[0].IFs.wires[i])
                diffpair.NODEs.n.connect(testerpair[1].IFs.wires[i])

            # usb ------
            usb_i = self.NODEs.usb_c[i].IFs

            usb_i.cc1.connect(self.NODEs.cc1.IFs.wires[i])
            usb_i.cc2.connect(self.NODEs.cc2.IFs.wires[i])
            usb_i.sbu1.connect(self.NODEs.sbu1.IFs.wires[i])
            usb_i.sbu2.connect(self.NODEs.sbu2.IFs.wires[i])
            usb_i.shield.connect(self.NODEs.shield.IFs.wires[i])
            # power
            for cable_if, tester in list(zip(usb_i.gnd, self.NODEs.gnd)) + list(
                zip(usb_i.vbus, self.NODEs.vbus)
            ):
                cable_if.connect(tester.IFs.wires[i])
            # diffpairs
            connect_diffpair_to_tester_pair(usb_i.rx1, self.NODEs.pair1_rx1)
            connect_diffpair_to_tester_pair(usb_i.rx2, self.NODEs.pair2_rx2)
            connect_diffpair_to_tester_pair(usb_i.tx1, self.NODEs.pair3_tx1)
            connect_diffpair_to_tester_pair(usb_i.tx2, self.NODEs.pair4_tx2)
            connect_diffpair_to_tester_pair(usb_i.d1, self.NODEs.d1)
            connect_diffpair_to_tester_pair(usb_i.d2, self.NODEs.d2)

            # rj45 -----
            for cable_pair, tester_pair in zip(
                self.NODEs.rj45[i].IFs.twisted_pairs,
                [
                    self.NODEs.pair1_rx1,
                    self.NODEs.pair2_rx2,
                    self.NODEs.pair3_tx1,
                    self.NODEs.pair4_tx2,
                ],
            ):
                connect_diffpair_to_tester_pair(cable_pair, tester_pair)


class Cable_Tester(Module):
    def __init__(self) -> None:
        super().__init__()

        # interfaces
        class _IFs(Module.IFS()):
            pass

        self.IFs = _IFs(self)

        # components
        class _NODEs(Module.NODES()):
            tester = Tester()
            psu = USB_C_PSU()

        self.NODEs = _NODEs(self)

        # power
        self.NODEs.tester.IFs.power_in.connect(self.NODEs.psu.IFs.power_out)

        # function

        # fill parameters
        cmps = get_all_nodes(self)
        for cmp in cmps:
            if isinstance(cmp, PairTester):
                pairtester = cmp
                pairtester.NODEs.indicator.NODEs.power_switch.NODEs.pull_resistor.set_resistance(
                    Constant(100 * K)
                )
            if isinstance(cmp, PoweredLED):
                cmp.NODEs.led.set_forward_parameters(
                    voltage_V=Constant(2), current_A=Constant(10 * m)
                )
                R_led = cmp.NODEs.led.get_trait(
                    LED.has_calculatable_needed_series_resistance
                ).get_needed_series_resistance_ohm(5)
                # Take higher resistance for dimmer LED
                R_led_dim = Range(R_led.value * 2, R_led.value * 4)
                cmp.NODEs.current_limiting_resistor.set_resistance(R_led_dim)

        # footprints
        for cmp in cmps:
            if not isinstance(cmp, Module):
                continue
            pick_component(cmp)
