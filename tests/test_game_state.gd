extends SceneTree
## TDD test for res://scripts/game_state.gd (GameState, critical logic).
##
## Run headless (no frames awaited, no scene changes):
##   godot --headless --path <project_root> --script res://tests/test_game_state.gd
##
## In --script mode Godot autoloads are NOT instantiated, so the script under
## test is created manually via load(...).new().
##
## On success prints the marker STATE_TESTS_OK and exits with code 0.
## On any failed assertion (or if the script cannot be loaded/instantiated)
## exits with code 1 and prints TEST: FAIL with the failing checks.

const SCRIPT_PATH := "res://scripts/game_state.gd"
const FRUIT_MIN := 0
const FRUIT_MAX := 3

var _checks := 0
var _failures := 0
# Fail-safe default: if _run() aborts on a runtime error before reaching its
# own exit path, _initialize still quits with a non-zero code (no timeout).
var _exit_code := 1


func _initialize() -> void:
	_run()
	quit(_exit_code)


func _run() -> void:
	var gs_script: Script = load(SCRIPT_PATH)
	if gs_script == null or not gs_script.can_instantiate():
		print("TEST: FAIL - could not load/instantiate %s (file missing or parse error)" % SCRIPT_PATH)
		return
	var gs = gs_script.new()

	# Guard: all required methods must exist before we call them, so a missing
	# API is reported as a clean test failure, not a runtime crash.
	for method in ["get_fruits", "set_fruits", "get_flag", "set_flag", "has_flag"]:
		if not gs.has_method(method):
			print("TEST: FAIL - %s is missing required method: %s" % [SCRIPT_PATH, method])
			_free_if_node(gs)
			return

	# Contract pin: GameState defines EXACTLY the five contract methods and
	# nothing else (docs/ARCHITECTURE.md section 2: "nothing else may be added").
	var expected_methods := ["get_fruits", "set_fruits", "get_flag", "set_flag", "has_flag"]
	var declared_methods: Array = []
	for method_info in gs.get_script().get_script_method_list():
		declared_methods.append(method_info.name)
	var unexpected: Array = []
	for method_name in declared_methods:
		if not expected_methods.has(method_name):
			unexpected.append(method_name)
	_check(unexpected.is_empty(), "GameState has no methods beyond the contract (extra: %s)" % [unexpected])
	_check(declared_methods.size() == expected_methods.size(),
			"GameState declares all five contract methods (declared: %s)" % [declared_methods])

	# --- fruit counter -----------------------------------------------------
	_check(gs.get_fruits() == 0, "initial fruits == 0 (got %d)" % gs.get_fruits())

	gs.set_fruits(-1)
	_check(gs.get_fruits() == FRUIT_MIN, "set_fruits(-1) clamps to 0 (got %d)" % gs.get_fruits())

	gs.set_fruits(7)
	_check(gs.get_fruits() == FRUIT_MAX, "set_fruits(7) clamps to 3 (got %d)" % gs.get_fruits())

	gs.set_fruits(FRUIT_MIN)
	_check(gs.get_fruits() == FRUIT_MIN, "boundary set_fruits(0) passes through (got %d)" % gs.get_fruits())

	gs.set_fruits(FRUIT_MAX)
	_check(gs.get_fruits() == FRUIT_MAX, "boundary set_fruits(3) passes through (got %d)" % gs.get_fruits())

	# --- flags: get_flag returns the default when unset --------------------
	_check(gs.get_flag("never_set_plain") == false, "get_flag(unset) returns default false")
	_check(gs.get_flag("never_set_explicit", true) == true, "get_flag(unset, true) returns explicit default true")

	# --- flags: has_flag distinguishes 'set to false' from 'never set' -----
	gs.set_flag("off_flag", false)
	_check(gs.has_flag("off_flag") == true, "has_flag('off_flag') is true even though its value is false")
	_check(gs.get_flag("off_flag", true) == false, "get_flag('off_flag', true) returns false (stored value beats default)")
	_check(gs.has_flag("never_set_flag") == false, "has_flag('never_set_flag') is false")

	# --- flags: set_flag stores and overwrites -----------------------------
	gs.set_flag("toggle_flag", true)
	_check(gs.get_flag("toggle_flag") == true, "set_flag stores true")
	gs.set_flag("toggle_flag", false)
	_check(gs.get_flag("toggle_flag") == false, "set_flag overwrites true with false")
	gs.set_flag("toggle_flag", true)
	_check(gs.get_flag("toggle_flag") == true, "set_flag overwrites false back to true")

	_free_if_node(gs)

	if _failures == 0:
		_exit_code = 0
		print("STATE_TESTS_OK (%d checks)" % _checks)
	else:
		print("TEST: FAIL - %d of %d checks failed" % [_failures, _checks])


func _check(ok: bool, what: String) -> void:
	_checks += 1
	if ok:
		print("  ok: %s" % what)
	else:
		_failures += 1
		print("  FAIL: %s" % what)


func _free_if_node(gs) -> void:
	if gs is Node:
		gs.free()
