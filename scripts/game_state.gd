extends Node
## Global game state autoload: boolean flags and the fruit counter.
##
## Contract (docs/ARCHITECTURE.md section 2): exactly these five methods,
## nothing else. Flag names come from dialogue data; this node stays a dumb
## store. It survives scene changes because it is an autoload.

const FRUITS_MIN: int = 0
const FRUITS_MAX: int = 3

var _flags: Dictionary[String, bool] = {}
var _fruits: int = 0


func set_flag(flag_name: String, value: bool) -> void:
	_flags[flag_name] = value


func get_flag(flag_name: String, default: bool = false) -> bool:
	return bool(_flags.get(flag_name, default))


func has_flag(flag_name: String) -> bool:
	return _flags.has(flag_name)


func set_fruits(count: int) -> void:
	_fruits = clampi(count, FRUITS_MIN, FRUITS_MAX)


func get_fruits() -> int:
	return _fruits
