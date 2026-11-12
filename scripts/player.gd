extends Node2D
## Temporary placeholder player: a colored rectangle, not hero art.
##
## Horizontal movement only. The rectangle stays inside the screen and inside
## the ground band of the 480x270 frame (docs/PROJECT_CONTEXT.md section 2).

const SPEED: float = 140.0
const WIDTH: float = 20.0
const HEIGHT: float = 24.0
const Y_CENTER: float = 240.0
## Ground band is y=225..258; the rect spans Y_CENTER +/- HEIGHT/2 = 228..252.
const BAND_TOP: float = 225.0
const BAND_BOTTOM: float = 258.0
## Screen is 480 wide; keep the full rectangle on screen.
const MIN_X: float = WIDTH / 2.0
const MAX_X: float = 480.0 - WIDTH / 2.0


static func clamp_x(x: float) -> float:
	return clampf(x, MIN_X, MAX_X)


func _process(delta: float) -> void:
	var axis: float = Input.get_axis("ui_left", "ui_right")
	position.x = clamp_x(position.x + axis * SPEED * delta)
	position.y = Y_CENTER
