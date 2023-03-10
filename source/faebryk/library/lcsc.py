#TODO should be part of faebryk

import logging

logger = logging.getLogger(__name__)

from easyeda2kicad.easyeda.easyeda_api import EasyedaApi
from easyeda2kicad.easyeda.easyeda_importer import EasyedaFootprintImporter, Easyeda3dModelImporter
from easyeda2kicad.kicad.export_kicad_footprint import ExporterFootprintKicad
from easyeda2kicad.kicad.export_kicad_3d_model import Exporter3dModelKicad
from faebryk.library.core import Component
import json
from pathlib import Path
from faebryk.library.trait_impl.component import has_defined_footprint

from faebryk.library.kicad import KicadFootprint


def attach_footprint(component: Component, partno: str, get_model : bool = True):
    #TODO dont hardcode relative paths    

    # easyeda api access & caching --------------------------------------------
    api = EasyedaApi()

    cache_base = Path("./build/cache/easyeda")
    cache_base.mkdir(parents=True, exist_ok=True)

    comp_path = cache_base.joinpath(partno)
    if not comp_path.exists():
        logger.debug(f"Did not find component {partno} in cache, downloading...")
        cad_data = api.get_cad_data_of_component(lcsc_id=partno)
        serialized = json.dumps(cad_data)
        comp_path.write_text(serialized)

    data = json.loads(comp_path.read_text())

    # API returned no data
    if not data:
        logging.error(f"Failed to fetch data from EasyEDA API for part {partno}")
        return

    easyeda_footprint = EasyedaFootprintImporter(easyeda_cp_cad_data=data).get_footprint()
    
    # paths -------------------------------------------------------------------
    name = easyeda_footprint.info.name
    out_base_path = Path(__file__).parent.joinpath("../../kicad/libs")
    fp_base_path = out_base_path.joinpath("footprints/lcsc.pretty")
    fp_base_path.mkdir(exist_ok=True, parents=True)
    footprint_filename = f"{name}.kicad_mod"
    footprint_filepath = fp_base_path.joinpath(footprint_filename)

    model_base_path = out_base_path.joinpath("3dmodels/lcsc")
    model_base_path_full = Path(model_base_path.as_posix() + ".3dshapes")
    model_base_path_full.mkdir(exist_ok=True, parents=True)
    
    # export to kicad ---------------------------------------------------------
    ki_footprint = ExporterFootprintKicad(easyeda_footprint)

    easyeda_model_info = Easyeda3dModelImporter(easyeda_cp_cad_data=data, download_raw_3d_model=False).output
    model_path = model_base_path_full.joinpath(f"{easyeda_model_info.name}.wrl")
    if get_model and not model_path.exists():
        logger.debug(f"Downloading & Exporting 3dmodel {model_path}")
        easyeda_model = Easyeda3dModelImporter(easyeda_cp_cad_data=data, download_raw_3d_model=True).output
        ki_model = Exporter3dModelKicad(easyeda_model)
        ki_model.export(model_base_path)
    else:
        ki_footprint.output.model_3d = None


    if not footprint_filepath.exists():
        logger.debug(f"Exporting footprint {footprint_filepath}")
        ki_footprint.export(
            footprint_full_path=footprint_filepath,
            model_3d_path="${KIPRJMOD}/../libs/3dmodels/lcsc.3dshapes"
        )

    # add trat to component ---------------------------------------------------
    component.add_trait(has_defined_footprint(KicadFootprint(f"lcsc:{easyeda_footprint.info.name}")))