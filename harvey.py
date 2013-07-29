import sublime, sublime_plugin

class HarveyCommand(sublime_plugin.TextCommand):
	def load_config(self):
		s = sublime.load_settings("Harvey.sublime-settings")
		global THEME; THEME = s.get('theme')
		global SYNTAX; SYNTAX = s.get('syntax')

	def run(self, edit):
		self.window = self.view.window()
		self.load_config()

		test = self.get_test_name()

		self.run_shell_command('echo "' + test + '"')

	def display_results(self):
		self.panel = self.window.get_output_panel("exec")
		self.window.run_command("show_panel", {"panel": "output.exec"})
		self.panel.settings().set("color_scheme", THEME)
		self.panel.set_syntax_file(SYNTAX)

	def get_test_name(self):
		region = self.view.sel()[0]
		text_string = self.view.substr(region)

		return text_string

	def run_shell_command(self, command):
		if not command:
			return False

		self.view.window().run_command("exec", {
			"cmd": [command],
			"shell": True
		})

		self.display_results()