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

def _make_text_safeish(text, fallback_encoding, method='decode'):
	# The unicode decode here is because sublime converts to unicode inside
	# insert in such a way that unknown characters will cause errors, which is
	# distinctly non-ideal... and there's no way to tell what's coming out of
	# git in output. So...
	try:
		unitext = getattr(text, method)('utf-8')
	except (UnicodeEncodeError, UnicodeDecodeError):
		unitext = getattr(text, method)(fallback_encoding)
	return unitext

class HarveyThread(threading.Thread):
	def __init__(self, command, on_done, working_dir, fallback_encoding="", **kwargs):
		threading.Thread.__init__(self)
		self.command = command
		self.on_done = on_done
		self.working_dir = working_dir
		self.kwargs = kwargs
		self.fallback_encoding = fallback_encoding

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

			output = _make_text_safeish(output, self.fallback_encoding)
			output = re.sub(r'[\x0e-\x1f\x7f-\xff]', '', output)
			output = re.sub(r'\[\d+m', '', output)

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
		self.theme = "Packages/Harvey/TestConsole.hidden-tmTheme"
		self.syntax = "Packages/Harvey/TestConsole.tmLanguage"
		self.harvey = settings.get("harvey")
		self.config = settings.get("config")

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

	def find_test_on_line(self):
		p = re.compile('\s*"id":\s*"(.*)"')
		region = self.view.sel()[0]
		line = self.view.substr(self.view.line(region))

		test = None
		m = p.match(line)
		if (m):
			test = m.group(1)

		return test

	def build_command(self, filename, test_id=None, reporter="console"):
		harvey = self.harvey
		config = self.config
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
		self.output_view.settings().set("color_scheme", self.theme)
		self.output_view.set_read_only(False)
		self._output_to_view(self.output_view, output, clear=True, **kwargs)
		self.output_view.set_read_only(True)
		self.get_window().run_command("show_panel", {"panel": "output.harvey"})

	def run_command(self, command, callback, working_dir, **kwargs):
		window = self.get_window()
		if window.active_view() and window.active_view().settings().get('fallback_encoding'):
			fallback_encoding = window.active_view().settings().get('fallback_encoding')
			kwargs['fallback_encoding'] = fallback_encoding.rpartition('(')[2].rpartition(')')[0]

		self.save_test_run(command, self.scratch, working_dir)

		thread = HarveyThread(command, callback, working_dir, **kwargs)
		thread.start()

	def quick_panel(self, *args, **kwargs):
		self.get_window().show_quick_panel(*args, **kwargs)

	def on_done(self, rc, error, result):
		if len(result) and rc == 0:
			self.show_panel(result)
		else:
			self.show_panel(self.command + '\n\n' + error + "\n\n" + result)

	def on_done_scratch(self, rc, error, result):
		message = result + '\n\n' + self.command
		self.show_scratch(message, 'HARVEY CONSOLE')

	def show_scratch(self, message, title):
		new_view = self.get_window().new_file()
		new_view.set_scratch(True)
		new_view.set_name(title)
		new_view.set_syntax_file("Packages/Harvey/Harvey-JSON.tmLanguage")
		new_view.settings().set("color_scheme", "Packages/Harvey/Harvey-JSON.hidden-tmTheme")
		edit = new_view.begin_edit()
		new_view.insert(edit, 0, message)
		new_view.end_edit(edit)

	def save_test_run(self, command, scratch, working_dir):
		s = sublime.load_settings("Harvey.last-run")

		s.set("last_test_run", command)
		s.set("last_test_working_dir", working_dir)
		s.set("last_test_scratch", scratch)

		sublime.save_settings("Harvey.last-run")


class HarveySelectTestCommand(HarveyCommand):
	"""
		The HarveySelectTestCommand display all the tests defined
		in a Harvey JSON test file in a list.

		Selecting a test from the list will run the test.
	"""

	def panel_done(self, picked):
		if picked < 0:
			return

		working_dir = self.get_parent_dir()
		test_id = self.test_ids[picked][0]

		if test_id == 'All tests':
			test_id = None

		if self.scratch:
			callback = self.on_done_scratch
		else:
			callback = self.on_done

		self.command = self.build_command(self.filename, test_id, self.reporter)
		self.run_command(self.command, callback, working_dir)


	def run(self, edit, reporter="console", scratch=False):
		"""
			Start point for the SelectTest command.
		"""
		self.filename = os.path.basename(self.view.file_name())
		if not self.filename.endswith('.json'):
			sublime.error_message('File must be a Harvey json file.')
			return

		if reporter not in ['console', 'json']:
			sublime.error_message('Invalid reporter: ' + reporter)
			return

		self.load_config()
		self.reporter = reporter
		self.scratch = scratch

		entireDocument = sublime.Region(0, self.view.size())
		selection = self.view.substr(entireDocument)

		try:
			test_json = json.loads(selection)
			self.test_ids = [["All tests", "Run all tests", "File: " + self.filename]]
			tests = [[test["id"], 'Method: ' + test['request']['method'], test['request']['resource']] \
								for test in test_json["tests"]]
			self.test_ids.extend(tests)
			self.quick_panel(self.test_ids, self.panel_done, sublime.MONOSPACE_FONT)
		except Exception as e:
			sublime.error_message(str(e))


class HarveyRunTestCommand(HarveyCommand):

	def run(self, edit, all=False, reporter="console", scratch=False):
		self.filename = os.path.basename(self.view.file_name())
		if not self.filename.endswith('.json'):
			sublime.error_message('File must be a Harvey json file.')
			return

		if reporter not in ['console', 'json']:
			sublime.error_message('Invalid reporter: ' + reporter)
			return

		self.load_config()

		working_dir = self.get_parent_dir()
		test_id = None

		if not all:
			test_id = self.get_test_id()
			if test_id == None or test_id == '':
				test_id = self.find_test_on_line()
			if test_id == None:
				sublime.error_message('No tests were selected')
				return

		if scratch:
			callback = self.on_done_scratch
		else:
			callback = self.on_done

		self.command = self.build_command(self.filename, test_id, reporter)
		self.run_command(self.command, callback, working_dir)


class HarveyLastTestCommand(HarveyCommand):

	def run(self, edit):
		self.load_config()

		s = sublime.load_settings("Harvey.last-run")
		command = s.get("last_test_run")
		working_dir = s.get("last_test_working_dir")
		self.scratch = s.get("last_test_scratch")

		if self.scratch:
			callback = self.on_done_scratch
		else:
			callback = self.on_done

		self.run_command(command, callback, working_dir)