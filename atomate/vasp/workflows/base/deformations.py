"""
This module defines the deformation workflow.
"""

from atomate.utils.utils import get_logger
from atomate.vasp.fireworks.core import TransmuterFW
from fireworks import Workflow
from pymatgen.io.vasp.sets import MPStaticSet

__author__ = "Kiran Mathew"
__credits__ = "Joseph Montoya"
__email__ = "kmathew@lbl.gov"

logger = get_logger(__name__)


def get_wf_deformations(
    structure,
    deformations,
    name="deformation",
    vasp_input_set=None,
    vasp_cmd="vasp",
    db_file=None,
    tag="",
    copy_vasp_outputs=True,
    metadata=None,
):
    """
    Returns a structure deformation workflow.

    Worfklow consists of: len(deformations) in which the structure is deformed followed
    by a static calculation.

    Args:
        structure (Structure): input structure to be optimized and run
        deformations (list of 3x3 array-likes): list of deformations
        name (str): some appropriate name for the transmuter fireworks.
        vasp_input_set (DictVaspInputSet): vasp input set for static deformed structure
            calculation.
        vasp_cmd (str): command to run
        db_file (str): path to file containing the database credentials.
        tag (str): some unique string that will be appended to the names of the
            fireworks so that the data from those tagged fireworks can be queried later
            during the analysis.
        copy_vasp_outputs (bool): whether or not copy the outputs from the previous calc
            (usually structure optimization) before the transmuter fireworks.
        metadata (dict): meta data

    Returns:
        Workflow
    """
    vasp_input_set = vasp_input_set or MPStaticSet(structure, force_gamma=True)

    fws = []
    for n, deformation in enumerate(deformations):
        fw = TransmuterFW(
            name=f"{tag} {name} {n}",
            structure=structure,
            transformations=["DeformStructureTransformation"],
            transformation_params=[{"deformation": deformation.tolist()}],
            vasp_input_set=vasp_input_set,
            copy_vasp_outputs=copy_vasp_outputs,
            vasp_cmd=vasp_cmd,
            db_file=db_file,
        )
        fws.append(fw)

    wfname = f"{structure.composition.reduced_formula}:{name}"

    return Workflow(fws, name=wfname, metadata=metadata)
