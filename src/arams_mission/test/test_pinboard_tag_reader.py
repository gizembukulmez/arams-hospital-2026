from arams_mission.pinboard_tag_reader import PinboardTagReader


def make_reader(required=3):
    return PinboardTagReader(valid_ids={1, 2, 3}, required_consistent_detections=required)


def test_locks_in_after_required_consistent_detections():
    reader = make_reader(required=3)
    assert reader.observe([2]) is None
    assert reader.observe([2]) is None
    assert reader.observe([2]) == 2


def test_stays_locked_once_confirmed():
    reader = make_reader(required=2)
    reader.observe([1])
    reader.observe([1])
    assert reader.observe([3]) == 1


def test_switching_ids_resets_the_count():
    reader = make_reader(required=3)
    reader.observe([1])
    reader.observe([1])
    reader.observe([2])
    reader.observe([2])
    assert reader.observe([2]) == 2


def test_empty_frame_resets_the_count():
    reader = make_reader(required=2)
    reader.observe([1])
    reader.observe([])
    assert reader.observe([1]) is None
    assert reader.observe([1]) == 1


def test_unknown_id_is_ignored():
    reader = make_reader(required=2)
    reader.observe([99])
    reader.observe([2])
    assert reader.observe([2]) == 2


def test_multiple_valid_ids_in_one_frame_is_ambiguous():
    reader = make_reader(required=2)
    reader.observe([1])
    reader.observe([1, 3])
    assert reader.observe([1]) is None
    assert reader.observe([1]) == 1
