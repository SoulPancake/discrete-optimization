#  Copyright (c) 2022 AIRBUS and its affiliates.
#  This source code is licensed under the MIT license found in the
#  LICENSE file in the root directory of this source tree.

import os
from typing import Optional

from discrete_optimization.datasets import get_data_home
from discrete_optimization.rcpsp.rcpsp_model import (
    MultiModeRCPSPModel,
    RCPSPModel,
    SingleModeRCPSPModel,
)


def get_data_available(
    data_folder: Optional[str] = None, data_home: Optional[str] = None
):
    """Get datasets available for rcpsp.

    Params:
        data_folder: folder where datasets for rcpsp whould be find.
            If None, we look in "rcpsp" subdirectory of `data_home`.
        data_home: root directory for all datasets. Is None, set by
            default to "~/discrete_optimization_data "

    """
    if data_folder is None:
        data_home = get_data_home(data_home=data_home)
        data_folder = f"{data_home}/rcpsp"

    try:
        files = [
            f for f in os.listdir(data_folder) if f.endswith(".sm") or f.endswith(".mm")
        ]
    except FileNotFoundError:
        files = []
    return [os.path.abspath(os.path.join(data_folder, f)) for f in files]


def parse_psplib(input_data):
    # parse the input
    lines = input_data.split("\n")

    # Retrieving section bounds
    horizon_ref_line_index = lines.index("RESOURCES") - 1

    prec_ref_line_index = lines.index("PRECEDENCE RELATIONS:")
    prec_start_line_index = prec_ref_line_index + 2
    duration_ref_line_index = lines.index("REQUESTS/DURATIONS:")
    prec_end_line_index = duration_ref_line_index - 2
    duration_start_line_index = duration_ref_line_index + 3
    res_ref_line_index = lines.index("RESOURCEAVAILABILITIES:")
    duration_end_line_index = res_ref_line_index - 2
    res_start_line_index = res_ref_line_index + 1

    # Parsing horizon
    tmp = lines[horizon_ref_line_index].split()
    horizon = int(tmp[2])

    # Parsing resource information
    tmp1 = lines[res_start_line_index].split()
    tmp2 = lines[res_start_line_index + 1].split()
    resources = {
        str(tmp1[(i * 2)]) + str(tmp1[(i * 2) + 1]): int(tmp2[i])
        for i in range(len(tmp2))
    }
    non_renewable_resources = [
        name for name in list(resources.keys()) if name.startswith("N")
    ]
    n_resources = len(resources.keys())

    # Parsing precedence relationship
    multi_mode = False
    successors = {}
    for i in range(prec_start_line_index, prec_end_line_index + 1):
        tmp = lines[i].split()
        task_id = int(tmp[0])
        n_modes = int(tmp[1])
        n_successors = int(tmp[2])
        successors[task_id] = [int(x) for x in tmp[3 : (3 + n_successors)]]

    # Parsing mode and duration information
    mode_details = {}
    for i_line in range(duration_start_line_index, duration_end_line_index + 1):
        tmp = lines[i_line].split()
        if len(tmp) == 3 + n_resources:
            task_id = int(tmp[0])
            mode_id = int(tmp[1])
            duration = int(tmp[2])
            resources_usage = [int(x) for x in tmp[3 : (3 + n_resources)]]
        else:
            multi_mode = True
            mode_id = int(tmp[0])
            duration = int(tmp[1])
            resources_usage = [int(x) for x in tmp[2 : (3 + n_resources)]]

        if int(task_id) not in list(mode_details.keys()):
            mode_details[int(task_id)] = {}
        mode_details[int(task_id)][mode_id] = {}  # Dict[int, Dict[str, int]]
        mode_details[int(task_id)][mode_id]["duration"] = duration
        for i in range(n_resources):
            mode_details[int(task_id)][mode_id][
                list(resources.keys())[i]
            ] = resources_usage[i]

    if multi_mode:
        problem = MultiModeRCPSPModel(
            resources=resources,
            non_renewable_resources=non_renewable_resources,
            mode_details=mode_details,
            successors=successors,
            horizon=horizon,
            horizon_multiplier=30,
        )
    else:
        problem = SingleModeRCPSPModel(
            resources=resources,
            non_renewable_resources=non_renewable_resources,
            mode_details=mode_details,
            successors=successors,
            horizon=horizon,
            horizon_multiplier=30,
        )
    return problem


def parse_file(file_path) -> RCPSPModel:
    with open(file_path, "r", encoding="utf-8") as input_data_file:
        input_data = input_data_file.read()
        rcpsp_model = parse_psplib(input_data)
        return rcpsp_model
