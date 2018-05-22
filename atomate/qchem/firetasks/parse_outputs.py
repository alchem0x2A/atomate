# coding: utf-8

from __future__ import division, print_function, unicode_literals, absolute_import

import json
import os

from fireworks import FiretaskBase, FWAction, explicit_serialize
from fireworks.utilities.fw_serializers import DATETIME_HANDLER

from atomate.common.firetasks.glue_tasks import get_calc_loc
from atomate.utils.utils import env_chk
from atomate.utils.utils import get_logger
from atomate.qchem.drones import QChemDrone

__author__ = "Samuel Blau"
__copyright__ = "Copyright 2018, The Materials Project"
__version__ = "0.1"
__maintainer__ = "Samuel Blau"
__email__ = "samblau1@gmail.com"
__status__ = "Alpha"
__date__ = "4/25/18"
__credits__ = "Brandon Wood, Shyam Dwaraknath, Xiaohui Qu"

logger = get_logger(__name__)


@explicit_serialize
class QChemToDb(FiretaskBase):
    """
    Enter a QChem run into the database. Uses current directory unless you
    specify calc_dir or calc_loc.

    Optional params:
        calc_dir (str): path to dir (on current filesystem) that contains QChem
            input and output files. Default: use current working directory.
        calc_loc (str OR bool): if True will set most recent calc_loc. If str
            search for the most recent calc_loc with the matching name
        input_file (str): name of the QChem input file
        output_file (str): name of the QChem output file
        additional_fields (dict): dict of additional fields to add
        db_file (str): path to file containing the database credentials.
            Supports env_chk. Default: write data to JSON file.
        fw_spec_field (str): if set, will update the task doc with the contents
            of this key in the fw_spec.
        multirun (bool): Whether the job to parse includes multiple
            calculations in one input / output pair.
    """
    optional_params = [
        "calc_dir", "calc_loc", "input_file", "output_file",
        "additional_fields", "db_file", "fw_spec_field", "multirun"
    ]

    def run_task(self, fw_spec):
        # get the directory that contains the QChem dir to parse
        calc_dir = os.getcwd()
        if "calc_dir" in self:
            calc_dir = self["calc_dir"]
        elif self.get("calc_loc"):
            calc_dir = get_calc_loc(self["calc_loc"],
                                    fw_spec["calc_locs"])["path"]
        input_file = "mol.qin"
        output_file = "mol.qout"
        if "input_file" in self:
            input_file = self["input_file"]
        if "output_file" in self:
            output_file = self["output_file"]

        multirun = False
        if "multirun" in self:
            multirun = self["multirun"]

        # parse the QChem directory
        logger.info("PARSING DIRECTORY: {}".format(calc_dir))

        drone = QChemDrone(additional_fields=self.get("additional_fields"))

        # assimilate (i.e., parse)
        task_doc = drone.assimilate(
            path=calc_dir, input_file=input_file, output_file=output_file, multirun=multirun)

        # Check for additional keys to set based on the fw_spec
        if self.get("fw_spec_field"):
            task_doc.update(fw_spec[self.get("fw_spec_field")])

        # Update fw_spec with final/optimized structure
        update_spec = {}
        if task_doc.get("output").get("optimized_molecule"):
            update_spec["prev_calc_molecule"] = task_doc["output"]["optimized_molecule"]

        # get the database connection
        db_file = env_chk(self.get('db_file'), fw_spec)

        # db insertion or taskdoc dump
        if not db_file:
            with open(os.path.join(calc_dir, "task.json"), "w") as f:
                f.write(json.dumps(task_doc, default=DATETIME_HANDLER))
        else:
            mmdb = CalcDb.from_db_file(db_file, admin=True)
            t_id = mmdb.insert_task(task_doc)
            logger.info("Finished parsing with task_id: {}".format(t_id))

        defuse_children = False
        if task_doc["state"] != "successful":
            defuse_unsuccessful = self.get("defuse_unsuccessful",
                                           DEFUSE_UNSUCCESSFUL)
            if defuse_unsuccessful is True:
                defuse_children = True
            elif defuse_unsuccessful is False:
                pass
            elif defuse_unsuccessful == "fizzle":
                raise RuntimeError(
                    "QChemToDb indicates that job is not successful "
                    "(perhaps your job did not converge within the "
                    "limit of electronic iterations)!")
            else:
                raise RuntimeError("Unknown option for defuse_unsuccessful: "
                                   "{}".format(defuse_unsuccessful))

        return FWAction(
            stored_data={"task_id": task_doc.get("task_id", None)},
            defuse_children=defuse_children, update_spec=update_spec)
