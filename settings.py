import sublime

import os.path


def fix_path(path, project_dir=None):
    """Resolves absolute path:
        absolute path is reported as is
        resolve paths with user home (~)
        other relative paths resolved against project dir"""
    path = os.path.expanduser(path)
    if not os.path.isabs(path) and project_dir:
        path = os.path.join(project_dir, path)
    return os.path.abspath(path)


class Settings(object):
    """Code search settings for the project.

    Attributes:
        csearch_path: The path to the csearch command.
        cindex_path: The path to the cindex command.
        index_filename: An optional path to a csearchindex file.
        paths_to_index: An optional list of paths to index.
    """

    def __init__(self, csearch_path, cindex_path, index_filename=None,
                 paths_to_index=None):
        self.csearch_path = csearch_path
        self.cindex_path = cindex_path
        self.index_filename = index_filename
        self.paths_to_index = paths_to_index or []

    def __eq__(self, other):
        return (isinstance(other, self.__class__) and
                self.csearch_path == other.csearch_path and
                self.cindex_path == other.cindex_path and
                self.index_filename == other.index_filename and
                self.paths_to_index == other.paths_to_index)

    def __ne__(self, other):
        return not self.__eq__(other)

    def __hash__(self):
        # Not really needed, so a very dumb implementation to just be correct.
        return 42

    def __repr__(self):
        s = ('{0}(csearch_path={1}; cindex_path={2}; index_filename={3};'
             ' paths_to_index={4})')
        return s.format(self.__class__, self.csearch_path, self.cindex_path,
                        self.index_filename, self.paths_to_index)


def get_project_settings(folders, index_project_folders=False):
    """Gets the Code Search settings for the current project.

    Args:
        folders: List of open folders
    Returns:
        A Settings object describing the code search settings.
    """
    settings = sublime.load_settings('AtlasCodeSearch.sublime-settings')
    path_cindex = settings.get('path_cindex')
    path_csearch = settings.get('path_csearch')
    search_folders = settings.get("search_path")

    index_filename = None
    paths_to_index = []

    if not isinstance(search_folders, list):
        search_folders = []

    # discover tree root
    project_roots = list(filter(None, map(discover_root, folders)))
    search_paths = map(lambda root: build_search_paths(root, search_folders), project_roots)

    if project_roots:
        # Use the first project root
        index_filename = os.path.join(project_roots[0], '.cindex')

    for paths in search_paths:
        paths_to_index.extend(paths)

    print(paths_to_index)

    return Settings(path_csearch, path_cindex,
                    index_filename=index_filename,
                    paths_to_index=paths_to_index)


def build_search_paths(project_root, search_folders):
    if not search_folders:
        return [project_root]

    folders = []
    for folder in search_folders:
        location = os.path.join(project_root, folder)
        if os.path.exists(location):
            folders.append(location)

    return folders


def discover_root(directory):
    '''
    Walk the directory bottoms-up to find the '.tree_root' file
    '''
    root_file_marker = ".tree_root"
    current_directory = directory

    while True:
        # Check if the .tree_root identifier is at this directory level
        filepath = os.path.join(current_directory, root_file_marker)
        if os.path.isfile(filepath):
            return current_directory

        if current_directory == '/':
            return None
        else:
            # Otherwise, pop up a level, search again
            current_directory = os.path.dirname(current_directory)

    return None
