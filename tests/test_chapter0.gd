extends SceneTree
## Headless test for chapter 0 data (data/chapter0.json).
##
## No frames awaited, no scene tree changes beyond instantiating the chapter
## scene (added in the scene-structure section). On success prints
## CHAPTER0_OK and exits with code 0; on any failure exits with code 1.

const DATA_PATH := "res://data/chapter0.json"
const BG_DIR := "res://assets/backgrounds/"
const TRAP_WORDS := ["потому что", "улитка", "иблис", "хасан"]
const REQUIRED_FIELDS := ["id", "bg", "tint", "gas", "speaker", "text", "src", "ref"]
# the igloo background is allowed to be absent (placeholder is drawn at runtime)
const BG_ALLOWED_MISSING := ["igloo.png"]

var _checks := 0
var _failures := 0
# Fail-safe default: quit(1) even if _run() aborts on a runtime error.
var _exit_code := 1


func _initialize() -> void:
	_run()
	quit(_exit_code)


func _check(ok: bool, what: String) -> void:
	_checks += 1
	if ok:
		print("  ok: %s" % what)
	else:
		_failures += 1
		print("  FAIL: %s" % what)


func _run() -> void:
	# --- data file -----------------------------------------------------------
	var f := FileAccess.open(DATA_PATH, FileAccess.READ)
	if f == null:
		print("TEST: FAIL - cannot open %s" % DATA_PATH)
		return
	var data = JSON.parse_string(f.get_as_text())
	if data == null or not (data is Array):
		print("TEST: FAIL - %s is not a JSON array" % DATA_PATH)
		return

	_check(data.size() == 7, "exactly 7 frames (got %d)" % data.size())

	# --- per-frame field checks ----------------------------------------------
	var ids_ok := true
	for i in data.size():
		var frame: Dictionary = data[i]
		for field in REQUIRED_FIELDS:
			if not frame.has(field):
				_check(false, "frame %d has field '%s'" % [i + 1, field])
				ids_ok = false
		if not ((frame.get("id") is int) or (frame.get("id") is float)):
			_check(false, "frame %d id is a number" % (i + 1))
			ids_ok = false
		elif int(frame.get("id")) != i + 1:
			ids_ok = false
	_check(ids_ok, "ids are 1..7 in order and every frame has all required fields")

	for i in data.size():
		var frame: Dictionary = data[i]
		var num: int = frame.get("id", i + 1)
		_check(frame.get("gas") is bool, "frame %d: gas is bool" % num)
		_check(frame.get("bg") is String, "frame %d: bg is a string" % num)
		_check(frame.get("tint") == null or frame.get("tint") is String,
				"frame %d: tint is null or string" % num)
		_check(frame.get("speaker") is String and frame.get("text") is String,
				"frame %d: speaker and text are strings" % num)
		_check(frame.get("src") in ["к", "у", "п"], "frame %d: src is к/у/п" % num)
		_check(frame.get("ref") is String and str(frame.get("ref")).length() > 0,
				"frame %d: ref is a non-empty string" % num)

		# bg file existence: "solid"/"solid_frame" are not files; igloo.png is
		# allowed to be missing (runtime placeholder)
		var bg: String = frame.get("bg", "")
		if bg != "solid" and bg != "solid_frame":
			var path := BG_DIR + bg
			if bg in BG_ALLOWED_MISSING:
				_check(true, "frame %d: bg '%s' may be missing (placeholder)" % [num, bg])
			else:
				_check(FileAccess.file_exists(path), "frame %d: bg file exists: %s" % [num, path])

		# trap words must not appear in visible strings
		var combined: String = (str(frame.get("text", "")) + " " + str(frame.get("speaker", ""))).to_lower()
		for w in TRAP_WORDS:
			_check(not combined.contains(w), "frame %d: no trap word '%s'" % [num, w])

	# --- scene structure (added in step 2; skipped while the scene is absent) -
	if ResourceLoader.exists("res://scenes/chapters/chapter0.tscn"):
		_check_scene()

	if _failures == 0:
		_exit_code = 0
		print("CHAPTER0_OK (%d checks)" % _checks)
	else:
		print("TEST: FAIL - %d of %d checks failed" % [_failures, _checks])


func _check_scene() -> void:
	var packed: PackedScene = load("res://scenes/chapters/chapter0.tscn")
	if packed == null:
		_check(false, "load scenes/chapters/chapter0.tscn")
		return
	var node: Node = packed.instantiate()
	# In --script mode the root is not inside the tree during _initialize, so
	# _ready would not run; the setup methods are invoked directly instead
	# (white-box, still without awaiting any frames).
	node._cache_nodes()
	node._setup_gas()
	node._load_frames()
	node._apply_frame(1)
	_check(node.name == "Chapter0", "chapter0 root node name")
	_check(node.get_script() != null, "chapter0 root has a script")
	_check(node.has_node("BgColor") and node.has_node("BgSprite"), "background nodes present")
	var gas := node.get_node_or_null("Gas") as CPUParticles2D
	_check(gas != null, "Gas CPUParticles2D present")
	_check(gas != null and gas.emitting == false, "Gas starts with emitting=false")
	_check(gas != null and gas.texture != null, "Gas has a texture (ImageTexture 4x4)")
	var film := node.get_node_or_null("FilmFrame") as Node2D
	_check(film != null and film.get_child_count() == 2, "FilmFrame has 2 ColorRects (outer/inner)")
	_check(film != null and film.visible == false, "FilmFrame hidden outside frame 2")
	var window := node.get_node_or_null("TextWindow") as ColorRect
	_check(window != null, "TextWindow ColorRect present")
	var text_label := node.get_node_or_null("TextWindow/TextLabel") as Label
	_check(text_label != null and text_label.autowrap_mode != TextServer.AUTOWRAP_OFF,
			"TextLabel autowrap enabled")
	_check(text_label != null and text_label.get_theme_font_size("font_size") == 10,
			"TextLabel font size is 10")
	var speaker := node.get_node_or_null("TextWindow/SpeakerLabel") as Label
	_check(speaker != null and speaker.visible == true,
			"SpeakerLabel visible on frame 1 (speaker = Летописец)")
	var blink := node.get_node_or_null("TextWindow/BlinkLabel") as Label
	_check(blink != null and blink.text == "▼", "BlinkLabel shows ▼")
	_check(node.has_node("Fade"), "Fade overlay present")
	_check(int(node.get("current_frame")) == 1, "current_frame starts at 1")

	# --- TDD П-34: invalid n must not mutate state before the guard ----------
	# placed BEFORE any check that sets chapter0_done, so the flag is still
	# in its initial state here; real autoload /root/GameState is used
	var gs = root.get_node_or_null("GameState")
	if gs == null:
		gs = load("res://scripts/game_state.gd").new()
		gs.name = "GameState"
		root.add_child(gs)
	_check(node.get("busy") == false, "П-34 precondition: busy is false")
	var flag_before: bool = gs.has_flag("chapter0_done")
	var flag_val_before: bool = gs.get_flag("chapter0_done")
	var cf_before: int = int(node.get("current_frame"))
	var text_before: String = node.text_label.text

	node._apply_frame(99)
	_check(int(node.get("current_frame")) == cf_before,
			"П-34: _apply_frame(99) keeps current_frame (got %s)" % str(node.get("current_frame")))
	_check(node.get("busy") == false, "П-34: _apply_frame(99) keeps busy false")
	_check(gs.has_flag("chapter0_done") == flag_before
			and gs.get_flag("chapter0_done") == flag_val_before,
			"П-34: _apply_frame(99) keeps chapter0_done state unchanged")
	_check(node.text_label.text == text_before,
			"П-34: _apply_frame(99) keeps the shown frame text")

	node._apply_frame(0)
	_check(int(node.get("current_frame")) == cf_before,
			"П-34: _apply_frame(0) keeps current_frame")
	node._apply_frame(-3)
	_check(int(node.get("current_frame")) == cf_before,
			"П-34: _apply_frame(-3) keeps current_frame")
	_check(gs.has_flag("chapter0_done") == flag_before
			and gs.get_flag("chapter0_done") == flag_val_before,
			"П-34: invalid n keeps chapter0_done state unchanged")

	# valid n still applies
	node._apply_frame(3)
	_check(int(node.get("current_frame")) == 3, "П-34: valid n still applies (current_frame 3)")
	_check(node.text_label.text == str(node.frames[2].get("text", "")),
			"П-34: valid n shows the frame 3 text")

	# empty dataset: _apply_frame must not mutate current_frame either
	node.frames.assign([])
	node.set("_last_frame", 0)
	var cf_before_empty: int = int(node.get("current_frame"))
	node._apply_frame(1)
	_check(int(node.get("current_frame")) == cf_before_empty,
			"П-34: _apply_frame on empty dataset keeps current_frame (got %s)"
					% str(node.get("current_frame")))

	# state isolation: restore the real dataset for the checks below
	node._load_frames()

	# --- TDD: the last frame comes from the loaded data, not a constant -------
	# reuses `gs` (the /root/GameState resolved in the П-34 block above)

	# real data: _last_frame must follow frames.size()
	var last_v: Variant = node.get("_last_frame")
	_check(last_v is int and int(last_v) == node.frames.size() and node.frames.size() == 7,
			"_last_frame follows frames.size() after load (last=%s, frames=%d)"
					% [str(last_v), node.frames.size()])

	# two-frame dataset: frame 2 is the last one (post-load state is emulated
	# by setting _last_frame directly; loading a 2-frame file would require
	# modifying data/chapter0.json, which is out of scope)
	node.frames.assign([
		{"id": 1, "bg": "solid", "tint": null, "gas": false, "speaker": "", "text": "", "src": "п", "ref": "t"},
		{"id": 2, "bg": "solid", "tint": null, "gas": false, "speaker": "", "text": "", "src": "п", "ref": "t"},
	])
	node.set("_last_frame", node.frames.size())
	node._apply_frame(2)
	_check(gs.has_flag("chapter0_done") == true,
			"frame 2 of a 2-frame dataset sets chapter0_done")
	_check(int(node.get("current_frame")) == 2, "current_frame is 2 after the last frame")
	node._advance()
	_check(node.get("busy") == false and int(node.get("current_frame")) == 2,
			"advance is blocked on the last frame (busy=%s, frame=%s)"
					% [str(node.get("busy")), str(node.get("current_frame"))])

	# empty dataset: no advancing, the last frame stays safe (0)
	node.frames.assign([])
	node.set("_last_frame", 0)
	node._apply_frame(1)
	node._advance()
	var last_empty: Variant = node.get("_last_frame")
	_check(last_empty is int and int(last_empty) == 0 and node.get("busy") == false,
			"empty dataset keeps _last_frame 0 and blocks advancing (last=%s, busy=%s)"
					% [str(last_empty), str(node.get("busy"))])

	# --- polish A5: the arrow blinks on intermediate frames, not the last ----
	# restore the real dataset after the blocks above
	node._load_frames()
	node._blink_t = 0.0
	node._apply_frame(1)
	node._process(0.016)
	_check(node.blink_label.visible == true,
			"polish A5: arrow visible on an intermediate frame")
	node._blink_t = 0.0
	node._apply_frame(int(node.get("_last_frame")))
	node._process(0.016)
	_check(node.blink_label.visible == false,
			"polish A5: arrow does not blink on the last frame")

	# --- polish A3: the placeholder label names the actual missing bg --------
	node.frames.assign([{"id": 1, "bg": "ghost.png", "tint": null, "gas": false,
			"speaker": "", "text": "", "src": "п", "ref": "t"}])
	node.set("_last_frame", node.frames.size())
	node._apply_frame(1)
	_check(node.placeholder_label.text == "ghost.png (placeholder)",
			"polish A3: placeholder label names the actual bg (got %s)"
					% str(node.placeholder_label.text))
	node._load_frames()  # restore the real dataset

	# --- polish A4: every loaded frame is a Dictionary ------------------------
	var all_dicts := true
	for f in node.frames:
		if not (f is Dictionary):
			all_dicts = false
	_check(all_dicts and node.frames.size() == 7,
			"polish A4: all %d loaded frames are Dictionaries" % node.frames.size())

	node.free()
