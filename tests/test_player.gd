extends SceneTree
## Headless test for the placeholder player bounds logic.
##
## No frames awaited, no scene changes (user rule: headless tests never wait
## for frames). On success prints PLAYER_TESTS_OK and exits with code 0;
## on any failure exits with code 1.

const SCRIPT_PATH := "res://scripts/player.gd"
const SCENE_PATH := "res://scenes/characters/player.tscn"

var _checks := 0
var _failures := 0
# Fail-safe default: quit(1) even if _run() aborts on a runtime error.
var _exit_code := 1


func _initialize() -> void:
	_run()
	quit(_exit_code)


func _run() -> void:
	var script: Script = load(SCRIPT_PATH)
	if script == null:
		print("TEST: FAIL - could not load %s" % SCRIPT_PATH)
		return

	# --- clamp: player rectangle never leaves the screen --------------------
	_check(script.call("clamp_x", -50.0) == 10.0, "clamp_x(-50) clamps to left edge 10")
	_check(script.call("clamp_x", 1000.0) == 470.0, "clamp_x(1000) clamps to right edge 470")
	_check(script.call("clamp_x", 240.0) == 240.0, "clamp_x inside range passes through")
	_check(script.call("clamp_x", 10.0) == 10.0, "clamp_x at exact left bound")
	_check(script.call("clamp_x", 470.0) == 470.0, "clamp_x at exact right bound")

	# --- constants: rect fits the ground band y=225..258 ---------------------
	var consts: Dictionary = script.get_script_constant_map()
	var band_top: float = consts.get("BAND_TOP", 0.0)
	var band_bottom: float = consts.get("BAND_BOTTOM", 0.0)
	var y_center: float = consts.get("Y_CENTER", 0.0)
	var height: float = consts.get("HEIGHT", 0.0)
	_check(band_top == 225.0 and band_bottom == 258.0, "ground band constants are 225..258")
	_check(y_center - height / 2.0 >= band_top, "rect top (%f) inside band" % (y_center - height / 2.0))
	_check(y_center + height / 2.0 <= band_bottom, "rect bottom (%f) inside band" % (y_center + height / 2.0))
	_check(consts.get("MIN_X", 0.0) == 10.0 and consts.get("MAX_X", 0.0) == 470.0, "bounds constants are 10..470")

	# --- player scene structure ----------------------------------------------
	var packed: PackedScene = load(SCENE_PATH)
	if packed == null:
		print("TEST: FAIL - could not load %s" % SCENE_PATH)
		return
	var player := packed.instantiate() as Node2D
	if player == null:
		print("TEST: FAIL - %s did not instantiate as Node2D" % SCENE_PATH)
		return
	var pscript := player.get_script() as Script
	_check(pscript != null and pscript.resource_path == SCRIPT_PATH, "player root has player.gd")
	var body := player.get_node_or_null("Body") as ColorRect
	_check(body != null and body.size == Vector2(20.0, 24.0), "player body is a 20x24 rectangle")
	player.free()

	if _failures == 0:
		_exit_code = 0
		print("PLAYER_TESTS_OK (%d checks)" % _checks)
	else:
		print("TEST: FAIL - %d of %d checks failed" % [_failures, _checks])


func _check(ok: bool, what: String) -> void:
	_checks += 1
	if ok:
		print("  ok: %s" % what)
	else:
		_failures += 1
		print("  FAIL: %s" % what)
