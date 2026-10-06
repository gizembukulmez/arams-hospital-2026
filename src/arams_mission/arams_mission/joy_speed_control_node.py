"""Thin ROS wrapper: bumps teleop_node's speed on D-pad Up/Down, like teleop_twist_keyboard."""

import rclpy
from rclpy.node import Node
from rclpy.parameter import Parameter
from rclpy.parameter_client import AsyncParameterClient
from rclpy.task import Future

from sensor_msgs.msg import Joy

from arams_mission.joy_speed_scaler import JoySpeedScaler

# DS4 buttons - confirmed via /joy on this controller, see docs in README.
_INCREASE_BUTTON = 11  # D-pad Up
_DECREASE_BUTTON = 12  # D-pad Down


class JoySpeedControlNode(Node):
    """Adjusts teleop_node's scale_linear.x/scale_angular.yaw on D-pad Up/Down."""

    def __init__(self) -> None:
        super().__init__('joy_speed_control_node')

        self.declare_parameter('teleop_node_name', 'teleop_node')
        self.declare_parameter('step_factor', 0.1)
        self.declare_parameter('initial_linear', 0.2)
        self.declare_parameter('initial_angular', 1.5)
        self.declare_parameter('min_linear', 0.05)
        self.declare_parameter('max_linear', 0.22)
        self.declare_parameter('min_angular', 0.2)
        self.declare_parameter('max_angular', 2.84)

        self._scaler = JoySpeedScaler(
            initial_linear=self.get_parameter('initial_linear').value,
            initial_angular=self.get_parameter('initial_angular').value,
            step_factor=self.get_parameter('step_factor').value,
            min_linear=self.get_parameter('min_linear').value,
            max_linear=self.get_parameter('max_linear').value,
            min_angular=self.get_parameter('min_angular').value,
            max_angular=self.get_parameter('max_angular').value,
        )

        teleop_node_name = self.get_parameter('teleop_node_name').value
        self._param_client = AsyncParameterClient(self, teleop_node_name)

        self._prev_buttons: list[int] | None = None
        self.create_subscription(Joy, 'joy', self._on_joy, 10)

    def _on_joy(self, msg: Joy) -> None:
        if self._prev_buttons is not None:
            if self._rising_edge(msg.buttons, _INCREASE_BUTTON):
                self._scaler.increase()
                self._push_scale()
            elif self._rising_edge(msg.buttons, _DECREASE_BUTTON):
                self._scaler.decrease()
                self._push_scale()
        self._prev_buttons = list(msg.buttons)

    def _rising_edge(self, buttons: list[int], index: int) -> bool:
        return (
            index < len(buttons)
            and index < len(self._prev_buttons)
            and self._prev_buttons[index] == 0
            and buttons[index] == 1
        )

    def _push_scale(self) -> None:
        future = self._param_client.set_parameters([
            Parameter('scale_linear.x', Parameter.Type.DOUBLE, self._scaler.linear),
            Parameter('scale_angular.yaw', Parameter.Type.DOUBLE, self._scaler.angular),
        ])
        future.add_done_callback(self._on_scale_set)

    def _on_scale_set(self, future: Future) -> None:
        self.get_logger().info(
            f'Speed scale set to linear={self._scaler.linear:.3f} '
            f'angular={self._scaler.angular:.3f}')


def main(args: list[str] | None = None) -> None:
    rclpy.init(args=args)
    node = JoySpeedControlNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
