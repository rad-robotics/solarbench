"""T3 environment: tighten (to the module manual's torque window) or loosen an M8 clamp bolt.

Stages (scored by solarbench.eval.stats):
    tighten: engaged -> snug -> in_spec -> released
    loosen:  engaged -> broken_away -> backed_off -> released
Damage: over-torque (installed torque above the module manual maximum).
Torque is measured at the UR16e wrist-3 joint (the socket's drive axis), like a nutrunner's transducer.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from typing import TYPE_CHECKING

import torch
from isaaclab.controllers import DifferentialIKController, DifferentialIKControllerCfg
from isaaclab.envs import DirectRLEnv
from isaaclab.utils.math import (
    combine_frame_transforms,
    matrix_from_quat,
    quat_apply,
    quat_apply_inverse,
    quat_from_angle_axis,
    quat_inv,
    quat_mul,
    subtract_frame_transforms,
)

from solarbench import wire
from solarbench.agents import prompts
from solarbench.eval.splits import episode_draws
from solarbench.specs.params import BOLT
from solarbench.tasks import channels
from solarbench.tasks.bolt import BoltParams, bolt_friction

if TYPE_CHECKING:
    from .clamp_env_cfg import ClampEnvCfg

STAGES = {"tighten": ("engaged", "snug", "in_spec", "released"),
          "loosen": ("engaged", "broken_away", "backed_off", "released")}


class ClampEnv(DirectRLEnv):
    cfg: ClampEnvCfg

    def __init__(self, cfg: ClampEnvCfg, render_mode: str | None = None, **kwargs):
        super().__init__(cfg, render_mode, **kwargs)
        self.robot, self.clamp = self.scene["robot"], self.scene["clamp"]
        dev, n = self.device, self.num_envs
        self.stages = STAGES[cfg.mode]
        # Newton/MuJoCo joint friction is one Coulomb value (frictionloss); PhysX splits it into static and dynamic
        # efforts, and dynamic defaults to 0 (the bolt would spin freely once moving), so set both there
        self._split_friction = "newton" not in type(cfg.sim.physics).__name__.lower()
        self.arm_ids = torch.tensor(self.robot.find_joints(list(cfg.arm_joints), preserve_order=True)[0], device=dev)
        self.w3 = self.robot.find_joints("wrist_3_joint")[0][0]
        wcfg = cfg.scene.robot.actuators["wrist"]
        self._kp_w3, self._kd_w3 = float(wcfg.stiffness), float(wcfg.damping)
        self._tau_w3_max = float(wcfg.joint_effort_limit["wrist_3_joint"])
        self.tool_idx = self.robot.find_bodies(cfg.tool_body)[0][0]
        self.jac_idx = self.tool_idx - 1 if self.robot.is_fixed_base else self.tool_idx
        self.jac_cols = self.arm_ids + self.robot.num_base_dofs
        self.ik = DifferentialIKController(DifferentialIKControllerCfg(
            command_type="pose", use_relative_mode=False, ik_method="dls", ik_params={"lambda_val": cfg.ik_damping}),
            num_envs=n, device=dev)
        self.tcp_off = torch.tensor(cfg.tcp_offset, device=dev).repeat(n, 1)
        self.arm_limits = self.robot.data.soft_joint_pos_limits.torch[0, self.arm_ids]
        self.arm_vel_limits = self.robot.data.joint_vel_limits.torch[0, self.arm_ids]
        self.bolt_body = self.clamp.find_bodies("Bolt")[0][0]
        self.bolt_joint = self.clamp.find_joints("bolt_joint")[0][0]
        # per-env bolt parameters, resampled every episode (ASSUMPTIONS P7, P22)
        full = lambda v: torch.full((n,), float(v), device=dev)  # noqa: E731
        k = (cfg.tau_install - float(BOLT.running_torque)) / float(BOLT.snug_to_spec_angle)
        self.bp = BoltParams(full(BOLT.running_torque), full(k), full(BOLT.breakaway_ratio), cfg.tau_spec_max,
                             full(BOLT.nut_factor), float(BOLT.nominal_diameter))
        self.tau_install = full(cfg.tau_install)
        loosen = cfg.mode == "loosen"
        self.theta0 = (self.tau_install - self.bp.tau_run) / k if loosen else full(cfg.start_theta_tighten)

        self.tgt_pos_b = torch.zeros(n, 3, device=dev)
        self.tgt_quat_b = torch.zeros(n, 4, device=dev)
        self.arm_q_des = torch.zeros(n, len(self.arm_ids), device=dev)
        self.prev_actions = torch.zeros(n, cfg.action_space, device=dev)
        self.theta = torch.zeros(n, device=dev)
        self.theta_ref = torch.zeros(n, device=dev)
        self.tau = torch.zeros(n, device=dev)
        self.engaged = torch.zeros(n, dtype=torch.bool, device=dev)
        self.depth = torch.zeros(n, device=dev)
        self.lateral = torch.zeros(n, device=dev)
        self.tcp_head_dist = torch.ones(n, device=dev)
        self.over_torque = torch.zeros(n, dtype=torch.bool, device=dev)
        self.sim_error = torch.zeros(n, dtype=torch.bool, device=dev)
        self.stage_time = torch.full((n, 4), -1.0, device=dev)
        self.peak_tau = torch.zeros(n, device=dev)
        self.vel_violation_steps = torch.zeros(n, device=dev)
        self._rewarded = torch.zeros(n, 4, dtype=torch.bool, device=dev)
        self.episode_index = torch.zeros(n, dtype=torch.long, device=dev)
        self._episodes_started = 0
        self.completed_episodes: list[dict] = []
        # wrist force-torque sensor (ASSUMPTIONS M12): the reaction wrench at the joint that holds the tool
        self.flange = self.scene["flange"]
        self._flange_joint = self.flange.body_names.index(cfg.tool_body)
        self._tool_mass = float(self.robot.data.body_mass.torch[0, self.tool_idx])
        self._tool_com = self.robot.data.body_com_pos_b.torch[0, self.tool_idx].clone()
        self._reaction_sum = torch.zeros(n, 6, device=dev)
        self._untouched = torch.ones(n, dtype=torch.bool, device=dev)  # no physics step yet in this episode
        self._wrench_noise = torch.zeros(n, self.max_episode_length, 6, device=dev)
        self.prompts = [""] * n  # the work order of the episode each environment is running

    @property
    def catalogue(self) -> dict:
        """What this task offers a policy (docs/interface.md, section 2)."""
        c = self.cfg
        return channels.catalogue(self.spec.id, round(1 / self.step_dt), [wire.TOOL_DELTA], ["tick"], [
            channels.proprio_channel(c.arm_joints, self.arm_limits, self.arm_vel_limits),
            channels.wrench_channel(c.wrench_force_range, c.wrench_torque_range),
            channels.policy_channel(c.observation_space)])

    # ------------------------------------------------------------------ frames
    def _root(self):
        return self.robot.data.root_pos_w.torch, self.robot.data.root_quat_w.torch

    def tcp_pose_w(self):
        pose = self.robot.data.body_pose_w.torch[:, self.tool_idx]
        return combine_frame_transforms(pose[:, :3], pose[:, 3:], self.tcp_off)

    def tcp_pose_b(self):
        rp, rq = self._root()
        p, q = self.tcp_pose_w()
        return subtract_frame_transforms(rp, rq, p, q)

    def head_top_w(self):
        pose = self.clamp.data.body_pose_w.torch[:, self.bolt_body]
        z = quat_apply(pose[:, 3:], torch.tensor([[0.0, 0.0, 1.0]], device=self.device).expand(self.num_envs, 3))
        return pose[:, :3] + self.cfg.head_top_offset * z, z

    def _measure(self) -> None:
        tcp_p, tcp_q = self.tcp_pose_w()
        z_t = quat_apply(tcp_q, torch.tensor([[0.0, 0.0, 1.0]], device=self.device).expand(self.num_envs, 3))
        head, z_b = self.head_top_w()
        rel = tcp_p - head
        self.depth = torch.sum(rel * z_t, dim=-1)  # > 0: head top is inside the socket
        along = torch.sum(rel * z_b, dim=-1, keepdim=True) * z_b
        self.lateral = (rel - along).norm(dim=-1)
        self.tcp_head_dist = rel.norm(dim=-1)
        cosang = torch.sum(-z_t * z_b, dim=-1)
        self.axis_err_deg = torch.rad2deg(torch.acos(cosang.clamp(-1.0, 1.0)))
        ang_ok = cosang > torch.cos(torch.deg2rad(torch.tensor(self.cfg.engage_angle_deg)))
        self.engaged = (self.depth > self.cfg.engage_depth) & (self.lateral < self.cfg.engage_lateral) & ang_ok
        self.theta = -self.clamp.data.joint_pos.torch[:, self.bolt_joint]  # tightening = -rotation about +Z
        # Wrist-3 drive torque, tightening positive. Isaac Lab's applied_torque does not carry the implicit PD drive,
        # so it is reconstructed like a joint-current estimate: kp*(q_des - q) - kd*qd + feedforward, clipped to the
        # UR16e wrist limit.
        jw = self.arm_ids[5]
        q, qd = self.robot.data.joint_pos.torch[:, jw], self.robot.data.joint_vel.torch[:, jw]
        tau = self._kp_w3 * (self.arm_q_des[:, 5] - q) - self._kd_w3 * qd
        self.tau = tau.clamp(-self._tau_w3_max, self._tau_w3_max)

    # ------------------------------------------------------------------ actions
    def _pre_physics_step(self, actions: torch.Tensor) -> None:
        a = actions.clamp(-1.0, 1.0)
        self.prev_actions[:] = self.actions
        self.actions[:] = a
        self.tgt_pos_b += a[:, :3] * self.cfg.max_tcp_step
        d_rot = a[:, 3:6] * self.cfg.max_rot_step
        ang = d_rot.norm(dim=-1)
        axis = torch.where(ang[:, None] > 1e-9, d_rot / ang.clamp(min=1e-9)[:, None],
                           torch.tensor([1.0, 0.0, 0.0], device=self.device))
        self.tgt_quat_b = quat_mul(quat_from_angle_axis(ang, axis), self.tgt_quat_b)
        cur, _ = self.tcp_pose_b()
        delta = self.tgt_pos_b - cur
        self.tgt_pos_b = cur + delta * (0.05 / delta.norm(dim=-1, keepdim=True).clamp(min=0.05))
        tool_pos_b = self.tgt_pos_b - quat_apply(self.tgt_quat_b, self.tcp_off)
        self.ik.set_command(torch.cat([tool_pos_b, self.tgt_quat_b], dim=-1))
        rp, rq = self._root()
        pose = self.robot.data.body_pose_w.torch[:, self.tool_idx]
        ee_p, ee_q = subtract_frame_transforms(rp, rq, pose[:, :3], pose[:, 3:])
        jac_w = self.robot.data.body_link_jacobian_w.torch[:, self.jac_idx, :, :][:, :, self.jac_cols]
        r_bw = matrix_from_quat(quat_inv(rq))
        jac_b = torch.cat([r_bw @ jac_w[:, :3], r_bw @ jac_w[:, 3:]], dim=1)
        # Kinematic command integration (as a position-controlled industrial arm does): step the commanded joints
        # from their own predicted pose x(q_des) ~ x(q) + J (q_des - q). Gravity is handled by the model-based
        # feedforward in _apply_action, so no measured-pose integrator (which oscillates on this arm) is needed.
        q = self.robot.data.joint_pos.torch[:, self.arm_ids]
        lag = (self.arm_q_des - q).unsqueeze(-1)
        pred_p = ee_p + (jac_b[:, :3] @ lag).squeeze(-1)
        rv = (jac_b[:, 3:] @ lag).squeeze(-1)
        ang = rv.norm(dim=-1)
        ax = torch.where(ang[:, None] > 1e-9, rv / ang.clamp(min=1e-9)[:, None],
                         torch.tensor([1.0, 0.0, 0.0], device=self.device))
        pred_q = quat_mul(quat_from_angle_axis(ang, ax), ee_q)
        q_des = self.ik.compute(pred_p, pred_q, jac_b, self.arm_q_des)
        q_des = torch.clamp(q_des, q - self.cfg.ik_windup, q + self.cfg.ik_windup)
        self.arm_q_des = q_des.clamp(self.arm_limits[:, 0], self.arm_limits[:, 1])

    def _apply_action(self) -> None:
        tc = self.robot.actuators.target_command
        tc.set_position_index(value=self.arm_q_des, joint_ids=self.arm_ids)
        # model-based gravity compensation feedforward (UR controllers do this); torque limits still apply
        g = self.robot.data.gravity_compensation_forces.torch[:, self.robot.num_base_dofs:]
        tc.set_effort_index(value=g[:, self.arm_ids], joint_ids=self.arm_ids)
        self._measure()
        flange = self.flange.data
        self._reaction_sum += torch.cat([flange.force.torch[:, self._flange_joint],
                                         flange.torque.torch[:, self._flange_joint]], dim=-1)
        # Bolt resistance as scheduled dry joint friction (implicit in the solver): the bolt turns only when the
        # socket applies more than the installed-torque requirement, and the wrist feels the reaction.
        fric = bolt_friction(self.bp, self.theta, self.cfg.mode == "loosen")
        dyn = fric[:, None] if self._split_friction else None
        self.clamp.write_joint_friction_coefficient_to_sim_index(joint_friction_coeff=fric[:, None],
                                                                 joint_dynamic_friction_coeff=dyn,
                                                                 joint_ids=[self.bolt_joint])
        self.over_torque |= self.bp.tau_req(self.theta) > self.bp.tau_max_spec
        self.peak_tau = torch.maximum(self.peak_tau, self.bp.tau_req(self.theta))

    # ------------------------------------------------------------------ MDP
    def _get_observations(self) -> dict:
        rp, rq = self._root()
        tcp_p, tcp_q = self.tcp_pose_b()
        head_w, z_b = self.head_top_w()
        head_b, _ = subtract_frame_transforms(rp, rq, head_w)
        jp, jv = self.robot.data.joint_pos.torch[:, self.arm_ids], self.robot.data.joint_vel.torch[:, self.arm_ids]
        obs = torch.cat([jp, 0.1 * jv, tcp_p, tcp_q, head_b - tcp_p, quat_apply_inverse(rq, z_b),
                         self.theta[:, None], (self.bp.tau_req(self.theta) / 16.0)[:, None],
                         (self.tau / 20.0)[:, None], self.engaged[:, None].float(), self.actions], dim=-1)
        return {"policy": torch.nan_to_num(obs).clamp(-20.0, 20.0), "clock": channels.clock(self.episode_length_buf),
                "proprio": channels.proprio(jp, jv, tcp_p, tcp_q), "wrench": self._wrench()}

    def _wrench(self) -> torch.Tensor:
        """Force and torque the surroundings apply to the tool, at the flange and in the tool frame: the mean of the
        sensor over the control tick, the tool's weight taken out, then noise and the sensor's range."""
        c, n = self.cfg, self.num_envs
        tool_quat = self.robot.data.body_pose_w.torch[:, self.tool_idx, 3:]
        gravity = quat_apply_inverse(tool_quat, torch.tensor(c.sim.gravity, device=self.device).expand(n, 3))
        sensed = channels.external_wrench(self._reaction_sum / c.decimation, gravity, self._tool_mass, self._tool_com)
        sensed[self._untouched] = 0.0
        self._reaction_sum[:] = 0.0
        self._untouched[:] = False
        tick = self.episode_length_buf.clamp(max=self.max_episode_length - 1)
        noise = self._wrench_noise[torch.arange(n, device=self.device), tick]
        sigma = torch.tensor([c.wrench_force_noise] * 3 + [c.wrench_torque_noise] * 3, device=self.device)
        limit = torch.tensor([c.wrench_force_range] * 3 + [c.wrench_torque_range] * 3, device=self.device)
        return torch.nan_to_num(sensed + sigma * noise).clamp(-limit, limit)

    def _stage_conditions(self) -> list[torch.Tensor]:
        reached = self.stage_time >= 0
        tau_inst = self.bp.tau_req(self.theta)
        away = ~self.engaged & (self.tcp_head_dist > self.cfg.released_distance)
        if self.cfg.mode == "tighten":
            return [self.engaged, reached[:, 0] & (self.theta >= 0),
                    reached[:, 1] & (tau_inst >= self.cfg.tau_spec_min), reached[:, 2] & away]
        return [self.engaged, reached[:, 0] & (self.theta < self.theta0 - 0.05),
                reached[:, 1] & (self.theta <= self.theta0 - self.cfg.backoff_angle), reached[:, 2] & away]

    def _get_rewards(self) -> torch.Tensor:
        t = (self.episode_length_buf.float() + 1) * self.step_dt
        reached = self.stage_time >= 0
        for i, c in enumerate(self._stage_conditions()):
            self.stage_time[:, i] = torch.where(c & ~reached[:, i], t, self.stage_time[:, i])
        qd = self.robot.data.joint_vel.torch[:, self.arm_ids].abs()
        self.vel_violation_steps += (qd > self.arm_vel_limits).any(dim=-1).float()
        reached = self.stage_time >= 0
        new = reached & ~self._rewarded
        self._rewarded |= reached
        c = self.cfg
        progress = (self.theta - self.theta0).abs() if c.mode == "loosen" else (self.theta - self.theta0)
        r = c.rew_reach * torch.exp(-self.tcp_head_dist / 0.05) * (~reached[:, 0])
        r += c.rew_engage * self.engaged.float() * 0.1
        r += c.rew_progress * self.engaged.float() * progress.clamp(0, 4.0) * 0.05
        r += c.rew_success * new.float().sum(dim=-1)
        r += c.rew_over_torque * self.over_torque.float()
        r += c.rew_action_rate * torch.sum((self.actions - self.prev_actions) ** 2, dim=-1)
        return torch.where(self.sim_error, torch.zeros_like(r), torch.nan_to_num(r))

    def _get_dones(self) -> tuple[torch.Tensor, torch.Tensor]:
        state = torch.cat([self.robot.data.joint_pos.torch, self.clamp.data.joint_pos.torch], dim=-1)
        self.sim_error |= ~torch.isfinite(state).all(dim=-1)
        done = (self.stage_time[:, -1] >= 0) | self.sim_error
        return done, self.episode_length_buf >= self.max_episode_length - 1

    # ------------------------------------------------------------------ reset
    def _record(self, env_ids: torch.Tensor) -> None:
        if self.common_step_counter == 0:
            return
        st = self.stage_time[env_ids].cpu()
        tau_final = self.bp.tau_req(self.theta)[env_ids].cpu()
        preload = self.bp.preload(self.theta)
        for k, e in enumerate(env_ids.tolist()):
            success = bool(st[k, -1] >= 0)
            if self.cfg.mode == "tighten":
                success &= bool(tau_final[k] <= self.cfg.tau_spec_max)
            rec = {f"t_{s}": float(st[k, i]) for i, s in enumerate(self.stages)}
            rec.update({f"stage_{s}": bool(st[k, i] >= 0) for i, s in enumerate(self.stages)})
            rec.update({
                "episode": int(self.episode_index[e]),
                "env_id": e, "sim_error": bool(self.sim_error[e]), "success": success,
                "damage": bool(self.over_torque[e]), "over_torque": bool(self.over_torque[e]),
                "safe_success": success and not bool(self.over_torque[e]),
                "installed_torque_Nm": float(tau_final[k]), "peak_installed_torque_Nm": float(self.peak_tau[e]),
                "preload_N": float(preload[e]),
                "bolt_angle_change_rad": float(self.theta[e] - self.theta0[e]),
                "bolt_params": {
                    "tau_run_Nm": float(self.bp.tau_run[e]), "stiffness_Nm_per_rad": float(self.bp.stiffness[e]),
                    "breakaway_ratio": float(self.bp.breakaway_ratio[e]), "nut_factor": float(self.bp.nut_factor[e]),
                    "theta0_rad": float(self.theta0[e])},
                "vel_limit_violation_steps": int(self.vel_violation_steps[e]),
                "duration_s": float(self.episode_length_buf[e]) * self.step_dt,
            })
            self.completed_episodes.append(rec)
        log = self.extras.setdefault("log", {})
        for i, s in enumerate(self.stages):
            log[f"Stage/{s}"] = (self.stage_time[env_ids, i] >= 0).float().mean()

    def _start_episodes(self, env_ids: torch.Tensor) -> torch.Tensor:
        """Give the episodes starting now their indices; return their draws (eval/splits.py), one row each."""
        first, self._episodes_started = self._episodes_started, self._episodes_started + len(env_ids)
        self.episode_index[env_ids] = torch.arange(first, self._episodes_started, device=self.device)
        ticks = self.max_episode_length
        draws = episode_draws(self.cfg.seed or 0, range(first, self._episodes_started), 12 + 6 * ticks)
        # sensor noise for every tick of the episode, standard normal, from the draws after the first twelve
        normal = 2**0.5 * torch.erfinv(2 * torch.as_tensor(draws[:, 12:]).clamp(1e-12, 1 - 1e-12) - 1)
        self._wrench_noise[env_ids] = normal.reshape(-1, ticks, 6).to(self.device, torch.float32)
        return torch.as_tensor(draws[:, :12], dtype=torch.float32, device=self.device)

    def _work_orders(self, env_ids: torch.Tensor) -> None:
        """Write the work order of the episodes starting now, with this task's own thresholds and site."""
        c = self.cfg
        rp, rq = self._root()
        head_w, axis_w = self.head_top_w()
        head, axis = quat_apply_inverse(rq, head_w - rp).tolist(), quat_apply_inverse(rq, axis_w).tolist()
        loose = [-math.degrees(angle) for angle in c.start_theta_tighten_range]
        values = dict(
            loose_min_deg=min(loose), loose_max_deg=max(loose), installed_min=c.tau_install_range[0],
            installed_max=c.tau_install_range[1], engage_depth_mm=1e3 * c.engage_depth,
            engage_lateral_mm=1e3 * c.engage_lateral, engage_angle_deg=c.engage_angle_deg, torque_min=c.tau_spec_min,
            torque_max=c.tau_spec_max, backoff_turns=c.backoff_angle / (2 * math.pi),
            released_mm=1e3 * c.released_distance, time_limit_s=c.episode_length_s)
        for e in env_ids.tolist():
            names = ("head_x", "head_y", "head_z", "axis_x", "axis_y", "axis_z")
            site = dict(zip(names, head[e] + axis[e], strict=True))
            self.prompts[e] = prompts.work_order(self.spec.id, **values, **site)

    def _sample_episode(self, env_ids: torch.Tensor, u: torch.Tensor) -> None:
        """Per-episode bolt variation within the assumed ranges (installed torque, stack stiffness, thread friction).

        Each parameter reads its own column of ``u``; columns 6 to 11 are the arm's starting offset.
        """
        c, b = self.cfg, self.bp

        def between(bounds, column):
            return bounds[0] + (bounds[1] - bounds[0]) * u[:, column]

        b.tau_run[env_ids] = between(c.running_torque_range, 0)
        b.stiffness[env_ids] = (c.tau_install - b.tau_run[env_ids]) / between(c.snug_to_spec_angle_range, 1)
        b.breakaway_ratio[env_ids] = between(c.breakaway_ratio_range, 2)
        b.nut_factor[env_ids] = between(c.nut_factor_range, 3)
        if c.mode == "loosen":
            self.tau_install[env_ids] = between(c.tau_install_range, 4)
            self.theta0[env_ids] = (self.tau_install[env_ids] - b.tau_run[env_ids]) / b.stiffness[env_ids]
        else:  # loose start; the angle also sets the hex phase the socket has to find
            self.theta0[env_ids] = between(c.start_theta_tighten_range, 5)

    def _reset_idx(self, env_ids: Sequence[int] | None) -> None:
        if env_ids is None:
            env_ids = torch.arange(self.num_envs, device=self.device)
        env_ids = torch.as_tensor(env_ids, device=self.device)
        self._record(env_ids)
        super()._reset_idx(env_ids)
        u = self._start_episodes(env_ids)
        self._sample_episode(env_ids, u)
        q = self.robot.data.default_joint_pos.torch[env_ids].clone()
        q[:, self.arm_ids] += (2 * u[:, 6:12] - 1) * self.cfg.arm_init_noise
        self.robot.write_joint_position_to_sim_index(position=q, env_ids=env_ids)
        self.robot.write_joint_velocity_to_sim_index(velocity=torch.zeros_like(q), env_ids=env_ids)
        qc = self.clamp.data.default_joint_pos.torch[env_ids].clone()
        qc[:, self.bolt_joint] = -self.theta0[env_ids]
        self.clamp.write_joint_position_to_sim_index(position=qc, env_ids=env_ids)
        self.clamp.write_joint_velocity_to_sim_index(velocity=torch.zeros_like(qc), env_ids=env_ids)
        self.theta_ref[env_ids] = self.theta0[env_ids]
        self.theta[env_ids] = self.theta0[env_ids]
        self._reaction_sum[env_ids] = 0.0
        self._untouched[env_ids] = True
        self._work_orders(env_ids)
        for buf, v in ((self.stage_time, -1.0), (self.peak_tau, 0.0), (self.vel_violation_steps, 0.0),
                       (self.actions, 0.0), (self.prev_actions, 0.0)):
            buf[env_ids] = v
        for buf in (self.over_torque, self.sim_error, self._rewarded):
            buf[env_ids] = False
        self.ik.reset(env_ids)
        p, q_ = self.tcp_pose_b()
        self.tgt_pos_b[env_ids], self.tgt_quat_b[env_ids] = p[env_ids], q_[env_ids]
        self.arm_q_des[env_ids] = self.robot.data.default_joint_pos.torch[env_ids][:, self.arm_ids]
