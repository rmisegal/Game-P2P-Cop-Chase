"""live_apply: opponent status/quit rendering and Restart activation in the live GUI."""

from types import SimpleNamespace

from police_thief.gui import live_apply


class FakeWindow:
    def __init__(self):
        self.labels = {}
        self.turn = None

    def set_label(self, key, value):
        self.labels[key] = value

    def set_turn(self, mine, text=None):
        self.turn = (mine, text)

    def render(self, view):
        pass


class FakeBar:
    def __init__(self):
        self.restart_enabled = False

    def set_restart_enabled(self, enabled):
        self.restart_enabled = enabled


def _app():
    return SimpleNamespace(_window=FakeWindow(), _role="police", _t0=None,
                           _bidi_i=False, _bidi_peer=False, _bar=FakeBar())


def test_control_enable_activates_when_both_opted_in():
    app = _app()
    app._bidi_i = True  # I already opted in
    live_apply.apply_event(app, {"type": "control_enable", "sender": "thief"})
    assert app._bidi_peer is True
    assert app._bar.restart_enabled is True
    assert "ACTIVE" in app._window.labels["opp_status"]


def test_control_enable_alone_does_not_activate():
    app = _app()  # I have NOT opted in
    live_apply.apply_event(app, {"type": "control_enable", "sender": "thief"})
    assert app._bar.restart_enabled is False


def test_control_status_renders_opponent_state():
    app = _app()
    live_apply.apply_event(app, {"type": "control_status", "status": "THINKING",
                                 "sub_game_number": 2, "step_budget": 1.0})
    assert "THINKING" in app._window.labels["opp_status"]


def test_control_quit_shows_banner():
    app = _app()
    live_apply.apply_event(app, {"type": "control_quit", "sender": "thief"})
    assert app._window.labels["opp_status"] == "QUIT"
    assert app._window.turn == (False, "OPPONENT QUIT")


def test_series_restart_banner():
    app = _app()
    live_apply.apply_event(app, {"type": "series_restart", "attempt": 3})
    assert "RESTARTED" in app._window.turn[1]


def test_error_and_incoming_events():
    app = _app()
    live_apply.apply_event(app, {"type": "error", "message": "boom"})
    assert app._window.labels["status"] == "boom"
    live_apply.apply_event(app, {"type": "incoming",
                                 "message": {"step": 3, "hint": "hi"}, "view": {}})
    assert app._window.labels["hint_in"] == "step 3: hi"
