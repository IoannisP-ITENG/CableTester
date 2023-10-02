import faebryk.libs.picker.lcsc as lcsc
from faebryk.core.core import Module, Parameter
from faebryk.library.can_attach_to_footprint_via_pinmap import (
    can_attach_to_footprint_via_pinmap,
)
from faebryk.library.Constant import Constant
from faebryk.library.has_resistance import has_resistance
from faebryk.library.LED import LED
from faebryk.library.MOSFET import MOSFET
from faebryk.library.Range import Range
from faebryk.library.Resistor import Resistor
from faebryk.library.RJ45_Receptacle import RJ45_Receptacle
from faebryk.library.USB_Type_C_Receptacle_24_pin import USB_Type_C_Receptacle_24_pin
from faebryk.libs.units import k


def pick_component(cmp: Module):
    def _find_partno() -> str | None:
        if isinstance(cmp, USB_Type_C_Receptacle_24_pin):
            return "C134092"

        if isinstance(cmp, RJ45_Receptacle):
            return "C138392"

        if isinstance(cmp, Resistor):
            resistance_param = cmp.get_trait(has_resistance).get_resistance()
            assert isinstance(resistance_param, Parameter)

            resistors = {
                "C137885": Constant(300),
                "C226726": Constant(5.1 * k),
                "C25741": Constant(100 * k),
                "C11702": Constant(1 * k),
            }

            for partno, resistance in resistors.items():
                if (
                    isinstance(resistance_param, Constant)
                    and resistance_param.value == resistance.value
                ):
                    return partno
                if (
                    isinstance(resistance_param, Range)
                    and resistance.value >= resistance_param.min
                    and resistance.value <= resistance_param.max
                ):
                    cmp.set_resistance(resistance)
                    return partno

            raise Exception(
                f"Could not find fitting resistor for value: {resistance_param}"
            )

        if isinstance(cmp, LED):
            cmp.add_trait(
                can_attach_to_footprint_via_pinmap(
                    {
                        "1": cmp.IFs.anode,
                        "2": cmp.IFs.cathode,
                    }
                )
            )

            return "C84256"

        if isinstance(cmp, MOSFET):
            cmp.add_trait(
                can_attach_to_footprint_via_pinmap(
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
                "Could not find fitting mosfet for: "
                f"{cmp.channel_type, cmp.saturation_type}"
            )

        return None

    partno = _find_partno()
    if partno is None:
        return
    lcsc.attach_footprint(cmp, partno)
