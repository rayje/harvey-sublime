harvey-sublime plugin
=========================

Features
--------

  - Run harvey tests (all tests from file / single test)

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

Mac:
 - Run single harvey test (console): `Command-Shift-R`
 - Run single harvey test (json): `Command-Shift-O`
 - Run all tests in harvey test file (console): `Command-Shift-A`

Linux/Windows:
 - Run single harvey test (console): `Ctrl-Shift-R`
 - Run single harvey test (json): `Ctrl-Shift-O`
 - Run all tests in harvey test file (console): `Ctrl-Shift-A`

Configuring
-----------
There are a few settings available to customize the harvey-sublime plugin. For the latest information on what settings are available, select the menu item `Preferences->Package Settings->Harvey->Settings - Default`.

Do **NOT** edit the default harvey-sublime settings. Your changes will be lost when the plugin is updated. ALWAYS edit the user harvey-sublime settings by selecting `Preferences->Package Settings->Harvey->Settings - User`. Note that individual settings you include in your user settings will _completely_ replace the corresponding default setting, so you must provide that setting in its entirety.

### Settings
The following is a description of the settings that can be overridden in the settings file:

* ***node*** - This is the location where the node executable lives. By default it expects the executable to be on the user's PATH. To configure the plugin to use another version of node.

* ***harvey-test-dir*** - This is the directory within the current project where the harvey tests live. 
		(Default: test/integration)

Future
------

 - Run last harvey test(s): `Command-Shift-E`
