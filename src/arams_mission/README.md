# arams_mission

Mission-level nodes for the ARAMS hospital TurtleBot3 robotic nurse: the
perceive, decide, and act components that make up the mission pipeline.

See the root [`README.md`](../../README.md#ai-generated-content) for the
AI-generated-content policy.

## Nodes

### tag_reader_node

Determines which AprilTag ID (tagStandard41h12, family `Standard41h12`) the
hospital's pinboard is showing, and publishes it once as the mission target.
Consumes `apriltag_ros`'s detections rather than running its own detection.
Detection doesn't start until `pinboard_approach_node` confirms arrival at
the pinboard. The same `/detections` stream also carries the three
door-mounted AprilTags (same family, same ID range), so reading it before
the robot has actually reached the pinboard risks locking onto a door tag
seen from a distance instead.

**Usage**

```
ros2 launch arams_mission tag_reader_launch.yaml
```

Run this *after* `mission_launch.yaml` has settled (Nav2 active, robot moving
toward the pinboard); see the root `README.md`'s run instructions for why
tag reading is a separate launch file rather than part of `mission_launch.yaml`
(startup CPU contention with Nav2's own composable-node loading). This brings
up `apriltag_ros`'s `apriltag_node` (remapped to the TurtleBot's
`/camera/image_raw` and `/camera/camera_info`) alongside `tag_reader_node`.

**Topics**

| Topic | Direction | Type | Notes |
|---|---|---|---|
| `/pinboard_ready` | sub | `arams_mission_msgs/msg/PinboardReady` | from `pinboard_approach_node`, latched; `/detections` subscription is deferred until this arrives |
| `/detections` | sub | `apriltag_msgs/msg/AprilTagDetectionArray` | from `apriltag_ros` |
| `/mission_target` | pub | `arams_mission_msgs/msg/MissionTarget` | published once, latched (`transient_local`) |

**Parameters** (`config/tag_reader.yaml`)

| Name | Type | Default | Description |
|---|---|---|---|
| `valid_ids` | int[] | `[1, 2, 3]` | tag IDs that can appear on the pinboard |
| `required_consistent_detections` | int | `5` | consecutive frames needed before locking in an ID |

Detection tuning (family, tag size, detector thresholds) lives in
`config/apriltag_41h12.yaml`, a copy of `apriltag_ros`'s vendored config
corrected for `arams_hospital_2.wbt` (that world has no moving tag, unlike
the vendor's example config).

### pinboard_approach_node

Sends one `NavigateToPose` goal, at startup, to a fixed pose that puts the
pinboard's AprilTag in the camera's view. The pinboard isn't guaranteed to
be visible from the spawn pose, so `tag_reader_node` can't lock in an ID
until the robot gets there first. Publishes `/pinboard_ready` only once
Nav2 reports `SUCCEEDED`; on `ABORTED`/`CANCELED`/a rejected goal it
publishes nothing and the mission stays stalled at tag reading, by design:
`tag_reader_node` never opens its detection subscription without a
confirmed arrival.

**Usage**

Brought up as part of `mission_launch.yaml` (see `room_navigator_node`
below); it needs Nav2's `navigate_to_pose` action server, so it can't run
standalone.

**Topics / actions**

| Interface | Direction | Type | Notes |
|---|---|---|---|
| `/navigate_to_pose` | action client | `nav2_msgs/action/NavigateToPose` | one goal, sent once at startup (with retries if Nav2 hasn't finished activating yet) |
| `/pinboard_ready` | pub | `arams_mission_msgs/msg/PinboardReady` | published once, latched, only on `SUCCEEDED` |

**Parameters** (`config/pinboard_approach.yaml`)

| Name | Type | Default | Description |
|---|---|---|---|
| `x` / `y` / `yaw` | double | placeholder `0.0` | pinboard-viewing pose in the map frame |

### room_navigator_node

Sends a `NavigateToPose` goal for the room named by `/navigate_command` and
reports the outcome on `/navigation_result`. Navigation-only: it used to also
open the target room's door itself, but that step moved to
`orchestrator_node`'s own `OPEN_DOOR` state, so this node no longer knows
anything about doors (see `orchestrator_node` below for why: owning the
door-open-then-navigate *sequence* is the orchestrator's job, not a single
node's). Takes its command from `orchestrator_node` rather than reacting
directly to `tag_reader_node`'s `/mission_target`; that decoupling matters,
since if it still triggered off the tag lock directly, it would start
navigating before the orchestrator's `OPEN_DOOR` state had a chance to run.

**Usage**

```
ros2 launch arams_mission mission_launch.yaml
```

This brings up Nav2 (`nav2_bringup`'s `bringup_launch.py`: map server, AMCL,
controller/planner/behavior servers, `bt_navigator`) against the saved
hospital map, alongside `room_navigator_node`. Requires
`ros-jazzy-navigation2` and `ros-jazzy-nav2-bringup` (`sudo apt install`,
not a rosdep-resolvable dependency) and the already-committed map at
`config/maps/hospital_map.yaml`.

**Topics / actions**

| Interface | Direction | Type | Notes |
|---|---|---|---|
| `/navigate_command` | sub | `arams_mission_msgs/msg/MissionTarget` | from `orchestrator_node`, not latched; a one-time command, not a fact worth replaying |
| `/navigate_to_pose` | action client | `nav2_msgs/action/NavigateToPose` | one goal per commanded room |
| `/navigation_result` | pub | `arams_mission_msgs/msg/NavigationResult` | one message per navigation attempt, not latched |

**Parameters** (`config/rooms.yaml`)

| Name | Type | Default | Description |
|---|---|---|---|
| `room_ids` | int[] | `[1, 2, 3]` | known room ids, under the `/**:` wildcard key so `orchestrator_node` reads the same list |
| `room_{id}.x/.y/.yaw` | double | placeholder `0.0` | approach pose in the map frame, per room |

Nav2 tuning lives in `config/nav2_params.yaml` (Burger-specific values,
`robot_radius` and max linear/angular velocity, carried over from the
verified-correct values in the vendored
`webots_ros2_turtlebot/resource/nav2_params.yaml`).

**Arrival semantics:** success is `NavigateToPose` reporting
`STATUS_SUCCEEDED`. `ABORTED`/`CANCELED`/a rejected goal are logged as
distinct failures and published on `/navigation_result`; there's no retry
here by design (see `room_navigator.py`'s `NavigationOutcome`).

### patient_state_node

Classifies the patient's state from the camera feed with a YOLO model and
publishes it continuously; this node itself has no notion of the mission's
progress. `orchestrator_node`'s `DETECT` state is what makes the readings
meaningful: it only subscribes once `room_navigator_node` reports arrival,
then collects a short settle window of readings and reports the majority
class, rather than trusting whatever frame happened to be classified first.

**Usage**

Brought up as part of `mission_launch.yaml` (see `room_navigator_node`
above). Requires `pip install ultralytics`. A model trained on this project's
own captures ships in `models/best.pt`; `mission_launch.yaml` points
`weights_path` at it via `$(find-pkg-share arams_mission)/models/best.pt`, so
no setup is needed to run it as-is; retrain only if you need to extend or
rebalance the dataset (below).

It was trained on 202 labeled images: `in_bed`=59, `on_floor`=101,
`standing`=42. `standing` and `in_bed` are thinner than ideal (each below the
~80-100/class target used during collection). `training/results/` has the
validation metrics (mAP50≈0.995, mAP50-95≈0.63; the gap between those two
suggests box-localization precision is the weaker point, not raw
classification). Run `training/evaluate_model.py` against the held-out val set
for a live per-class accuracy read before trusting it in a graded run.

**Topics**

| Topic | Direction | Type | Notes |
|---|---|---|---|
| `/camera/image_raw` | sub | `sensor_msgs/msg/Image` | robot camera |
| `/patient_state` | pub | `arams_mission_msgs/msg/PatientState` | one message per confident detection |

**Parameters** (`config/patient_state.yaml`)

| Name | Type | Default | Description |
|---|---|---|---|
| `camera_topic` | string | `/camera/image_raw` | camera topic to subscribe to |
| `weights_path` | string | `models/best.pt` | path to the trained YOLO weights; overridden at launch with the resolved package-share path (ROS2 param yaml files aren't launch-substituted) |
| `min_period_sec` | double | `0.5` | minimum seconds between classified frames; YOLO inference is CPU-heavy enough to compete with Nav2/Webots for CPU if run on every frame |

#### Retraining the model

A model already ships in `models/best.pt` (see above); only repeat this if
you're extending or rebalancing the dataset.

1. Collect frames of the patient in each of the three states with this
   package's own `collect_images` node (below) while driving around by hand;
   `teleop_launch.yaml` works for this:
   ```
   ros2 launch arams_mission teleop_launch.yaml
   ```
   and in another terminal, one run per state:
   ```
   ros2 run arams_mission collect_images \
       --ros-args -p camera_topic:=/camera/image_raw \
                  -p save_dir:=$HOME/arams_dataset/raw
   ```
   Rooms are behind closed doors; open the one you're driving into first
   (e.g. `ros2 service call /open_door_1 std_srvs/srv/Trigger`). Each patient's
   state is randomized independently at sim startup, so one run won't give
   you all three states reliably, so expect to restart the sim
   (`arams_challenge_launch.py`) a few times, checking each room, to build a
   balanced set. Aim for a few hundred frames total, spread across all three
   states and a range of distances/angles to the patient.
2. Label the frames in YOLO format (one class per bounding box, from
   `in_bed` / `on_floor` / `standing`, e.g. with Roboflow or LabelImg) and
   export into the layout `training/data.yaml` expects:
   ```
   arams_dataset/
     images/train/*.jpg
     images/val/*.jpg
     labels/train/*.txt   <- one .txt per image, YOLO format
     labels/val/*.txt
   ```
   Class indices in the label files must match `data.yaml`'s `names:` order
   (`0: in_bed`, `1: on_floor`, `2: standing`), which in turn must match
   `arams_mission.patient_detector.PatientState`.
3. Point `training/data.yaml`'s `path:` at that dataset folder.
4. Fine-tune, outside ROS, in a plain Python environment (not the ROS
   workspace's `install/` overlay):
   ```
   pip install ultralytics
   cd src/arams_mission/training
   python3 train_yolo.py
   ```
   Produces `runs/detect/train/weights/best.pt`.
5. Sanity-check it before wiring it in: `python3 evaluate_model.py` prints
   per-class accuracy against `data.yaml`'s val set.
6. Copy the new file over `models/best.pt` (replacing the one that ships in
   the repo) and rebuild so the installed copy under `install/`'s share dir
   picks it up.

### orchestrator_node

Sequences the whole mission: reads `tag_reader_node`'s locked tag, opens the
matching room's door (`DoorClient`, reused directly, no separate door node),
commands `room_navigator_node` to navigate in, collects a short settle window
of `patient_state_node` readings and takes the majority class, then reports
the result. Owns no low-level logic itself; it calls each other node's
existing capability and reacts to the result. The actual decision logic lives
in the plain `MissionStateMachine` class (`mission_state_machine.py`, no ROS
imports, unit-tested in isolation; see `test/test_mission_state_machine.py`).

States: `READ_TAG → OPEN_DOOR → NAVIGATE → DETECT → REPORT → DONE`. Door-open
failures retry once before failing the mission; any other failure (tag never
locks, navigation fails, no patient state observed) reports immediately with
no retry.

**Usage**

Brought up as part of `mission_launch.yaml`. It sits idle in `READ_TAG` until
`tag_reader_launch.yaml` (run separately; see that node's section above)
locks in a tag, then completes the rest of the mission end to end with no
further manual steps.

**Topics / services**

| Interface | Direction | Type | Notes |
|---|---|---|---|
| `/mission_target` | sub | `arams_mission_msgs/msg/MissionTarget` | from `tag_reader_node`, latched |
| door services | client | `std_srvs/srv/Trigger` via `DoorClient` | one client per room, same as `room_navigator_node` used to hold |
| `/navigate_command` | pub | `arams_mission_msgs/msg/MissionTarget` | commands `room_navigator_node`, not latched |
| `/navigation_result` | sub | `arams_mission_msgs/msg/NavigationResult` | from `room_navigator_node` |
| `/patient_state` | sub | `arams_mission_msgs/msg/PatientState` | from `patient_state_node`; subscription is created lazily, only on arrival, mirroring `tag_reader_node`'s own deferred-subscription pattern, so pre-arrival readings are never seen at all rather than filtered out |
| `/mission_report` | pub | `arams_mission_msgs/msg/MissionReport` | published once at REPORT, latched: the mission's final outcome |

**Known limitation:** `DoorClient.open_door_async()` blocks on
`wait_for_service()` with no timeout. Since this node (like every node in
this package) runs a `SingleThreadedExecutor`, a door service that never
appears would hang the whole node before any timer or retry logic here could
run. Doors are part of the prelaunched world and should already exist by
`OPEN_DOOR`, so this is an accepted, documented risk rather than something
handled.

**Parameters** (`config/orchestrator.yaml`, plus `room_ids` from
`config/rooms.yaml`'s `/**:` wildcard key)

| Name | Type | Default | Description |
|---|---|---|---|
| `read_tag_timeout_sec` | double | `180.0` | fail the mission if no tag locks in within this long, generous since `tag_reader_launch.yaml` is started as a separate, later command (see Usage) |
| `detect_timeout_sec` | double | `30.0` | fail DETECT if zero patient-state readings arrive within this long (a partial window still succeeds; see below) |
| `door_open_max_attempts` | int | `2` | door-open attempts before failing OPEN_DOOR |
| `detect_settle_count` | int | `3` | patient-state readings collected before taking the majority class |

### collect_images (dev tool)

Saves camera frames to disk while teleoperating the robot around a patient in
each of the three states, for building the `patient_state_node` training set.
Not part of the graded mission flow.

```
ros2 run arams_mission collect_images \
    --ros-args -p camera_topic:=/camera/image_raw \
               -p save_dir:=$HOME/arams_dataset/raw
```

### PS4 controller teleop (dev/mapping tool)

Manual driving via a DualShock 4 controller, for building a map by hand
instead of the keyboard. Not part of the graded mission flow.

**Usage**

```
ros2 launch arams_mission teleop_launch.yaml
```

Brings up `joy_node`, `teleop_twist_joy`'s `teleop_node`, and
`joy_speed_control_node`. Hold **L1** and move the left stick to drive;
release L1 to stop (deadman switch). D-pad **Up**/**Down** bumps the overall
speed by 10% per press, clamped to the TurtleBot3 Burger's real limits
(0.22 m/s linear, 2.84 rad/s angular), mirroring `teleop_twist_keyboard`'s
`q`/`z` keys.

**Controller mapping** (this specific DS4/driver combo, confirmed via
`ros2 topic echo /joy`; indices can differ on other hardware/drivers)

| Index | Axis |
|---|---|
| 0 | Left stick horizontal (drive turn) |
| 1 | Left stick vertical (drive forward/back) |
| 2 | Right stick horizontal |
| 3 | Right stick vertical |
| 4 | L2 (analog only, no digital button) |
| 5 | R2 (analog only, no digital button) |

| Index | Button |
|---|---|
| 0 | Cross |
| 1 | Circle |
| 2 | Square |
| 3 | Triangle |
| 4 | Share |
| 5 | PS |
| 6 | Options |
| 7 | L3 |
| 8 | R3 |
| 9 | L1 (deadman) |
| 10 | R1 |
| 11 | D-pad Up (speed +) |
| 12 | D-pad Down (speed -) |
| 13 | D-pad Left |
| 14 | D-pad Right |
| 15 | Touchpad click |

### joy_speed_control_node

Adjusts `teleop_node`'s `scale_linear.x`/`scale_angular.yaw` at runtime via
its parameter service, on D-pad Up/Down rising edges.

**Topics**

| Topic | Direction | Type | Notes |
|---|---|---|---|
| `/joy` | sub | `sensor_msgs/msg/Joy` | from `joy_node` |

**Parameters** (`config/teleop_joy.yaml`)

| Name | Type | Default | Description |
|---|---|---|---|
| `teleop_node_name` | string | `teleop_node` | node whose speed parameters get adjusted |
| `step_factor` | double | `0.1` | fractional change per D-pad press |
| `initial_linear` | double | `0.2` | must match `teleop_node`'s `scale_linear.x` |
| `initial_angular` | double | `1.5` | must match `teleop_node`'s `scale_angular.yaw` |
| `min_linear` / `max_linear` | double | `0.05` / `0.22` | clamp range, m/s |
| `min_angular` / `max_angular` | double | `0.2` / `2.84` | clamp range, rad/s |
