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
	def __init__(self, command, on_done, working_dir, console=False, fallback_encoding="", **kwargs):
		threading.Thread.__init__(self)
		self.command = command
		self.on_done = on_done
		self.working_dir = working_dir
		self.kwargs = kwargs
		self.fallback_encoding = fallback_encoding
		self.console = console

	def run(self):
		try:
			if self.working_dir != "":
				os.chdir(self.working_dir)

			proc = subprocess.Popen(self.command,
				cwd=self.working_dir,
				stdout=subprocess.PIPE,
				stderr=subprocess.PIPE,
				shell=True)

			main_thread(sublime.status_message, "Running Harvey Test")
			output, error = proc.communicate()
			return_code = proc.poll()
			main_thread(sublime.status_message, "Harvey Test Complete")

			if self.console:
				main_thread(sublime.status_message, "Formatting Harvey Test Results")
				output = _make_text_safeish(output, self.fallback_encoding)
				output = re.sub(r'[\x0e-\x1f\x7f-\xff]', '', output)
				output = re.sub(r'\[\d+m', '', output)
				main_thread(sublime.status_message, "Formatting Complete")

			main_thread(self.on_done, return_code, error, output, **self.kwargs)

		except subprocess.CalledProcessError as e:
			main_thread(self.on_done, e.returncode, e.output, e.cmd)

		except OSError as e:
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
		self.addTestFiles = settings.get('addTestFiles')

	def get_parent_dir(self):
		"""
			Find the parent directory for the Node app
			that contains the harvey tests
		"""
		filename = self.view.file_name()
		dirname = os.path.dirname(filename);

		index = dirname.find(self.test_dir)
		root_dir = dirname[:index]

		if (os.path.exists(root_dir)):
			print('rootdir:', root_dir)
			return root_dir

		print('Could not find parent dir, searching view folders')
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
		addTestFiles = self.addTestFiles
		test = "%s/%s" % (test_dir, filename)
		command = '%s %s -c %s -r %s -t %s' % \
				(node, harvey, config, reporter, test)

		if addTestFiles and len(addTestFiles) > 0:
			testfiles = ",".join(addTestFiles)
			command = command + ' --addTestFiles ' + testfiles

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

		# Scroll to last line
		lines, _ = self.output_view.rowcol(self.output_view.size())
		pt = self.output_view.text_point(lines-1, 0)
		self.output_view.show(pt)


	def run_command(self, command, callback, working_dir, **kwargs):
		window = self.get_window()
		if window.active_view() and window.active_view().settings().get('fallback_encoding'):
			fallback_encoding = window.active_view().settings().get('fallback_encoding')
			kwargs['fallback_encoding'] = fallback_encoding.rpartition('(')[2].rpartition(')')[0]

		if (hasattr(self, 'reporter')):
			kwargs['console'] = (self.reporter == 'console')
		else:
			kwargs['console'] = False

		self.save_test_run(command, self.scratch, working_dir, kwargs['console'])

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
		if len(message) > 0:
			edit = new_view.begin_edit()
			new_view.insert(edit, 0, message)
			new_view.end_edit(edit)

		# Goto the first line
		pt = new_view.text_point(0, 0)
		new_view.sel().clear()
		new_view.sel().add(sublime.Region(pt))
		new_view.show(pt)

	def save_test_run(self, command, scratch, working_dir, console):
		s = sublime.load_settings("Harvey.last-run")

		s.set("last_test_run", command)
		s.set("last_test_working_dir", working_dir)
		s.set("last_test_scratch", scratch)
		s.set("last_test_console", console)

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
		self.reporter = reporter
		self.scratch = scratch

		working_dir = self.get_parent_dir()
		test_id = None

		if not all:
			test_id = self.get_test_id()
			if test_id == None or test_id == '':
				test_id = self.find_test_on_line()
			if test_id == None:
				sublime.error_message('No tests were selected')
				return

		if self.scratch:
			callback = self.on_done_scratch
		else:
			callback = self.on_done

		self.command = self.build_command(self.filename, test_id, reporter)
		self.run_command(self.command, callback, working_dir)


class HarveyLastTestCommand(HarveyCommand):

	def run(self, edit):
		self.load_config()

		s = sublime.load_settings("Harvey.last-run")
		self.command = s.get("last_test_run")
		working_dir = s.get("last_test_working_dir")
		self.scratch = s.get("last_test_scratch")
		console = s.get("last_test_console")

		if self.scratch:
			callback = self.on_done_scratch
		else:
			callback = self.on_done

		if console == True:
			self.reporter = 'console'

		self.run_command(self.command, callback, working_dir)

class HarveyNewScratchCommand(HarveyCommand):

	def run(self, edit):
		self.show_scratch('', 'SCRATCH')

class HarveyShowPanelCommand(HarveyCommand):

	def run(self, edit):
		self.get_window().run_command("show_panel", {"panel": "output.harvey"})

class HarveyOpenTestFileCommand(HarveyCommand):

	def panel_done(self, index):
		if (index < 0):
			return

		print(self.files[index])
		file_path = os.path.join(self.full_path, self.files[index][0])
		if not os.path.exists(file_path):
			print('File not found:', file_path)
			return

		self.get_window().open_file(file_path)

	def run(self, edit):
		self.load_config()

		parent_dir = self.get_parent_dir()
		full_path = os.path.join(parent_dir, self.test_dir)
		if not os.path.exists(full_path):
			print('Could not find path:', full_path)
			return

		self.full_path = full_path
		for root, dirs, files in os.walk(full_path):
			self.files = sorted([[f, os.path.join(root, f)] for f in files if f.endswith('json')])
			self.files.append(['-'*80, '', ''])
			break

		self.quick_panel(self.files, self.panel_done, sublime.MONOSPACE_FONT)

class HarveyGoToCommand(HarveyCommand):

	def panel_done(self, index):
		if index < 0:
			return

		key = self.data.keys()[index]
		self.selection = self.data[key]
		if isinstance(self.selection, list):
			print('is list: ', str(self.selection))
		elif self.selection.hasattr('keys'):
			self.start(self.selection)

	def panel_complete(self, index):
		if index < 0:
			return

		selection = self.selection[index]
		lineno = 0
		for line in self.lines:
			if line.contains('"id": ' + selection):
				# Goto line
				pt = self.view.text_point(lineno, 0)
				self.view.sel().clear()
				self.view.sel().add(sublime.Region(pt))
				self.view.show(pt)

				break

			lineno += 1

	def complete(self, data):
		keys = data.keys()
		self.quick_panel(keys, self.panel_complete, sublime.MONOSPACE_FONT)

	def start(self, data):
		keys = data.keys()
		self.quick_panel(keys, self.panel_done, sublime.MONOSPACE_FONT)

	def run(self, edit):
		self.load_config()

		filename = self.view.file_name()
		if not os.path.exists(filename):
			print('File not found:', filename)
			return

		f = open(filename, 'r')
		self.lines = f.readlines()
		f.close()


		content = "".join(self.lines)
		self.data = json.loads(content)
		self.start(self.data)

class HarveyGoToTestCommand(HarveyCommand):

	def panel_done(self, index):
		if index < 0:
			return

		key = self.data.keys()[index]
		self.selection = self.data[key]
		if isinstance(self.selection, list):
			print('is list: ', str(self.selection))
		elif self.selection.hasattr('keys'):
			self.start(self.selection)

	def panel_complete(self, index):
		if index < 0:
			return

		test = self.data["tests"][index]
		word = test["id"]
		view = self.view

		pattern = re.escape('"id": "' + word + '"')
		r1 = view.find(pattern, 0)
		if not r1:
			sublime.error_message("No definition found for: " + test["id"])
			return

		# Setup Region to be highlighted
		def_line_region = view.line(r1)
		def_line = view.substr(def_line_region)
		lindex = def_line.find(word)
		select_region_start = def_line_region.a + lindex
		select_region_end = select_region_start + len(word)
		select_region = sublime.Region(select_region_start, select_region_end)

		view.sel().clear()
		view.sel().add(select_region)

		# Scroll to the line where the definition exists
		view.show(select_region)


	def complete(self, data):
		keys = data.keys()
		self.quick_panel(keys, self.panel_complete, sublime.MONOSPACE_FONT)

	def start(self, data):
		keys = [test["id"]for test in data['tests']]
		self.quick_panel(keys, self.panel_complete, sublime.MONOSPACE_FONT)

	def run(self, edit):
		self.load_config()

		filename = self.view.file_name()
		if not os.path.exists(filename):
			print('File not found:', filename)
			return

		f = open(filename, 'r')
		self.lines = f.readlines()
		f.close()

		content = "".join(self.lines)
		self.data = json.loads(content)
		self.start(self.data)


class HarveyGoToDefinitionCommand(HarveyCommand):

	p = re.compile('\"')

	def find_word_in_quotes(self, line, index):
		if line[index] == '"':
			index = index - 1

		m = self.p.search(line[index:])
		if not m:
			raise Exception('No quotes found in line')

		rindex = index + m.span()[0]
		lindex = line[:index].rfind('"')

		if lindex < 0:
			raise Exception('No quotes found in line')

		return line[lindex+1:rindex]

	def run(self, edit, forward = True, sub_words = False):
		"""
			Searches for the definition of the word highlighted
			within the Harvey test file.

			This command will search for the pattern:
				"id": "<word>"
			where <word> is the word either highlighted, or
			the word near the cursor.
		"""
		view = self.view
		print(self.view.sel())
		# Find the region where the cursor is located
		region = self.view.sel()[0]
		# Find the line based on the region
		line_region = view.line(region)
		# Find the index of the cursor on the line
		index = region.b - line_region.a
		# Get the line as a string
		line = view.substr(line_region)
		# Find the word in double quotes
		try:
			word = self.find_word_in_quotes(line, index)
		except Exception as e:
			print(e)
			return

		pattern = '"id": "' + word + '"'
		r1 = view.find(pattern, 0)
		if not r1:
			sublime.error_message("No definition found for: " + word)
			return

		# Setup Region to be highlighted
		def_line_region = view.line(r1)
		def_line = view.substr(def_line_region)
		lindex = def_line.find(word)
		select_region_start = def_line_region.a + lindex
		select_region_end = select_region_start + len(word)
		select_region = sublime.Region(select_region_start, select_region_end)

		view.sel().clear()
		view.sel().add(select_region)

		# Scroll to the line where the definition exists
		view.show(select_region)


# class AutoCompleteCommand(sublime_plugin.EventListener):

#     def on_query_completions(self, view, prefix, locations):
#     	print 'on_query_completions'
#         window = sublime.active_window()
#         views = window.views()
#         print len(views)
#         print '-', view.buffer_id()
#         for v in views:
#         	print v.buffer_id()
#         print 'pre:', prefix
#         print 'sel.a:', view.sel()[0].a

#         # get results from each tab
#         results = [v.extract_completions(prefix) for v in window.views() if v.buffer_id() != view.buffer_id()]
#         print results
#         results = [(item,item) for sublist in results for item in sublist] #flatten
#         results = list(set(results)) # make unique
#         results.sort() # sort
#         return results

	# def on_post_save(self, view):
	# 	import inspect
	# 	print 'EventListener'
	# 	print inspect.getmembers(sublime, predicate=inspect.isfunction)

# class HarveyTest(HarveyCommand):
# 	def run(self, edit):
# 		import inspect
# 		print inspect.getdoc(sublime.View)