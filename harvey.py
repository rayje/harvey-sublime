import sublime
import sublime_plugin
import os
import subprocess

def run_cmd(cwd, cmd):
	"""
		Run a command using the shell
	"""
	proc = subprocess.Popen(cmd, cwd=cwd, shell=True,
							stdout=subprocess.PIPE, stderr=subprocess.PIPE)
	output, error = proc.communicate()
	return_code = proc.poll()
	return (return_code, error, output.decode('utf8'))

class HarveyCommand(sublime_plugin.TextCommand):

	def load_config(self):
		s = sublime.load_settings("Harvey.sublime-settings")
		global THEME; THEME = s.get('theme')
		global SYNTAX; SYNTAX = s.get('syntax')
		global HARVEY_TEST_DIR; HARVEY_TEST_DIR = s.get("harvey-test-dir")
		global NODE; NODE = s.get("node")

	def find_partition_folder(self):
		folders = self.view.window().folders()
		for folder in folders:
			if folder.endswith(HARVEY_TEST_DIR):
				return folder[:folder.index(HARVEY_TEST_DIR)]
			return folder

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

class HarveyRunJsonCommand(HarveyCommand):

	def run(self, edit):
		self.window = self.view.window()
		self.load_config()

		cwd = self.find_partition_folder()
		file_name = os.path.basename(self.view.file_name())
		test_name = self.get_test_name()

		new_view = None
		new_view = self.window.new_file()

		cmd = '%s node_modules/harvey/bin/harvey -t %s/%s -r json --tags "%s" -c test/integration/config.json' % \
					(NODE, HARVEY_TEST_DIR, file_name, test_name)

		if new_view != None:
			ed = new_view.begin_edit()

			rc, error, result = run_cmd(cwd, cmd)
			if rc != 0:
				message = "`%s` exited with a status code of %s\n\n%s" % (cmd, rc, error)
			else:
				message = result

			new_view.insert(ed, 0, message)
			new_view.end_edit(ed)

class HarveySingleTestCommand(HarveyCommand):

	def run(self, edit):
		self.window = self.view.window()
		self.load_config()

		working_dir = self.find_partition_folder()
		file_name = os.path.basename(self.view.file_name())
		test_name = self.get_test_name()

		cmd = '%s node_modules/harvey/bin/harvey -t %s/%s -r console --tags "%s"' % \
					(NODE, HARVEY_TEST_DIR, file_name, test_name)

		self.run_shell_command(cmd, working_dir)

	def display_results(self):
		self.panel = self.window.get_output_panel("exec")
		self.window.run_command("show_panel", {"panel": "output.exec"})
		self.panel.settings().set("color_scheme", THEME)
		self.panel.set_syntax_file(SYNTAX)
