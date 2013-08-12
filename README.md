harvey-sublime plugin
=========================

A Sublime plugin to assist in test development for [Harvey][splitscreen_link]

Features
--------

The following are the commands the plugin provides:
 * ***harvey_run_test*** - Runs a single test or all tests in a Harvey test file.
 * ***harvey_select_test*** - Runs the test selected from a quick panel.
 * ***harvey_last_test*** - Re-runs the last test.

Each of the commands listed above can be output either to a scratch file or to the console.

The harvey_run_test and harvey_select_test commands both take default arguments that define how to run and output the test. Each of the arguments can be overridden by adding an entry to your default keymap file.

Installation
------------

Go to your Sublime Text 2 `Packages` directory

 - OS X:    `~/Library/Application\ Support/Sublime\ Text\ 2/Packages`
 - Windows: `%APPDATA%/Sublime Text 2/Packages/`
 - Linux:   `~/.config/sublime-text-2/Packages/`

and clone the repository:

	git clone git@github.com:rayje/harvey-sublime.git Harvey

Usage
-----

 * To run a test either highlight the Test ID or place the cursor within the Test ID text.

Keyboard mappings
-----------------

The following are the default key mapping for the commands listed above. The defaults can be overridden by adding an entry to the `Default keymap - User` file.

**Mac:**
 - Run single harvey test (reporter=console, output=console): `Command-Shift-R`
 - Run single harvey test (reporter=json, output=scratch): `Command-Shift-O`
 - Run all tests in harvey test file (reporter=console, output=scratch): `Command-Shift-A`
 - Select a test to run from quick panel (reporter=json, output=scratch): `Command-Shift-I`
 - Select a test to run from quick panel (reporter=console, output=console): `Command-Shift-U`
 - Run the last test: `Command+Shift+L`

**Linux/Windows:**
 - Run single harvey test (reporter=console, output=console): `Control-Shift-R`
 - Run single harvey test (reporter=json, output=scratch): `Control-Shift-O`
 - Run all tests in harvey test file (reporter=console, output=scratch): `Control-Shift-A`
 - Select a test to run from quick panel (reporter=json, output=scratch): `Control-Shift-I`
 - Select a test to run from quick panel (reporter=console, output=console): `Control-Shift-U`
 - Run the last test: `Control+Shift+L`

### Overriding Default Keybindings

To override the default keybindings your User Keybinding File and add the following keybindings:

**To override the harvey_run_test command**

```json
[
    {
		"keys": ["ctrl+shift+r"],
		"command": "harvey_run_test",
		"args": {
			// To run all tests in a test file, set this value to true
			"all": false,
			// Reporter to be used in the Harvey command
			// Valid reporters: console, json
			"reporter": "console",
			// To output to a scratch file, set this value to true
			// false will output to console
			"scratch": false
		}
	}
]
```

**To override the harvey_select_test command**

```json
[
    {
		"keys": ["super+shift+u"],
		"command": "harvey_select_test",
		"args": {
			// Reporter to be used in the Harvey command
			// Valid reporters: console, json
			"reporter": "console",
			// To output to a scratch file, set this value to true
			// false will output to console
			"scratch": false
		}
	}
]
```

Configuring
-----------
There are a few settings available to customize the harvey-sublime plugin. For the latest information on what settings are available, select the menu item `Preferences->Package Settings->Harvey->Settings - Default`.

Do **NOT** edit the default harvey-sublime settings. Your changes will be lost when the plugin is updated. ALWAYS edit the user harvey-sublime settings by selecting `Preferences->Package Settings->Harvey->Settings - User`. Note that individual settings you include in your user settings will _completely_ replace the corresponding default setting, so you must provide that setting in its entirety.

### Settings
The following is a description of the settings that can be overridden in the settings file:

* ***node*** - This is the location where the node executable lives. By default it expects the executable to be on the user's PATH. To configure the plugin to use another version of node.

* ***harvey-test-dir*** - This is the directory within the current project where the harvey tests live.
		(Default: test/integration)

* ***harvey*** - The location of the Harvey executable.
		(Default: node_modules/harvey/bin/harvey)

* ***config*** - The config file to be used in the command line argument.
		(Default: test/integration/config.json)