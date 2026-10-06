"""Builds a stamped ROS pose message from a plain RoomPose.

Shared by pinboard_approach_node and room_navigator_node; both send a
single NavigateToPose goal and need the same map-frame PoseStamped
construction. Kept out of room_navigator.py, which stays ROS-free.
"""

from geometry_msgs.msg import PoseStamped

from arams_mission.room_navigator import RoomPose, yaw_to_quaternion_z_w


def pose_stamped(pose: RoomPose, stamp, frame_id: str = 'map') -> PoseStamped:
    """Build a PoseStamped from a RoomPose, at the given stamp."""
    msg = PoseStamped()
    msg.header.frame_id = frame_id
    msg.header.stamp = stamp
    msg.pose.position.x = pose.x
    msg.pose.position.y = pose.y
    msg.pose.orientation.z, msg.pose.orientation.w = yaw_to_quaternion_z_w(pose.yaw_rad)
    return msg
