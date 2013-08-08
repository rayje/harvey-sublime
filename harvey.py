import sublime
import sublime_plugin
import os
import subprocess
import json
import re
import threading

def main_thread(callback, *args, **kwargs):
    # sublime.set_timeout gets used to send things onto the main thread
    # most sublime.[something] calls need to be on the main thread
    sublime.set_timeout(functools.partial(callback, *args, **kwargs), 0)

def _make_text_safeish(text, fallback_encoding, method='decode'):
    try:
        unitext = getattr(text, method)('utf-8')
    except (UnicodeEncodeError, UnicodeDecodeError):
        unitext = getattr(text, method)(fallback_encoding)
    return unitext

class HarveyThread(threading.Thread):
	def __init__(self, command, on_done, working_dir):
		threading.Thread.__init__(self)
		self.command = command
		self.on_done = on_done
		self.working_dir = working_dir

	def run(self):
		try:
			shell = os.name == 'nt'
			if self.working_dir != "":
				os.chdir(self.working_dir)

			proc = subprocess.Popen(self.command,
				stdout=subprocess.PIPE, 
				stderr=subprocess.STDOUT,
				shell=shell, 
				universal_newlines=True)

			output, error = proc.communicate()
			return_code = proc.poll()

			main_thread(self.on_done,
				_make_text_safeish(output, self.fallback_encoding), **self.kwargs)
		except subprocess.CalledProcessError, e:
			main_thread(self.on_done, e.returncode)
		except OSError, e:
			if e.errno == 2:
				main_thread(sublime.error_message, "Git binary could not be found in PATH\n\nConsider using the git_command setting for the Git plugin\n\nPATH is: %s" % os.environ['PATH'])
			else:
				raise e


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

	def get_window(self):
		return self.view.window()

	def load_config(self):
		settings = sublime.load_settings("Harvey.sublime-settings")
		self.test_dir = settings.get("harvey-test-dir")
		self.node = settings.get("node")
		self.theme = settings.get("theme")
		self.syntax = settings.get('syntax')

	def get_parent_dir(self):
		"""
			Find the parent directory for the Node app
			that contains the harvey tests
		"""
		folders = self.view.window().folders()
		last_folder = ''

		for folder in folders:
			if folder.endswith(self.test_dir):
				return folder[:folder.index(self.test_dir)]
			last_folder = folder

		return last_folder

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

	def run_cmd(self, cwd, cmd):
		"""
			Run a command using the shell
		"""
		proc = subprocess.Popen(cmd,
								cwd=cwd,
								shell=True,
								stdout=subprocess.PIPE,
								stderr=subprocess.PIPE)
		output, error = proc.communicate()
		return_code = proc.poll()

		return (return_code, error, output.decode('utf8'))

	def run_test(self, cwd, filename, reporter="console", test_id=None):
		cmd = '%s node_modules/harvey/bin/harvey -t %s/%s -r %s -c test/integration/config.json' % \
					(self.node, self.test_dir, filename, reporter)

		if test_id != None:
			tags = ' --tags "%s"' % (test_id)
			cmd = cmd + tags

		return run_cmd(cwd, cmd)

	def _output_to_view(self, output_file, output, clear=False, **kwargs):
		output_file.set_syntax_file(self.syntax)
		edit = output_file.begin_edit()
		if clear:
			region = sublime.Region(0, self.output_view.size())
			output_file.erase(edit, region)
		output_file.insert(edit, 0, output)
		output_file.end_edit(edit)

	def show_panel(self, output, **kwargs):
		if not hasattr(self, 'output_view'):
			self.output_view = self.get_window().get_output_panel("harvey")
		self.output_view.set_syntax_file(self.syntax)
		self.output_view.set_read_only(False)
		self._output_to_view(self.output_view, output, clear=True, **kwargs)
		self.output_view.set_read_only(True)
		self.get_window().run_command("show_panel", {"panel": "output.harvey"})


class HarveyRunJsonCommand(HarveyCommand):

	def run(self, edit):
		self.window = self.view.window()
		self.load_config()

		cwd = self.get_parent_dir()
		file_name = os.path.basename(self.view.file_name())
		test_name = self.get_test_name()

		new_view = None
		new_view = self.window.new_file()
		new_view.set_scratch(True)

		cmd = '%s node_modules/harvey/bin/harvey -t %s/%s -r json --tags "%s" -c test/integration/config.json' % \
					(self.node, self.test_dir, file_name, test_name)

		if new_view != None:
			ed = new_view.begin_edit()

			rc, error, result = run_cmd(cwd, cmd)
			if rc != 0:
				message = "`%s` exited with a status code of %s\n\n%s" % (cmd, rc, error)
			else:
				message = result
			message = message + '\n\n' + cmd

			new_view.insert(ed, 0, message)
			new_view.end_edit(ed)

class HarveySingleTestCommand(HarveyCommand):

	def run(self, edit):
		self.window = self.view.window()
		self.load_config()

		working_dir = self.get_parent_dir()
		file_name = os.path.basename(self.view.file_name())
		test_name = self.get_test_name()

		cmd = '%s node_modules/harvey/bin/harvey -t %s/%s -r console --tags "%s" -c test/integration/config.json' % \
					(self.node, self.test_dir, file_name, test_name)

		self.run_shell_command(cmd, working_dir)

	def display_results(self):
		self.panel = self.window.get_output_panel("exec")
		self.window.run_command("show_panel", {"panel": "output.exec"})
		self.panel.settings().set("color_scheme", self.theme)
		self.panel.set_syntax_file(self.syntax)

class HarveyAllTestsCommand(HarveyCommand):

	def run(self, edit):
		self.window = self.view.window()
		self.load_config()

		working_dir = self.get_parent_dir()
		file_name = os.path.basename(self.view.file_name())

		cmd = '%s node_modules/harvey/bin/harvey -t %s/%s -r console -c test/integration/config.json' % \
					(self.node, self.test_dir, file_name)

		self.run_shell_command(cmd, working_dir)

	def display_results(self):
		self.panel = self.window.get_output_panel("exec")
		self.window.run_command("show_panel", {"panel": "output.exec"})
		self.panel.settings().set("color_scheme", self.theme)
		self.panel.set_syntax_file(self.syntax)

class HarveySelectTestCommand(HarveyCommand):

	def panel_done(self, picked):
		test_id = self.test_ids[picked]

		working_dir = self.get_parent_dir()
		filename = os.path.basename(self.view.file_name())

		rc, error, result = self.run_test(working_dir, filename, test_id=test_id)
		if rc == 0:
			self.show_panel(result)
		else:
			self.show_panel(error + "\n\n" + result)

	def quick_panel(self, *args, **kwargs):
		self.get_window().show_quick_panel(*args, **kwargs)

	def run(self, edit):
		filename = os.path.basename(self.view.file_name())
		if not filename.endswith('.json'):
			sublime.error_message('File must be a Harvey json file.')
			return

		self.load_config()

		entireDocument = sublime.Region(0, self.view.size())
		selection = self.view.substr(entireDocument)

		try:
			hvy = json.loads(selection)
			self.test_ids = [test["id"] for test in hvy["tests"]]
			self.quick_panel(self.test_ids, self.panel_done, sublime.MONOSPACE_FONT)
		except Exception as e:
			sublime.error_message(str(e))

class HarveyTestCommand(HarveyCommand):

	def run(self, edit):
		p = re.compile('\s*"id":\s*"(.*)"')
		region = self.view.sel()[0]

		line = self.view.substr(self.view.line(region))

		m = p.match(line)
		if (m):
			print m.group(1)
		else:
			print "no match"
