import sublime
import sublime_plugin
import os
import subprocess

def cwd_for_window(window):
    """
    Return the working directory in which the window's commands should run.

    In the common case when the user has one folder open, return that.
    Otherwise, return one of the following (in order of preference):
        1) One of the open folders, preferring a folder containing the active
           file.
        2) The directory containing the active file.
        3) The user's home directory.
    """
    folders = window.folders()
    if len(folders) == 1:
        return folders[0]
    else:
        active_view = window.active_view()
        active_file_name = active_view.file_name() if active_view else None
        if not active_file_name:
            return folders[0] if len(folders) else os.path.expanduser("~")
        for folder in folders:
            if active_file_name.startswith(folder):
                return folder
        return os.path.dirname(active_file_name)

def run_cmd(cwd, cmd):
	proc = subprocess.Popen(cmd, cwd=cwd, shell=True,
							stdout=subprocess.PIPE, stderr=subprocess.PIPE)
	output, error = proc.communicate()
	return_code = proc.poll()
	return (return_code, error, output.decode('utf8'))

class HarveyTestCommand(sublime_plugin.TextCommand):

	def run(self, edit):
		self.window = self.view.window()
		new_view = None
		new_view = self.window.new_file()

		cwd = cwd_for_window(self.window)

		if new_view != None:
			ed = new_view.begin_edit()

			rc, error, result = run_cmd(cwd, 'ls -l')
			if rc != 0:
				message = "`%s` exited with a status code of %s\n\n%s" % (cmd, return_code, error)
			else:
				message = result

			new_view.insert(ed, 0, message)
			new_view.end_edit(ed)

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

		cmd = 'echo ' + cmd

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