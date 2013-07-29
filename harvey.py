import sublime, sublime_plugin

class HarveyCommand(sublime_plugin.TextCommand):
	def load_config(self):
		s = sublime.load_settings("Harvey.sublime-settings")
		global THEME; THEME = s.get('theme')
		global SYNTAX; SYNTAX = s.get('syntax')

	def run(self, edit):
		self.window = self.view.window()
		self.load_config()

		self.display_results()

	def display_results(self):
		self.panel = self.window.get_output_panel("exec")
		self.window.run_command("show_panel", {"panel": "output.exec"})
		self.panel.settings().set("color_scheme", THEME)
		self.panel.set_syntax_file(SYNTAX)