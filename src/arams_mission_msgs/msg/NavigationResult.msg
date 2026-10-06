# Published once per navigation attempt by room_navigator_node, not latched:
# a single live event per mission, consumed by orchestrator_node.
int8 SUCCEEDED=0
int8 ABORTED=1
int8 CANCELED=2
int8 REJECTED=3
int8 UNKNOWN_ROOM=4
int8 outcome
int32 room_id
string detail
