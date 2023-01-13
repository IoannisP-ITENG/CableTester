from enum import Enum
import logging

logger = logging.getLogger("local_library")

from faebryk.library.core import Component, Interface
from faebryk.library.trait_impl.component import has_defined_type_description, can_bridge_defined, has_defined_footprint, has_defined_footprint_pinmap
from faebryk.library.library.interfaces import Electrical, Power
from faebryk.library.library.components import Resistor, LED
from faebryk.library.library.parameters import TBD
from faebryk.library.util import times


class MOSFET(Component):
    class ChannelType(Enum):
        N_CHANNEL = 1
        P_CHANNEL = 2

    class SaturationType(Enum):
        ENHANCEMENT = 1
        DEPLETION = 2

    def __new__(cls, *args, **kwargs):
        self = super().__new__(cls)
        self._setup_traits()
        return self

    def __init__(
        self, channel_type: ChannelType, saturation_type: SaturationType
    ) -> None:
        super().__init__()
        self._setup_interfaces()

    def _setup_traits(self):
        self.add_trait(has_defined_type_description("MOSFET"))

    def _setup_interfaces(self):
        class _IFs(Component.InterfacesCls()):
            source = Electrical()
            gate = Electrical()
            drain = Electrical()

        self.IFs = _IFs(self)
        self.add_trait(can_bridge_defined(self.IFs.source, self.IFs.drain))


class PowerSwitch(Component):
    def __init__(self, lowside: bool, normally_closed: bool) -> None:
        super().__init__()  # interfaces

        class _IFs(Component.InterfacesCls()):
            #TODO replace with logical
            logic_in = Electrical()
            power_in = Power()
            switched_power_out = Power()

        self.IFs = _IFs(self)

        # components
        class _CMPs(Component.ComponentsCls()):
            mosfet = MOSFET(
                MOSFET.ChannelType.N_CHANNEL
                if lowside
                else MOSFET.ChannelType.P_CHANNEL,
                MOSFET.SaturationType.ENHANCEMENT,
            )
            pull_resistor = Resistor(TBD)

        self.CMPs = _CMPs(self)

        # pull gate
        self.CMPs.mosfet.IFs.gate.connect_via(
            self.CMPs.pull_resistor,
            self.IFs.power_in.IFs.lv
            if lowside and not normally_closed
            else self.IFs.power_in.IFs.hv,
        )

        # passthrough non-switched side, bridge switched side
        if lowside:
            self.IFs.power_in.IFs.hv.connect(self.IFs.switched_power_out.IFs.hv)
            self.IFs.power_in.IFs.lv.connect_via(
                self.CMPs.mosfet, self.IFs.switched_power_out.IFs.lv
            )
        else:
            self.IFs.power_in.IFs.lv.connect(self.IFs.switched_power_out.IFs.lv)
            self.IFs.power_in.IFs.hv.connect_via(
                self.CMPs.mosfet, self.IFs.switched_power_out.IFs.hv
            )

        # Add bridge trait
        self.add_trait(can_bridge_defined(self.IFs.power_in, self.IFs.switched_power_out))

class PoweredLED(Component):
    def __init__(self) -> None:
        super().__init__()

        class _IFs(Component.InterfacesCls()):
            power = Power()

        self.IFs = _IFs(self)

        class _CMPs(Component.ComponentsCls()):
            current_limiting_resistor = Resistor(TBD)
            led = LED()

        self.CMPs = _CMPs(self)

        self.IFs.power.IFs.hv.connect(self.CMPs.led.IFs.anode)
        self.IFs.power.IFs.lv.connect_via(self.CMPs.current_limiting_resistor, self.CMPs.led.IFs.cathode)

#TODO
class Logical(Interface):
    def __init__(self, high_ref: Electrical, low_ref: Electrical) -> None:
        super().__init__()

class DifferentialPair(Interface):
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)

        class _IFs(Interface.InterfacesCls()):
            p = Electrical()
            n = Electrical()

        self.IFs = _IFs(self)

    def connect(self, other: Interface) -> Interface:
        assert type(other) is DifferentialPair, "can't connect to different type"
        for s, d in zip(self.IFs.get_all(), other.IFs.get_all()):
            s.connect(d)

        return self


class USB_C_Receptacle(Component):
    def __init__(self) -> None:
        super().__init__()

        # interfaces
        class _IFs(Component.InterfacesCls()):
            cc1 = Electrical()
            cc2 = Electrical()
            sbu1 = Electrical()
            sbu2 = Electrical()
            shield = Electrical()
            # power
            gnd = times(4, Electrical)
            vbus = times(4, Electrical)
            # diffpairs: p, n
            rx1 = DifferentialPair()
            rx2 = DifferentialPair()
            tx1 = DifferentialPair()
            tx2 = DifferentialPair()
            d1 = DifferentialPair()
            d2 = DifferentialPair()

        self.IFs = _IFs(self)


        self.add_trait(has_defined_footprint_pinmap(
            {
                "A1": self.IFs.gnd[0],
                "A2": self.IFs.tx1.IFs.p,
                "A3": self.IFs.tx1.IFs.n,
                "A4": self.IFs.vbus[0],
                "A5": self.IFs.cc1,
                "A6": self.IFs.d1.IFs.p,
                "A7": self.IFs.d1.IFs.n,
                "A8": self.IFs.sbu1,
                "A9": self.IFs.vbus[1],
                "A10": self.IFs.rx2.IFs.n,
                "A11": self.IFs.rx2.IFs.p,
                "A12": self.IFs.gnd[1],

                "B1": self.IFs.gnd[2],
                "B2": self.IFs.tx2.IFs.p,
                "B3": self.IFs.tx2.IFs.n,
                "B4": self.IFs.vbus[2],
                "B5": self.IFs.cc2,
                "B6": self.IFs.d2.IFs.p,
                "B7": self.IFs.d2.IFs.n,
                "B8": self.IFs.sbu2,
                "B9": self.IFs.vbus[3],
                "B10": self.IFs.rx1.IFs.n,
                "B11": self.IFs.rx1.IFs.p,
                "B12": self.IFs.gnd[3],

                "0": self.IFs.shield,
            }
        ))

        self.add_trait(has_defined_type_description(f"x"))

class RJ45_Receptacle(Component):
    def __init__(self) -> None:
        super().__init__()

        # interfaces
        class _IFs(Component.InterfacesCls()):
            twisted_pairs = times(4, DifferentialPair)

        self.IFs = _IFs(self)

        self.add_trait(has_defined_footprint_pinmap({
            "1": self.IFs.twisted_pairs[0].IFs.p,
            "2": self.IFs.twisted_pairs[0].IFs.n,
            "3": self.IFs.twisted_pairs[1].IFs.p,
            "4": self.IFs.twisted_pairs[1].IFs.n,
            "5": self.IFs.twisted_pairs[2].IFs.p,
            "6": self.IFs.twisted_pairs[2].IFs.n,
            "7": self.IFs.twisted_pairs[3].IFs.p,
            "8": self.IFs.twisted_pairs[3].IFs.n,
        }))
        self.add_trait(has_defined_type_description(f"x"))