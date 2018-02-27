import sublime
import sublime_plugin

import bisect
import functools
import operator
import os
import platform
import re
import subprocess
import threading

from AtlasCodeSearch import parser
from AtlasCodeSearch import settings


class _CsearchListener(object):
    """A listener interface for handling callbacks while processing csearch."""

    def on_finished(self, output, err=None):
        """Callback for when everything is finished.

        Args:
            output: The raw output of the csearch command.
            err: An optional error object if something unexpected happened.
        """
        pass


class CsearchCommand(sublime_plugin.WindowCommand, _CsearchListener):
    """A window command to run the search command."""

    def __init__(self, *args, **kwargs):
        super(CsearchCommand, self).__init__(*args, **kwargs)
        self._is_running = False
        self._last_search = 'file:* case:yes "'

    def run(self, query=None):
        """Runs the search command.

        Args:
            query: An optional search query.
        """
        if self._is_running:
            return
        self._is_running = True

        if query:
            self._on_search(query)
            return
        self.window.show_input_panel(
            'csearch', self._last_search, self._on_search, None,
            functools.partial(self._finish, None, None, cancel=True))

    def _get_results_view(self):
        view = next((view for view in self.window.views()
                     if view.name() == 'Code Search Results'), None)
        if not view:
            view = self.window.new_file()
            view.set_name('Code Search Results')
            view.set_scratch(True)
            settings = view.settings()
            settings.set('line_numbers', False)
            settings.set('gutter', False)
            settings.set('spell_check', False)
            view.set_syntax_file(('Packages/AtlasCodeSearch/'
                                  'Code Search Results.hidden-tmLanguage'))
        return view

    def _on_search(self, result):
        self._last_search = result

        view = self._get_results_view()
        self._write_message('Searching for "{0}"\n\n'.format(result),
                            view=view, erase=True)
        view.set_status('AtlasCodeSearch', 'Searching...')
        try:
            s = settings.get_project_settings(self.window.project_data(),
                                              self.window.project_file_name())
            _CsearchThread(parser.parse_query(result), self,
                           path_csearch=s.csearch_path,
                           index_filename=s.index_filename).start()
        except Exception as e:
            self._finish(None, err=e)

    def _finish(self, output, matches, err=None, cancel=False):
        self._is_running = False
        if cancel:
            return

        view = self._get_results_view()
        view.erase_status('AtlasCodeSearch')

        if err:
            self._print_error(err, output)
            return

        if not matches:
            self._write_message('No matches found\n', view=view)
            return

        query = parser.parse_query(self._last_search)
        result = '\n\n'.join((str(f) for f in matches))
        num_files = len(matches)
        num_matches = functools.reduce(operator.add,
                                       (len(r.matches) for r in matches))
        result += '\n\n{0} matches across {1} files\n'.format(num_matches,
                                                              num_files)
        self._write_message(result, view=view)

        flags = 0
        if not query.case:
            flags = sublime.IGNORECASE
        reg = view.find_all(query.query_re(), flags)
        reg = reg[1:]  # Skip the first match, it's the "title"
        view.add_regions('AtlasCodeSearch', reg, 'text.csearch', '',
                         sublime.HIDE_ON_MINIMAP | sublime.DRAW_NO_FILL)
        self.window.focus_view(view)

    def _print_error(self, err, output):
        if isinstance(err, subprocess.CalledProcessError):
            output = err.output
        view = self._get_results_view()
        msg = '{0}\n\n{1}\n'.format(err, output)
        self._write_message(msg, view=view)
        self.window.focus_view(view)

    def _write_message(self, msg, view=None, erase=False):
        if view is None:
            view = self._get_results_view()
        view.set_read_only(False)
        if erase:
            view.run_command('select_all')
            view.run_command('right_delete')
        view.run_command('append', {'characters': msg})
        view.set_read_only(True)

    def on_finished(self, output, err=None):
        matches = None
        if output:
            try:
                matches = parser.parse_search_output(output)
            except Exception as e:
                err = e
        sublime.set_timeout(
            functools.partial(self._finish, output, matches, err=err))


def fix_windows_output(output):
    """Normalize file paths in csearch output on windows platform."""

    result = []
    # replace ntpaths to posix
    r = re.compile(r"^([^:]*):([^:]*):([^:]*):(.*)$")
    for line in output.splitlines():
        m = r.match(line)
        if m:
            line = '/{0}{1}:{2}:{3}'.format(m.group(1),
                                            m.group(2).replace('\\', '/'),
                                            m.group(3),
                                            m.group(4))
        result.append(line)
    return '\n'.join(result)


class _CsearchThread(threading.Thread):
    """Runs the csearch command in a thread."""

    def __init__(self, search, listener, path_csearch='csearch',
                 index_filename=None):
        super(_CsearchThread, self).__init__()
        self._search = search
        self._listener = listener
        self._path_csearch = path_csearch
        self._index_filename = index_filename

    def run(self):
        try:
            output = self._do_search()
            self._listener.on_finished(output)
        except Exception as e:
            self._listener.on_finished(None, err=e)

    def _do_search(self):
        env = os.environ.copy()
        if self._index_filename:
            env['CSEARCHINDEX'] = self._index_filename
        try:
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        except:
            startupinfo = None
        cmd = [self._path_csearch, '-n']
        cmd.extend(self._search.args())
        proc = subprocess.Popen(cmd,
                                stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE,
                                env=env, startupinfo=startupinfo)
        output, stderr = proc.communicate()
        retcode = proc.poll()
        if retcode and stderr:
            error = subprocess.CalledProcessError(retcode, cmd)
            error.output = stderr
            raise error
        u8 = output.decode('utf-8')
        if platform.system() == 'Windows':
            return fix_windows_output(u8)
        return u8


class CodeSearchResultsGoToFileCommand(sublime_plugin.WindowCommand):
    """Window command to open the file from the search results."""

    def run(self):
        view = self.window.active_view()
        if 'Code Search Results' not in view.settings().get('syntax'):
            return

        line = view.line(view.sel()[0])

        line_nums = view.find_by_selector(
            'constant.numeric.line-number.match.csearch')
        i = bisect.bisect(line_nums, line)
        if not line.contains(line_nums[i]):
            return
        linenum = view.substr(line_nums[i])

        file_names = view.find_by_selector('entity.name.filename.csearch')
        i = bisect.bisect_left(file_names, line)
        if not i:
            return
        filename = view.substr(file_names[i - 1])

        matches = view.get_regions('AtlasCodeSearch')
        col = 0
        i = bisect.bisect(matches, line)
        if line.contains(matches[i]):
            col = matches[i].a - line.a - 6  # 6 is the amount of padding

        self.window.open_file('{0}:{1}:{2}'.format(filename, linenum, col),
                              sublime.ENCODED_POSITION)
        # TODO(pope): Consider highlighting the match


class DoubleClickCallback(sublime_plugin.WindowCommand):
    def run(self):
        self.window.run_command("code_search_results_go_to_file")
