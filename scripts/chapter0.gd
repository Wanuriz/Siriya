extends Node2D
## Chapter 0 «Плёнка»: a viewer scene, no player, no walking.
##
## ui_accept flips through the film frames of data/chapter0.json (7 frames).
## A semi-transparent text window sits on top; gas particles run only on
## frames 2 and 7; arriving at frame 7 sets the GameState flag chapter0_done
## through the existing API. Transitions fade 0.3 s out and back; ui_accept is
## ignored while fading and on the last frame; there is no going back.

const DATA_PATH := "res://data/chapter0.json"
const BG_DIR := "res://assets/backgrounds/"
const DARK_COLOR := Color("3b3251")
const FRAME_BORDER_COLOR := Color("8d7da8")
const TEXT_COLOR := Color("f5cba9")
const LABEL_COLOR := Color("fde073")
const INDIGO_TINT := Color("363a8c")
const FADE_TIME := 0.3
const LAST_FRAME := 7

var frames: Array = []
var current_frame: int = 0
var busy: bool = false

var _fade_phase := 0        # 0 = idle, 1 = fade out, 2 = fade in
var _fade_alpha := 0.0
var _pending_frame := 0
var _blink_t := 0.0

var bg_color: ColorRect
var bg_sprite: Sprite2D
var film_frame: Node2D
var gas: CPUParticles2D
var text_label: Label
var speaker_label: Label
var blink_label: Label
var placeholder_label: Label
var fade_rect: ColorRect


func _cache_nodes() -> void:
	# Resolved explicitly (not @onready) so the setup can also run outside the
	# tree, e.g. from headless tests where _ready does not fire.
	bg_color = $BgColor
	bg_sprite = $BgSprite
	film_frame = $FilmFrame
	gas = $Gas
	text_label = $TextWindow/TextLabel
	speaker_label = $TextWindow/SpeakerLabel
	blink_label = $TextWindow/BlinkLabel
	placeholder_label = $PlaceholderLabel
	fade_rect = $Fade


func _ready() -> void:
	_cache_nodes()
	_setup_gas()
	_load_frames()
	_apply_frame(1)


func _load_frames() -> void:
	var f := FileAccess.open(DATA_PATH, FileAccess.READ)
	if f == null:
		return
	var data = JSON.parse_string(f.get_as_text())
	if data is Array:
		frames = data


func _setup_gas() -> void:
	# pixel-square particles: a 4x4 ImageTexture filled with the palette dark color
	var img := Image.create(4, 4, false, Image.FORMAT_RGBA8)
	img.fill(Color(DARK_COLOR.r, DARK_COLOR.g, DARK_COLOR.b, 0.85))
	gas.texture = ImageTexture.create_from_image(img)
	gas.amount = 40
	gas.lifetime = 6.0
	gas.emission_shape = CPUParticles2D.EMISSION_SHAPE_RECTANGLE
	gas.emission_rect_extents = Vector2(230, 4)
	gas.direction = Vector2(0, -1)
	gas.spread = 10.0
	gas.gravity = Vector2(0, -15)
	gas.initial_velocity_min = 8.0
	gas.initial_velocity_max = 18.0
	gas.scale_amount_min = 0.75
	gas.scale_amount_max = 1.5


func _process(delta: float) -> void:
	_blink_t += delta
	blink_label.visible = fmod(_blink_t, 1.0) < 0.5
	if _fade_phase == 0:
		return
	if _fade_phase == 1:
		_fade_alpha += delta / FADE_TIME
		if _fade_alpha >= 1.0:
			_fade_alpha = 1.0
			_apply_frame(_pending_frame)
			_fade_phase = 2
	elif _fade_phase == 2:
		_fade_alpha -= delta / FADE_TIME
		if _fade_alpha <= 0.0:
			_fade_alpha = 0.0
			_fade_phase = 0
			busy = false
	fade_rect.color = Color(DARK_COLOR.r, DARK_COLOR.g, DARK_COLOR.b, _fade_alpha)


func _unhandled_input(event: InputEvent) -> void:
	if event.is_action_pressed("ui_accept"):
		_advance()


func _advance() -> void:
	if busy or current_frame >= LAST_FRAME or frames.is_empty():
		return
	busy = true
	_fade_phase = 1
	_pending_frame = current_frame + 1


func _apply_frame(n: int) -> void:
	current_frame = n
	if frames.is_empty() or n < 1 or n > frames.size():
		return
	var frame: Dictionary = frames[n - 1]
	var bg: String = str(frame.get("bg", "solid"))
	film_frame.visible = bg == "solid_frame"
	placeholder_label.visible = false
	bg_sprite.visible = false
	bg_color.color = DARK_COLOR
	if bg != "solid" and bg != "solid_frame":
		var path := BG_DIR + bg
		if ResourceLoader.exists(path):
			bg_sprite.texture = load(path)
			bg_sprite.visible = true
		else:
			# placeholder for a missing background file (e.g. igloo.png):
			# solid light color from the palette + a debug label
			bg_color.color = TEXT_COLOR
			placeholder_label.visible = true
	var tint = frame.get("tint")
	bg_sprite.modulate = INDIGO_TINT if tint == "indigo" else Color.WHITE
	gas.emitting = bool(frame.get("gas", false))
	text_label.text = str(frame.get("text", ""))
	var speaker: String = str(frame.get("speaker", ""))
	speaker_label.text = speaker
	speaker_label.visible = speaker != ""
	if n == LAST_FRAME:
		GameState.set_flag("chapter0_done", true)
