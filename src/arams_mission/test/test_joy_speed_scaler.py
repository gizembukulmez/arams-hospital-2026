from arams_mission.joy_speed_scaler import JoySpeedScaler


def make_scaler(step_factor=0.1, max_linear=0.22, max_angular=2.84):
    return JoySpeedScaler(
        initial_linear=0.2,
        initial_angular=1.5,
        step_factor=step_factor,
        min_linear=0.05,
        max_linear=max_linear,
        min_angular=0.2,
        max_angular=max_angular,
    )


def test_increase_scales_both_speeds_up():
    scaler = make_scaler(max_linear=10, max_angular=10)
    scaler.increase()
    assert scaler.linear == 0.2 * 1.1
    assert scaler.angular == 1.5 * 1.1


def test_decrease_scales_both_speeds_down():
    scaler = make_scaler()
    scaler.decrease()
    assert scaler.linear == 0.2 * 0.9
    assert scaler.angular == 1.5 * 0.9


def test_increase_clamps_to_max():
    scaler = make_scaler()
    for _ in range(50):
        scaler.increase()
    assert scaler.linear == 0.22
    assert scaler.angular == 2.84


def test_decrease_clamps_to_min():
    scaler = make_scaler()
    for _ in range(50):
        scaler.decrease()
    assert scaler.linear == 0.05
    assert scaler.angular == 0.2


def test_increase_then_decrease_is_not_exactly_reversible():
    scaler = make_scaler()
    scaler.increase()
    scaler.decrease()
    assert scaler.linear != 0.2
