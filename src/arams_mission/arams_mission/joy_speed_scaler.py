"""Tracks an adjustable linear/angular drive speed, stepped up or down by a fixed factor.

Plain Python, no ROS: keeps application logic out of ROS nodes.
"""


class JoySpeedScaler:
    """Adjustable linear/angular speed, mirroring teleop_twist_keyboard's q/z step keys.

    Each step multiplies both speeds by the same factor and clamps them to
    the robot's actual limits, so repeated presses converge on the max/min
    instead of overshooting it.
    """

    def __init__(
        self,
        initial_linear: float,
        initial_angular: float,
        step_factor: float,
        min_linear: float,
        max_linear: float,
        min_angular: float,
        max_angular: float,
    ) -> None:
        self._linear = initial_linear
        self._angular = initial_angular
        self._step_factor = step_factor
        self._min_linear = min_linear
        self._max_linear = max_linear
        self._min_angular = min_angular
        self._max_angular = max_angular

    @property
    def linear(self) -> float:
        return self._linear

    @property
    def angular(self) -> float:
        return self._angular

    def increase(self) -> None:
        """Scale both speeds up by one step, clamped to their max."""
        self._linear = min(self._linear * (1 + self._step_factor), self._max_linear)
        self._angular = min(self._angular * (1 + self._step_factor), self._max_angular)

    def decrease(self) -> None:
        """Scale both speeds down by one step, clamped to their min."""
        self._linear = max(self._linear * (1 - self._step_factor), self._min_linear)
        self._angular = max(self._angular * (1 - self._step_factor), self._min_angular)
