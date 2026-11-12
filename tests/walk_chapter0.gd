extends SceneTree
## Windowed walk test for chapter 0 «Плёнка» — run WITHOUT --headless
## (it awaits frames):
##   godot --path . --script res://tests/walk_chapter0.gd
##
## Drives ui_accept through all 7 film frames, verifies single-frame steps,
## gas emission only on frames 2 and 7, the chapter0_done flag, that a spare
## accept on the last frame does nothing, and saves one screenshot per frame
## with a text-window pixel check. In --script mode autoloads are not
## instantiated, so a GameState instance is added manually. A 45 s fail-safe
## timer quits with code 1 if anything hangs. On success prints WALK_CH0_OK.

const SCENE_PATH := "res://scenes/chapters/chapter0.tscn"
const TEXT_COLOR := Color(0.960784, 0.796078, 0.662745)  # #F5CBA9
const GAS_FRAMES := [2, 7]

var _checks := 0
var _failures := 0
var _exit_code := 1
var _done := false


func _initialize() -> void:
	_run()


func _on_timeout() -> void:
	if not _done:
		print("TEST: FAIL - walk_chapter0 timed out after 45 s")
		quit(1)


func _check(ok: bool, what: String) -> void:
	_checks += 1
	if ok:
		print("  ok: %s" % what)
	else:
		_failures += 1
		print("  FAIL: %s" % what)


func _frames(n: int) -> void:
	for i in n:
		await process_frame


func _wait_until(predicate: Callable, max_frames: int) -> bool:
	for i in max_frames:
		if predicate.call():
			return true
		await process_frame
	return false


func _press_accept() -> void:
	var ev := InputEventKey.new()
	ev.keycode = KEY_ENTER
	ev.pressed = true
	Input.parse_input_event(ev)


func _shot(frame_num: int) -> void:
	await _frames(3)
	# the logic may already be idle while the last rendered frame still shows
	# the fade; wait for two completed draws before capturing
	await RenderingServer.frame_post_draw
	await RenderingServer.frame_post_draw
	var img: Image = root.get_texture().get_image()
	var path := ProjectSettings.globalize_path("res://art/screens/ch0_%02d.png" % frame_num)
	img.save_png(path)
	print("  [shot %d] fade.a=%.4f img=%dx%d" % [frame_num,
			current_scene.get_node("Fade").color.a, img.get_width(), img.get_height()])
	# the text window must be actually drawn: count text-colored pixels in the
	# window region (x 8..472, y 6..80)
	var hits := 0
	for y in range(6, 80):
		for x in range(8, 472, 4):
			var c := img.get_pixel(x, y)
			if absf(c.r - TEXT_COLOR.r) < 0.04 and absf(c.g - TEXT_COLOR.g) < 0.04 \
					and absf(c.b - TEXT_COLOR.b) < 0.04:
				hits += 1
	_check(hits >= 30, "frame %d: text window drawn (text-color pixels %d >= 30)" % [frame_num, hits])


func _run() -> void:
	var timer := Timer.new()
	timer.wait_time = 45.0
	timer.one_shot = true
	timer.autostart = true
	timer.timeout.connect(_on_timeout)
	root.add_child(timer)

	# use the SAME GameState object the scene writes to: the real autoload if
	# present, a manual node otherwise (script mode does not load autoloads)
	var gs = root.get_node_or_null("GameState")
	if gs == null:
		gs = load("res://scripts/game_state.gd").new()
		gs.name = "GameState"
		root.add_child(gs)

	change_scene_to_file(SCENE_PATH)
	var loaded := await _wait_until(func() -> bool:
		return current_scene != null and current_scene.scene_file_path == SCENE_PATH \
				and not current_scene.get("busy") \
				and current_scene.get_node("Fade").color.a < 0.01, 300)
	# reset guard: if a stray press flipped the first frame during load, reload
	if int(current_scene.get("current_frame")) != 1:
		change_scene_to_file(SCENE_PATH)
		await _wait_until(func() -> bool:
			return current_scene != null and not current_scene.get("busy") \
					and int(current_scene.get("current_frame")) == 1 \
					and current_scene.get_node("Fade").color.a < 0.01, 300)
	_check(loaded, "chapter0 loads and finishes its initial state")
	_check(int(current_scene.get("current_frame")) == 1, "starts at frame 1")
	_check(gs.has_flag("chapter0_done") == false, "flag chapter0_done absent before frame 7")
	_check(current_scene.get_node("Gas").emitting == false, "frame 1: gas off")
	await _shot(1)

	for n in range(1, 7):
		_press_accept()
		if n == 1:
			# while the fade runs, a spare ui_accept must be ignored
			await _frames(5)
			_press_accept()
		var reached := await _wait_until(func() -> bool:
			return current_scene != null and not current_scene.get("busy") \
					and int(current_scene.get("current_frame")) == n + 1 \
					and current_scene.get_node("Fade").color.a < 0.01, 240)
		_check(reached, "accept advances to frame %d (exactly +1, spare presses ignored)" % (n + 1))
		var gas_on: bool = (n + 1) in GAS_FRAMES
		_check(current_scene.get_node("Gas").emitting == gas_on,
				"frame %d: gas emitting == %s" % [n + 1, str(gas_on)])
		await _shot(n + 1)

	_check(gs.has_flag("chapter0_done") == true, "flag chapter0_done set after frame 7")
	_press_accept()
	await _frames(20)
	_check(int(current_scene.get("current_frame")) == 7, "extra ui_accept on frame 7 does nothing")
	_check(current_scene.get("busy") == false, "no transition started after the last frame accept")

	_done = true
	if _failures == 0:
		_exit_code = 0
		print("WALK_CH0_OK (%d checks)" % _checks)
	else:
		print("TEST: FAIL - %d of %d checks failed" % [_failures, _checks])
	quit(_exit_code)
