extends Node2D
## Minimal location root script: F1 opens the bazaar, F2 opens the oasis,
## F3 opens chapter 0.
##
## Pressing the key of the current location is a no-op. This script does not
## touch GameState: it persists across switches on its own because it is an
## autoload (docs/ARCHITECTURE.md section 3).

const SCENES: Dictionary = {
	KEY_F1: "res://scenes/locations/bazaar.tscn",
	KEY_F2: "res://scenes/locations/oasis.tscn",
	KEY_F3: "res://scenes/chapters/chapter0.tscn",
}


func _unhandled_input(event: InputEvent) -> void:
	var key_event := event as InputEventKey
	if key_event == null or not key_event.pressed or key_event.echo:
		return
	if not SCENES.has(key_event.keycode):
		return
	var target: String = SCENES[key_event.keycode]
	if target == scene_file_path:
		return
	get_tree().change_scene_to_file(target)
