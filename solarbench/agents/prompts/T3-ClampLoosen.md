# Work order: loosen a module clamp bolt

Break the clamp bolt in front of the robot loose and back it off, then take the tool away.

The bolt is an M8 with a hex head and a right-hand thread. The centre of the top of its head is at ({head_x:.3f}, {head_y:.3f}, {head_z:.3f}) m in the base frame, and its axis points out of the head along ({axis_x:.3f}, {axis_y:.3f}, {axis_z:.3f}). The bolt starts tightened to an installed torque between {installed_min:g} and {installed_max:g} N·m, with its flats at any angle. Installed torque is the tightening torque the bolt has reached.

The job is judged on the conditions below, in this order, and on nothing else.
- [engaged] The socket is seated on the head: the top of the head at least {engage_depth_mm:g} mm inside the socket, with the socket's axis within {engage_lateral_mm:g} mm and {engage_angle_deg:g} degrees of the bolt's.
- [broken_away] The bolt has started to turn in the loosening direction.
- [backed_off] The bolt has been turned back {backoff_turns:g} of a turn from where it started.
- [released] The socket is off the head, its face more than {released_mm:g} mm from the top of the head.
- [over_torque] If the bolt is tightened instead and its installed torque goes above {torque_max:g} N·m at any moment, the clamp is damaged and the job has failed, whatever happens afterwards.

You have {time_limit_s:g} s. A job that is not finished by then has failed.
