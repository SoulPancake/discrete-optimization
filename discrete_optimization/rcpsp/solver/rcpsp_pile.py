#  Copyright (c) 2022 AIRBUS and its affiliates.
#  This source code is licensed under the MIT license found in the
#  LICENSE file in the root directory of this source tree.

import logging
import random
from enum import Enum
from heapq import heappop, heappush
from typing import Dict, Iterable, List

import networkx as nx
import numpy as np

from discrete_optimization.generic_tools.cp_tools import CPSolverName, ParametersCP
from discrete_optimization.generic_tools.do_problem import (
    ParamsObjectiveFunction,
    build_aggreg_function_and_params_objective,
)
from discrete_optimization.generic_tools.do_solver import SolverDO
from discrete_optimization.generic_tools.result_storage.result_storage import (
    ResultStorage,
)
from discrete_optimization.rcpsp.rcpsp_model import (
    MultiModeRCPSPModel,
    PartialSolution,
    RCPSPModel,
    RCPSPModelCalendar,
    RCPSPSolution,
)
from discrete_optimization.rcpsp.solver.cp_solvers import CP_MRCPSP_MZN_MODES

logger = logging.getLogger(__name__)


class GreedyChoice(Enum):
    MOST_SUCCESSORS = 1
    SAMPLE_MOST_SUCCESSORS = 2
    FASTEST = 3
    TOTALLY_RANDOM = 4


pop = heappop
push = heappush


class PileSolverRCPSP(SolverDO):
    def __init__(
        self,
        rcpsp_model: RCPSPModel,
        params_objective_function: ParamsObjectiveFunction = None,
        **kwargs,
    ):
        self.rcpsp_model = rcpsp_model
        self.resources = rcpsp_model.resources
        self.non_renewable = rcpsp_model.non_renewable_resources
        self.n_jobs = rcpsp_model.n_jobs
        self.mode_details = rcpsp_model.mode_details
        self.graph = rcpsp_model.compute_graph()
        self.nx_graph: nx.DiGraph = self.graph.to_networkx()
        self.successors_map = {}
        self.predecessors_map = {}
        successors = {
            n: nx.algorithms.descendants(self.nx_graph, n)
            for n in self.nx_graph.nodes()
        }
        self.source = self.rcpsp_model.source_task
        self.sink = self.rcpsp_model.sink_task
        self.all_activities = set(self.rcpsp_model.tasks_list)
        for k in successors:
            self.successors_map[k] = {"succs": successors[k], "nb": len(successors[k])}
        predecessors = {
            n: nx.algorithms.ancestors(self.nx_graph, n) for n in self.nx_graph.nodes()
        }
        for k in predecessors:
            self.predecessors_map[k] = {
                "succs": predecessors[k],
                "nb": len(predecessors[k]),
            }
        (
            self.aggreg_from_sol,
            self.aggreg_from_dict,
            self.params_objective_function,
        ) = build_aggreg_function_and_params_objective(
            problem=self.rcpsp_model,
            params_objective_function=params_objective_function,
        )
        if isinstance(self.rcpsp_model, (MultiModeRCPSPModel, RCPSPModelCalendar)):
            solver = CP_MRCPSP_MZN_MODES(
                self.rcpsp_model, cp_solver_name=CPSolverName.CHUFFED
            )
            params_cp = ParametersCP.default()
            params_cp.time_limit = 1
            params_cp.nr_solutions = 1
            params_cp.all_solutions = False
            result_storage = solver.solve(parameters_cp=params_cp)
            one_mode_setting = result_storage[0]
            self.modes_dict = {}
            for i in range(len(one_mode_setting)):
                self.modes_dict[i + 1] = one_mode_setting[i]
        else:
            self.modes_dict = {t: 1 for t in self.mode_details}

    def solve(self, **kwargs) -> ResultStorage:
        greedy_choice = kwargs.get("greedy_choice", GreedyChoice.MOST_SUCCESSORS)
        current_succ = {
            k: {
                "succs": set(self.successors_map[k]["succs"]),
                "nb": self.successors_map[k]["nb"],
            }
            for k in self.successors_map
        }
        current_pred = {
            k: {
                "succs": set(self.predecessors_map[k]["succs"]),
                "nb": self.predecessors_map[k]["nb"],
            }
            for k in self.predecessors_map
        }
        schedule = {}
        current_ressource_available = self.resources.copy()
        current_ressource_non_renewable = {
            nr: self.resources[nr] for nr in self.non_renewable
        }
        schedule[self.source] = {"start_time": 0, "end_time": 0}
        available_activities = {
            n for n in current_pred if n not in schedule and current_pred[n]["nb"] == 0
        }
        available_activities.update(
            {n for n in self.all_activities if n not in current_pred}
        )
        for neighbor in current_pred:
            if self.source in current_pred[neighbor]["succs"]:
                current_pred[neighbor]["succs"].remove(self.source)
                current_pred[neighbor]["nb"] -= 1
                if current_pred[neighbor]["nb"] == 0:
                    available_activities.add(neighbor)
        queue = []
        current_time = 0
        perm = []
        while len(schedule) < self.n_jobs:
            logger.debug(len(schedule))
            logger.debug(f"available activities : {available_activities}")
            possible_activities = [
                n
                for n in available_activities
                if all(
                    self.mode_details[n][self.modes_dict[n]][r]
                    <= current_ressource_available[r]
                    for r in current_ressource_available
                )
            ]
            logger.debug(f"Ressources : {current_ressource_available}")
            while len(possible_activities) > 0:
                next_activity = None
                if greedy_choice == GreedyChoice.MOST_SUCCESSORS:
                    next_activity = max(
                        possible_activities, key=lambda x: current_succ[x]["nb"]
                    )
                if greedy_choice == GreedyChoice.SAMPLE_MOST_SUCCESSORS:
                    prob = np.array(
                        [
                            current_succ[possible_activities[i]]["nb"]
                            for i in range(len(possible_activities))
                        ]
                    )
                    s = np.sum(prob)
                    if s != 0:
                        prob = prob / s
                    else:
                        prob = (
                            1.0
                            / len(possible_activities)
                            * np.ones((len(possible_activities)))
                        )
                    next_activity = np.random.choice(
                        np.arange(0, len(possible_activities)), size=1, p=prob
                    )[0]
                    next_activity = possible_activities[next_activity]
                if greedy_choice == GreedyChoice.FASTEST:
                    next_activity = min(
                        possible_activities,
                        key=lambda x: self.mode_details[x][self.modes_dict[x]][
                            "duration"
                        ],
                    )
                if greedy_choice == GreedyChoice.TOTALLY_RANDOM:
                    next_activity = random.choice(possible_activities)
                available_activities.remove(next_activity)
                if next_activity in self.rcpsp_model.index_task_non_dummy:
                    perm += [self.rcpsp_model.index_task_non_dummy[next_activity]]
                schedule[next_activity] = {}
                schedule[next_activity]["start_time"] = current_time
                schedule[next_activity]["end_time"] = (
                    current_time
                    + self.mode_details[next_activity][self.modes_dict[next_activity]][
                        "duration"
                    ]
                )
                push(
                    queue, (schedule[next_activity]["end_time"], next_activity, "end_")
                )
                for r in self.resources:
                    current_ressource_available[r] -= self.mode_details[next_activity][
                        self.modes_dict[next_activity]
                    ][r]
                    if r in current_ressource_non_renewable:
                        current_ressource_non_renewable[r] -= self.mode_details[
                            next_activity
                        ][self.modes_dict[next_activity]][r]
                logger.debug(
                    (
                        current_time,
                        "Current ressource available : ",
                        current_ressource_available,
                    )
                )
                possible_activities = [
                    n
                    for n in available_activities
                    if all(
                        self.mode_details[n][self.modes_dict[n]][r]
                        <= current_ressource_available[r]
                        for r in current_ressource_available
                    )
                ]
            current_time, activity, descr = pop(queue)
            for neighbor in current_pred:
                if activity in current_pred[neighbor]["succs"]:
                    current_pred[neighbor]["succs"].remove(activity)
                    current_pred[neighbor]["nb"] -= 1
                    if current_pred[neighbor]["nb"] == 0:
                        available_activities.add(neighbor)
            for r in self.resources:
                if r not in current_ressource_non_renewable:
                    current_ressource_available[r] += self.mode_details[activity][
                        self.modes_dict[activity]
                    ][r]
        logger.debug(f"Final Time {current_time}")
        sol = RCPSPSolution(
            problem=self.rcpsp_model,
            rcpsp_permutation=perm,
            rcpsp_schedule=schedule,
            rcpsp_modes=[
                self.modes_dict[t] for t in self.rcpsp_model.tasks_list_non_dummy
            ],
            rcpsp_schedule_feasible=True,
        )
        result_storage = ResultStorage(
            list_solution_fits=[(sol, self.aggreg_from_sol(sol))],
            best_solution=sol,
            mode_optim=self.params_objective_function.sense_function,
        )
        return result_storage


class PileSolverRCPSP_Calendar(SolverDO):
    def __init__(
        self,
        rcpsp_model: RCPSPModelCalendar,
        params_objective_function: ParamsObjectiveFunction = None,
        **kwargs,
    ):
        self.rcpsp_model = rcpsp_model
        self.resources = rcpsp_model.resources
        self.non_renewable = rcpsp_model.non_renewable_resources
        self.n_jobs = rcpsp_model.n_jobs
        self.n_jobs_non_dummy = rcpsp_model.n_jobs_non_dummy
        self.mode_details = rcpsp_model.mode_details
        self.graph = rcpsp_model.compute_graph()
        self.nx_graph: nx.DiGraph = self.graph.to_networkx()
        self.successors_map = {}
        self.predecessors_map = {}
        successors = {
            n: nx.algorithms.descendants(self.nx_graph, n)
            for n in self.nx_graph.nodes()
        }
        self.source = self.rcpsp_model.source_task
        self.sink = self.rcpsp_model.sink_task
        self.all_activities = set(self.rcpsp_model.tasks_list)
        for k in successors:
            self.successors_map[k] = {"succs": successors[k], "nb": len(successors[k])}
        predecessors = {
            n: nx.algorithms.ancestors(self.nx_graph, n) for n in self.nx_graph.nodes()
        }
        for k in predecessors:
            self.predecessors_map[k] = {
                "succs": predecessors[k],
                "nb": len(predecessors[k]),
            }
        (
            self.aggreg_from_sol,
            self.aggreg_from_dict,
            self.params_objective_function,
        ) = build_aggreg_function_and_params_objective(
            problem=self.rcpsp_model,
            params_objective_function=params_objective_function,
        )
        if isinstance(self.rcpsp_model, (MultiModeRCPSPModel, RCPSPModelCalendar)):
            solver = CP_MRCPSP_MZN_MODES(
                self.rcpsp_model, cp_solver_name=CPSolverName.CHUFFED
            )
            params_cp = ParametersCP.default()
            params_cp.time_limit = 1
            params_cp.nr_solutions = 1
            params_cp.all_solutions = False
            result_storage = solver.solve(parameters_cp=params_cp)
            one_mode_setting = result_storage[0]
            self.modes_dict = {}
            for i in range(len(one_mode_setting)):
                self.modes_dict[i + 1] = one_mode_setting[i]
        else:
            self.modes_dict = {t: 1 for t in self.mode_details}
        self.with_calendar = isinstance(self.rcpsp_model, RCPSPModelCalendar)

    def solve(self, **kwargs) -> ResultStorage:
        greedy_choice = kwargs.get("greedy_choice", GreedyChoice.MOST_SUCCESSORS)
        current_succ = {
            k: {
                "succs": set(self.successors_map[k]["succs"]),
                "nb": self.successors_map[k]["nb"],
            }
            for k in self.successors_map
        }
        current_pred = {
            k: {
                "succs": set(self.predecessors_map[k]["succs"]),
                "nb": self.predecessors_map[k]["nb"],
            }
            for k in self.predecessors_map
        }
        schedule = {}
        partial_solution: PartialSolution = kwargs.get("partial_solution", None)
        if partial_solution is not None:
            if partial_solution.start_times is not None:
                starting_time = 0
                for task in partial_solution.start_times:
                    schedule[task] = {"start_time": partial_solution.start_times[task]}
                    starting_time = max(
                        starting_time, partial_solution.start_times[task]
                    )
            if partial_solution.end_times is not None:
                for task in partial_solution.end_times:
                    if task in schedule:
                        schedule[task]["end_time"] = partial_solution.end_times[task]

        current_ressource_available = {}
        for r in self.resources:
            if isinstance(self.resources[r], Iterable):
                current_ressource_available[r] = (
                    list(self.resources[r]) + [self.resources[r][-1]] * 100
                )
            else:
                current_ressource_available[r] = [
                    self.resources[r] for i in range(self.rcpsp_model.horizon)
                ]

        current_ressource_non_renewable = {
            nr: current_ressource_available[nr] for nr in self.non_renewable
        }
        if self.source not in schedule:
            schedule[self.source] = {"start_time": 0, "end_time": 0}
        available_activities = {
            n for n in current_pred if n not in schedule and current_pred[n]["nb"] == 0
        }
        available_activities.update(
            {n for n in self.all_activities if n not in current_pred}
        )
        for neighbor in current_pred:
            if self.source in current_pred[neighbor]["succs"]:
                current_pred[neighbor]["succs"].remove(self.source)
                current_pred[neighbor]["nb"] -= 1
                if current_pred[neighbor]["nb"] == 0:
                    available_activities.add(neighbor)
        logger.debug(current_pred)
        queue = []
        current_time = 0
        perm = []
        while len(schedule) < self.n_jobs:
            logger.debug((len(schedule), current_time))
            logger.debug(f"available activities : {available_activities}")
            possible_activities = [
                n
                for n in available_activities
                if all(
                    self.mode_details[n][self.modes_dict[n]][r]
                    <= current_ressource_available[r][
                        min(time, len(current_ressource_available[r]) - 1)
                    ]
                    for r in current_ressource_available
                    for time in range(
                        current_time,
                        current_time
                        + self.mode_details[n][self.modes_dict[n]]["duration"],
                    )
                )
            ]
            logger.debug(f"Ressources : {current_ressource_available}")
            while len(possible_activities) > 0:
                if greedy_choice == GreedyChoice.MOST_SUCCESSORS:
                    next_activity = max(
                        possible_activities, key=lambda x: current_succ[x]["nb"]
                    )
                if greedy_choice == GreedyChoice.SAMPLE_MOST_SUCCESSORS:
                    prob = np.array(
                        [
                            current_succ[possible_activities[i]]["nb"]
                            for i in range(len(possible_activities))
                        ]
                    )
                    s = np.sum(prob)
                    if s != 0:
                        prob = prob / s
                    else:
                        prob = (
                            1.0
                            / len(possible_activities)
                            * np.ones((len(possible_activities)))
                        )
                    next_activity = np.random.choice(
                        np.arange(0, len(possible_activities)), size=1, p=prob
                    )[0]
                    next_activity = possible_activities[next_activity]
                if greedy_choice == GreedyChoice.FASTEST:
                    next_activity = min(
                        possible_activities,
                        key=lambda x: self.mode_details[x][self.modes_dict[x]][
                            "duration"
                        ],
                    )
                if greedy_choice == GreedyChoice.TOTALLY_RANDOM:
                    next_activity = random.choice(possible_activities)
                available_activities.remove(next_activity)
                perm += [next_activity - 2]
                schedule[next_activity] = {}
                schedule[next_activity]["start_time"] = current_time
                schedule[next_activity]["end_time"] = (
                    current_time
                    + self.mode_details[next_activity][self.modes_dict[next_activity]][
                        "duration"
                    ]
                )
                push(
                    queue, (schedule[next_activity]["end_time"], next_activity, "end_")
                )
                mode = self.modes_dict[next_activity]
                duration = self.mode_details[next_activity][mode]["duration"]
                for r in self.resources:
                    for t in range(current_time, current_time + duration):
                        current_ressource_available[r][t] -= self.mode_details[
                            next_activity
                        ][mode][r]
                        if r in current_ressource_non_renewable:
                            current_ressource_non_renewable[r][t] -= self.mode_details[
                                next_activity
                            ][mode][r]
                possible_activities = [
                    n
                    for n in available_activities
                    if all(
                        self.mode_details[n][self.modes_dict[n]][r]
                        <= current_ressource_available[r][time]
                        for r in current_ressource_available
                        for time in range(
                            current_time,
                            current_time
                            + self.mode_details[n][self.modes_dict[n]]["duration"]
                            + 1,
                        )
                    )
                ]
            if len(queue) > 0:
                current_time, activity, descr = pop(queue)
                for neighbor in current_pred:
                    if activity in current_pred[neighbor]["succs"]:
                        current_pred[neighbor]["succs"].remove(activity)
                        current_pred[neighbor]["nb"] -= 1
                        if current_pred[neighbor]["nb"] == 0:
                            available_activities.add(neighbor)
            else:
                current_time += 1
        logger.debug(f"Final Time {current_time}")
        sol = RCPSPSolution(
            problem=self.rcpsp_model,
            rcpsp_permutation=perm[:-1],
            rcpsp_schedule=schedule,
            rcpsp_modes=[
                self.modes_dict[t] for t in self.rcpsp_model.tasks_list_non_dummy
            ],
            rcpsp_schedule_feasible=True,
        )
        result_storage = ResultStorage(
            list_solution_fits=[(sol, self.aggreg_from_sol(sol))],
            best_solution=sol,
            mode_optim=self.params_objective_function.sense_function,
        )
        return result_storage


class Executor(PileSolverRCPSP):
    def __init__(self, rcpsp_model: RCPSPModel):
        super().__init__(rcpsp_model)
        self.immediate_predecessors = {
            n: list(self.nx_graph.predecessors(n)) for n in self.nx_graph.nodes()
        }
        self.immediate_successors = {
            n: list(self.nx_graph.neighbors(n)) for n in self.nx_graph.nodes()
        }

    def update(self, rcpsp_model: RCPSPModel):
        self.mode_details = rcpsp_model.mode_details
        self.resources = rcpsp_model.resources

    def compute_schedule_from_priority_list(
        self, permutation_jobs: List[int], modes_dict: Dict[int, int]
    ):
        current_pred = {
            k: {
                "succs": set(self.immediate_predecessors[k]),
                "nb": len(self.immediate_predecessors[k]),
            }
            for k in self.immediate_predecessors
        }
        schedule = {}
        current_ressource_available = self.resources.copy()
        current_ressource_non_renewable = {
            nr: self.resources[nr] for nr in self.non_renewable
        }
        schedule[self.source] = {"start_time": 0, "end_time": 0}
        available_activities = {
            n for n in current_pred if n not in schedule and current_pred[n]["nb"] == 0
        }
        available_activities.update(
            {n for n in self.all_activities if n not in current_pred}
        )
        for neighbor in self.immediate_successors[1]:
            if 1 in current_pred[neighbor]["succs"]:
                current_pred[neighbor]["succs"].remove(1)
                current_pred[neighbor]["nb"] -= 1
                if current_pred[neighbor]["nb"] == 0:
                    available_activities.add(neighbor)
        permutation_jobs.remove(1)
        queue = []
        current_time = 0
        perm = []
        while len(schedule) < self.n_jobs + 2:
            possible_activities = [
                n
                for n in available_activities
                if all(
                    self.mode_details[n][modes_dict[n]][r]
                    <= current_ressource_available[r]
                    for r in current_ressource_available
                )
            ]
            while len(possible_activities) > 0:
                next_activity = min(
                    possible_activities, key=lambda x: permutation_jobs.index(x)
                )
                available_activities.remove(next_activity)
                perm += [next_activity - 2]
                schedule[next_activity] = {}
                schedule[next_activity]["start_time"] = current_time
                schedule[next_activity]["end_time"] = (
                    current_time
                    + self.mode_details[next_activity][modes_dict[next_activity]][
                        "duration"
                    ]
                )
                permutation_jobs.remove(next_activity)
                push(
                    queue, (schedule[next_activity]["end_time"], next_activity, "end_")
                )
                for r in self.resources:
                    current_ressource_available[r] -= self.mode_details[next_activity][
                        modes_dict[next_activity]
                    ][r]
                    if r in current_ressource_non_renewable:
                        current_ressource_non_renewable[r] -= self.mode_details[
                            next_activity
                        ][modes_dict[next_activity]][r]
                possible_activities = [
                    n
                    for n in available_activities
                    if all(
                        self.mode_details[n][modes_dict[n]][r]
                        <= current_ressource_available[r]
                        for r in current_ressource_available
                    )
                ]
            current_time, activity, descr = pop(queue)
            for neighbor in self.immediate_successors[activity]:
                if activity in current_pred[neighbor]["succs"]:
                    current_pred[neighbor]["succs"].remove(activity)
                    current_pred[neighbor]["nb"] -= 1
                    if current_pred[neighbor]["nb"] == 0:
                        available_activities.add(neighbor)
            for r in self.resources:
                if r not in current_ressource_non_renewable:
                    current_ressource_available[r] += self.mode_details[activity][
                        modes_dict[activity]
                    ][r]
        sol = RCPSPSolution(
            problem=self.rcpsp_model,
            rcpsp_permutation=perm[:-1],
            rcpsp_schedule=schedule,
            rcpsp_modes=[modes_dict[i + 1] for i in range(self.n_jobs)],
            rcpsp_schedule_feasible=True,
        )
        result_storage = ResultStorage(
            list_solution_fits=[(sol, self.aggreg_from_sol(sol))],
            best_solution=sol,
            mode_optim=self.params_objective_function.sense_function,
        )
        return result_storage
