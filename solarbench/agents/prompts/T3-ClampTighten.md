# Work order: tighten a module clamp bolt

Tighten the clamp bolt in front of the robot into the module manufacturer's torque window, then take the tool away.

The bolt is an M8 with a hex head and a right-hand thread. The centre of the top of its head is at ({head_x:.3f}, {head_y:.3f}, {head_z:.3f}) m in the base frame, and its axis points out of the head along ({axis_x:.3f}, {axis_y:.3f}, {axis_z:.3f}). The bolt starts loose, between {loose_min_deg:.0f} and {loose_max_deg:.0f} degrees short of snug, with its flats at any angle. Installed torque is the tightening torque the bolt has reached; it is near zero until the bolt is snug and rises as the bolt is turned further.

The job is judged on the conditions below, in this order, and on nothing else.
- [engaged] The socket is seated on the head: the top of the head at least {engage_depth_mm:g} mm inside the socket, with the socket's axis within {engage_lateral_mm:g} mm and {engage_angle_deg:g} degrees of the bolt's.
- [snug] The bolt has been turned until it is snug, the point where the clamp starts to resist.
- [in_spec] The installed torque has reached {torque_min:g} N·m.
- [released] The socket is off the head, its face more than {released_mm:g} mm from the top of the head.
- [over_torque] If the installed torque goes above {torque_max:g} N·m at any moment, the clamp is damaged and the job has failed, whatever happens afterwards.

You have {time_limit_s:g} s. A job that is not finished by then has failed.
