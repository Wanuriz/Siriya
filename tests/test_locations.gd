extends SceneTree
## Headless test for the location scenes and the switching contract.
##
## No frames awaited, no scene changes: scenes are only loaded and
## instantiated in memory. Real switching with input events is covered by the
## windowed walk test (tests/walk_locations.gd). On success prints
## LOCATION_TESTS_OK and exits 0; on failure exits 1.

const BAZAAR_PATH := "res://scenes/locations/bazaar.tscn"
const OASIS_PATH := "res://scenes/locations/oasis.tscn"
const LOCATION_SCRIPT := "res://scripts/location.gd"
const PLAYER_SCRIPT := "res://scripts/player.gd"

var _checks := 0
var _failures := 0
var _exit_code := 1


func _initialize() -> void:
	_run()
	quit(_exit_code)


func _run() -> void:
	# --- project settings: pixel-art setup ------------------------------------
	_check(ProjectSettings.get_setting("application/config/name", "") == "SIRIYA",
			"config name is SIRIYA")
	_check(int(ProjectSettings.get_setting("display/window/size/viewport_width", 0)) == 480,
			"viewport width is 480")
	_check(int(ProjectSettings.get_setting("display/window/size/viewport_height", 0)) == 270,
			"viewport height is 270")
	_check(int(ProjectSettings.get_setting("display/window/size/window_width_override", 0)) == 960,
			"window width override is 960 (integer 2x)")
	_check(int(ProjectSettings.get_setting("display/window/size/window_height_override", 0)) == 540,
			"window height override is 540 (integer 2x)")
	_check(ProjectSettings.get_setting("display/window/stretch/mode", "") == "viewport",
			"stretch mode is viewport")
	_check(ProjectSettings.get_setting("display/window/stretch/aspect", "") == "keep",
			"stretch aspect is keep")
	_check(ProjectSettings.get_setting("display/window/stretch/scale_mode", "") == "integer",
			"stretch scale mode is integer")
	_check(int(ProjectSettings.get_setting("rendering/textures/canvas_textures/default_texture_filter", -1)) == 0,
			"default texture filter is Nearest (0)")
	_check(ProjectSettings.get_setting("autoload/GameState", "") == "*res://scripts/game_state.gd",
			"GameState autoload registered (persists across scene changes)")
	_check(ProjectSettings.get_setting("application/run/main_scene", "") == BAZAAR_PATH,
			"main scene is bazaar")

	# --- switching contract: F1 -> bazaar, F2 -> oasis ------------------------
	var loc_script: Script = load(LOCATION_SCRIPT)
	if loc_script == null:
		print("TEST: FAIL - could not load %s" % LOCATION_SCRIPT)
		return
	var consts: Dictionary = loc_script.get_script_constant_map()
	var scenes_map: Dictionary = consts.get("SCENES", {})
	_check(scenes_map.get(KEY_F1, "") == BAZAAR_PATH, "F1 maps to bazaar scene")
	_check(scenes_map.get(KEY_F2, "") == OASIS_PATH, "F2 maps to oasis scene")

	# --- scene structure ------------------------------------------------------
	_check_location(BAZAAR_PATH, "Bazaar", "bazaar.png", "bazaar")
	_check_location(OASIS_PATH, "Oasis", "oasis.png", "oasis")

	if _failures == 0:
		_exit_code = 0
		print("LOCATION_TESTS_OK (%d checks)" % _checks)
	else:
		print("TEST: FAIL - %d of %d checks failed" % [_failures, _checks])


func _check_location(path: String, expected_root: String, bg_file: String, expected_label: String) -> void:
	var packed: PackedScene = load(path)
	if packed == null:
		_check(false, "load %s" % path)
		return
	var node: Node = packed.instantiate()
	_check(node.name == expected_root, "%s root node name" % path)
	var loc := node.get_script() as Script
	_check(loc != null and loc.resource_path == LOCATION_SCRIPT, "%s root has location.gd" % path)

	var bg := node.get_node_or_null("Background") as Sprite2D
	_check(bg != null, "%s has Background Sprite2D" % path)
	if bg != null:
		var tex := bg.texture
		_check(tex != null and tex.resource_path.get_file() == bg_file,
				"%s background texture is %s" % [path, bg_file])
		_check(bg.centered == false, "%s background is not centered (covers 0,0..480,270)" % path)

	var label := node.get_node_or_null("DebugSceneName") as Label
	_check(label != null and label.text == expected_label, "%s debug label text" % path)

	var player := node.get_node_or_null("Player") as Node2D
	_check(player != null, "%s has Player instance" % path)
	if player != null:
		_check(player.position == Vector2(240.0, 240.0), "%s player starts at 240,240" % path)
		var pscript := player.get_script() as Script
		_check(pscript != null and pscript.resource_path == PLAYER_SCRIPT, "%s player has player.gd" % path)
		var body := player.get_node_or_null("Body") as ColorRect
		_check(body != null and body.size == Vector2(20.0, 24.0), "%s player body 20x24" % path)

	node.free()


func _check(ok: bool, what: String) -> void:
	_checks += 1
	if ok:
		print("  ok: %s" % what)
	else:
		_failures += 1
		print("  FAIL: %s" % what)
