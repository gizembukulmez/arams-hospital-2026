-- Local cartographer config for the Webots TurtleBot3 Burger.
-- Based on turtlebot3_cartographer/config/turtlebot3_lds_2d.lua, with
-- imu_sampling_ratio = 0 so we never subscribe to /imu. The Webots IMU
-- plugin can emit two messages with the same sim-time stamp, which crashes
-- cartographer's MapByTime monotonic-time check.

include "map_builder.lua"
include "trajectory_builder.lua"

options = {
  map_builder = MAP_BUILDER,
  trajectory_builder = TRAJECTORY_BUILDER,
  map_frame = "map",
  tracking_frame = "base_footprint",
  published_frame = "odom",
  odom_frame = "odom",
  provide_odom_frame = false,
  publish_frame_projected_to_2d = true,
  use_odometry = true,
  use_nav_sat = false,
  use_landmarks = false,
  num_laser_scans = 1,
  num_multi_echo_laser_scans = 0,
  num_subdivisions_per_laser_scan = 1,
  num_point_clouds = 0,
  lookup_transform_timeout_sec = 0.2,
  submap_publish_period_sec = 0.3,
  pose_publish_period_sec = 5e-3,
  trajectory_publish_period_sec = 30e-3,
  rangefinder_sampling_ratio = 1.,
  odometry_sampling_ratio = 1.,
  fixed_frame_pose_sampling_ratio = 1.,
  imu_sampling_ratio = 0.,
  landmarks_sampling_ratio = 1.,
}

MAP_BUILDER.use_trajectory_builder_2d = true

TRAJECTORY_BUILDER_2D.min_range = 0.12
TRAJECTORY_BUILDER_2D.max_range = 3.5
TRAJECTORY_BUILDER_2D.missing_data_ray_length = 3.
TRAJECTORY_BUILDER_2D.use_imu_data = false
TRAJECTORY_BUILDER_2D.use_online_correlative_scan_matching = true
TRAJECTORY_BUILDER_2D.motion_filter.max_angle_radians = math.rad(0.1)

-- Widened from Cartographer's defaults (0.1 m / ~20 deg) so the scan
-- matcher can still find the right match when the odometry-only initial
-- guess is further off than usual — there's no IMU here (see comment at
-- top of file), so rotation error between scans is worse than a typical
-- Cartographer setup and the default search window is too narrow to
-- recover from it, which is what produces a folded/hinged map.
TRAJECTORY_BUILDER_2D.real_time_correlative_scan_matcher.linear_search_window = 0.2
TRAJECTORY_BUILDER_2D.real_time_correlative_scan_matcher.angular_search_window = math.rad(30.)

-- Loosened toward Cartographer's own stock defaults (0.55 / 0.6) — the
-- previous, stricter values made the pose-graph optimizer less willing to
-- accept a loop-closure correction, so once local drift/a fold happened,
-- it was harder to correct even when the robot looped back over known
-- territory.
POSE_GRAPH.constraint_builder.min_score = 0.55
POSE_GRAPH.constraint_builder.global_localization_min_score = 0.6

return options
