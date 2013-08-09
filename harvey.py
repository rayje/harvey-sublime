import sublime
import sublime_plugin
import os
import subprocess
import json
import re
import threading
import functools

def main_thread(callback, *args, **kwargs):
	# sublime.set_timeout gets used to send things onto the main thread
	# most sublime.[something] calls need to be on the main thread
	sublime.set_timeout(functools.partial(callback, *args, **kwargs), 0)

class HarveyThread(threading.Thread):
	def __init__(self, command, on_done, working_dir, **kwargs):
		threading.Thread.__init__(self)
		self.command = command
		self.on_done = on_done
		self.working_dir = working_dir
		self.kwargs = kwargs

	def run(self):
		try:
			if self.working_dir != "":
				os.chdir(self.working_dir)

			proc = subprocess.Popen(self.command,
				cwd=self.working_dir,
				stdout=subprocess.PIPE,
				stderr=subprocess.PIPE,
				shell=True)

			output, error = proc.communicate()
			return_code = proc.poll()

			main_thread(self.on_done, return_code, error, output, **self.kwargs)

		except subprocess.CalledProcessError, e:
			main_thread(self.on_done, e.returncode, e.output, e.cmd)

		except OSError, e:
			if e.errno == 2:
				error_message = "Node binary could not be found in PATH\n\nPATH is: %s" % os.environ['PATH']
				main_thread(sublime.error_message, error_message)
			else:
				raise e


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

	def get_test_id(self):
		return self.view.substr(self.view.sel()[0])

	def build_command(self, filename, test_id=None, reporter="console"):
		harvey = 'node_modules/harvey/bin/harvey'
		config = 'test/integration/config.json'
		node = self.node
		test_dir = self.test_dir
		test = "%s/%s" % (test_dir, filename)
		command = '%s %s -c %s -r %s -t %s' % \
				(node, harvey, config, reporter, test)

		if test_id:
			tags = ' --tags "%s"' % test_id
			command = command + tags

		return command

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

	def run_command(self, command, callback, working_dir, **kwargs):
		thread = HarveyThread(command, callback, working_dir, **kwargs)
		thread.start()

	def quick_panel(self, *args, **kwargs):
		self.get_window().show_quick_panel(*args, **kwargs)

	def on_done(self, rc, error, result):
		if len(result) and rc == 0:
			self.show_panel(result)
		else:
			self.show_panel(self.command + '\n\n' + error + "\n\n" + result)

	def show_scratch(self, message, title):
		new_view = self.get_window().new_file()
		new_view.set_scratch(True)
		new_view.set_name(title)
		edit = new_view.begin_edit()
		new_view.insert(edit, 0, message)
		new_view.end_edit(edit)


class HarveyRunJsonCommand(HarveyCommand):

	def run(self, edit):
		self.load_config()

		working_dir = self.get_parent_dir()
		filename = os.path.basename(self.view.file_name())
		test_id = self.get_test_id()

		self.command = self.build_command(filename, test_id)
		self.run_command(self.command, self.on_done, working_dir)

	def on_done(self, rc, error, result):
		if rc != 0:
			message = "`%s` exited with a status code of %s\n\n%s" % (self.command, rc, error)
		else:
			message = result
		message = message + '\n\n' + self.command

		self.show_scratch(message, 'HARVEY CONSOLE')


class HarveySingleTestCommand(HarveyCommand):

	def run(self, edit):
		self.load_config()

		working_dir = self.get_parent_dir()
		filename = os.path.basename(self.view.file_name())
		test_id = self.get_test_id()

		self.command = self.build_command(filename, test_id, "json")
		self.run_command(self.command, self.on_done, working_dir)


class HarveyAllTestsCommand(HarveyCommand):

	def run(self, edit):
		self.load_config()

		working_dir = self.get_parent_dir()
		filename = os.path.basename(self.view.file_name())

		self.command = self.build_command(filename)
		self.run_command(self.command, self.on_done, working_dir)


class HarveySelectTestCommand(HarveyCommand):
	"""
		The HarveySelectTestCommand display all the tests defined
		in a Harvey JSON test file in a list.

		Selecting a test from the list will run the test.
	"""

	def panel_done(self, picked):
		test_id = self.test_ids[picked]
		working_dir = self.get_parent_dir()

		self.command = self.build_command(self.filename, test_id, "json")
		self.run_command(self.command, self.on_done, working_dir)

	def run(self, edit):
		"""
			Start point for the SelectTest command.
		"""
		self.filename = os.path.basename(self.view.file_name())
		if not self.filename.endswith('.json'):
			sublime.error_message('File must be a Harvey json file.')
			return

		self.load_config()

		entireDocument = sublime.Region(0, self.view.size())
		selection = self.view.substr(entireDocument)

		try:
			test_json = json.loads(selection)
			self.test_ids = [test["id"] for test in test_json["tests"]]
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
