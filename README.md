# ARAMS Hospital: TurtleBot3 Robotic Nurse

Course project (FH Aachen, ARAMS 2026): a TurtleBot3 in Webots reads a
pinboard AprilTag, opens the matching room's door, navigates in, and
classifies the patient's state. See "Running the mission" below for the full
task flow in practice.

## AI-generated content

This project was developed with **Claude Code** (Anthropic; the Claude
Sonnet 5 model), used throughout as a pair-programming tool. The authors
specified the architecture, node interfaces, and design decisions (the
perceive/decide/act structure, Nav2 reuse and map-based navigation, the
orchestrator's explicit state machine, parameter tuning choices), and Claude
Code generated implementation code, tests, and documentation from those
specs; every change was reviewed by the authors before being committed.
Per-commit AI attribution is recorded in the git history
(`Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>` trailers). Run
`git log` to see which commits it applies to.

## Requirements

**ROS 2 distro: Jazzy**, on **Ubuntu 24.04 (Noble)**. Install ROS 2 Jazzy
Desktop first if you haven't: https://docs.ros.org/en/jazzy/Installation.html

### ROS packages

Most of this workspace's ROS dependencies are resolved automatically by
`rosdep` in step 3 below, so you don't need to apt-install them by hand. The
following four are the exception (Nav2's own release packaging isn't
rosdep-resolvable on a fresh Jazzy install):

```bash
sudo apt install ros-jazzy-navigation2 ros-jazzy-nav2-bringup \
                  ros-jazzy-nav2-lifecycle-manager ros-jazzy-nav2-amcl
```

`apriltag_ros` and the `webots_ros2_*` packages are **built from source** as
part of this workspace (they live under `src/`). Do not apt-install them.

### Webots

Install Webots **R2025a** separately (it's the simulator app, not a ROS
package): https://cyberbotics.com/#download (get the `.deb` for Ubuntu).

### Python packages

```bash
pip install ultralytics
```

Needed for `patient_state_node`'s YOLO classifier. No version is pinned in
this repo. (`opencv-python` is *not* needed via pip; it comes in through
rosdep as the `python3-opencv` system package.)

## Setup / How to run

### 1. Clone

```bash
git clone https://git.fh-aachen.de/ca2324s/arams_hospital_2026.git arams_hospital
cd arams_hospital
```

Packages already live directly under this repo's `src/`; the cloned repo
root *is* your colcon workspace root, nothing to move.

### 2. Deactivate conda (do this before anything else below)

If a conda/miniforge base environment is active it shadows system Python and
the `empy` version `rosidl` needs, and the build breaks. Check, then disable:

```bash
echo $CONDA_DEFAULT_ENV     # anything other than empty/blank means it's active
conda deactivate            # repeat if you see more than one env stacked
```

### 3. Install ROS dependencies

```bash
rosdep update
rosdep install --from-paths src --ignore-src -r -y
```

(First time using rosdep on this machine ever? Run `sudo rosdep init` once,
before `rosdep update`.)

### 4. Build the workspace

```bash
colcon build --packages-up-to arams_mission webots_ros2_turtlebot
```

This builds only what the mission actually needs: our own packages plus
`webots_ros2_turtlebot` and its real dependencies. It deliberately skips the
other `webots_ros2_*` robot packages vendored under `src/webots_arams/`
(epuck, mavic, tesla, tiago, husarion, universal_robot, crazyflie); they're
unused here and not yet verified on Jazzy.

### 5. Source the workspace

```bash
source install/setup.bash
```

Do this in every new terminal you use for the `ros2 launch`/`ros2 run`
commands below.

## Running the mission

Each of these runs in its own terminal (after step 5 above in each one).

**1. Start the simulator** (stands in for what the graders prelaunch):

```bash
ros2 launch webots_ros2_turtlebot arams_challenge_launch.py
```

Opens Webots with the hospital world: TurtleBot3 Burger, the walking nurse,
three closed doors, and a pinboard showing a randomized AprilTag. Watch the
console for a line like `Pinnwand zeigt AprilTag 41h12 ID 2`; that tells you
which room to expect this run (room *N* ↔ tag *N*, fixed mapping).

**2. Bring up Nav2 + mission nodes**:

```bash
ros2 launch arams_mission mission_launch.yaml
```

Starts Nav2 (map server against the already-committed
`config/maps/hospital_map.yaml`, AMCL, planner/controller/behavior servers),
`pinboard_approach_node` (drives to the pinboard-viewing pose once),
`room_navigator_node`, `patient_state_node`, and `orchestrator_node`, the
state machine that sequences the mission once a tag is read.

> **Known limitation:** `patient_state_node` will fail on startup if
> `config/patient_state.yaml`'s `weights_path` still points at a placeholder
> (`best.pt`) instead of a trained model; see `src/arams_mission/README.md`
> if you haven't trained one yet (`training/train_yolo.py`). A shipped model
> already lives in `models/best.pt` by default, so this normally isn't hit.

You should see the robot drive toward the pinboard in Webots.

**3. Once Nav2 has settled, bring up tag reading**:

```bash
ros2 launch arams_mission tag_reader_launch.yaml
```

Wait until step 2 shows the robot actually moving toward the pinboard (Nav2
fully active) before running this. Starting it at the same instant as step 2
was found to intermittently break Nav2's own startup (`apriltag_node`'s
continuous full-resolution detection competing with Nav2's composable-node
loading for CPU badly enough to cause activation failures). Starts
`apriltag_ros`'s `apriltag_node` (remapped to the robot's camera) and
`tag_reader_node`. Once the tag is seen consistently for 5 frames it locks in
and publishes the target. `orchestrator_node` (from step 2) then opens the
matching room's door, navigates in, classifies the patient over a short
settle window, and reports the result both on the console and on the latched
`/mission_report` topic (`ros2 topic echo /mission_report --once`), with no
further manual steps.

**Optional, not part of a normal run:** `teleop_launch.yaml` is a PS4-controller
teleop tool used only for building the map by hand, not needed here since
`config/maps/hospital_map.yaml` already exists.

## More about the code

Node-by-node docs (topics, services/actions, parameters, dev tools, and the
YOLO patient-state training workflow) live in
[`src/arams_mission/README.md`](src/arams_mission/README.md).
