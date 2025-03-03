#  Copyright (c) 2022 AIRBUS and its affiliates.
#  This source code is licensed under the MIT license found in the
#  LICENSE file in the root directory of this source tree.

from typing import Any, Dict, Tuple

from discrete_optimization.generic_rcpsp_tools.large_neighborhood_search_scheduling import (
    LargeNeighborhoodSearchScheduling,
)
from discrete_optimization.generic_tools.cp_tools import ParametersCP
from discrete_optimization.generic_tools.do_solver import SolverDO
from discrete_optimization.generic_tools.ea.ga_tools import (
    ParametersAltGa,
    ParametersGa,
)
from discrete_optimization.generic_tools.lp_tools import MilpSolverName, ParametersMilp
from discrete_optimization.generic_tools.result_storage.result_storage import (
    ResultStorage,
)
from discrete_optimization.rcpsp.rcpsp_model import (
    MultiModeRCPSPModel,
    RCPSPModel,
    RCPSPModelCalendar,
    SingleModeRCPSPModel,
)
from discrete_optimization.rcpsp.rcpsp_model_preemptive import RCPSPModelPreemptive
from discrete_optimization.rcpsp.solver.calendar_solver_iterative import (
    SolverWithCalendarIterative,
)
from discrete_optimization.rcpsp.solver.cp_lns_solver import (
    LargeNeighborhoodSearchRCPSP,
)
from discrete_optimization.rcpsp.solver.cp_solvers import (
    CP_MRCPSP_MZN,
    CP_MRCPSP_MZN_PREEMMPTIVE,
    CP_RCPSP_MZN,
    CP_RCPSP_MZN_PREEMMPTIVE,
    CPSolverName,
)
from discrete_optimization.rcpsp.solver.cpm import CPM
from discrete_optimization.rcpsp.solver.gphh_solver import GPHH
from discrete_optimization.rcpsp.solver.ls_solver import LS_SOLVER, LS_RCPSP_Solver
from discrete_optimization.rcpsp.solver.rcpsp_cp_lns_solver import LNS_CP_RCPSP_SOLVER
from discrete_optimization.rcpsp.solver.rcpsp_ga_solver import (
    GA_MRCPSP_Solver,
    GA_RCPSP_Solver,
)
from discrete_optimization.rcpsp.solver.rcpsp_lp_lns_solver import LNS_LP_RCPSP_SOLVER
from discrete_optimization.rcpsp.solver.rcpsp_lp_solver import LP_MRCPSP, LP_RCPSP
from discrete_optimization.rcpsp.solver.rcpsp_pile import (
    GreedyChoice,
    PileSolverRCPSP,
    PileSolverRCPSP_Calendar,
)
from discrete_optimization.rcpsp.specialized_rcpsp.rcpsp_specialized_constraints import (
    RCPSPModelSpecialConstraints,
    RCPSPModelSpecialConstraintsPreemptive,
)

solvers = {
    "lp": [
        (
            LP_RCPSP,
            {
                "lp_solver": MilpSolverName.CBC,
                "parameters_milp": ParametersMilp.default(),
            },
        ),
        (
            LP_MRCPSP,
            {
                "lp_solver": MilpSolverName.CBC,
                "parameters_milp": ParametersMilp.default(),
            },
        ),
    ],
    "greedy": [
        (PileSolverRCPSP, {"greedy_choice": GreedyChoice.MOST_SUCCESSORS}),
        (PileSolverRCPSP_Calendar, {"greedy_choice": GreedyChoice.MOST_SUCCESSORS}),
    ],
    "cp": [
        (
            CP_RCPSP_MZN,
            {
                "cp_solver_name": CPSolverName.CHUFFED,
                "parameters_cp": ParametersCP.default(),
            },
        ),
        (
            CP_MRCPSP_MZN,
            {
                "cp_solver_name": CPSolverName.CHUFFED,
                "parameters_cp": ParametersCP.default(),
            },
        ),
        (
            CP_RCPSP_MZN_PREEMMPTIVE,
            {
                "cp_solver_name": CPSolverName.CHUFFED,
                "parameters_cp": ParametersCP.default(),
            },
        ),
        (
            CP_MRCPSP_MZN_PREEMMPTIVE,
            {
                "cp_solver_name": CPSolverName.CHUFFED,
                "parameters_cp": ParametersCP.default(),
            },
        ),
    ],
    "critical-path": [(CPM, {})],
    "lns": [
        (
            LNS_LP_RCPSP_SOLVER,
            {"nb_iteration_lns": 100, "lp_solver": MilpSolverName.CBC},
        ),
        (
            LNS_CP_RCPSP_SOLVER,
            {"nb_iteration_lns": 100, "nb_iteration_no_improvement": 100},
        ),
    ],
    "lns-lp": [
        (
            LNS_LP_RCPSP_SOLVER,
            {"nb_iteration_lns": 100, "lp_solver": MilpSolverName.CBC},
        )
    ],
    "lns-cp": [
        (
            LNS_CP_RCPSP_SOLVER,
            {"nb_iteration_lns": 100, "nb_iteration_no_improvement": 100},
        )
    ],
    "lns-cp-rcpsp": [
        (
            LargeNeighborhoodSearchRCPSP,
            {
                "nb_iteration_lns": 100,
                "nb_iteration_no_improvement": 100,
                "parameters_cp": ParametersCP.default(),
                "cut_part": 1,
                "add_objective_makespan": False,
                "fraction_subproblem": 0.6,
            },
        )
    ],
    "lns-scheduling": [
        (
            LargeNeighborhoodSearchScheduling,
            {
                "nb_iteration_lns": 100,
                "nb_iteration_no_improvement": 100,
                "parameters_cp": ParametersCP.default_fast_lns(),
                "cp_solver_name": CPSolverName.CHUFFED,
            },
        )
    ],
    "ls": [(LS_RCPSP_Solver, {"ls_solver": LS_SOLVER.SA, "nb_iteration_max": 2000})],
    "ga": [
        (GA_RCPSP_Solver, {"parameters_ga": ParametersGa.default_rcpsp()}),
        (GA_MRCPSP_Solver, {"parameters_ga": ParametersAltGa.default_mrcpsp()}),
    ],
    "lns-cp-calendar": [
        (
            SolverWithCalendarIterative,
            {
                "parameters_cp": ParametersCP.default(),
                "nb_iteration_lns": 20,
                "skip_first_iteration": False,
            },
        )
    ],
    "gphh": [(GPHH, {})],
}

solvers_map = {}
for key in solvers:
    for solver, param in solvers[key]:
        solvers_map[solver] = (key, param)

solvers_compatibility = {
    LP_RCPSP: [SingleModeRCPSPModel, RCPSPModel],
    LP_MRCPSP: [
        MultiModeRCPSPModel,
        SingleModeRCPSPModel,
        RCPSPModelCalendar,
        RCPSPModel,
    ],
    PileSolverRCPSP: [SingleModeRCPSPModel, MultiModeRCPSPModel, RCPSPModel],
    PileSolverRCPSP_Calendar: [
        SingleModeRCPSPModel,
        MultiModeRCPSPModel,
        RCPSPModelCalendar,
        RCPSPModel,
    ],
    CP_RCPSP_MZN: [SingleModeRCPSPModel, RCPSPModelSpecialConstraints, RCPSPModel],
    CP_MRCPSP_MZN: [
        SingleModeRCPSPModel,
        MultiModeRCPSPModel,
        RCPSPModelCalendar,
        RCPSPModelSpecialConstraints,
        RCPSPModel,
    ],
    CP_RCPSP_MZN_PREEMMPTIVE: [RCPSPModelPreemptive],
    CP_MRCPSP_MZN_PREEMMPTIVE: [RCPSPModelPreemptive],
    LNS_LP_RCPSP_SOLVER: [
        SingleModeRCPSPModel,
        MultiModeRCPSPModel,
        RCPSPModelCalendar,
        RCPSPModelSpecialConstraints,
        RCPSPModel,
    ],
    LNS_CP_RCPSP_SOLVER: [
        SingleModeRCPSPModel,
        MultiModeRCPSPModel,
        RCPSPModelCalendar,
        RCPSPModelSpecialConstraints,
        RCPSPModel,
    ],
    LS_RCPSP_Solver: [
        SingleModeRCPSPModel,
        MultiModeRCPSPModel,
        RCPSPModelCalendar,
        RCPSPModelSpecialConstraints,
        RCPSPModelPreemptive,
        RCPSPModelSpecialConstraintsPreemptive,
        RCPSPModel,
    ],
    GA_RCPSP_Solver: [
        SingleModeRCPSPModel,
        RCPSPModelCalendar,
        RCPSPModelSpecialConstraints,
        RCPSPModelPreemptive,
        RCPSPModelSpecialConstraintsPreemptive,
        RCPSPModel,
    ],
    GA_MRCPSP_Solver: [
        MultiModeRCPSPModel,
        RCPSPModelCalendar,
        RCPSPModelSpecialConstraints,
        RCPSPModelPreemptive,
        RCPSPModelSpecialConstraintsPreemptive,
        RCPSPModel,
    ],
    SolverWithCalendarIterative: [
        SingleModeRCPSPModel,
        MultiModeRCPSPModel,
        RCPSPModelCalendar,
        RCPSPModel,
    ],
    LargeNeighborhoodSearchRCPSP: [
        SingleModeRCPSPModel,
        MultiModeRCPSPModel,
        RCPSPModelCalendar,
        RCPSPModelSpecialConstraints,
        RCPSPModelPreemptive,
        RCPSPModelSpecialConstraintsPreemptive,
        RCPSPModel,
    ],
    LargeNeighborhoodSearchScheduling: [
        SingleModeRCPSPModel,
        MultiModeRCPSPModel,
        RCPSPModelCalendar,
        RCPSPModelSpecialConstraints,
        RCPSPModelPreemptive,
        RCPSPModelSpecialConstraintsPreemptive,
        RCPSPModel,
    ],
    CPM: [
        SingleModeRCPSPModel,
        MultiModeRCPSPModel,
        RCPSPModelCalendar,
        RCPSPModelSpecialConstraints,
        RCPSPModelPreemptive,
        RCPSPModelSpecialConstraintsPreemptive,
        RCPSPModel,
    ],
    GPHH: [
        SingleModeRCPSPModel,
        MultiModeRCPSPModel,
        RCPSPModelCalendar,
        RCPSPModelSpecialConstraints,
        RCPSPModelPreemptive,
        RCPSPModelSpecialConstraintsPreemptive,
        RCPSPModel,
    ],
}


def look_for_solver(domain):
    class_domain = domain.__class__
    return look_for_solver_class(class_domain)


def look_for_solver_class(class_domain):
    available = []
    for solver in solvers_compatibility:
        if class_domain in solvers_compatibility[solver]:
            available += [solver]
    return available


def solve(method, rcpsp_model: RCPSPModel, **args) -> ResultStorage:
    if method == GPHH:
        solver = GPHH([rcpsp_model], rcpsp_model, **args)
    else:
        solver = method(rcpsp_model, **args)
    try:
        solver.init_model(**args)
    except:
        pass
    return solver.solve(**args)


def solve_return_solver(
    method, rcpsp_model: RCPSPModel, **args
) -> Tuple[ResultStorage, SolverDO]:
    if method == GPHH:
        solver = GPHH([rcpsp_model], rcpsp_model, **args)
    else:
        solver = method(rcpsp_model, **args)
    try:
        solver.init_model(**args)
    except:
        pass
    return solver.solve(**args), solver


def return_solver(method, rcpsp_model: RCPSPModel, **args) -> ResultStorage:
    if method == GPHH:
        solver = GPHH([rcpsp_model], rcpsp_model, **args)
    else:
        solver = method(rcpsp_model, **args)
    try:
        solver.init_model(**args)
    except:
        pass
    return solver


def get_solver_default_arguments(method) -> Dict[str, Any]:
    try:
        return solvers_map[method][1]
    except KeyError:
        raise KeyError(f"{method} is not in the list of available solvers for RCPSP.")
