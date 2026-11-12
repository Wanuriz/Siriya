extends SceneTree
## Headless test for the chronicler dialog icon (assets/ui/scribe_icon.png).
##
## No frames awaited, no scene tree changes. On success prints SCRIBE_ICON_OK
## and exits with code 0; on any failure exits with code 1.

const ICON_PATH := "res://assets/ui/scribe_icon.png"
const PALETTE_PATH := "res://art/palette_v3.hex"
const EXPECTED_SIZE := Vector2i(48, 48)
const OPAQUE_MIN := 350
const OPAQUE_MAX := 1500
const UNIQUE_COLORS_MAX := 16

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


func _load_palette() -> Dictionary:
	var out := {}
	var f := FileAccess.open(PALETTE_PATH, FileAccess.READ)
	if f == null:
		return out
	while not f.eof_reached():
		var line: String = f.get_line().strip_edges().to_upper()
		if line.length() == 6:
			out[line] = true
	return out


func _run() -> void:
	# --- file exists and loads -----------------------------------------------
	if not FileAccess.file_exists(ICON_PATH):
		print("TEST: FAIL - %s does not exist" % ICON_PATH)
		return
	var bytes := FileAccess.get_file_as_bytes(ICON_PATH)
	var img := Image.new()
	var err := img.load_png_from_buffer(bytes)
	if err != OK:
		print("TEST: FAIL - cannot decode PNG: %s" % ICON_PATH)
		return

	# --- size and format ------------------------------------------------------
	_check(Vector2i(img.get_width(), img.get_height()) == EXPECTED_SIZE,
			"size is exactly 48x48 (got %dx%d)" % [img.get_width(), img.get_height()])
	var has_alpha_format: bool = img.get_format() in [
			Image.FORMAT_RGBA8, Image.FORMAT_RGBA4444, Image.FORMAT_RGBA16,
			Image.FORMAT_LA8]
	_check(has_alpha_format, "format has an alpha channel (format %d)" % img.get_format())

	# --- alpha is binary (0 or 255 only) ---------------------------------------
	var binary_alpha := true
	for y in img.get_height():
		for x in img.get_width():
			var a := img.get_pixel(x, y).a8
			if a != 0 and a != 255:
				binary_alpha = false
	_check(binary_alpha, "alpha is only 0 or 255 (no semi-transparent pixels)")

	# --- corners transparent ----------------------------------------------------
	var corners_ok := true
	for c in [Vector2i(0, 0), Vector2i(47, 0), Vector2i(0, 47), Vector2i(47, 47)]:
		if img.get_pixel(c.x, c.y).a8 != 0:
			corners_ok = false
	_check(corners_ok, "4 corner pixels are transparent")

	# --- opaque pixels: palette membership, count, unique colors ----------------
	var palette := _load_palette()
	_check(palette.size() == 48, "palette file loaded (48 colors, got %d)" % palette.size())
	var opaque := 0
	var unique := {}
	var off_palette: Array = []
	for y in img.get_height():
		for x in img.get_width():
			var c := img.get_pixel(x, y)
			if c.a8 != 255:
				continue
			opaque += 1
			var hex := "%02X%02X%02X" % [c.r8, c.g8, c.b8]
			unique[hex] = true
			if not palette.has(hex) and off_palette.size() < 5:
				off_palette.append(hex)
	_check(off_palette.is_empty(),
			"all opaque pixels are palette colors (first off-palette: %s)" % str(off_palette))
	_check(opaque >= OPAQUE_MIN and opaque <= OPAQUE_MAX,
			"opaque pixels %d in [%d..%d]" % [opaque, OPAQUE_MIN, OPAQUE_MAX])
	_check(unique.size() <= UNIQUE_COLORS_MAX,
			"unique opaque colors %d <= %d" % [unique.size(), UNIQUE_COLORS_MAX])

	if _failures == 0:
		_exit_code = 0
		print("SCRIBE_ICON_OK (%d checks)" % _checks)
	else:
		print("TEST: FAIL - %d of %d checks failed" % [_failures, _checks])
