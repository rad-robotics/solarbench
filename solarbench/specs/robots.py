"""Embodiment actuator limits for SolarBench, with provenance.

Isaac Lab's stock G1 configs override arm and hand effort limits to 300 N*m (ASSUMPTIONS E1). SolarBench
replaces them with the manufacturer URDF values below, which also match the drive ``maxForce`` authored in
the Isaac Sim ``g1.usd``. A task that a robot cannot do within these limits is a benchmark result.
"""

from __future__ import annotations

from .params import P

SRC_G1_URDF = (
    "unitreerobotics/unitree_ros@15ebe53 robots/g1_description/g1_29dof_with_hand_rev_1_0.urdf "
    "(BSD-3); identical to drive maxForce in Isaac Sim Robots/Unitree/G1/g1.usd"
)

G1_EFFORT = {
    # joint regex: P(effort limit N*m)
    ".*_shoulder_pitch_joint": P(25.0, "N*m", SRC_G1_URDF),
    ".*_shoulder_roll_joint": P(25.0, "N*m", SRC_G1_URDF),
    ".*_shoulder_yaw_joint": P(25.0, "N*m", SRC_G1_URDF),
    ".*_elbow_joint": P(25.0, "N*m", SRC_G1_URDF),
    ".*_wrist_roll_joint": P(25.0, "N*m", SRC_G1_URDF),
    ".*_wrist_pitch_joint": P(5.0, "N*m", SRC_G1_URDF),
    ".*_wrist_yaw_joint": P(5.0, "N*m", SRC_G1_URDF),
    ".*_hand_thumb_0_joint": P(2.45, "N*m", SRC_G1_URDF),
    ".*_hand_thumb_[12]_joint": P(1.4, "N*m", SRC_G1_URDF),
    ".*_hand_(index|middle)_[01]_joint": P(1.4, "N*m", SRC_G1_URDF),
}

G1_VELOCITY = {
    ".*_shoulder_.*_joint": P(37.0, "rad/s", SRC_G1_URDF),
    ".*_elbow_joint": P(37.0, "rad/s", SRC_G1_URDF),
    ".*_wrist_roll_joint": P(37.0, "rad/s", SRC_G1_URDF),
    ".*_wrist_(pitch|yaw)_joint": P(22.0, "rad/s", SRC_G1_URDF),
    ".*_hand_thumb_0_joint": P(3.14, "rad/s", SRC_G1_URDF),
    ".*_hand_(thumb_[12]|index_[01]|middle_[01])_joint": P(12.0, "rad/s", SRC_G1_URDF),
}

G1_STANDING_PELVIS_HEIGHT = P(0.75, "m", "isaaclab_assets G1_29DOF_CFG init_state", "CITED")

# --- Universal Robots UR16e (mobile-manipulator arm) -------------------------------------------------------------
SRC_UR16E = ("UniversalRobots/Universal_Robots_ROS2_Description@81f7c9fe config/ur16e/joint_limits.yaml (BSD-3); "
             "the Isaac Sim ur16e.usd authors 56 N*m on the wrists, we use UR's 54")
UR16E_EFFORT = {
    "shoulder_pan_joint": P(330.0, "N*m", SRC_UR16E),
    "shoulder_lift_joint": P(330.0, "N*m", SRC_UR16E),
    "elbow_joint": P(150.0, "N*m", SRC_UR16E),
    "wrist_1_joint": P(54.0, "N*m", SRC_UR16E),
    "wrist_2_joint": P(54.0, "N*m", SRC_UR16E),
    "wrist_3_joint": P(54.0, "N*m", SRC_UR16E),
}
UR16E_VELOCITY = {
    "shoulder_(pan|lift)_joint": P(2.094, "rad/s", SRC_UR16E, note="120 deg/s"),
    "elbow_joint": P(3.142, "rad/s", SRC_UR16E, note="180 deg/s"),
    "wrist_[123]_joint": P(3.142, "rad/s", SRC_UR16E, note="180 deg/s"),
}
UR16E_PAYLOAD = P(16.0, "kg", "https://www.universal-robots.com/products/ur16e/", note="includes the tool")
UR16E_FLANGE_D6 = P(0.1165, "m", SRC_UR16E, "DERIVED", "wrist_2 -> wrist_3 offset in ur16e.usd; flange at wrist_3")
# force-torque sensor built into the tool flange; the same range and precision on each axis
SRC_UR16E_FT = ("https://www.universal-robots.com/media/1819035/ur16e-tech-spec_tcn_202105.pdf, "
                "'Force sensing, tool flange/torque sensor'")
UR16E_FT_FORCE_RANGE = P(160.0, "N", SRC_UR16E_FT)
UR16E_FT_TORQUE_RANGE = P(10.0, "N*m", SRC_UR16E_FT)
UR16E_FT_FORCE_PRECISION = P(5.0, "N", SRC_UR16E_FT, note="the sheet does not say what precision means statistically")
UR16E_FT_TORQUE_PRECISION = P(0.2, "N*m", SRC_UR16E_FT)

# --- Clearpath Husky A300 (parked base in T3) -------------------------------------------------------------------
SRC_HUSKY = "https://clearpathrobotics.com/husky-spec-comparison/ (A300 column)"
HUSKY_A300_LENGTH = P(0.990, "m", SRC_HUSKY)
HUSKY_A300_WIDTH = P(0.698, "m", SRC_HUSKY)
HUSKY_A300_HEIGHT = P(0.372, "m", SRC_HUSKY)
HUSKY_A300_MASS = P(80.0, "kg", SRC_HUSKY)
HUSKY_A300_CLEARANCE = P(0.130, "m", SRC_HUSKY)
HUSKY_A300_PAYLOAD_ALL_TERRAIN = P(50.0, "kg", SRC_HUSKY)
HUSKY_A300_WHEEL_DIAMETER = P(0.330, "m", "none", "ASSUMED", "not on the spec page")

# --- socket tool on the UR16e flange --------------------------------------------------------------------------
SOCKET_TOOL_LENGTH = P(0.160, "m", "none", "ASSUMED", "adapter + 13 mm socket, flange to socket face")
SOCKET_TOOL_MASS = P(1.2, "kg", "none", "ASSUMED")
SOCKET_ACROSS_FLATS = P(0.0133, "m", "ISO 2725 / DIN 3124 13 mm socket", "DERIVED", "13 mm AF + 0.3 mm clearance")
