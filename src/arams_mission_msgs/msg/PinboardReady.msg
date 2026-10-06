# Zero-payload signal: the pinboard-viewing pose has been reached and
# tag_reader_node may begin reading /detections. Published once, latched,
# and only on a successful NavigateToPose, never on ABORTED/CANCELED/
# REJECTED, so a failed approach leaves the mission stalled at tag reading
# instead of reading tags from an unconfirmed pose.
