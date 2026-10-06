"""webots_ros2_driver plugin: slowly oscillate a floating AprilTag.

Loaded as an <extern>-controller plugin for the "moving_apriltag" Robot (which
must be a Supervisor). Each step it moves the robot along world X with a slow
sine, so the tag drifts toward/away from the TurtleBot camera.

Native Webots controllers don't work here because WebotsLauncher copies the
world to /tmp, so the controllers/ directory is not found -- a driver plugin
runs inside the extern-controller process instead.
"""

import math


class AprilTagOscillator:
    def init(self, webots_node, properties):
        self.__robot = webots_node.robot  # Supervisor instance
        self.__amplitude = float(properties.get('amplitude', 0.4))  # meters
        self.__period = float(properties.get('period', 200.0))       # seconds/cycle

        node = self.__robot.getSelf()
        self.__translation_field = node.getField('translation')
        self.__origin = list(self.__translation_field.getSFVec3f())

    def step(self):
        offset = self.__amplitude * math.sin(2.0 * math.pi * self.__robot.getTime() / self.__period)
        self.__translation_field.setSFVec3f([
            self.__origin[0],
            self.__origin[1] + offset,
            self.__origin[2],
        ])
