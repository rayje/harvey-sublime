import sublime
import sublime_plugin
import os


class HarveyCommand(sublime_plugin.TextCommand):
	
	def load_config(self):
		s = sublime.load_settings("Harvey.sublime-settings")
		global THEME; THEME = s.get('theme')
		global SYNTAX; SYNTAX = s.get('syntax')
		global HARVEY_TEST_DIR; HARVEY_TEST_DIR = s.get("harvey-test-dir")
		global NODE; NODE = s.get("node")

	def run(self, edit):
		self.window = self.view.window()
		self.load_config()

		working_dir = self.find_partition_folder()
		file_name = os.path.basename(self.view.file_name())
		test_name = self.get_test_name()

		cmd = "%s node_modules/harvey/bin/harvey -t %s/%s -r console --tags %s" % \
					(NODE, HARVEY_TEST_DIR, file_name, test_name)

		self.run_shell_command(cmd, working_dir)

	def find_partition_folder(self):
		folders = self.view.window().folders()
		for folder in folders:
			if folder.endswith(HARVEY_TEST_DIR):
				return folder[:folder.index(HARVEY_TEST_DIR)]
			return folder

	def display_results(self):
		self.panel = self.window.get_output_panel("exec")
		self.window.run_command("show_panel", {"panel": "output.exec"})
		self.panel.settings().set("color_scheme", THEME)
		self.panel.set_syntax_file(SYNTAX)

	def get_test_name(self):
		region = self.view.sel()[0]
		text_string = self.view.substr(region)

		return text_string

	def run_shell_command(self, command, working_dir):
		if not command:
			return False

		self.view.window().run_command("exec", {
			"cmd": [command],
			"shell": True,
			"working_dir": working_dir
		})

		self.display_results()