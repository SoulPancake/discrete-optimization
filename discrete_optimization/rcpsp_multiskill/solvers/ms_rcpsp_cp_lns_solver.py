#  Copyright (c) 2022 AIRBUS and its affiliates.
#  This source code is licensed under the MIT license found in the
#  LICENSE file in the root directory of this source tree.

import random
from enum import Enum
from typing import Any, Iterable, List, Optional

import numpy as np
from minizinc import Instance

from discrete_optimization.generic_tools.cp_tools import (
    CPSolver,
    CPSolverName,
    ParametersCP,
)
from discrete_optimization.generic_tools.do_problem import get_default_objective_setup
from discrete_optimization.generic_tools.lns_cp import (
    LNS_CP,
    ConstraintHandler,
    SolverDO,
)
from discrete_optimization.generic_tools.result_storage.result_storage import (
    ResultStorage,
)
from discrete_optimization.rcpsp_multiskill.rcpsp_multiskill import (
    MS_RCPSPModel,
    MS_RCPSPSolution,
)
from discrete_optimization.rcpsp_multiskill.solvers.cp_solvers import CP_MS_MRCPSP_MZN
from discrete_optimization.rcpsp_multiskill.solvers.lns_post_process_rcpsp import (
    PostProMSRCPSP,
)
from discrete_optimization.rcpsp_multiskill.solvers.ms_rcpsp_lp_lns_solver import (
    InitialMethodRCPSP,
    InitialSolutionMS_RCPSP,
)


class ConstraintHandlerStartTimeInterval_CP(ConstraintHandler):
    def __init__(
        self,
        problem: MS_RCPSPModel,
        fraction_to_fix: float = 0.9,
        minus_delta: int = 2,
        plus_delta: int = 2,
        fraction_task_to_fix_employee: float = 0.5,
    ):
        self.problem = problem
        self.fraction_to_fix = fraction_to_fix
        self.minus_delta = minus_delta
        self.plus_delta = plus_delta
        self.fraction_task_to_fix_employee = fraction_task_to_fix_employee

    def adding_constraint_from_results_store(
        self,
        cp_solver: CP_MS_MRCPSP_MZN,
        child_instance: Instance,
        result_storage: ResultStorage,
        last_result_store: Optional[ResultStorage] = None,
    ) -> Iterable[Any]:
        r = random.random()
        if r <= 0.2:
            current_solution, fit = result_storage.get_last_best_solution()
        elif r <= 0.4:
            current_solution, fit = result_storage.get_best_solution_fit()
        elif r <= 0.99:
            current_solution, fit = result_storage.get_random_best_solution()
        else:
            current_solution, fit = result_storage.get_random_solution()
        current_solution: MS_RCPSPSolution = current_solution
        max_time = max(
            [current_solution.get_end_time(x) for x in current_solution.schedule]
        )
        last_jobs = [
            x
            for x in current_solution.schedule
            if current_solution.get_end_time(x) >= max_time - 20
        ]
        nb_jobs = self.problem.n_jobs
        jobs_to_fix = set(
            random.sample(
                current_solution.schedule.keys(), int(self.fraction_to_fix * nb_jobs)
            )
        )
        for lj in last_jobs:
            if lj in jobs_to_fix:
                jobs_to_fix.remove(lj)
        list_strings = []
        self.employees_position = self.problem.employees_list
        task_to_fix = set(
            random.sample(
                current_solution.schedule.keys(),
                int(self.fraction_task_to_fix_employee * nb_jobs),
            )
        )
        employee_to_not_fix = set(
            random.sample(
                range(1, len(self.employees_position) + 1),
                min(
                    5,
                    int(
                        (1 - self.fraction_task_to_fix_employee)
                        * len(self.employees_position)
                    ),
                ),
            )
        )
        employee_usage = {
            emp: [
                task
                for task in current_solution.employee_usage
                if emp in current_solution.employee_usage[task]
            ]
            for emp in self.problem.employees
        }

        for i in range(1, len(self.employees_position) + 1):
            if i in employee_to_not_fix:
                continue
            for task in task_to_fix:
                emp = self.employees_position[i - 1]
                index_minizinc = cp_solver.index_in_minizinc[task]
                if (
                    task in current_solution.employee_usage
                    and emp in current_solution.employee_usage[task]
                    and len(current_solution.employee_usage[task][emp]) > 0
                ):
                    string1 = (
                        "constraint unit_used["
                        + str(i)
                        + ","
                        + str(index_minizinc)
                        + "] = 1;\n"
                    )
                else:
                    string1 = (
                        "constraint unit_used["
                        + str(i)
                        + ","
                        + str(index_minizinc)
                        + "] = 0;\n"
                    )
                child_instance.add_string(string1)
                list_strings += [string1]
        for job in [self.problem.sink_task]:
            index_minizinc = cp_solver.index_in_minizinc[job]
            start_time_j = current_solution.schedule[job]["start_time"]
            string1 = (
                "constraint start["
                + str(index_minizinc)
                + "] <= "
                + str(start_time_j)
                + ";\n"
            )
            list_strings += [string1]
            child_instance.add_string(string1)
        for job in jobs_to_fix:
            start_time_j = current_solution.schedule[job]["start_time"]
            index_minizinc = cp_solver.index_in_minizinc[job]
            min_st = max(start_time_j - self.minus_delta, 0)
            max_st = min(start_time_j + self.plus_delta, max_time)
            string1 = (
                "constraint start["
                + str(index_minizinc)
                + "] <= "
                + str(max_st)
                + ";\n"
            )
            string2 = (
                "constraint start["
                + str(index_minizinc)
                + "] >= "
                + str(min_st)
                + ";\n"
            )
            list_strings += [string1]
            list_strings += [string2]
            child_instance.add_string(string1)
            child_instance.add_string(string2)
        for job in current_solution.schedule.keys():
            index_minizinc = cp_solver.index_in_minizinc[job]
            if job in jobs_to_fix:
                continue
            string1 = (
                "constraint start["
                + str(index_minizinc)
                + "] <= "
                + str(max_time)
                + ";\n"
            )
            child_instance.add_string(string1)
            list_strings += [string1]
        return list_strings

    def remove_constraints_from_previous_iteration(
        self,
        cp_solver: CP_MS_MRCPSP_MZN,
        child_instance,
        previous_constraints: Iterable[Any],
    ):
        pass


class Params:
    fraction_to_fix: float
    minus_delta: int
    plus_delta: int
    fraction_task_to_fix_employee: float

    def __init__(
        self,
        fraction_to_fix: float = 0.9,
        minus_delta: int = 2,
        plus_delta: int = 2,
        fraction_task_to_fix_employee: float = 0.5,
    ):
        self.fraction_to_fix = fraction_to_fix
        self.minus_delta = minus_delta
        self.plus_delta = plus_delta
        self.fraction_task_to_fix_employee = fraction_task_to_fix_employee


class ConstraintHandlerMix(ConstraintHandler):
    def __init__(
        self, problem: MS_RCPSPModel, list_params: List[Params], list_proba: List[float]
    ):
        self.problem = problem
        self.list_params = list_params
        self.list_proba = list_proba
        if isinstance(self.list_proba, list):
            self.list_proba = np.array(self.list_proba)
        self.list_proba = self.list_proba / np.sum(self.list_proba)
        self.index_np = np.array(range(len(self.list_proba)), dtype=np.int)
        self.current_iteration = 0
        self.status = {
            i: {"nb_usage": 0, "nb_improvement": 0}
            for i in range(len(self.list_params))
        }
        self.last_index_param = None
        self.last_fitness = None

    def adding_constraint_from_results_store(
        self,
        cp_solver: CP_MS_MRCPSP_MZN,
        child_instance: Instance,
        result_storage: ResultStorage,
        last_result_store: Optional[ResultStorage] = None,
    ) -> Iterable[Any]:
        new_fitness = result_storage.get_best_solution_fit()[1]
        if self.last_index_param is not None:
            if new_fitness != self.last_fitness:
                self.status[self.last_index_param]["nb_improvement"] += 1
                self.last_fitness = new_fitness
                self.list_proba[self.last_index_param] *= 1.05
                self.list_proba = self.list_proba / np.sum(self.list_proba)
            else:
                self.list_proba[self.last_index_param] *= 0.95
                self.list_proba = self.list_proba / np.sum(self.list_proba)
        else:
            self.last_fitness = new_fitness
        if random.random() <= 0.95:
            choice = np.random.choice(self.index_np, size=1, p=self.list_proba)[0]
        else:
            max_improvement = max(
                [
                    self.status[x]["nb_improvement"]
                    / max(self.status[x]["nb_usage"], 1)
                    for x in self.status
                ]
            )
            choice = random.choice(
                [
                    x
                    for x in self.status
                    if self.status[x]["nb_improvement"]
                    / max(self.status[x]["nb_usage"], 1)
                    == max_improvement
                ]
            )
        d_params = {
            key: getattr(self.list_params[int(choice)], key)
            for key in self.list_params[0].__dict__.keys()
        }
        ch = ConstraintHandlerStartTimeInterval_CP(problem=self.problem, **d_params)
        self.current_iteration += 1
        self.last_index_param = choice
        self.status[self.last_index_param]["nb_usage"] += 1
        return ch.adding_constraint_from_results_store(
            cp_solver, child_instance, result_storage, last_result_store
        )

    def remove_constraints_from_previous_iteration(
        self, cp_solver: CPSolver, child_instance, previous_constraints: Iterable[Any]
    ):
        pass


class OptionNeighbor(Enum):
    MIX_ALL = 0
    MIX_FAST = 1
    MIX_LARGE_NEIGH = 2
    OM = 4
    DEBUG = 3


def build_neighbor_operator(option_neighbor: OptionNeighbor, rcpsp_model):
    params_om = [
        Params(
            fraction_to_fix=0.75,
            minus_delta=2000,
            plus_delta=2000,
            fraction_task_to_fix_employee=0.5,
        )
    ]
    params_all = [
        Params(
            fraction_to_fix=0.9,
            minus_delta=1,
            plus_delta=1,
            fraction_task_to_fix_employee=0.5,
        ),
        Params(
            fraction_to_fix=0.85,
            minus_delta=3,
            plus_delta=3,
            fraction_task_to_fix_employee=0.75,
        ),
        Params(
            fraction_to_fix=0.9,
            minus_delta=4,
            plus_delta=4,
            fraction_task_to_fix_employee=0.75,
        ),
        Params(
            fraction_to_fix=0.9,
            minus_delta=4,
            plus_delta=4,
            fraction_task_to_fix_employee=0.7,
        ),
        Params(
            fraction_to_fix=0.92,
            minus_delta=10,
            plus_delta=0,
            fraction_task_to_fix_employee=0.7,
        ),
        Params(
            fraction_to_fix=0.88,
            minus_delta=0,
            plus_delta=10,
            fraction_task_to_fix_employee=0.7,
        ),
        Params(
            fraction_to_fix=0.9,
            minus_delta=10,
            plus_delta=0,
            fraction_task_to_fix_employee=0.7,
        ),
        Params(
            fraction_to_fix=0.8,
            minus_delta=5,
            plus_delta=5,
            fraction_task_to_fix_employee=0.9,
        ),
        Params(
            fraction_to_fix=0.85,
            minus_delta=15,
            plus_delta=15,
            fraction_task_to_fix_employee=1.0,
        ),
        Params(
            fraction_to_fix=0.9,
            minus_delta=3,
            plus_delta=3,
            fraction_task_to_fix_employee=0.6,
        ),
        Params(
            fraction_to_fix=1.0,
            minus_delta=5,
            plus_delta=5,
            fraction_task_to_fix_employee=0.6,
        ),
        Params(
            fraction_to_fix=0.85,
            minus_delta=1,
            plus_delta=1,
            fraction_task_to_fix_employee=0.5,
        ),
        Params(
            fraction_to_fix=0.8,
            minus_delta=2,
            plus_delta=2,
            fraction_task_to_fix_employee=0.85,
        ),
        Params(
            fraction_to_fix=0.85,
            minus_delta=5,
            plus_delta=5,
            fraction_task_to_fix_employee=0.6,
        ),
        Params(
            fraction_to_fix=0.85,
            minus_delta=5,
            plus_delta=5,
            fraction_task_to_fix_employee=0.6,
        ),
        Params(
            fraction_to_fix=0.85,
            minus_delta=5,
            plus_delta=5,
            fraction_task_to_fix_employee=0.6,
        ),
        Params(
            fraction_to_fix=0.85,
            minus_delta=5,
            plus_delta=5,
            fraction_task_to_fix_employee=0.6,
        ),
        Params(
            fraction_to_fix=0.95,
            minus_delta=5,
            plus_delta=5,
            fraction_task_to_fix_employee=0.5,
        ),
        Params(
            fraction_to_fix=0.95,
            minus_delta=5,
            plus_delta=5,
            fraction_task_to_fix_employee=0.5,
        ),
        Params(
            fraction_to_fix=0.85,
            minus_delta=5,
            plus_delta=5,
            fraction_task_to_fix_employee=0.7,
        ),
        Params(
            fraction_to_fix=0.9,
            minus_delta=1,
            plus_delta=1,
            fraction_task_to_fix_employee=0.6,
        ),
        Params(
            fraction_to_fix=0.9,
            minus_delta=1,
            plus_delta=1,
            fraction_task_to_fix_employee=0.6,
        ),
        Params(
            fraction_to_fix=0.8,
            minus_delta=2,
            plus_delta=2,
            fraction_task_to_fix_employee=0.95,
        ),
        Params(
            fraction_to_fix=0.98,
            minus_delta=2,
            plus_delta=2,
            fraction_task_to_fix_employee=0.98,
        ),
        Params(
            fraction_to_fix=0.9,
            minus_delta=3,
            plus_delta=3,
            fraction_task_to_fix_employee=0.6,
        ),
        Params(
            fraction_to_fix=0.98,
            minus_delta=3,
            plus_delta=3,
            fraction_task_to_fix_employee=0.2,
        ),
        Params(
            fraction_to_fix=0.98,
            minus_delta=8,
            plus_delta=8,
            fraction_task_to_fix_employee=0.75,
        ),
        Params(
            fraction_to_fix=0.98,
            minus_delta=10,
            plus_delta=10,
            fraction_task_to_fix_employee=1.0,
        ),
    ]
    params_fast = [
        Params(
            fraction_to_fix=0.9,
            minus_delta=1,
            plus_delta=1,
            fraction_task_to_fix_employee=0.93,
        ),
        Params(
            fraction_to_fix=0.8,
            minus_delta=1,
            plus_delta=1,
            fraction_task_to_fix_employee=0.95,
        ),
        Params(
            fraction_to_fix=0.8,
            minus_delta=2,
            plus_delta=2,
            fraction_task_to_fix_employee=1.0,
        ),
        Params(
            fraction_to_fix=0.9,
            minus_delta=1,
            plus_delta=1,
            fraction_task_to_fix_employee=0.93,
        ),
        Params(
            fraction_to_fix=0.92,
            minus_delta=3,
            plus_delta=3,
            fraction_task_to_fix_employee=0.93,
        ),
        Params(
            fraction_to_fix=0.98,
            minus_delta=7,
            plus_delta=7,
            fraction_task_to_fix_employee=0.92,
        ),
        Params(
            fraction_to_fix=0.95,
            minus_delta=5,
            plus_delta=5,
            fraction_task_to_fix_employee=0.95,
        ),
    ]
    params_debug = [
        Params(
            fraction_to_fix=1.0,
            minus_delta=0,
            plus_delta=0,
            fraction_task_to_fix_employee=1.0,
        )
    ]
    params_large = [
        Params(
            fraction_to_fix=0.9,
            minus_delta=12,
            plus_delta=12,
            fraction_task_to_fix_employee=0.93,
        ),
        Params(
            fraction_to_fix=0.8,
            minus_delta=3,
            plus_delta=3,
            fraction_task_to_fix_employee=0.0,
        ),
        Params(
            fraction_to_fix=0.7,
            minus_delta=12,
            plus_delta=12,
            fraction_task_to_fix_employee=0.8,
        ),
        Params(
            fraction_to_fix=0.7,
            minus_delta=5,
            plus_delta=5,
            fraction_task_to_fix_employee=0.1,
        ),
        Params(
            fraction_to_fix=0.6,
            minus_delta=3,
            plus_delta=3,
            fraction_task_to_fix_employee=0.85,
        ),
        Params(
            fraction_to_fix=0.4,
            minus_delta=2,
            plus_delta=2,
            fraction_task_to_fix_employee=1.0,
        ),
        Params(
            fraction_to_fix=0.9,
            minus_delta=4,
            plus_delta=4,
            fraction_task_to_fix_employee=0.7,
        ),
        Params(
            fraction_to_fix=0.7,
            minus_delta=4,
            plus_delta=4,
            fraction_task_to_fix_employee=0.7,
        ),
        Params(
            fraction_to_fix=0.8,
            minus_delta=5,
            plus_delta=5,
            fraction_task_to_fix_employee=0.3,
        ),
    ]
    params = None
    if option_neighbor == OptionNeighbor.MIX_ALL:
        params = params_all
    if option_neighbor == OptionNeighbor.MIX_FAST:
        params = params_fast
    if option_neighbor == OptionNeighbor.MIX_LARGE_NEIGH:
        params = params_large
    if option_neighbor == OptionNeighbor.DEBUG:
        params = params_debug
    if option_neighbor == OptionNeighbor.OM:
        params = params_om
    probas = [1 / len(params)] * len(params)
    constraint_handler = ConstraintHandlerMix(
        problem=rcpsp_model, list_params=params, list_proba=probas
    )
    return constraint_handler


class LNS_CP_MS_RCPSP_SOLVER(SolverDO):
    def __init__(
        self,
        rcpsp_model: MS_RCPSPModel,
        option_neighbor: OptionNeighbor = OptionNeighbor.MIX_ALL,
        **kwargs
    ):
        self.rcpsp_model = rcpsp_model
        self.solver = CP_MS_MRCPSP_MZN(
            rcpsp_model=self.rcpsp_model, cp_solver_name=CPSolverName.CHUFFED, **kwargs
        )
        self.solver.init_model(**kwargs)
        self.parameters_cp = kwargs.get("parameters_cp", ParametersCP.default())
        params_objective_function = get_default_objective_setup(
            problem=self.rcpsp_model
        )
        self.constraint_handler = build_neighbor_operator(
            option_neighbor=option_neighbor, rcpsp_model=self.rcpsp_model
        )
        if "partial_solution" in kwargs:
            if kwargs["partial_solution"] is not None:
                self.post_pro = None
            else:
                self.post_pro = PostProMSRCPSP(
                    problem=self.rcpsp_model,
                    params_objective_function=params_objective_function,
                )
        else:
            self.post_pro = PostProMSRCPSP(
                problem=self.rcpsp_model,
                params_objective_function=params_objective_function,
            )
        self.initial_solution_provider = InitialSolutionMS_RCPSP(
            problem=self.rcpsp_model,
            initial_method=InitialMethodRCPSP.PILE_CALENDAR,
            params_objective_function=params_objective_function,
        )
        self.lns_solver = LNS_CP(
            problem=self.rcpsp_model,
            cp_solver=self.solver,
            initial_solution_provider=self.initial_solution_provider,
            constraint_handler=self.constraint_handler,
            post_process_solution=self.post_pro,
            params_objective_function=params_objective_function,
        )

    def solve(self, **kwargs) -> ResultStorage:
        return self.lns_solver.solve_lns(
            parameters_cp=kwargs.get("parameters_cp", self.parameters_cp),
            nb_iteration_lns=kwargs.get("nb_iteration_lns", 100),
            skip_first_iteration=kwargs.get("skip_first_iteration", False),
            nb_iteration_no_improvement=kwargs.get("nb_iteration_no_improvement", None),
            max_time_seconds=kwargs.get("max_time_seconds", None),
        )
