extends SceneTree
## Windowed walk test: real input events drive scene switching, movement and
## GameState persistence across switches.
##
## This test awaits frames, so it must be run WINDOWED, not headless:
##   godot --path . --script res://tests/walk_locations.gd
##
## In --script mode autoloads are not instantiated, so a GameState instance
## is added to the root manually, mimicking the autoload.
## On success prints WALK_TESTS_OK and exits 0; a 30s fail-safe timer quits
## with code 1 if the coroutine ever hangs.

const BAZAAR_PATH := "res://scenes/locations/bazaar.tscn"
const OASIS_PATH := "res://scenes/locations/oasis.tscn"

var _checks := 0
var _failures := 0
var _exit_code := 1
var _done := false


func _initialize() -> void:
	_run()


func _run() -> void:
	# Fail-safe: if the coroutine hangs or crashes, still exit non-zero.
	var timer := Timer.new()
	timer.wait_time = 30.0
	timer.one_shot = true
	timer.autostart = true
	timer.timeout.connect(_on_timeout)
	root.add_child(timer)

	# GameState instance mimicking the autoload singleton.
	var gs = load("res://scripts/game_state.gd").new()
	gs.name = "GameState"
	root.add_child(gs)
	gs.set_flag("walk_test_flag", true)
	gs.set_fruits(2)

	# --- start at bazaar -------------------------------------------------------
	change_scene_to_file(BAZAAR_PATH)
	await _frames(5)
	_check(current_scene != null and current_scene.scene_file_path == BAZAAR_PATH,
			"game starts at bazaar")

	# --- F2 -> oasis, GameState persists ---------------------------------------
	_press_key(KEY_F2)
	await _frames(10)
	_check(current_scene != null and current_scene.scene_file_path == OASIS_PATH,
			"F2 opens oasis")
	_check(gs.get_flag("walk_test_flag") == true, "flag survives F2 switch")
	_check(gs.get_fruits() == 2, "fruits survive F2 switch")

	# --- F1 -> bazaar, GameState persists ---------------------------------------
	_press_key(KEY_F1)
	await _frames(10)
	_check(current_scene != null and current_scene.scene_file_path == BAZAAR_PATH,
			"F1 opens bazaar again")
	_check(gs.get_flag("walk_test_flag") == true, "flag survives F1 switch")
	_check(gs.get_fruits() == 2, "fruits survive F1 switch")

	# --- F1 in bazaar is a no-op (scene instance is not reloaded) ---------------
	var before_id: int = current_scene.get_instance_id()
	_press_key(KEY_F1)
	await _frames(10)
	_check(current_scene.get_instance_id() == before_id,
			"F1 in bazaar does not reload the scene (no-op)")

	# --- movement: reach the left wall, then the right wall ---------------------
	var player := current_scene.get_node("Player") as Node2D
	_check(player != null, "player exists in the scene")
	if player != null:
		Input.action_press("ui_left")
		var reached := await _wait_until(func() -> bool: return player.position.x <= 10.001, 600)
		Input.action_release("ui_left")
		_check(reached, "player reaches the left wall")
		_check(player.position.x >= 10.0 - 0.01, "player never passes the left bound (x=%f)" % player.position.x)
		_check(absf(player.position.x - 10.0) <= 0.05, "player stops at the left bound (x=%f)" % player.position.x)
		_check(player.position.y == 240.0, "player stays on the ground band (y=240)")

		Input.action_press("ui_right")
		reached = await _wait_until(func() -> bool: return player.position.x >= 469.999, 600)
		Input.action_release("ui_right")
		_check(reached, "player reaches the right wall")
		_check(player.position.x <= 470.0 + 0.01, "player never passes the right bound (x=%f)" % player.position.x)
		_check(absf(player.position.x - 470.0) <= 0.05, "player stops at the right bound (x=%f)" % player.position.x)

	_finish()


func _press_key(keycode: int) -> void:
	var ev := InputEventKey.new()
	ev.keycode = keycode
	ev.pressed = true
	Input.parse_input_event(ev)
	var ev_up := InputEventKey.new()
	ev_up.keycode = keycode
	ev_up.pressed = false
	Input.parse_input_event(ev_up)


func _frames(count: int) -> void:
	for i in count:
		await process_frame


func _wait_until(predicate: Callable, max_frames: int) -> bool:
	for i in max_frames:
		if predicate.call():
			return true
		await process_frame
	return false


func _on_timeout() -> void:
	if not _done:
		print("TEST: FAIL - walk test timed out after 30s")
		quit(1)


func _finish() -> void:
	_done = true
	if _failures == 0:
		_exit_code = 0
		print("WALK_TESTS_OK (%d checks)" % _checks)
	else:
		print("TEST: FAIL - %d of %d checks failed" % [_failures, _checks])
	quit(_exit_code)


func _check(ok: bool, what: String) -> void:
	_checks += 1
	if ok:
		print("  ok: %s" % what)
	else:
		_failures += 1
		print("  FAIL: %s" % what)
