"""T2 environment: MC4 disconnect + reconnect with a torque-limited humanoid hand.

Stages (scored by :mod:`solarbench.eval.stats`, not by the reward):
    grasped -> unlocked -> separated -> realigned -> relatched -> released
Success requires all stages; *safe success* additionally requires zero damage events
(latch broken, cable over-pull) during the episode.
"""

from __future__ import annotations

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

from solarbench.eval.splits import episode_draws
from solarbench.specs import MC4
from solarbench.tasks.latch import LatchParams, LatchState, latch_step

from .mc4_env_cfg import LAYOUT

if TYPE_CHECKING:
    from .mc4_env_cfg import MC4EnvCfg

STAGES = ("grasped", "unlocked", "separated", "realigned", "relatched", "released")


class MC4Env(DirectRLEnv):
    cfg: MC4EnvCfg

    def __init__(self, cfg: MC4EnvCfg, render_mode: str | None = None, **kwargs):
        super().__init__(cfg, render_mode, **kwargs)
        self.robot, self.female = self.scene["robot"], self.scene["female"]
        self.stages = STAGES
        self.sensors = {k: self.scene[f"contact_{k}"] for k in ("thumb", "fingers", "palm")}
        dev, n = self.device, self.num_envs

        self.arm_ids = torch.tensor(self.robot.find_joints(list(cfg.arm_joints), preserve_order=True)[0], device=dev)
        hand_ids, hand_names = self.robot.find_joints("right_hand_.*_joint")
        self.hand_ids = torch.tensor(hand_ids, device=dev)
        self.hand_open = self._hand_vector(cfg.hand_open, hand_names)
        self.hand_closed = self._hand_vector(cfg.hand_closed, hand_names)
        self.ee_idx = self.robot.find_bodies(cfg.ee_body)[0][0]
        self.jac_idx = self.ee_idx - 1 if self.robot.is_fixed_base else self.ee_idx
        self.jac_cols = self.arm_ids + self.robot.num_base_dofs
        self.ik = DifferentialIKController(
            DifferentialIKControllerCfg(
                command_type="pose", use_relative_mode=False, ik_method="dls", ik_params={"lambda_val": cfg.ik_damping}
            ),
            num_envs=n,
            device=dev,
        )
        self.grasp_offset = torch.tensor(cfg.grasp_offset, device=dev).repeat(n, 1)
        self.arm_limits = self.robot.data.soft_joint_pos_limits.torch[0, self.arm_ids]
        self.arm_vel_limits = self.robot.data.joint_vel_limits.torch[0, self.arm_ids]

        # fixed connector geometry (env frame -> world via env origins)
        o = self.scene.env_origins
        self.mouth_w = o + torch.tensor(LAYOUT.male_pose().pos, device=dev, dtype=torch.float32)
        self.axis_w = torch.tensor(LAYOUT.connector_axis(), device=dev, dtype=torch.float32).repeat(n, 1)
        self.conn_quat_w = torch.tensor(LAYOUT.male_pose().rot, device=dev, dtype=torch.float32).repeat(n, 1)
        self.anchor_w = o + torch.tensor(LAYOUT.female_tie(), device=dev, dtype=torch.float32)  # last cable tie
        body_len = float(MC4.housing_length)
        self.cable_exit_b = torch.tensor((body_len + float(MC4.cable_stub_length), 0.0, 0.0), device=dev).repeat(n, 1)
        # Grasp site 36 mm out from the mouth when seated: Dex3 index/middle sit +/-28.5 mm along the connector
        # axis, so a centred grasp would put a fingertip inside the male sleeve's footprint.
        self.grasp_site_b = torch.tensor((cfg.grasp_site_local_x, 0.0, 0.0), device=dev).repeat(n, 1)

        self.latch = LatchState(n, dev)
        self.latch_params = LatchParams(cfg.gate_depth, cfg.latch_depth, cfg.seated_depth)

        # controller targets (robot base frame, grasp point)
        self.tgt_pos_b = torch.zeros(n, 3, device=dev)
        self.tgt_quat_b = torch.zeros(n, 4, device=dev)
        self.arm_q_des = torch.zeros(n, len(self.arm_ids), device=dev)
        self.hand_q_des = self.hand_open.clone()
        self.unlock_cmd = torch.zeros(n, dtype=torch.bool, device=dev)
        self.prev_actions = torch.zeros(n, cfg.action_space, device=dev)

        # per-step measurements
        self.depth = torch.zeros(n, device=dev)
        self.f_hand_w = torch.zeros(n, 3, device=dev)
        self.grasped = torch.zeros(n, dtype=torch.bool, device=dev)
        self.grasp_score = torch.zeros(n, device=dev)
        self.cable_tension = torch.zeros(n, device=dev)
        self._lateral = torch.zeros(n, device=dev)
        self._hand_dist = torch.ones(n, device=dev)

        # episode bookkeeping
        self.stage_time = torch.full((n, len(STAGES)), -1.0, device=dev)
        self.peak = {k: torch.zeros(n, device=dev) for k in ("hand_force", "cable_tension", "push_force")}
        self.cable_overpull = torch.zeros(n, dtype=torch.bool, device=dev)
        self.sim_error = torch.zeros(n, dtype=torch.bool, device=dev)
        self.vel_violation_steps = torch.zeros(n, device=dev)
        self.episode_index = torch.zeros(n, dtype=torch.long, device=dev)
        self._episodes_started = 0
        self.completed_episodes: list[dict] = []
        self._rewarded = torch.zeros(n, len(STAGES), dtype=torch.bool, device=dev)
        self._cables = self._init_cable_drawing() if cfg.show_cables else None

    # ------------------------------------------------------------------ render-only cables (env 0)
    def _init_cable_drawing(self):
        import isaaclab.sim as sim_utils
        import numpy as np
        from isaaclab.markers import VisualizationMarkers, VisualizationMarkersCfg

        from solarbench.render.cable import polyline_segments, sagging_curve

        o = self.scene.env_origins[0].cpu().numpy()
        fem = [p + o for p in LAYOUT.female_lead_static()]
        male = [p + o for p in LAYOUT.male_lead_static()]
        hang = sagging_curve(male[0], -LAYOUT.connector_axis(), male[1], -np.array([1.0, 0, 0]), 0.16, n=10)
        static = [polyline_segments(np.array(fem)), polyline_segments(hang), polyline_segments(np.array(male[1:]))]
        markers = VisualizationMarkers(VisualizationMarkersCfg(prim_path="/Visuals/Cables", markers={
            "cable": sim_utils.CylinderCfg(radius=float(MC4.cable_od) / 2, height=1.0, visual_material=(
                sim_utils.PreviewSurfaceCfg(diffuse_color=(0.02, 0.02, 0.022), roughness=0.6)))}))
        tie_dir = fem[-1] - fem[-2]
        return dict(markers=markers, static=static, tie=fem[-1], tie_dir=tie_dir / np.linalg.norm(tie_dir),
                    curve=sagging_curve, segs=polyline_segments)

    def _draw_cables(self) -> None:
        import numpy as np

        c = self._cables
        pos, quat = self.female.data.root_pos_w.torch[0], self.female.data.root_quat_w.torch[0]
        exit_w = (pos + quat_apply(quat[None], self.cable_exit_b[:1])[0]).cpu().numpy()
        d0 = quat_apply(quat[None], torch.tensor([[1.0, 0.0, 0.0]], device=self.device))[0].cpu().numpy()
        tail = c["curve"](exit_w, d0, c["tie"], c["tie_dir"], self.cfg.tether_length, n=24)
        parts = [*c["static"], c["segs"](tail)]
        ctr = np.concatenate([p[0] for p in parts])
        q = np.concatenate([p[1] for p in parts])
        ln = np.concatenate([p[2] for p in parts])
        sc = np.stack([np.ones_like(ln), np.ones_like(ln), ln], axis=1)
        c["markers"].visualize(translations=torch.tensor(ctr, dtype=torch.float32),
                               orientations=torch.tensor(q, dtype=torch.float32),
                               scales=torch.tensor(sc, dtype=torch.float32))

    # ------------------------------------------------------------------ helpers
    def _hand_vector(self, spec: dict, names: list[str]) -> torch.Tensor:
        import re

        v = torch.zeros(len(names), device=self.device)
        for pattern, value in spec.items():
            for i, nm in enumerate(names):
                if re.fullmatch(pattern, nm):
                    v[i] = value
        return v.repeat(self.num_envs, 1)

    def _root(self):
        return self.robot.data.root_pos_w.torch, self.robot.data.root_quat_w.torch

    def grasp_pose_b(self) -> tuple[torch.Tensor, torch.Tensor]:
        """Grasp point (palm + offset) pose in the robot base frame."""
        pose = self.robot.data.body_pose_w.torch[:, self.ee_idx]
        g_pos_w, g_quat_w = combine_frame_transforms(pose[:, :3], pose[:, 3:], self.grasp_offset)
        rp, rq = self._root()
        return subtract_frame_transforms(rp, rq, g_pos_w, g_quat_w)

    def female_site_w(self) -> tuple[torch.Tensor, torch.Tensor]:
        pos, quat = self.female.data.root_pos_w.torch, self.female.data.root_quat_w.torch
        return pos + quat_apply(quat, self.grasp_site_b), quat

    def _measure(self) -> None:
        tip = self.female.data.root_pos_w.torch
        self.depth = torch.sum((self.mouth_w - tip) * self.axis_w, dim=-1)
        f = {}
        for k, s in self.sensors.items():
            fm = s.data.force_matrix_w
            f[k] = fm.torch.sum(dim=(1, 2)) if fm is not None else torch.zeros(self.num_envs, 3, device=self.device)
        # force exerted *by the hand on the housing* (sensor reports force on the sensor body)
        self.f_hand_w = f["thumb"] + f["fingers"] + f["palm"]
        thr = self.cfg.grasp_force_threshold
        # Opposed contact: fingers against the thumb (pinch) or against the palm (power grasp).
        fingers = f["fingers"].norm(dim=-1) > thr
        opposed = (fingers & ((f["thumb"].norm(dim=-1) > thr) | (f["palm"].norm(dim=-1) > thr))).float()
        # Contacts against a rigidly latched housing chatter step to step; filter like a real tactile signal.
        alpha = self.physics_dt / (self.cfg.grasp_filter_tau + self.physics_dt)
        self.grasp_score += alpha * (opposed - self.grasp_score)
        self.grasped = self.grasp_score > 0.5

    # ------------------------------------------------------------------ actions
    def _pre_physics_step(self, actions: torch.Tensor) -> None:
        a = actions.clamp(-1.0, 1.0)
        self.prev_actions[:] = self.actions
        self.actions[:] = a
        d_pos = a[:, :3] * self.cfg.max_ee_step
        d_rot = a[:, 3:6] * self.cfg.max_rot_step
        self.tgt_pos_b += d_pos
        ang = d_rot.norm(dim=-1)
        axis = torch.where(
            ang[:, None] > 1e-9, d_rot / ang.clamp(min=1e-9)[:, None], torch.tensor([1.0, 0, 0], device=self.device)
        )
        self.tgt_quat_b = quat_mul(quat_from_angle_axis(ang, axis), self.tgt_quat_b)
        # keep targets within 5 cm of the current grasp point (no wind-up against obstacles)
        cur_pos, _ = self.grasp_pose_b()
        delta = self.tgt_pos_b - cur_pos
        self.tgt_pos_b = cur_pos + delta * (0.05 / delta.norm(dim=-1, keepdim=True).clamp(min=0.05))
        self._solve_ik()
        w = (a[:, 6:7] + 1.0) / 2.0
        self.hand_q_des = self.hand_open + w * (self.hand_closed - self.hand_open)
        self.unlock_cmd = a[:, 7] > 0.0

    def _solve_ik(self) -> None:
        # palm target from grasp target (offset is a pure translation in the palm frame)
        palm_pos_b = self.tgt_pos_b - quat_apply(self.tgt_quat_b, self.grasp_offset)
        self.ik.set_command(torch.cat([palm_pos_b, self.tgt_quat_b], dim=-1))
        rp, rq = self._root()
        pose = self.robot.data.body_pose_w.torch[:, self.ee_idx]
        ee_pos_b, ee_quat_b = subtract_frame_transforms(rp, rq, pose[:, :3], pose[:, 3:])
        jac_w = self.robot.data.body_link_jacobian_w.torch[:, self.jac_idx, :, :][:, :, self.jac_cols]
        r_bw = matrix_from_quat(quat_inv(rq))  # world -> base rotation
        jac_b = torch.cat([r_bw @ jac_w[:, :3], r_bw @ jac_w[:, 3:]], dim=1)
        q = self.robot.data.joint_pos.torch[:, self.arm_ids]
        # Integral IK: step from the previous joint target, not the measured joints, so gravity sag does not
        # leave a steady-state error under PD control. Anti-windup keeps the target within ik_windup of the
        # measured joints, which also bounds the effort the arm applies against obstacles (still torque-limited).
        dq = self.ik.compute(ee_pos_b, ee_quat_b, jac_b, q) - q
        q_des = self.arm_q_des + dq
        q_des = torch.clamp(q_des, q - self.cfg.ik_windup, q + self.cfg.ik_windup)
        self.arm_q_des = q_des.clamp(self.arm_limits[:, 0], self.arm_limits[:, 1])

    def _apply_action(self) -> None:
        tc = self.robot.actuators.target_command
        tc.set_position_index(value=self.arm_q_des, joint_ids=self.arm_ids)
        tc.set_position_index(value=self.hand_q_des, joint_ids=self.hand_ids)
        self._connector_physics()

    def _connector_physics(self) -> None:
        """Latch projection + cable tether, once per physics step (see solarbench.tasks.latch)."""
        self._measure()
        f_axial = torch.sum(self.f_hand_w * self.axis_w, dim=-1)  # +: pulls out (towards the robot)
        push, pull = (-f_axial).clamp(min=0.0), f_axial.clamp(min=0.0)
        dmax, dmin = latch_step(
            self.latch, self.latch_params, self.depth, push, pull, self.grasped, self.unlock_cmd, self.physics_dt
        )
        target = torch.minimum(torch.maximum(self.depth, dmin), dmax)
        fix = (target - self.depth).abs() > 1e-6
        if fix.any():
            ids = fix.nonzero(as_tuple=False).squeeze(-1)
            pose = torch.cat([self.female.data.root_pos_w.torch, self.female.data.root_quat_w.torch], dim=-1)[ids]
            pose[:, :3] -= ((target - self.depth)[ids, None]) * self.axis_w[ids]
            vel = self.female.data.root_vel_w.torch[ids].clone()
            v_ax = torch.sum(vel[:, :3] * self.axis_w[ids], dim=-1, keepdim=True)
            vel[:, :3] -= v_ax * self.axis_w[ids]  # remove axial velocity into the violated bound
            self.female.write_root_pose_to_sim_index(root_pose=pose, env_ids=ids)
            self.female.write_root_velocity_to_sim_index(root_velocity=vel, env_ids=ids)
        self.peak["push_force"] = torch.maximum(self.peak["push_force"], push)

        # cable: tension-only spring between junction box exit and the housing's cable exit
        pos, quat = self.female.data.root_pos_w.torch, self.female.data.root_quat_w.torch
        exit_w = pos + quat_apply(quat, self.cable_exit_b)
        d = self.anchor_w - exit_w
        dist = d.norm(dim=-1).clamp(min=1e-6)
        u = d / dist[:, None]
        v_exit = self.female.data.root_lin_vel_w.torch
        stretch = (dist - self.cfg.tether_length).clamp(min=0.0)
        tension = (
            self.cfg.tether_stiffness * stretch
            - self.cfg.tether_damping * torch.sum(v_exit * u, dim=-1) * (stretch > 0)
        ).clamp(min=0.0)
        self.cable_tension = tension
        self.female.instantaneous_wrench_composer.add_forces_and_torques_index(
            forces=(tension[:, None] * u)[:, None, :], positions=exit_w[:, None, :], body_ids=[0], is_global=True
        )

    # ------------------------------------------------------------------ MDP
    def _get_observations(self) -> dict:
        if self._cables is not None:
            self._draw_cables()
        rp, rq = self._root()
        g_pos, g_quat = self.grasp_pose_b()
        f_pos_w, f_quat_w = self.female_site_w()
        f_pos_b, f_quat_b = subtract_frame_transforms(rp, rq, f_pos_w, f_quat_w)
        mouth_b, _ = subtract_frame_transforms(rp, rq, self.mouth_w)
        axis_b = quat_apply_inverse(rq, self.axis_w)
        f_hand_b = quat_apply_inverse(rq, self.f_hand_w)
        jp = self.robot.data.joint_pos.torch
        jv = self.robot.data.joint_vel.torch
        flags = torch.stack([self.latch.latched, self.latch.open, self.grasped], dim=-1).float()
        obs = torch.cat(
            [
                jp[:, self.arm_ids],
                0.1 * jv[:, self.arm_ids],
                jp[:, self.hand_ids],  # 21
                g_pos,
                g_quat,  # 7
                f_pos_b - g_pos,
                f_quat_b,  # 7
                mouth_b - g_pos,
                axis_b,  # 6
                self.depth[:, None] * 50.0,
                flags,
                (self.latch.unlock_timer / 0.2)[:, None],  # 5
                0.02 * f_hand_b,
                0.02 * self.cable_tension[:, None],  # 4
                self.actions,  # 8
            ],
            dim=-1,
        )
        return {"policy": torch.nan_to_num(obs).clamp(-20.0, 20.0)}

    def _update_stages(self) -> None:
        t = (self.episode_length_buf.float() + 1) * self.step_dt
        f_pos_w, _ = self.female_site_w()
        tip = self.female.data.root_pos_w.torch
        rel = tip - self.mouth_w
        lateral = (rel - torch.sum(rel * self.axis_w, -1, keepdim=True) * self.axis_w).norm(dim=-1)
        g_pos_b, _ = self.grasp_pose_b()
        rp, rq = self._root()
        g_pos_w = rp + quat_apply(rq, g_pos_b)
        hand_dist = (g_pos_w - f_pos_w).norm(dim=-1)
        st = self.stage_time
        reached = st >= 0
        cond = [
            self.grasped,
            reached[:, 0] & ~self.latch.latched,
            reached[:, 1] & (self.depth < -self.cfg.separated_distance),
            reached[:, 2] & (lateral < 0.0015) & (self.depth > 0.0),
            reached[:, 3] & self.latch.latched,
            reached[:, 4] & ~self.grasped & (hand_dist > self.cfg.released_distance),
        ]
        for i, c in enumerate(cond):
            st[:, i] = torch.where(c & ~reached[:, i], t, st[:, i])
        self.cable_overpull |= torch.nan_to_num(self.cable_tension, nan=0.0) > float(MC4.max_cable_pull)
        self.peak["hand_force"] = torch.maximum(self.peak["hand_force"], self.f_hand_w.norm(dim=-1))
        self.peak["cable_tension"] = torch.maximum(self.peak["cable_tension"], self.cable_tension)
        qd = self.robot.data.joint_vel.torch[:, self.arm_ids].abs()
        self.vel_violation_steps += (qd > self.arm_vel_limits).any(dim=-1).float()
        self._lateral, self._hand_dist = lateral, hand_dist

    def _get_rewards(self) -> torch.Tensor:
        self._update_stages()
        reached = self.stage_time >= 0
        new = reached & ~self._rewarded
        self._rewarded |= reached
        c = self.cfg
        r = c.rew_reach * torch.exp(-self._hand_dist / 0.05) * (~reached[:, 2])
        bonus = torch.tensor(
            [c.rew_grasp, c.rew_unlock, c.rew_separate, c.rew_align, c.rew_latch, c.rew_latch], device=self.device
        )
        r += (new.float() * bonus).sum(dim=-1)
        r += c.rew_separate * reached[:, 1] * (~reached[:, 2]) * (-self.depth).clamp(0, 0.02) / 0.02 * 0.1
        r += c.rew_align * reached[:, 2] * (~reached[:, 4]) * torch.exp(-self._lateral / 0.003) * 0.1
        r += c.rew_insert * reached[:, 2] * (~reached[:, 4]) * self.depth.clamp(0, c.latch_depth) / c.latch_depth * 0.1
        r += c.rew_action_rate * torch.sum((self.actions - self.prev_actions) ** 2, dim=-1)
        r += c.rew_damage * (self.latch.broken | self.cable_overpull).float()
        # Simulator failures (non-finite state, flagged in _get_dones) carry no learning signal.
        return torch.where(self.sim_error, torch.zeros_like(r), torch.nan_to_num(r, nan=0.0, posinf=0.0, neginf=0.0))

    def _get_dones(self) -> tuple[torch.Tensor, torch.Tensor]:
        success = self.stage_time[:, -1] >= 0
        damaged = self.latch.broken
        # Non-finite physics state is a simulator failure, reported separately and never scored as damage.
        state = torch.cat([self.female.data.root_pos_w.torch, self.robot.data.joint_pos.torch], dim=-1)
        self.sim_error |= ~torch.isfinite(state).all(dim=-1)
        return success | damaged | self.sim_error, self.episode_length_buf >= self.max_episode_length - 1

    # ------------------------------------------------------------------ reset
    def _record_episodes(self, env_ids: torch.Tensor) -> None:
        if self.common_step_counter == 0:
            return
        st = self.stage_time[env_ids].cpu()
        dmg = (self.latch.broken | self.cable_overpull)[env_ids].cpu()
        for k, e in enumerate(env_ids.tolist()):
            rec = {f"t_{s}": float(st[k, i]) for i, s in enumerate(STAGES)}
            rec.update({f"stage_{s}": bool(st[k, i] >= 0) for i, s in enumerate(STAGES)})
            rec.update(
                {
                    "env_id": e,
                    "episode": int(self.episode_index[e]),
                    "sim_error": bool(self.sim_error[e]),
                    "success": bool(st[k, -1] >= 0),
                    "damage": bool(dmg[k]),
                    "latch_broken": bool(self.latch.broken[e]),
                    "cable_overpull": bool(self.cable_overpull[e]),
                    "safe_success": bool(st[k, -1] >= 0 and not dmg[k]),
                    "peak_hand_force_N": float(self.peak["hand_force"][e]),
                    "peak_push_force_N": float(self.peak["push_force"][e]),
                    "peak_cable_tension_N": float(self.peak["cable_tension"][e]),
                    "vel_limit_violation_steps": int(self.vel_violation_steps[e]),
                    "insertion_force_N": float(self.latch.insertion_force[e]),
                    "duration_s": float(self.episode_length_buf[e]) * self.step_dt,
                }
            )
            self.completed_episodes.append(rec)
        log = self.extras.setdefault("log", {})
        for i, s in enumerate(STAGES):
            log[f"Stage/{s}"] = (self.stage_time[env_ids, i] >= 0).float().mean()
        log["Metrics/damage_rate"] = dmg.float().mean()
        log["Metrics/sim_error_rate"] = self.sim_error[env_ids].float().mean()

    def _reset_idx(self, env_ids: Sequence[int] | None) -> None:
        if env_ids is None:
            env_ids = torch.arange(self.num_envs, device=self.device)
        env_ids = torch.as_tensor(env_ids, device=self.device)
        self._record_episodes(env_ids)
        super()._reset_idx(env_ids)
        k = len(env_ids)

        q = self.robot.data.default_joint_pos.torch[env_ids].clone()
        self.robot.write_joint_position_to_sim_index(position=q, env_ids=env_ids)
        self.robot.write_joint_velocity_to_sim_index(velocity=torch.zeros_like(q), env_ids=env_ids)

        fp = torch.tensor(LAYOUT.female_pose(self.cfg.seated_depth).pos, device=self.device, dtype=torch.float32)
        pose = torch.cat([self.scene.env_origins[env_ids] + fp, self.conn_quat_w[env_ids]], dim=-1)
        self.female.write_root_pose_to_sim_index(root_pose=pose, env_ids=env_ids)
        self.female.write_root_velocity_to_sim_index(
            root_velocity=torch.zeros(k, 6, device=self.device), env_ids=env_ids
        )
        # Each episode's latch forces depend on the seed and the episode's index alone (eval/splits.py).
        first, self._episodes_started = self._episodes_started, self._episodes_started + k
        self.episode_index[env_ids] = torch.arange(first, self._episodes_started, device=self.device)
        draws = episode_draws(self.cfg.seed or 0, range(first, self._episodes_started), 2)
        u = torch.as_tensor(draws, dtype=torch.float32, device=self.device)
        lo, hi = self.cfg.insertion_force_range
        f_ins = lo + (hi - lo) * u[:, 0]
        lo, hi = self.cfg.withdrawal_force_range
        f_wd = lo + (hi - lo) * u[:, 1]
        self.latch.reset(env_ids, torch.ones(k, dtype=torch.bool, device=self.device), f_ins, f_wd)

        self.stage_time[env_ids] = -1.0
        self._rewarded[env_ids] = False
        for v in self.peak.values():
            v[env_ids] = 0.0
        self.cable_overpull[env_ids] = False
        self.sim_error[env_ids] = False
        self.vel_violation_steps[env_ids] = 0.0
        self.actions[env_ids] = 0.0
        self.prev_actions[env_ids] = 0.0
        self.hand_q_des[env_ids] = self.hand_open[env_ids]
        self.unlock_cmd[env_ids] = False
        self.grasp_score[env_ids] = 0.0
        self.ik.reset(env_ids)
        self._reset_targets(env_ids)

    def _reset_targets(self, env_ids: torch.Tensor) -> None:
        """Targets start at the current (default-pose) grasp point; arm targets at the default joints."""
        g_pos, g_quat = self.grasp_pose_b()
        self.tgt_pos_b[env_ids] = g_pos[env_ids]
        self.tgt_quat_b[env_ids] = g_quat[env_ids]
        self.arm_q_des[env_ids] = self.robot.data.default_joint_pos.torch[env_ids][:, self.arm_ids]
