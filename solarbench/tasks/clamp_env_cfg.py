"""T3: tighten / loosen a module clamp bolt with a UR16e + socket tool on a parked Husky A300."""

from __future__ import annotations

import isaaclab.sim as sim_utils
from isaaclab.actuators import ImplicitActuatorCfg
from isaaclab.assets import ArticulationCfg, AssetBaseCfg, RigidObjectCfg
from isaaclab.envs import DirectRLEnvCfg
from isaaclab.scene import InteractiveSceneCfg
from isaaclab.sensors import JointWrenchSensorCfg
from isaaclab.sim import RigidBodyMaterialCfg, SimulationCfg
from isaaclab.utils import configclass
from isaaclab.visualizers import VisualizerCfg
from isaaclab_newton.physics import MJWarpSolverCfg, NewtonCfg, NewtonCollisionPipelineCfg
from isaaclab_newton.sim.schemas import MujocoCollisionCfg
from isaaclab_ov.physics import OvPhysxCfg
from isaaclab_tasks.utils import PresetCfg

from solarbench.specs import FRICTION, LONGI_LR7_72HVD, TABLE_DEFAULT
from solarbench.specs.params import BOLT
from solarbench.specs.robots import (
    UR16E_FT_FORCE_PRECISION,
    UR16E_FT_FORCE_RANGE,
    UR16E_FT_TORQUE_PRECISION,
    UR16E_FT_TORQUE_RANGE,
)
from solarbench.tasks.layout import ASSET_ROOT, LowMountLayout, asset_usd
from solarbench.tasks.robots import ur16e_socket_cfg

LAYOUT = LowMountLayout(TABLE_DEFAULT, LONGI_LR7_72HVD)
_HUSKY, _ARM = LAYOUT.husky_and_arm_pose()
_CLAMP = LAYOUT.end_clamp_pose()
_kinematic = sim_utils.UsdPhysicsRigidBodyCfg(kinematic_enabled=True)


def _module(i: int, name: str) -> RigidObjectCfg:
    pose = LAYOUT.module_pose(i)
    return RigidObjectCfg(prim_path=f"{{ENV_REGEX_NS}}/{name}",
                          spawn=sim_utils.UsdFileCfg(usd_path=asset_usd(LONGI_LR7_72HVD.name), rigid_props=_kinematic),
                          init_state=RigidObjectCfg.InitialStateCfg(pos=pose.pos, rot=pose.rot))


@configclass
class ClampSceneCfg(InteractiveSceneCfg):
    ground = AssetBaseCfg(prim_path="/World/ground", spawn=sim_utils.GroundPlaneCfg(
        physics_material=RigidBodyMaterialCfg(static_friction=float(FRICTION.ground_gravel),
                                              dynamic_friction=float(FRICTION.ground_gravel))))
    light = AssetBaseCfg(prim_path="/World/light", spawn=sim_utils.DomeLightCfg(intensity=2500.0))
    table = RigidObjectCfg(prim_path="{ENV_REGEX_NS}/Table", spawn=sim_utils.UsdFileCfg(
        usd_path=asset_usd("fixed_tilt_table_1p"), rigid_props=_kinematic))
    module_0 = _module(0, "Module0")
    module_1 = _module(1, "Module1")
    module_2 = _module(2, "Module2")
    clamp = ArticulationCfg(
        prim_path="{ENV_REGEX_NS}/Clamp",
        spawn=sim_utils.UsdFileCfg(usd_path=asset_usd("end_clamp_m8"), fix_root_link=True, collision_props=[
            sim_utils.UsdPhysicsCollisionCfg(),
            # stiff socket-on-head contact (ASSUMPTIONS P23)
            MujocoCollisionCfg(solref=(0.004, 1.0), solimp=(0.99, 0.999, 0.0002, 0.5, 2.0), priority=1)]),
        init_state=ArticulationCfg.InitialStateCfg(pos=_CLAMP.pos, rot=_CLAMP.rot, joint_pos={"bolt_joint": 0.0}),
        # passive joint; armature = reflected drive inertia scale, keeps the friction constraint stiff (P21)
        actuators={"bolt": ImplicitActuatorCfg(joint_names_expr=["bolt_joint"], stiffness=0.0, damping=1e-3,
                                               armature=0.05, joint_effort_limit=1000.0)},
    )
    husky = RigidObjectCfg(prim_path="{ENV_REGEX_NS}/Husky", spawn=sim_utils.UsdFileCfg(
        usd_path=asset_usd("husky_a300_parked"), rigid_props=_kinematic),
        init_state=RigidObjectCfg.InitialStateCfg(pos=_HUSKY.pos, rot=_HUSKY.rot))
    robot: ArticulationCfg = ur16e_socket_cfg(pos=_ARM.pos)
    # reaction wrench at every joint of the arm; the task reads the one that holds the tool (ASSUMPTIONS M12)
    flange = JointWrenchSensorCfg(prim_path="{ENV_REGEX_NS}/Robot")
    scenery: AssetBaseCfg | None = None

    def __post_init__(self):
        self.robot.init_state.rot = _ARM.rot


@configclass
class ClampSimCfg(PresetCfg):
    newton_mjwarp: SimulationCfg = SimulationCfg(
        dt=1 / 600, render_interval=20, use_newton_actuators=False,  # bolt projection runs every substep (H5)
        default_visualizer_cfg=VisualizerCfg(eye=(2.45, -0.55, 1.35), lookat=(1.73, 0.47, 0.80)),
        physics=NewtonCfg(solver_cfg=MJWarpSolverCfg(
            solver="newton", integrator="implicitfast", cone="elliptic", impratio=10.0, iterations=100,
            ls_iterations=50, njmax=600, nconmax=300, use_mujoco_contacts=False),
            collision_cfg=NewtonCollisionPipelineCfg(rigid_contact_max=20000), num_substeps=1),
    )
    ovphysx: SimulationCfg = SimulationCfg(dt=1 / 600, render_interval=20, use_newton_actuators=False,
                                           physics=OvPhysxCfg())
    default = newton_mjwarp


@configclass
class ClampEnvCfg(DirectRLEnvCfg):
    mode: str = "tighten"  # or "loosen"
    episode_length_s = 30.0  # roughly a technician's time per clamp
    decimation = 20
    action_space = 6  # R1: [d_pos(3), d_rot(3)] of the socket face frame
    observation_space = 35
    state_space = 0
    sim: ClampSimCfg = ClampSimCfg()
    scene: ClampSceneCfg = ClampSceneCfg(num_envs=16, env_spacing=8.0, replicate_physics=True)

    max_tcp_step: float = 0.006
    max_rot_step: float = 0.05
    ik_damping: float = 0.05
    ik_windup: float = 0.25
    arm_joints: tuple[str, ...] = ("shoulder_pan_joint", "shoulder_lift_joint", "elbow_joint", "wrist_1_joint",
                                   "wrist_2_joint", "wrist_3_joint")
    tool_body: str = "socket_tool"
    # wrist force-torque sensor: the one built into the UR16e flange (ASSUMPTIONS M12)
    wrench_force_range: float = float(UR16E_FT_FORCE_RANGE)
    wrench_torque_range: float = float(UR16E_FT_TORQUE_RANGE)
    wrench_force_noise: float = float(UR16E_FT_FORCE_PRECISION) / 3  # standard deviation per sample
    wrench_torque_noise: float = float(UR16E_FT_TORQUE_PRECISION) / 3
    tcp_offset: tuple[float, float, float] = (0.0, 0.0, 0.160)  # socket face on the tool axis (SOCKET_TOOL_LENGTH)
    head_top_offset: float = 0.0016 + float(BOLT.head_height)  # washer + head above the bolt link origin

    # bolt model (BoltSpec; module manual torque window)
    tau_spec_min: float = float(LONGI_LR7_72HVD.clamp_torque_min)
    tau_spec_max: float = float(LONGI_LR7_72HVD.clamp_torque_max)
    tau_install: float = 16.0  # nominal installation torque; defines the stack stiffness with snug_to_spec_angle
    start_theta_tighten: float = -3.14159  # half a turn loose (nominal)
    # per-episode variation (ASSUMPTIONS P22)
    tau_install_range: tuple[float, float] = (14.0, 18.0)  # loosen start: anywhere in the manual's window
    start_theta_tighten_range: tuple[float, float] = (-3.7, -2.6)  # +-30 deg about half a turn loose
    running_torque_range: tuple[float, float] = (0.5, 1.2)
    snug_to_spec_angle_range: tuple[float, float] = (0.35, 0.75)
    breakaway_ratio_range: tuple[float, float] = (0.8, 1.0)
    nut_factor_range: tuple[float, float] = (0.16, 0.24)
    arm_init_noise: float = 0.05  # rad, uniform per arm joint
    backoff_angle: float = 0.75 * 6.28319  # loosen success: 3/4 turn (wrist-3 range +-2 pi; ASSUMPTIONS M8)
    engage_lateral: float = 0.0012
    engage_angle_deg: float = 6.0
    engage_depth: float = 0.0025  # head >= 2.5 mm inside the socket (on the hex flats)
    released_distance: float = 0.03

    rew_reach: float = 1.0
    rew_engage: float = 5.0
    rew_progress: float = 3.0
    rew_success: float = 20.0
    rew_over_torque: float = -20.0
    rew_action_rate: float = -0.01

    def enable_scenery(self) -> None:
        self.scene.scenery = AssetBaseCfg(prim_path="/World/Scenery", spawn=sim_utils.UsdFileCfg(
            usd_path=str(ASSET_ROOT / "scenes/low_mount_site_row_end/low_mount_site_row_end.usda")))
        self.scene.ground.spawn.visible = False


@configclass
class ClampLoosenEnvCfg(ClampEnvCfg):
    mode: str = "loosen"
