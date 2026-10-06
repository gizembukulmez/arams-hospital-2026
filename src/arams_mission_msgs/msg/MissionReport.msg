# Published once by orchestrator_node at REPORT, latched: the mission's
# final outcome.
bool success
int8 READ_TAG=0
int8 OPEN_DOOR=1
int8 NAVIGATE=2
int8 DETECT=3
int8 failed_stage
int32 room_id
bool patient_state_known
arams_mission_msgs/PatientState patient_state
string detail
