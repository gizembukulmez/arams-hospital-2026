"""Thin ROS wrapper around each room's /open_door_N Trigger service."""

from rclpy.node import Node
from rclpy.task import Future
from std_srvs.srv import Trigger


class DoorClient:
    """Opens a room's door via its /open_door_N service, one client per room."""

    def __init__(self, node: Node, room_ids: list[int]) -> None:
        self._clients = {
            room_id: node.create_client(Trigger, f'open_door_{room_id}')
            for room_id in room_ids
        }

    def open_door_async(self, room_id: int) -> Future:
        """Call the door service for room_id, returning its response future."""
        client = self._clients[room_id]
        client.wait_for_service()
        return client.call_async(Trigger.Request())
