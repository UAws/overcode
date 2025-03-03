#!/usr/bin/python
# -*- coding: utf-8 -*-

# PythonTidy.py
# 2006 Oct 27 . ccr

'''PythonTidy.py cleans up, regularizes, and reformats the text of
Python scripts.

===========================================
Copyright © 2006 Charles Curtis Rhode
===========================================

This program is free software; you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation; either version 2 of the License, or (at
your option) any later version.

This program is distributed in the hope that it will be useful, but
WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program; if not, write to the Free Software
Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA 02110-1301
USA.

===========================================
Charles Curtis Rhode,
1518 N 3rd, Sheboygan, WI 53081
mailto:CRhode@LacusVeris.com?subject=PythonTidy
===========================================

This script reads Python code from standard input and writes a revised
version to standard output.

Alternatively, it may be invoked with file names as arguments:

  python PythonTidy.py input output

Suffice it to say that *input* defaults to \'-\', the standard input,
and *output* defaults to \'-\', the standard output.

It means to encapsulate the wisdom revealed in:

o Rossum, Guido van, and Barry Warsaw. "PEP 8: Style Guide for Python
Code." 23 Mar. 2006. Python.org. 28 Nov. 2006
<http://www.python.org/dev/peps/pep-0008/>.

Python scripts are usually so good looking that no beautification is
required.  However, from time to time, it may be necessary to alter
the style to conform to changing standards.  This script converts
programs in a consistent way.  It abstracts the pretty presentation of
the symbolic code from the humdrum[1] process of writing it and
getting it to work.

This script assumes that the input Python code is well-formed and
works to begin with.  It doesn\'t check.  If all goes well, the output
Python code will work, too.  Of course, you are advised to test it
fully to be sure.

This script should be run only by python.2.5 (and perhaps higher) on
scripts written for that version (and perhaps lower) because of its
limited knowledge of and expectations for the abstract syntax tree
node classes returned by the *compiler* module.  It wouldn\'t hurt
much to try it from (and on) other versions, though, and it might
actually work.

Search this script for "Python Version Dependency."

Most of the Python 2.5 test suite passes through PythonTidy.py
unimpaired.  Here are some tests that don\t:

    test_cProfile.py
    test_dis.py
    test_doctest.py
    test_grammar.py
    test_inspect.py
    test_pep263.py
    test_profile.py
    test_sys.py
    test_trace.py

The more esoteric capabilities of PythonTidy.py had to be turned off
to avoid corrupting the test-suite code.  In practice, you\'ll want to
run with PERSONAL = True (See, below.) to use all the functionality,
and of course you\'ll have the good taste to find and patch all the
glitches it introduces.

[1] "Humdrum: A low cart with three wheels, drawn by one horse." The
Collaborative International Dictionary of English v.0.48.

'''



DEBUG = False
PERSONAL = False

VERSION = '1.11'  # 2007 Jan 22

# 2007 Jan 22 . v1.11 . ccr . This update implements a couple of
# well-taken user requests:

# Jens Diemer wants a module-level function, *tidy_up*, to accept file
# names or file-like objects.

# Wolfgang Grafen wants trailing spaces eliminated to avoid spurious
# differences with pre-tidied code.

# 2007 Jan 14 . v1.10 . ccr . There was a big problem with earlier
# versions: Canonical values were substituted for strings and numbers.
# For example, decimal integers were substituted for hexadecimal, and
# escaped strings for raw strings.  Authors of Python scripts usually
# use peculiar notations for peculiar purposes, and doing away with
# them negatively impacts the readability of the code.

# This version preserves the original constants (parsed by *tokenize*)
# in a literal pool indexed by the value they evaluate to.  The
# canonical values (output by *compiler*) are then translated back
# (when possible) to the original constants by looking them up in the
# literal pool.

# 2006 Dec 19 . v1.9 . ccr . If class name is a string, pass it to
# personal substitutions routine to distinguish module globals like
# gtk.VBox from class attributes like gtk.Dialog.vbox.

# 2006 Dec 17 . v1.8 . ccr . Trailing comma in function parameter list
# is not allowed in all cases.  Catch substitutions that collide with
# built-ins.

# 2006 Dec 14 . v1.7 . ccr . Track line numbers on output.
# Write a "Name Substitutions Report" on stderr.

# 2006 Dec 13 . v1.6 . ccr . A *yield* may appear in parens when it is
# the subject of an assignment; otherwise, not.

# 2006 Dec 05 . v1.5 . ccr . Strings default to single quotes when
# DOUBLE_QUOTED_STRINGS = False.  Pass the newline convention from
# input to output (transparently :-) ).

# 2006 Dec 01 . v1.4 . ccr . Tighten qualifications for in-line
# comments.  Decode string nodes.  Enclose docstrings in double
# quotes.  Allow file-name arguments.

# 2006 Nov 30 . v1.3 . ccr . Safe check against names of *compiler* .
# abstract syntax tree nodes rather than their classes to step around
# one Python Version Dependency.

import sys
import os
import codecs
import io
import re
if DEBUG:
    import token
import tokenize
import compiler

ZERO = 0
SPACE = ' '
NULL = ''
NA = -1
APOST = "'"

# Old code is parsed.  New code is generated from the parsed version,
# using these literals:

COL_LIMIT = 272
INDENTATION = '    '
ASSIGNMENT = ' = '
FUNCTION_PARAM_ASSIGNMENT = '='
FUNCTION_PARAM_SEP = ', '
LIST_SEP = ', '
SUBSCRIPT_SEP = ', '
DICT_COLON = ': '
SLICE_COLON = ':'
COMMENT_PREFIX = '#'
SHEBANG = '#!/usr/bin/python'
CODING = 'utf-8'
CODING_SPEC = '# -*- coding: %s -*-' % CODING
BLANK_LINE = NULL
KEEP_BLANK_LINES = True
ADD_BLANK_LINES_AROUND_COMMENTS = True
MAX_SEPS_BEFORE_SPLIT_LINE = 8
MAX_LINES_BEFORE_SPLIT_LIT = 2
LEFT_MARGIN = NULL
LEFTJUST_DOC_STRINGS = False
DOUBLE_QUOTED_STRINGS = False  # 2006 Dec 05
RECODE_STRINGS = False  # 2006 Dec 01
OVERRIDE_NEWLINE = None  # 2006 Dec 05

# Repertoire of name-transformation functions:

def all_lower_case(str, **attribs):
    return str.lower()


def all_upper_case(str, **attribs):
    return str.upper()


def title_case(str, **attribs):
    return str.title()


def strip_underscores(str, **attribs):
    return str.replace('_', NULL)


def insert_underscores(str, **attribs):
    return UNDERSCORE_PATTERN.sub('_\\1', str)


def is_magic(str):
    return str in ['self', 'cls'] or str.startswith('__') and str.endswith('__')


def underscore_to_camel_case(str, **attribs):
    if is_magic(str):
        return str
    else:
        return strip_underscores(title_case(camel_case_to_underscore(str)))


def camel_case_to_underscore(str, **attribs):
    if is_magic(str):
        return str
    else:
        return all_lower_case(insert_underscores(str))


def unmangle(str, **attribs):
    if str.startswith('__'):
        str = str[2:]
    return str


def munge(str, **attribs):
    """Create an unparsable name.

    """

    return '<*%s*>' % str


def substitutions(str, **attribs):
    result = SUBSTITUTE_FOR.get(str, str)
    module = attribs.get('module')  # 2006 Dec 19
    if module is None:
        pass
    else:
        result = SUBSTITUTE_FOR.get('%s.%s' % (module, str), result)
    return result


def elide_c(str, **attribs):
    return ELIDE_C_PATTERN.sub('\\1', str)


def elide_a(str, **attribs):
    return ELIDE_A_PATTERN.sub('\\1', str)


def elide_f(str, **attribs):
    return ELIDE_F_PATTERN.sub('\\1', str)


# Name-transformation scripts:

LOCAL_NAME_SCRIPT = []
GLOBAL_NAME_SCRIPT = []
CLASS_NAME_SCRIPT = []
FUNCTION_NAME_SCRIPT = []

                             # It is not wise to monkey with the
                             # spelling of function names (methods)
                             # where they are defined unless you are
                             # willing to change their spelling where
                             # they are referred to as class
                             # attributes, too.

FORMAL_PARAM_NAME_SCRIPT = []

                             # It is not wise to monkey with the
                             # spelling of formal parameters for fear
                             # of changing those of functions
                             # (methods) defined in other modules.

ATTR_NAME_SCRIPT = []

                             # It is not wise to monkey with the
                             # spelling of attributes (methods) for
                             # fear of changing those of classes
                             # defined in other modules.

# Author's preferences:

if PERSONAL:
    LEFTJUST_DOC_STRINGS = True
    LOCAL_NAME_SCRIPT.extend([unmangle, camel_case_to_underscore])
    GLOBAL_NAME_SCRIPT.extend([unmangle, camel_case_to_underscore, 
                              all_upper_case])
    CLASS_NAME_SCRIPT.extend([elide_c, underscore_to_camel_case])
    FUNCTION_NAME_SCRIPT.extend([camel_case_to_underscore])
    FORMAL_PARAM_NAME_SCRIPT.extend([elide_a, camel_case_to_underscore])
    ATTR_NAME_SCRIPT.extend([elide_f, camel_case_to_underscore, 
                            substitutions])

# Other global constants:

UNDERSCORE_PATTERN = re.compile('(?<=[a-z])([A-Z])')
COMMENT_PATTERN = re.compile('#')
SHEBANG_PATTERN = re.compile('#!')
CODING_PATTERN = re.compile('coding[=:]\\s*([.\\w\\-_]+)')
NEW_LINE_PATTERN = re.compile('(?<!\\\\)\\\\n')
UNIVERSAL_NEW_LINE_PATTERN = re.compile(r'((?:\r\n)|(?:\r)|(?:\n))')
QUOTE_PATTERN = re.compile(r'([rRuU]{,2})((?:""")|(?:%s)|(?:")|(?:%s))((?:%s)|(?:\\%s)|)' \
                           % (APOST * 3, APOST, APOST, APOST))  # 2006 Jan 14
ELIDE_C_PATTERN = re.compile('^c([A-Z])')
ELIDE_A_PATTERN = re.compile('^a([A-Z])')
ELIDE_F_PATTERN = re.compile('^f([A-Z])')
SUBSTITUTE_FOR = {
    'abday_1':'ABDAY_1',
    'abday_2':'ABDAY_2',
    'abday_3':'ABDAY_3',
    'abday_4':'ABDAY_4',
    'abday_5':'ABDAY_5',
    'abday_6':'ABDAY_6',
    'abday_7':'ABDAY_7',
    'abmon_1':'ABMON_1',
    'abmon_10':'ABMON_10',
    'abmon_11':'ABMON_11',
    'abmon_12':'ABMON_12',
    'abmon_2':'ABMON_2',
    'abmon_3':'ABMON_3',
    'abmon_4':'ABMON_4',
    'abmon_5':'ABMON_5',
    'abmon_6':'ABMON_6',
    'abmon_7':'ABMON_7',
    'abmon_8':'ABMON_8',
    'abmon_9':'ABMON_9',
    'accel_group': 'AccelGroup',
    'action_default': 'ACTION_DEFAULT',
    'action_copy': 'ACTION_COPY',
    'align_left': 'ALIGN_LEFT',
    'align_right': 'ALIGN_RIGHT',
    'align_center': 'ALIGN_CENTER',
    'alignment': 'Alignment',
    'button_press': 'BUTTON_PRESS',
    'button_press_mask': 'BUTTON_PRESS_MASK',
    'buttons_cancel': 'BUTTONS_CANCEL', 
    'can_default': 'CAN_DEFAULT',
    'can_focus': 'CAN_FOCUS',
    'cell_renderer_pixbuf': 'CellRendererPixbuf',
    'cell_renderer_text': 'CellRendererText',
    'check_button': 'CheckButton',
    'child_nodes': 'childNodes',
    'color': 'Color',
    'config_parser': 'ConfigParser',
    'cursor': 'Cursor',
    'day_1':'DAY_1',
    'day_2':'DAY_2',
    'day_3':'DAY_3',
    'day_4':'DAY_4',
    'day_5':'DAY_5',
    'day_6':'DAY_6',
    'day_7':'DAY_7',
    'dest_default_all': 'DEST_DEFAULT_ALL',
    'dialog_modal': 'DIALOG_MODAL', 
    'dict_reader': 'DictReader', 
    'dict_writer': 'DictWriter', 
    'dir_tab_forward': 'DIR_TAB_FORWARD',
    'dotall': 'DOTALL',
    'dotall': 'DOTALL',
    'enter_notify_mask': 'ENTER_NOTIFY_MASK',
    'error': 'Error',
    'event_box': 'EventBox', 
    'expand': 'EXPAND',
    'exposure_mask': 'EXPOSURE_MASK',
    'file_selection': 'FileSelection',
    'fill': 'FILL',
    'ftp': 'FTP',
    'get_attribute': 'getAttribute',
    'gtk.button': 'Button',
    'gtk.combo': 'Combo',
    'gtk.dialog': 'Dialog',
    'gtk.entry': 'Entry',
    'pixmap': 'Pixmap',
    'gtk.image': 'Image',
    'gtk.label': 'Label',
    'gtk.menu': 'Menu',
    'gtk.pack_end': 'PACK_END',
    'gtk.pack_start': 'PACK_START',
    'gtk.vbox': 'VBox',
    'gtk.window': 'Window',
    'hand2': 'HAND2',
    'hbox': 'HBox', 
    'icon_size_button': 'ICON_SIZE_BUTTON', 
    'icon_size_dialog': 'ICON_SIZE_DIALOG',
    'icon_size_dnd': 'ICON_SIZE_DND',
    'icon_size_large_toolbar': 'ICON_SIZE_LARGE_TOOLBAR',
    'icon_size_menu': 'ICON_SIZE_MENU',
    'icon_size_small_toolbar': 'ICON_SIZE_SMALL_TOOLBAR',
    'image_menu_item': 'ImageMenuItem',
    'item_factory': 'ItemFactory',
    'justify_center': 'JUSTIFY_CENTER',
    'justify_fill': 'JUSTIFY_FILL',
    'justify_left': 'JUSTIFY_LEFT',
    'justify_right': 'JUSTIFY_RIGHT',
    'list_item': 'ListItem',
    'list_store': 'ListStore',
    'menu_bar': 'MenuBar',
    'message_dialog': 'MessageDialog', 
    'message_info': 'MESSAGE_INFO', 
    'mon_1':'MON_1',
    'mon_10':'MON_10',
    'mon_11':'MON_11',
    'mon_12':'MON_12',
    'mon_2':'MON_2',
    'mon_3':'MON_3',
    'mon_4':'MON_4',
    'mon_5':'MON_5',
    'mon_6':'MON_6',
    'mon_7':'MON_7',
    'mon_8':'MON_8',
    'mon_9':'MON_9',
    'multiline': 'MULTILINE',
    'node_type': 'nodeType',
    'notebook': 'Notebook',
    'o_creat': 'O_CREAT', 
    'o_excl': 'O_EXCL',
    'o_ndelay': 'O_NDELAY',
    'o_rdwr': 'O_RDWR', 
    'p_nowait':'P_NOWAIT',
    'parsing_error': 'ParsingError',
    'pointer_motion_mask': 'POINTER_MOTION_MASK',
    'pointer_motion_hint_mask': 'POINTER_MOTION_HINT_MASK',
    'policy_automatic': 'POLICY_AUTOMATIC',
    'policy_never': 'POLICY_NEVER',
    'radio_button': 'RadioButton',
    'realized': 'REALIZED',
    'relief_none': 'RELIEF_NONE',
    'request':'Request',
    'response_cancel': 'RESPONSE_CANCEL', 
    'response_delete_event': 'RESPONSE_DELETE_EVENT',
    'response_no': 'RESPONSE_NO',
    'response_none': 'RESPONSE_NONE',
    'response_ok': 'RESPONSE_OK', 
    'response_yes': 'RESPONSE_YES',
    'scrolled_window': 'ScrolledWindow',
    'shadow_in': 'SHADOW_IN',
    'sniffer': 'Sniffer', 
    'sort_ascending': 'SORT_ASCENDING',
    'sort_descending': 'SORT_DESCENDING',
    'state_normal': 'STATE_NORMAL',
    'stock_add': 'STOCK_ADD',
    'stock_apply': 'STOCK_APPLY', 
    'stock_bold': 'STOCK_BOLD',
    'stock_cancel': 'STOCK_CANCEL',
    'stock_close': 'STOCK_CLOSE',
    'stock_convert': 'STOCK_CONVERT',
    'stock_copy': 'STOCK_COPY',
    'stock_cut': 'STOCK_CUT',
    'stock_dialog_info': 'STOCK_DIALOG_INFO',
    'stock_dialog_info': 'STOCK_DIALOG_INFO',
    'stock_dialog_question': 'STOCK_DIALOG_QUESTION',
    'stock_execute': 'STOCK_EXECUTE', 
    'stock_find': 'STOCK_FIND',
    'stock_find_and_replace': 'STOCK_FIND_AND_REPLACE',
    'stock_go_back': 'STOCK_GO_BACK',
    'stock_go_forward': 'STOCK_GO_FORWARD',
    'stock_help': 'STOCK_HELP',
    'stock_index': 'STOCK_INDEX',
    'stock_jump_to': 'STOCK_JUMP_TO',
    'stock_new': 'STOCK_NEW',
    'stock_no': 'STOCK_NO',
    'stock_ok': 'STOCK_OK',
    'stock_open': 'STOCK_OPEN',
    'stock_paste': 'STOCK_PASTE',
    'stock_preferences': 'STOCK_PREFERENCES',
    'stock_print_preview': 'STOCK_PRINT_PREVIEW',
    'stock_quit': 'STOCK_QUIT',
    'stock_refresh': 'STOCK_REFRESH',
    'stock_remove': 'STOCK_REMOVE',
    'stock_save': 'STOCK_SAVE',
    'stock_save_as': 'STOCK_SAVE_AS',
    'stock_yes': 'STOCK_YES',
    'string_io': 'StringIO',
    'style_italic': 'STYLE_ITALIC',
    'sunday': 'SUNDAY',
    'tab': 'Tab',
    'tab_array': 'TabArray',
    'tab_left': 'TAB_LEFT',
    'table': 'Table',
    'target_same_app': 'TARGET_SAME_APP',
    'target_same_widget': 'TARGET_SAME_WIDGET',
    'text_iter': 'TextIter',
    'text_node': 'TEXT_NODE',
    'text_tag': 'TextTag',
    'text_view': 'TextView',
    'text_window_text': 'TEXT_WINDOW_TEXT',
    'text_window_widget': 'TEXT_WINDOW_WIDGET',
    'text_wrapper':'TextWrapper',
    'tooltips': 'Tooltips', 
    'tree_view': 'TreeView',
    'tree_view_column': 'TreeViewColumn',
    'type_string': 'TYPE_STRING',
    'underline_single': 'UNDERLINE_SINGLE',
    'weight_bold': 'WEIGHT_BOLD',
    'window_toplevel': 'WINDOW_TOPLEVEL', 
    'wrap_none': 'WRAP_NONE',
    'wrap_word': 'WRAP_WORD',
    }


class InputUnit(object):

    """File-buffered wrapper for sys.stdin.

    """

    def __init__(self, file_in):
        object.__init__(self)
        self.is_file_like = hasattr(file_in, 'read')  # 2007 Jan 22
        if self.is_file_like:
            buffer = file_in.read()  # 2006 Dec 05
        else:
            unit = open(os.path.expanduser(file_in), 'rb')
            buffer = unit.read()  # 2006 Dec 05
            unit.close()
        self.lines = UNIVERSAL_NEW_LINE_PATTERN.split(buffer)  # 2006 Dec 05
        if len(self.lines) > 2:
            if OVERRIDE_NEWLINE is None:
                self.newline = self.lines[1]  # ... the first delimiter.
            else:
                self.newline = OVERRIDE_NEWLINE
            look_ahead = '\n'.join([self.lines[ZERO],self.lines[2]])
        else:
            self.newline = '\n'
            look_ahead = NULL
        match = CODING_PATTERN.search(look_ahead)
        if match is None:
            self.coding = 'ascii'
        else:
            self.coding = match.group(1)
        self.rewind()  # 2006 Dec 05
        return

    def rewind(self):  # 2006 Dec 05
        self.ndx = ZERO
        self.end = len(self.lines) - 1
        return self

    def __next__(self):  # 2006 Dec 05
        if self.ndx > self.end:
            raise StopIteration
        elif self.ndx == self.end:
            result = self.lines[self.ndx]
        else:
            result = self.lines[self.ndx] + '\n'
        self.ndx += 2
        return result

    def __iter__(self):  # 2006 Dec 05
        return self

    def readline(self):  # 2006 Dec 05
        try:
            result = next(self)
        except StopIteration:
            result = NULL
        return result

    def readlines(self):  # 2006 Dec 05
        self.rewind()
        return [line for line in self]

    def __str__(self):  # 2006 Dec 05
        return NULL.join(self.readlines())

    def decode(self, str):
        return str  # It will not do to feed Unicode to *compiler.parse*.


class OutputUnit(object):

    """Line-buffered wrapper for sys.stdout.

    """

    def __init__(self, file_out):
        object.__init__(self)
        self.is_file_like = hasattr(file_out, 'write')  # 2007 Jan 22
        if self.is_file_like:
            self.unit = codecs.getwriter(CODING)(file_out)
        else:
            self.unit = codecs.open(os.path.expanduser(file_out), 'wb', CODING)
        self.blank_line_count = 1
        self.margin = LEFT_MARGIN
        self.newline = INPUT.newline  # 2006 Dec 05
        self.lineno = ZERO  # 2006 Dec 14
        self.buffer = NULL 
        return

    def close(self):  # 2006 Dec 01
        self.unit.write(self.buffer)  # 2007 Jan 22
        if self.is_file_like:
            pass
        else:
            self.unit.close()
        return self

    def line_init(self, indent=ZERO, lineno=ZERO):
        self.blank_line_count = ZERO
        self.col = ZERO
        if DEBUG:
            margin = '%5i %s' % (lineno, INDENTATION * indent)
        else:
            margin = self.margin + INDENTATION * indent
        self.tab_stack = []
        self.tab_set(len(margin) + len(INDENTATION))
        self.chunks = []
        self.line_more(margin)
        return self

    def line_more(self, chunk=NULL, tab_set=False, tab_clear=False, 
                  can_split_after=False, can_break_after=False):
        self.chunks.append([chunk, tab_set, tab_clear, can_split_after, 
                           can_break_after])
        self.col += len(chunk)
        return self

    def line_term(self):

        def is_split_needed():
            width = len(chunk)
            pos = self.pos
            return pos + width > COL_LIMIT and pos > ZERO

        self.pos = ZERO
        can_split_before = False
        can_break_before = False
        for (chunk, tab_set, tab_clear, can_split_after, can_break_after) in \
            self.chunks:
            if is_split_needed():
                if can_split_before:
                    self.line_split()
                elif can_break_before:
                    self.line_break()
            self.put(chunk)  # 2006 Dec 14
            self.pos += len(chunk)
            if tab_set:
                self.tab_set(self.pos)
            if tab_clear:
                self.tab_clear()
            can_split_before = can_split_after
            can_break_before = can_break_after
        self.put(self.newline)  # 2006 Dec 05
        return self

    def line_split(self):
        self.put(self.newline)  # 2006 Dec 05
        self.pos = self.tab_forward()
        return self

    def line_break(self):
        self.put('\\%s' % self.newline)  # 2006 Dec 14
        self.pos = self.tab_forward()
        return self

    def tab_forward(self):
        if len(self.tab_stack) > 1:
            col = (self.tab_stack)[1]
        else:
            col = (self.tab_stack)[ZERO]
        self.put(SPACE * col)  # 2006 Dec 14
        return col

    def put(self, text):  # 2006 Dec 14
        self.lineno += text.count(self.newline)
        self.buffer += text  # 2007 Jan 22
        if self.buffer.endswith('\n'):
            self.unit.write(self.buffer.rstrip())
            self.unit.write('\n')
            self.buffer = NULL
        return self

    def put_blank_line(self, trace, count=1):
        count -= self.blank_line_count
        while count > ZERO:
            self.put(BLANK_LINE)  # 2006 Dec 14
            self.put(self.newline)  # 2006 Dec 05
            if DEBUG:
                self.put(str(trace))  # 2006 Dec 14
            self.blank_line_count += 1
            count -= 1
        return self

    def tab_set(self, col):
        if col > COL_LIMIT / 2:
            col = (self.tab_stack)[-1] + 4
        self.tab_stack.append(col)
        return self

    def tab_clear(self):
        if len(self.tab_stack) > 1:
            result = self.tab_stack.pop()
        else:
            result = None
        return result

    def inc_margin(self):
        self.margin += INDENTATION
        return self

    def dec_margin(self):
        self.margin = (self.margin)[:-len(INDENTATION)]
        return self


class Comments(dict):

    """Collection of comments (blank lines) parsed out of the
    input Python code and indexed by line number.

    """

    def __init__(self):
        self.literal_pool = {}  # 2007 Jan 14
        lines = tokenize.generate_tokens(INPUT.readline)
        for (token_type, token_string, start, end, line) in lines:
            if DEBUG:
                print((token.tok_name)[token_type], token_string, start, \
                    end, line)
            (self.max_lineno, scol) = start
            (erow, ecol) = end
            if token_type in [tokenize.COMMENT, tokenize.NL]:
                token_string = token_string.strip().decode(INPUT.coding)
                if SHEBANG_PATTERN.match(token_string) is not None:
                    pass
                elif CODING_PATTERN.search(token_string) is not None and \
                    self.max_lineno <= 2:
                    pass
                else:
                    token_string = COMMENT_PATTERN.sub(COMMENT_PREFIX, 
                            token_string, 1)
                    self[self.max_lineno] = [scol, token_string]
            elif token_type in [tokenize.NUMBER, tokenize.STRING]:  # 2007 Jan 14
                try:
                    token_string = token_string.strip().decode(INPUT.coding, 'backslashreplace')
                    canonical_value = repr(eval(token_string))
                    if canonical_value == token_string:
                        pass
                    else:
                        original_values = self.literal_pool.setdefault(canonical_value, [])
                        for (token, lineno) in original_values:  # 2007 Jan 17
                            if token == token_string:
                                break
                        else:
                            original_values.append([token_string, self.max_lineno])
                except:
                    pass
        self.prev_lineno = NA
        self[self.prev_lineno] = (ZERO, SHEBANG)
        self[ZERO] = (ZERO, CODING_SPEC)
        return 

    def merge(self, lineno=None, fin=False):

        def is_blank():
            return token_string in [NULL, BLANK_LINE]

        def is_blank_line_needed():
            return ADD_BLANK_LINES_AROUND_COMMENTS and not (is_blank() and 
                    KEEP_BLANK_LINES)

        if fin:
            lineno = self.max_lineno + 1
        on1 = True
        found = False
        while self.prev_lineno < lineno:
            if self.prev_lineno in self:
                (scol, token_string) = self[self.prev_lineno]
                if on1 and is_blank_line_needed():
                    OUTPUT.put_blank_line(1)
                if is_blank():
                    if KEEP_BLANK_LINES:
                        OUTPUT.put_blank_line(2)
                else:

                    OUTPUT.line_init().line_more('%s%s' % (SPACE * scol, 
                            token_string)).line_term()
                    found = True
                on1 = False
            self.prev_lineno += 1
        if found and is_blank_line_needed() and not fin:
            OUTPUT.put_blank_line(3)
        return self

    def put_inline(self, lineno):
        on1 = True
        while self.prev_lineno <= lineno:
            if self.prev_lineno in self:
                (scol, token_string) = self[self.prev_lineno]
                if token_string in [NULL]:
                    pass
                else:
                    if on1:
                        OUTPUT.line_more(SPACE * 2)
                        col = OUTPUT.col
                    else:
                        OUTPUT.line_init().line_more(SPACE * col)
                    OUTPUT.line_more(token_string).line_term()
                    on1 = False
            self.prev_lineno += 1
        if on1:
            OUTPUT.line_term()
        return self


class Name(list):  # 2006 Dec 14

    """Maps new name to old names.

    """

    def __init__(self, new):
        self.new = new
        self.is_reported = False
        return

    def append(self, item):
        if item in self:
            pass
        else:
            list.append(self, item)
        return

    def rept_collision(self, key):
        self.append(key)  # 2006 Dec 17
        if len(self) == 1:
            pass
        elif self.is_reported:
            pass
        else:
            sys.stderr.write("Error:  %s ambiguously replaced by '%s' at line %i.\n" % \
                             (str(self), self.new, OUTPUT.lineno + 1))
            self.is_reported = True
        return self

    def rept_external(self, expr):
        if isinstance(expr, NodeName):
            expr = expr.name.str
        else:
            expr = str(expr)
        if expr in ['self','cls']:
            pass
        elif self.new == self[ZERO]:
            pass
        else:
            sys.stderr.write("Warning:  '%s.%s,' defined elsewhere, replaced by '.%s' at line %i.\n" % \
                             (expr, self[ZERO], self.new, OUTPUT.lineno + 1))
        return self


class NameSpace(list):

    """Dictionary of names (variables).
    
    Actually a list of dictionaries.  The current scope is the top one
    (ZEROth member).

    """

    def push_scope(self):
        self.insert(ZERO, {})
        return self

    def pop_scope(self):
        return self.pop(ZERO)

    def make_name(self, name, rules):
        name = name.get_as_str()
        key = name
        for rule in rules:
            name = rule(name)
        name = self[ZERO].setdefault(name,Name(name))  # 2006 Dec 14
        self[ZERO].setdefault(key,name)
        name.append(key)
        return name

    def make_local_name(self, name):
        if self.is_global():
            result = self.make_global_name(name)
        else:
            result = self.make_name(name, LOCAL_NAME_SCRIPT)
        return result

    def make_global_name(self, name):
        return self.make_name(name, GLOBAL_NAME_SCRIPT)

    def make_class_name(self, name):
        return self.make_name(name, CLASS_NAME_SCRIPT)

    def make_function_name(self, name):
        return self.make_name(name, FUNCTION_NAME_SCRIPT)

    def make_formal_param_name(self, name):
        return self.make_name(name, FORMAL_PARAM_NAME_SCRIPT)

    def make_imported_name(self, name):
        return self.make_name(name, [])

    def make_attr_name(self, expr, name):
        if isinstance(expr, NodeName):  # 2006 Dec 19
            module = expr.name.str
        else:
            module = None
        name = name.get_as_str()
        key = name
        for rule in ATTR_NAME_SCRIPT:
            name = rule(name, module=module)  # 2006 Dec 19
        name = Name(name)  # 2006 Dec 14
        name.append(key)
        name.rept_external(expr)
        return name.new

    def make_keyword_name(self, name):
        name = name.get_as_str()
        key = name
        for rule in FORMAL_PARAM_NAME_SCRIPT:
            name = rule(name)
        name = Name(name)  # 2006 Dec 14
        name.append(key)
        return name.new

    def get_name(self, node):
        name = key = node.get_as_str()  # 2006 Dec 17
        for scope in self:
            if key in scope:
                name = scope[key]
                name.rept_collision(key)  # 2006 Dec 14
                name = name.new
                break
        return name

    def has_name(self, node):
        name = node.get_as_str()
        return name in self[ZERO]

    def is_global(self):
        return len(self) == 1


def transform(indent, lineno, node):
    """Convert the nodes in the abstract syntax tree returned by the
    *compiler* module to objects with *put* methods.
    
    The kinds of nodes are a Python Version Dependency.

    """

    def isinstance_(node, class_name):  # 2006 Nov 30
        """Safe check against name of a node class rather than the
        class itself, which may or may not be supported at the current
        Python version.

        """

        class_ = getattr(compiler.ast, class_name, None)
        if class_ is None:
            result = False
        else:
            result = isinstance(node, class_)
        return result

    if isinstance_(node, 'Node') and node.lineno is not None:
        lineno = node.lineno
    if isinstance_(node, 'Add'):
        result = NodeAdd(indent, lineno, node.left, node.right)
    elif isinstance_(node, 'And'):
        result = NodeAnd(indent, lineno, node.nodes)
    elif isinstance_(node, 'AssAttr'):
        result = NodeAsgAttr(indent, lineno, node.expr, node.attrname, 
                             node.flags)
    elif isinstance_(node, 'AssList'):
        result = NodeAsgList(indent, lineno, node.nodes)
    elif isinstance_(node, 'AssName'):
        result = NodeAsgName(indent, lineno, node.name, node.flags)
    elif isinstance_(node, 'AssTuple'):
        result = NodeAsgTuple(indent, lineno, node.nodes)
    elif isinstance_(node, 'Assert'):
        result = NodeAssert(indent, lineno, node.test, node.fail)
    elif isinstance_(node, 'Assign'):
        result = NodeAssign(indent, lineno, node.nodes, node.expr)
    elif isinstance_(node, 'AugAssign'):
        result = NodeAugAssign(indent, lineno, node.node, node.op, node.expr)
    elif isinstance_(node, 'Backquote'):
        result = NodeBackquote(indent, lineno, node.expr)
    elif isinstance_(node, 'Bitand'):
        result = NodeBitAnd(indent, lineno, node.nodes)
    elif isinstance_(node, 'Bitor'):
        result = NodeBitOr(indent, lineno, node.nodes)
    elif isinstance_(node, 'Bitxor'):
        result = NodeBitXor(indent, lineno, node.nodes)
    elif isinstance_(node, 'Break'):
        result = NodeBreak(indent, lineno)
    elif isinstance_(node, 'CallFunc'):
        result = NodeCallFunc(indent, lineno, node.node, node.args, node.star_args, 
                              node.dstar_args)
    elif isinstance_(node, 'Class'):
        result = NodeClass(indent, lineno, node.name, node.bases, node.doc, 
                           node.code)
    elif isinstance_(node, 'Compare'):
        result = NodeCompare(indent, lineno, node.expr, node.ops)
    elif isinstance_(node, 'Const'):
        result = NodeConst(indent, lineno, node.value)
    elif isinstance_(node, 'Continue'):
        result = NodeContinue(indent, lineno)
    elif isinstance_(node, 'Decorators'):
        result = NodeDecorators(indent, lineno, node.nodes)
    elif isinstance_(node, 'Dict'):
        result = NodeDict(indent, lineno, node.items)
    elif isinstance_(node, 'Discard'):
        result = NodeDiscard(indent, lineno, node.expr)
    elif isinstance_(node, 'Div'):
        result = NodeDiv(indent, lineno, node.left, node.right)
    elif isinstance_(node, 'Ellipsis'):
        result = NodeEllipsis(indent, lineno)
    elif isinstance_(node, 'Exec'):
        result = NodeExec(indent, lineno, node.expr, node.locals, node.globals)
    elif isinstance_(node, 'FloorDiv'):
        result = NodeFloorDiv(indent, lineno, node.left, node.right)
    elif isinstance_(node, 'For'):
        result = NodeFor(indent, lineno, node.assign, node.list, node.body, 
                         node.else_)
    elif isinstance_(node, 'From'):
        result = NodeFrom(indent, lineno, node.modname, node.names)
    elif isinstance_(node, 'Function'):
        result = NodeFunction(
            indent, 
            lineno, 
            getattr(node, 'decorators', None), 
            node.name, 
            node.argnames, 
            node.defaults, 
            node.flags, 
            node.doc, 
            node.code, 
            )
    elif isinstance_(node, 'GenExpr'):
        result = NodeGenExpr(indent, lineno, node.code)
    elif isinstance_(node, 'GenExprFor'):
        result = NodeGenExprFor(indent, lineno, node.assign, node.iter, 
                                node.ifs)
    elif isinstance_(node, 'GenExprIf'):
        result = NodeGenExprIf(indent, lineno, node.test)
    elif isinstance_(node, 'GenExprInner'):
        result = NodeGenExprInner(indent, lineno, node.expr, node.quals)
    elif isinstance_(node, 'Getattr'):
        result = NodeGetAttr(indent, lineno, node.expr, node.attrname)
    elif isinstance_(node, 'Global'):
        result = NodeGlobal(indent, lineno, node.names)
    elif isinstance_(node, 'If'):
        result = NodeIf(indent, lineno, node.tests, node.else_)
    elif isinstance_(node, 'IfExp'):
        result = NodeIfExp(indent, lineno, node.test, node.then, node.else_)
    elif isinstance_(node, 'Import'):
        result = NodeImport(indent, lineno, node.names)
    elif isinstance_(node, 'Invert'):
        result = NodeInvert(indent, lineno, node.expr)
    elif isinstance_(node, 'Keyword'):
        result = NodeKeyword(indent, lineno, node.name, node.expr)
    elif isinstance_(node, 'Lambda'):
        result = NodeLambda(indent, lineno, node.argnames, node.defaults, 
                            node.flags, node.code)
    elif isinstance_(node, 'LeftShift'):
        result = NodeLeftShift(indent, lineno, node.left, node.right)
    elif isinstance_(node, 'List'):
        result = NodeList(indent, lineno, node.nodes)
    elif isinstance_(node, 'ListComp'):
        result = NodeListComp(indent, lineno, node.expr, node.quals)
    elif isinstance_(node, 'ListCompFor'):
        result = NodeListCompFor(indent, lineno, node.assign, node.list, 
                                 node.ifs)
    elif isinstance_(node, 'ListCompIf'):
        result = NodeListCompIf(indent, lineno, node.test)
    elif isinstance_(node, 'Mod'):
        result = NodeMod(indent, lineno, node.left, node.right)
    elif isinstance_(node, 'Module'):
        result = NodeModule(indent, lineno, node.doc, node.node)
    elif isinstance_(node, 'Mul'):
        result = NodeMul(indent, lineno, node.left, node.right)
    elif isinstance_(node, 'Name'):
        result = NodeName(indent, lineno, node.name)
    elif isinstance_(node, 'Not'):
        result = NodeNot(indent, lineno, node.expr)
    elif isinstance_(node, 'Or'):
        result = NodeOr(indent, lineno, node.nodes)
    elif isinstance_(node, 'Pass'):
        result = NodePass(indent, lineno)
    elif isinstance_(node, 'Power'):
        result = NodePower(indent, lineno, node.left, node.right)
    elif isinstance_(node, 'Print'):
        result = NodePrint(indent, lineno, node.nodes, node.dest)
    elif isinstance_(node, 'Printnl'):
        result = NodePrintnl(indent, lineno, node.nodes, node.dest)
    elif isinstance_(node, 'Raise'):
        result = NodeRaise(indent, lineno, node.expr1, node.expr2, node.expr3)
    elif isinstance_(node, 'Return'):
        result = NodeReturn(indent, lineno, node.value)
    elif isinstance_(node, 'RightShift'):
        result = NodeRightShift(indent, lineno, node.left, node.right)
    elif isinstance_(node, 'Slice'):
        result = NodeSlice(indent, lineno, node.expr, node.flags, node.lower, 
                           node.upper)
    elif isinstance_(node, 'Sliceobj'):
        result = NodeSliceobj(indent, lineno, node.nodes)
    elif isinstance_(node, 'Stmt'):
        result = NodeStmt(indent, lineno, node.nodes)
    elif isinstance_(node, 'Sub'):
        result = NodeSub(indent, lineno, node.left, node.right)
    elif isinstance_(node, 'Subscript'):
        result = NodeSubscript(indent, lineno, node.expr, node.flags, 
                               node.subs)
    elif isinstance_(node, 'TryExcept'):
        result = NodeTryExcept(indent, lineno, node.body, node.handlers, 
                               node.else_)
    elif isinstance_(node, 'TryFinally'):
        result = NodeTryFinally(indent, lineno, node.body, node.final)
    elif isinstance_(node, 'Tuple'):
        result = NodeTuple(indent, lineno, node.nodes)
    elif isinstance_(node, 'UnaryAdd'):
        result = NodeUnaryAdd(indent, lineno, node.expr)
    elif isinstance_(node, 'UnarySub'):
        result = NodeUnarySub(indent, lineno, node.expr)
    elif isinstance_(node, 'While'):
        result = NodeWhile(indent, lineno, node.test, node.body, node.else_)
    elif isinstance_(node, 'With'):
        result = NodeWith(indent, lineno, node.expr, node.vars, node.body)
    elif isinstance_(node, 'Yield'):
        result = NodeYield(indent, lineno, node.value)
    elif isinstance(node, str):
        result = NodeStr(indent, lineno, node)
    elif isinstance(node, int):
        result = NodeInt(indent, lineno, node)
    else:
        result = node
    return result


class Node(object):

    """Parent of parsed tokens.

    """

    tag = 'Generic node'

    def __init__(self, indent, lineno):
        object.__init__(self)
        self.indent = indent
        self.lineno = lineno
        if DEBUG:
            sys.stderr.write('%5i %s\n' % (self.lineno, self.tag))
        return 

    def line_init(self, need_blank_line=ZERO):
        COMMENTS.merge(self.get_lineno())
        OUTPUT.put_blank_line(4, count=need_blank_line)
        OUTPUT.line_init(self.indent, self.get_lineno())
        return self

    def line_more(self, chunk, tab_set=False, tab_clear=False, 
                  can_split_after=False, can_break_after=False):
        OUTPUT.line_more(chunk, tab_set, tab_clear, can_split_after, 
                         can_break_after)
        return self

    def line_term(self, lineno=ZERO):
        lineno = max(self.get_hi_lineno(), self.get_lineno())  # , lineno)  # 2006 Dec 01 
        COMMENTS.put_inline(lineno)
        return self

    def put(self, can_split=False):
        '''Place self on output.
        
        For the "Generic" node, this is abstract.  A Generic node *is*
        instantiated for nodes of unrecognized type, and we don\'t
        know what to do for them, so we just place a string on output
        that should force an error when Python is used to interpret
        the result.

        '''

        self.line_more(' /* %s at line %i */ ' % (self.tag, self.get_lineno()))
        return self

    def get_lineno(self):
        return self.lineno

    def get_hi_lineno(self):
        return self.get_lineno()

    def inc_margin(self):
        OUTPUT.inc_margin()
        return self

    def dec_margin(self):
        OUTPUT.dec_margin()
        return self

    def marshal_names(self):
        return self

    def make_local_name(self):
        return self


class NodeOpr(Node):

    """Operator.

    """

    tag = 'Opr'
    is_commutative = True

    def put_expr(self, node, can_split=False):
        if type(node) in OPERATOR_TRUMPS[type(self)] or type(node) in \
            OPERATOR_LEVEL[type(self)] and not self.is_commutative:
            self.line_more('(', tab_set=True)
            node.put(can_split=True)
            self.line_more(')', tab_clear=True)
        else:
            node.put(can_split=can_split)
        return self


class NodeStr(Node):

    """String value.

    """

    tag = 'Str'

    def __init__(self, indent, lineno, str):
        Node.__init__(self, indent, lineno)
        self.set_as_str(str)
        return 

    def put(self, can_split=False):
        self.line_more(self.get_as_str())
        return self

    def get_as_str(self):
        return self.str

    def set_as_str(self, str_):
        self.str = str_
        if isinstance(self.str, str):
            pass
        elif not RECODE_STRINGS:  # 2006 Dec 01
            pass
        else:
            try:
                self.str = self.str.decode(INPUT.coding)
            except UnicodeError:
                pass
            try:
                self.str = str(self.str)
            except UnicodeError:
                pass
        return self

    def put_doc(self, need_blank_line=ZERO):
        doc = self.get_as_str()
        if LEFTJUST_DOC_STRINGS:
            doc = doc.strip()
            lines = doc.splitlines()
            lines = [line.strip() for line in lines]
            lines.extend([NULL, NULL])
            margin = '%s%s' % (OUTPUT.newline, INDENTATION * self.indent)  # 2006 Dec 05
            doc = margin.join(lines)
        self.line_init(need_blank_line=need_blank_line)  # 2006 Dec 01
        quoted = self.force_double_quote(doc)
        lines = NEW_LINE_PATTERN.split(quoted)
        quoted = OUTPUT.newline.join(lines)  # 2006 Dec 05
        self.put_multi_line(quoted)
        self.line_term()
        OUTPUT.put_blank_line(5)
        return self

    def force_double_quote(self, lit):  # 2006 Dec 01
        lit = repr("'" + lit)
        match = QUOTE_PATTERN.match(lit)
        (prefix, quote, apost) = match.group(1, 2, 3)
        if (quote, apost) == ("'", "\\'"):
            pass
        elif (quote, apost) == ("'''", "\\'"):  # 2007 Jan 14
            pass
        elif (quote, apost) == ('"', "'"):
            pass
        elif (quote, apost) == ('"""', "'"):  # 2007 Jan 14
            pass
        else:
            raise NotImplementedError
        lit = QUOTE_PATTERN.sub(prefix + quote, lit, 1)
        return lit

    def put_lit(self):
        lit = self.get_as_str()
        result = repr(lit)
        original_values = COMMENTS.literal_pool.get(result, [])  # 2007 Jan 14
        if len(original_values) == 1:
            (lit, lineno) = original_values[ZERO]
        else:
            if DOUBLE_QUOTED_STRINGS:  # 2006 Dec 05
                lit = self.force_double_quote(lit)
            else:
                lit = result
        lines = NEW_LINE_PATTERN.split(lit)
        if len(lines) > MAX_LINES_BEFORE_SPLIT_LIT:
            lit = OUTPUT.newline.join(lines)  # 2006 Dec 05
            self.put_multi_line(lit)
        else:
            self.line_more(lit)
        return self

    def put_multi_line(self, lit):  # 2006 Dec 01
        match = QUOTE_PATTERN.match(lit)
        (prefix, quote, apost) = match.group(1, 2, 3)
        if len(quote) == 3:  # 2006 Jan 14
            head = prefix + quote + apost
            tail = NULL
        else:
            head = prefix + quote * 3 + apost
            tail = quote * 2
        lit = QUOTE_PATTERN.sub(head, lit, 1) + tail
        self.line_more(lit)
        return self


class NodeInt(Node):

    """Integer value.

    """

    tag = 'Int'

    def __init__(self, indent, lineno, int):
        Node.__init__(self, indent, lineno)
        self.int = int
        return 

    def put(self, can_split=False):
        self.line_more(self.get_as_repr())
        return self

    def get_as_repr(self):
        result = repr(self.int)
        original_values = COMMENTS.literal_pool.get(result, [])  # 2006 Jan 14
        if len(original_values) == 1:
            (result, lineno) = original_values[ZERO]
        return result


class NodeAdd(NodeOpr):

    """Add operation.

    """

    tag = 'Add'

    def __init__(self, indent, lineno, left, right):
        Node.__init__(self, indent, lineno)
        self.left = transform(indent, lineno, left)
        self.right = transform(indent, lineno, right)
        return 

    def put(self, can_split=False):
        self.put_expr(self.left, can_split=can_split)
        self.line_more(' + ', can_split_after=can_split, can_break_after=
                       True)
        self.put_expr(self.right, can_split=can_split)
        return self

    def get_hi_lineno(self):
        return self.right.get_hi_lineno()


class NodeAnd(NodeOpr):

    '''Logical "and" operation.

    '''

    tag = 'And'

    def __init__(self, indent, lineno, nodes):
        Node.__init__(self, indent, lineno)
        self.nodes = [transform(indent, lineno, node) for node in nodes]
        return 

    def put(self, can_split=False):
        for node in (self.nodes)[:1]:
            self.put_expr(node, can_split=can_split)
        for node in (self.nodes)[1:]:
            self.line_more(' and ', can_split_after=can_split, 
                           can_break_after=True)
            self.put_expr(node, can_split=can_split)
        return self

    def get_hi_lineno(self):
        return (self.nodes)[-1].get_hi_lineno()


class NodeAsgAttr(NodeOpr):

    """Assignment to a class attribute.

    """

    tag = 'AsgAttr'

    def __init__(self, indent, lineno, expr, attrname, flags):
        Node.__init__(self, indent, lineno)
        self.expr = transform(indent, lineno, expr)
        self.attrname = transform(indent, lineno, attrname)
        self.flags = transform(indent, lineno, flags)
        return 

    def put(self, can_split=False):
        is_del = self.flags.get_as_str() in ['OP_DELETE']
        if is_del:
            self.line_init()
            self.line_more('del ')
        if isinstance(self.expr, NodeConst):
            self.line_more('(')
            self.expr.put(can_split=True)
            self.line_more(')')
        else:
            self.put_expr(self.expr, can_split=can_split)
        self.line_more('.')
        self.line_more(NAME_SPACE.make_attr_name(self.expr, self.attrname))
        if DEBUG:
            self.line_more(' /* AsgAttr flags:  ')
            self.flags.put()
            self.line_more(' */ ')
        if is_del:
            self.line_term()
        return self

    def get_hi_lineno(self):
        return self.expr.get_hi_lineno()


class NodeAsgList(Node):

    """A list as a destination of an assignment operation.

    """

    tag = 'AsgList'

    def __init__(self, indent, lineno, nodes):
        Node.__init__(self, indent, lineno)
        self.nodes = [transform(indent, lineno, node) for node in nodes]
        return 

    def put(self, can_split=False):
        self.line_more('[', tab_set=True)
        if len(self.nodes) > MAX_SEPS_BEFORE_SPLIT_LINE:
            self.line_term()
            self.inc_margin()
            for node in self.nodes:
                self.line_init()
                node.put(can_split=True)
                self.line_more(LIST_SEP)
                self.line_term()
            self.line_init()
            self.dec_margin()
        else:
            for node in (self.nodes)[:1]:
                node.put(can_split=True)
            self.line_more(LIST_SEP, can_split_after=True)
            for node in (self.nodes)[1:2]:
                node.put(can_split=True)
            for node in (self.nodes)[2:]:
                self.line_more(LIST_SEP, can_split_after=True)
                node.put(can_split=True)
        self.line_more(']', tab_clear=True)
        return self

    def make_local_name(self):
        for node in self.nodes:
            node.make_local_name()
        return self

    def get_hi_lineno(self):
        return node[-1].get_hi_lineno()


class NodeAsgName(Node):

    """Destination of an assignment operation.

    """

    tag = 'AsgName'

    def __init__(self, indent, lineno, name, flags):
        Node.__init__(self, indent, lineno)
        self.name = transform(indent, lineno, name)
        self.flags = transform(indent, lineno, flags)
        return 

    def put(self, can_split=False):
        is_del = self.flags.get_as_str() in ['OP_DELETE']
        if is_del:
            self.line_init()
            self.line_more('del ')
        self.line_more(NAME_SPACE.get_name(self.name))
        if DEBUG:
            self.line_more(' /* AsgName flags:  ')
            self.flags.put()
            self.line_more(' */ ')
        if is_del:
            self.line_term()
        return self

    def make_local_name(self):
        if NAME_SPACE.has_name(self.name):
            pass
        else:
            NAME_SPACE.make_local_name(self.name)
        return self

    def get_hi_lineno(self):
        return self.name.get_hi_lineno()


class NodeAsgTuple(Node):

    """A tuple as a destination of an assignment operation.

    """

    tag = 'AsgTuple'

    def __init__(self, indent, lineno, nodes):
        Node.__init__(self, indent, lineno)
        self.nodes = [transform(indent, lineno, node) for node in nodes]
        return 

    def put(self, can_split=False):
        self.line_more('(', tab_set=True)
        if len(self.nodes) > MAX_SEPS_BEFORE_SPLIT_LINE:
            self.line_term()
            self.inc_margin()
            for node in self.nodes:
                self.line_init()
                node.put(can_split=True)
                self.line_more(LIST_SEP)
                self.line_term()
            self.line_init()
            self.dec_margin()
        else:
            for node in (self.nodes)[:1]:
                node.put(can_split=True)
            self.line_more(LIST_SEP, can_split_after=True)
            for node in (self.nodes)[1:2]:
                node.put(can_split=True)
            for node in (self.nodes)[2:]:
                self.line_more(LIST_SEP, can_split_after=True)
                node.put(can_split=True)
        self.line_more(')', tab_clear=True)
        return self

    def make_local_name(self):
        for node in self.nodes:
            node.make_local_name()
        return self

    def get_hi_lineno(self):
        return (self.nodes)[-1].get_hi_lineno()


class NodeAssert(Node):

    """Assertion.

    """

    tag = 'Assert'

    def __init__(self, indent, lineno, test, fail):
        Node.__init__(self, indent, lineno)
        self.test = transform(indent, lineno, test)
        self.fail = transform(indent, lineno, fail)
        return 

    def put(self, can_split=False):
        self.line_init()
        self.line_more('assert ')
        self.test.put(can_split=can_split)
        if self.fail is None:
            pass
        else:
            self.line_more(LIST_SEP, can_break_after=True)
            self.fail.put()
        self.line_term()
        return self

    def get_hi_lineno(self):
        lineno = self.test.get_hi_lineno()
        if self.fail is None:
            pass
        else:
            lineno = self.fail.get_hi_lineno()
        return lineno


class NodeAssign(Node):

    """Set one or more destinations to the value of the expression.

    """

    tag = 'Assign'

    def __init__(self, indent, lineno, nodes, expr):
        Node.__init__(self, indent, lineno)
        self.nodes = [transform(indent, lineno, node) for node in nodes]
        self.expr = transform(indent, lineno, expr)
        return 

    def put(self, can_split=False):
        self.line_init()
        for node in self.nodes:
            node.put(can_split=can_split)
            self.line_more(ASSIGNMENT, can_break_after=True)
        if isinstance(self.expr, NodeYield):  # 2006 Dec 13
            self.line_more('(')
            self.expr.put(can_split=True)
            self.line_more(')')
        else:
            self.expr.put(can_split=can_split)
        self.line_term()
        return self

    def marshal_names(self):
        for node in self.nodes:
            node.make_local_name()
        return self

    def get_hi_lineno(self):
        return self.expr.get_hi_lineno()


class NodeAugAssign(Node):

    """Augment the destination by the value of the expression.

    """

    tag = 'AugAssign'

    def __init__(self, indent, lineno, node, op, expr):
        Node.__init__(self, indent, lineno)
        self.node = transform(indent, lineno, node)
        self.op = transform(indent, lineno, op)
        self.expr = transform(indent, lineno, expr)
        return 

    def put(self, can_split=False):
        self.line_init()
        self.node.put(can_split=can_split)
        op = ASSIGNMENT.replace('=', self.op.get_as_str())
        self.line_more(op, can_break_after=True)
        self.expr.put(can_split=can_split)
        self.line_term()
        return self

    def marshal_names(self):
        self.node.make_local_name()
        return self

    def get_hi_lineno(self):
        return self.expr.get_hi_lineno()


class NodeBackquote(Node):

    """String conversion a'la *repr*.

    """

    tag = 'Backquote'

    def __init__(self, indent, lineno, expr):
        Node.__init__(self, indent, lineno)
        self.expr = transform(indent, lineno, expr)
        return 

    def put(self, can_split=False):
        self.line_more('`')
        self.expr.put(can_split=can_split)
        self.line_more('`')
        return self

    def get_hi_lineno(self):
        return self.expr.get_hi_lineno()


class NodeBitAnd(NodeOpr):

    '''Bitwise "and" operation (set union).

    '''

    tag = 'BitAnd'

    def __init__(self, indent, lineno, nodes):
        Node.__init__(self, indent, lineno)
        self.nodes = [transform(indent, lineno, node) for node in nodes]
        return 

    def put(self, can_split=False):
        for node in (self.nodes)[:1]:
            self.put_expr(node, can_split=can_split)
        for node in (self.nodes)[1:]:
            self.line_more(' & ', can_split_after=can_split, 
                           can_break_after=True)
            self.put_expr(node, can_split=can_split)
        return self

    def get_hi_lineno(self):
        return (self.nodes)[-1].get_hi_lineno()


class NodeBitOr(NodeOpr):

    '''Bitwise "or" operation (set intersection).

    '''

    tag = 'BitOr'

    def __init__(self, indent, lineno, nodes):
        Node.__init__(self, indent, lineno)
        self.nodes = [transform(indent, lineno, node) for node in nodes]
        return 

    def put(self, can_split=False):
        for node in (self.nodes)[:1]:
            self.put_expr(node, can_split=can_split)
        for node in (self.nodes)[1:]:
            self.line_more(' | ', can_split_after=can_split, 
                           can_break_after=True)
            self.put_expr(node, can_split=can_split)
        return self

    def get_hi_lineno(self):
        return (self.nodes)[-1].get_hi_lineno()


class NodeBitXor(NodeOpr):

    '''Bitwise "xor" operation.

    '''

    tag = 'BitXor'

    def __init__(self, indent, lineno, nodes):
        Node.__init__(self, indent, lineno)
        self.nodes = [transform(indent, lineno, node) for node in nodes]
        return 

    def put(self, can_split=False):
        for node in (self.nodes)[:1]:
            self.put_expr(node, can_split=can_split)
        for node in (self.nodes)[1:]:
            self.line_more(' ^ ', can_split_after=can_split, 
                           can_break_after=True)
            self.put_expr(node, can_split=can_split)
        return self

    def get_hi_lineno(self):
        return (self.nodes)[-1].get_hi_lineno()


class NodeBreak(Node):

    """Escape from a loop.

    """

    tag = 'Break'

    def __init__(self, indent, lineno):
        Node.__init__(self, indent, lineno)
        return 

    def put(self, can_split=False):
        self.line_init()
        self.line_more('break')
        self.line_term()
        return self


class NodeCallFunc(Node):

    """Function invocation.

    """

    tag = 'CallFunc'

    def __init__(self, indent, lineno, node, args, star_args, dstar_args):
        Node.__init__(self, indent, lineno)
        self.node = transform(indent, lineno, node)
        self.args = [transform(indent, lineno, arg) for arg in args]
        self.star_args = transform(indent, lineno, star_args)
        self.dstar_args = transform(indent, lineno, dstar_args)
        if len(self.args) == 1:
            arg = (self.args)[ZERO]
            if isinstance(arg, NodeGenExpr):
                arg.need_parens = False
        return 

    def put(self, can_split=False):

        def count_seps():
            result = len(self.args)
            if self.star_args is None:
                pass
            else:
                result += 1
            if self.dstar_args is None:
                pass
            else:
                result += 1
            return result

        if isinstance(self.node, NodeLambda):
            self.line_more('(')
            self.node.put(can_split=True)
            self.line_more(')')
        else:
            self.node.put(can_split=can_split)
        self.line_more('(', tab_set=True)
        if count_seps() > MAX_SEPS_BEFORE_SPLIT_LINE:
            self.line_term()
            self.inc_margin()
            for arg in self.args:
                self.line_init()
                arg.put(can_split=True)
                self.line_more(LIST_SEP)
                self.line_term()
            if self.star_args is None:
                pass
            else:
                self.line_init()
                self.line_more('*')
                self.star_args.put(can_split=True)
                self.line_more(LIST_SEP)
                self.line_term()
            if self.dstar_args is None:
                pass
            else:
                self.line_init()
                self.line_more('**')
                self.dstar_args.put(can_split=True)
                self.line_more(LIST_SEP)
                self.line_term()
            self.line_init()
            self.dec_margin()
        else:
            for arg in (self.args)[:-1]:
                arg.put(can_split=True)
                self.line_more(FUNCTION_PARAM_SEP, can_split_after=True)
            for arg in (self.args)[-1:]:
                arg.put(can_split=True)
                if self.star_args is None and self.dstar_args is None:
                    pass
                else:
                    self.line_more(FUNCTION_PARAM_SEP, can_split_after=
                                   True)
            if self.star_args is None:
                pass
            else:
                self.line_more('*')
                self.star_args.put(can_split=True)
                if self.dstar_args is None:
                    pass
                else:
                    self.line_more(FUNCTION_PARAM_SEP, can_split_after=
                                   True)
            if self.dstar_args is None:
                pass
            else:
                self.line_more('**')
                self.dstar_args.put(can_split=True)
        self.line_more(')', tab_clear=True)
        return self

    def get_lineno(self):
        return self.node.get_lineno()

    def get_hi_lineno(self):
        lineno = Node.get_hi_lineno(self)
        if self.args:
            lineno = (self.args)[-1].get_hi_lineno()
        if self.star_args is None:
            pass
        else:
            lineno = self.star_args.get_hi_lineno()
        if self.dstar_args is None:
            pass
        else:
            lineno = self.dstar_args.get_hi_lineno()
        return lineno


class NodeClass(Node):

    """Class declaration.

    """

    tag = 'Class'

    def __init__(self, indent, lineno, name, bases, doc, code):
        Node.__init__(self, indent, lineno)
        self.name = transform(indent, lineno, name)
        self.bases = [transform(indent, lineno, base) for base in bases]
        self.doc = transform(indent + 1, lineno, doc)
        self.code = transform(indent + 1, lineno, code)
        return 

    def put(self, can_split=False):
        self.line_init(need_blank_line=2)
        self.line_more('class ')
        self.line_more(NAME_SPACE.get_name(self.name))
        if self.bases:
            self.line_more('(')
            for base in (self.bases)[:1]:
                base.put(can_split=True)
            for base in (self.bases)[1:]:
                self.line_more(LIST_SEP, can_split_after=True)
                base.put(can_split=True)
            self.line_more(')')
        self.line_more(':')
        self.line_term(self.code.get_lineno() - 1)
        if self.doc is None:
            pass
        else:
            self.doc.put_doc(need_blank_line=1)
        OUTPUT.put_blank_line(6)
        self.push_scope()
        self.code.marshal_names()
        self.code.put()
        self.pop_scope()
        OUTPUT.put_blank_line(7, count=2)
        return self

    def push_scope(self):
        NAME_SPACE.push_scope()
        return self

    def pop_scope(self):
        NAME_SPACE.pop_scope()
        return self

    def marshal_names(self):
        NAME_SPACE.make_class_name(self.name)
        return self

    def get_hi_lineno(self):
        lineno = self.name.get_hi_lineno()
        if self.bases:
            lineno = (self.bases)[-1].get_hi_lineno()
        return lineno


class NodeCompare(NodeOpr):

    """Logical comparison.

    """

    tag = 'Compare'
    is_commutative = False

    def __init__(self, indent, lineno, expr, ops):
        Node.__init__(self, indent, lineno)
        self.expr = transform(indent, lineno, expr)
        self.ops = [(op, transform(indent, lineno, ex)) for (op, ex) in 
                    ops]
        return 

    def put(self, can_split=False):
        self.put_expr(self.expr, can_split=can_split)
        for (op, ex) in self.ops:
            self.line_more(' %s ' % op, can_split_after=can_split, 
                           can_break_after=True)
            ex.put(can_split=can_split)
        return self

    def get_hi_lineno(self):
        (op, ex) = (self.ops)[-1]
        return ex.get_hi_lineno()


class NodeConst(Node):

    """Literal or expression.

    """

    tag = 'Const'

    def __init__(self, indent, lineno, value):
        Node.__init__(self, indent, lineno)
        self.value = transform(indent, lineno, value)
        return 

    def put(self, can_split=False):
        if isinstance(self.value, NodeStr):
            self.value.put_lit()
        elif isinstance(self.value, Node):
            self.value.put(can_split=can_split)
        else:
            result = repr(self.value)
            original_values = COMMENTS.literal_pool.get(result, [])  # 2006 Jan 14
            if len(original_values) == 1:
                (result, lineno) = original_values[ZERO]
            self.line_more(result)
        return self

    def is_none(self):
        return self.value is None


class NodeContinue(Node):

    """Start a new trip through a loop.

    """

    tag = 'Continue'

    def __init__(self, indent, lineno):
        Node.__init__(self, indent, lineno)
        return 

    def put(self, can_split=False):
        self.line_init()
        self.line_more('continue')
        self.line_term()
        return self


class NodeDecorators(Node):

    """Functions that take a class method (the next) and a return
    callable object, e.g., *classmethod*.

    """

    def __init__(self, indent, lineno, nodes):
        Node.__init__(self, indent, lineno)
        self.nodes = [transform(indent, lineno, node) for node in nodes]
        return 

    def put(self, spacing=ZERO, can_split=False):
        for node in self.nodes:
            self.line_init(need_blank_line=spacing)
            self.line_more('@')
            node.put(can_split=can_split)
            self.line_term()
            spacing = ZERO
        return self

    def get_hi_lineno(self):
        return (self.nodes)[-1].get_hi_lineno()


class NodeDict(Node):

    """Declaration of a map (dictionary).

    """

    tag = 'Dict'

    def __init__(self, indent, lineno, items):
        Node.__init__(self, indent, lineno)
        self.items = [(transform(indent, lineno, key), transform(indent, 
                      lineno, value)) for (key, value) in items]
        return 

    def put(self, can_split=False):

        def put_item():
            key.put(can_split=can_split)
            self.line_more(DICT_COLON)
            value.put(can_split=can_split)
            return 

        self.line_more('{', tab_set=True)
        if len(self.items) > MAX_SEPS_BEFORE_SPLIT_LINE:
            self.line_term()
            self.inc_margin()
            for (key, value) in self.items:
                self.line_init()
                put_item()
                self.line_more(LIST_SEP)
                self.line_term()
            self.line_init()
            self.dec_margin()
        else:
            for (key, value) in (self.items)[:1]:
                put_item()
            for (key, value) in (self.items)[1:]:
                self.line_more(LIST_SEP, can_split_after=True)
                put_item()
        self.line_more('}', tab_clear=True)
        return self

    def get_hi_lineno(self):
        lineno = Node.get_hi_lineno(self)
        if self.items:
            (key, value) = (self.items)[-1]
            lineno = value.get_hi_lineno()
        return lineno


class NodeDiscard(Node):

    """Evaluate an expression (function) without saving the result.

    """

    tag = 'Discard'

    def __init__(self, indent, lineno, expr):
        Node.__init__(self, indent, lineno)
        self.expr = transform(indent, lineno, expr)
        return 

    def put(self, can_split=False):
        self.line_init()
        self.expr.put(can_split=can_split)
        self.line_term()
        return self

    def marshal_names(self):
        self.expr.marshal_names()
        return self

    def get_lineno(self):
        return self.expr.get_lineno()

    def get_hi_lineno(self):
        return self.expr.get_hi_lineno()


class NodeDiv(NodeOpr):

    """Division operation.

    """

    tag = 'Div'
    is_commutative = False

    def __init__(self, indent, lineno, left, right):
        Node.__init__(self, indent, lineno)
        self.left = transform(indent, lineno, left)
        self.right = transform(indent, lineno, right)
        return 

    def put(self, can_split=False):
        self.put_expr(self.left, can_split=can_split)
        self.line_more(' / ', can_split_after=can_split, can_break_after=
                       True)
        self.put_expr(self.right, can_split=can_split)
        return self

    def get_hi_lineno(self):
        return self.right.get_hi_lineno()


class NodeEllipsis(Node):

    tag = 'Ellipsis'

    def __init__(self, indent, lineno):
        Node.__init__(self, indent, lineno)
        return 

    def put(self, can_split=False):
        self.line_more('...')
        return self


class NodeExec(Node):

    """Execute a given string of Python code in a specified namespace.

    """

    tag = 'Exec'

    def __init__(self, indent, lineno, expr, locals, globals):
        Node.__init__(self, indent, lineno)
        self.expr = transform(indent, lineno, expr)
        self.locals = transform(indent, lineno, locals)
        self.globals = transform(indent, lineno, globals)
        return 

    def put(self, can_split=False):
        self.line_init()
        self.line_more('exec ')
        self.expr.put(can_split=can_split)
        if self.locals is None:
            pass
        else:
            self.line_more(' in ', can_break_after=True)
            self.locals.put(can_split=can_split)
            if self.globals is None:
                pass
            else:
                self.line_more(LIST_SEP, can_break_after=True)
                self.globals.put(can_split=can_split)
        self.line_term()
        return self

    def get_hi_lineno(self):
        lineno = self.expr.get_hi_lineno()
        if self.locals is None:
            pass
        else:
            lineno = self.locals.get_hi_lineno()
            if self.globals is None:
                pass
            else:
                lineno = self.globals.get_hi_lineno()
        return lineno


class NodeFor(Node):

    """For loop.

    """

    tag = 'For'

    def __init__(self, indent, lineno, assign, list, body, else_):
        Node.__init__(self, indent, lineno)
        self.assign = transform(indent, lineno, assign)
        self.list = transform(indent, lineno, list)
        self.body = transform(indent + 1, lineno, body)
        self.else_ = transform(indent + 1, lineno, else_)
        return 

    def put(self, can_split=False):
        self.line_init()
        self.line_more('for ')
        self.assign.put(can_split=can_split)
        self.line_more(' in ', can_break_after=True)
        self.list.put(can_split=can_split)
        self.line_more(':')
        self.line_term(self.body.get_lineno() - 1)
        self.body.put()
        if self.else_ is None:
            pass
        else:
            self.line_init()
            self.line_more('else:')
            self.line_term(self.else_.get_lineno() - 1)
            self.else_.put()
        return self

    def marshal_names(self):
        self.assign.make_local_name()
        self.body.marshal_names()
        if self.else_ is None:
            pass
        else:
            self.else_.marshal_names()
        return self

    def get_hi_lineno(self):
        return self.list.get_hi_lineno()


class NodeFloorDiv(NodeOpr):

    """Floor division operation.

    """

    tag = 'FloorDiv'
    is_commutative = False

    def __init__(self, indent, lineno, left, right):
        Node.__init__(self, indent, lineno)
        self.left = transform(indent, lineno, left)
        self.right = transform(indent, lineno, right)
        return 

    def put(self, can_split=False):
        self.put_expr(self.left, can_split=can_split)
        self.line_more(' // ', can_split_after=can_split, 
                       can_break_after=True)
        self.put_expr(self.right, can_split=can_split)
        return self

    def get_hi_lineno(self):
        return self.right.get_hi_lineno()


class NodeFrom(Node):

    """Import a name space.

    """

    tag = 'From'

    def __init__(self, indent, lineno, modname, names):
        Node.__init__(self, indent, lineno)
        self.modname = transform(indent, lineno, modname)
        self.names = [(transform(indent, lineno, identifier), transform(indent, 
                      lineno, name)) for (identifier, name) in names]
        return 

    def put(self, can_split=False):

        def put_name():
            identifier.put(can_split=can_split)
            if name is None:
                pass
            else:
                self.line_more(' as ')
                name.put(can_split=can_split)
            return 

        self.line_init()
        self.line_more('from ')
        self.modname.put(can_split=can_split)
        self.line_more(' import ')
        for (identifier, name) in (self.names)[:-1]:
            put_name()
            self.line_more(LIST_SEP, can_break_after=True)
        for (identifier, name) in (self.names)[-1:]:
            put_name()
        self.line_term()
        return self

    def marshal_names(self):
        for (identifier, name) in self.names:
            if name is None:
                NAME_SPACE.make_imported_name(identifier)
            else:
                NAME_SPACE.make_local_name(name)
        return self

    def get_hi_lineno(self):
        (identifier, name) = (self.names)[-1]
        lineno = identifier.get_hi_lineno()
        if name is None:
            pass
        else:
            lineno = name.get_hi_lineno()
        return lineno


class NodeFunction(Node):

    """Function declaration.

    """

    tag = 'Function'

    def __init__(
        self, 
        indent, 
        lineno, 
        decorators, 
        name, 
        argnames, 
        defaults, 
        flags, 
        doc, 
        code, 
        ):

        Node.__init__(self, indent, lineno)
        self.decorators = transform(indent, lineno, decorators)
        self.name = transform(indent, lineno, name)
        self.argnames = self.walk(argnames, self.xform)
        self.defaults = [transform(indent, lineno, default) for default in 
                         defaults]
        self.flags = transform(indent, lineno, flags)
        self.doc = transform(indent + 1, lineno, doc)
        self.code = transform(indent + 1, lineno, code)
        return 

    def walk(self, tuple_, func, need_tuple=False):
        if isinstance(tuple_, tuple) or isinstance(tuple_, list):
            result = [self.walk(item, func, need_tuple) for item in 
                      tuple_]
            if need_tuple:
                result = tuple(result)
        else:
            result = func(tuple_)
        return result

    def xform(self, node):
        result = transform(self.indent, self.lineno, node)
        return result

    def pair_up(self, args, defaults):
        args = args[:]  # This function manipulates its arguments
        defaults = defaults[:]  # destructively, so make copies first.
        stars = []
        args.reverse()
        defaults.reverse()
        is_excess_positionals = self.flags.int & 4
        is_excess_keywords = self.flags.int & 8
        if is_excess_positionals == ZERO:
            pass
        else:
            stars.insert(ZERO, '*')
            defaults.insert(ZERO, None)
        if is_excess_keywords == ZERO:
            pass
        else:
            stars.insert(ZERO, '**')
            defaults.insert(ZERO, None)
        result = map(None, args, defaults, stars)
        result.reverse()
        return result

    def put_parm(self, arg, default, stars, can_split=True):
        if stars is None:
            pass
        else:
            self.line_more(stars)
        tuple_ = self.walk(arg, NAME_SPACE.get_name, need_tuple=True)
        tuple_ = str(tuple_)
        tuple_ = tuple_.replace("'", NULL).replace(',)', ', )')
        self.line_more(tuple_)
        if default is None:
            pass
        else:
            self.line_more(FUNCTION_PARAM_ASSIGNMENT)
            default.put(can_split=can_split)
        return 

    def put(self, can_split=False):

        if NAME_SPACE.is_global():
            spacing = 2
        else:
            spacing = 1
        if self.decorators is None:
            pass
        else:
            self.decorators.put(spacing)
            spacing = ZERO
        self.line_init(need_blank_line=spacing)
        self.line_more('def ')
        self.line_more(NAME_SPACE.get_name(self.name))
        self.push_scope()
        parms = self.pair_up(self.argnames, self.defaults)
        for (arg, default, stars) in parms:
            self.walk(arg, NAME_SPACE.make_formal_param_name)
        self.code.marshal_names()
        self.line_more('(', tab_set=True)
        if len(parms) > MAX_SEPS_BEFORE_SPLIT_LINE:
            self.line_term()
            self.inc_margin()
            for (arg, default, stars) in parms[:-1]:
                self.line_init()
                self.put_parm(arg, default, stars)
                self.line_more(FUNCTION_PARAM_SEP)
                self.line_term()
            for (arg, default, stars) in parms[-1:]:
                self.line_init()
                self.put_parm(arg, default, stars)
                if stars is None:  # 2006 Dec 17
                    self.line_more(FUNCTION_PARAM_SEP)
                self.line_term()
            self.line_init()
            self.dec_margin()
        else:
            for (arg, default, stars) in parms[:1]:
                self.put_parm(arg, default, stars)
            for (arg, default, stars) in parms[1:]:
                self.line_more(FUNCTION_PARAM_SEP, can_split_after=True)
                self.put_parm(arg, default, stars)
        self.line_more('):', tab_clear=True)
        if DEBUG:
            self.line_more(' /* Function flags:  ')
            self.flags.put()
            self.line_more(' */ ')
        self.line_term(self.code.get_lineno() - 1)
        if self.doc is None:
            pass
        else:
            self.doc.put_doc()
        self.code.put()
        self.pop_scope()
        OUTPUT.put_blank_line(8, count=spacing)
        return self

    def push_scope(self):
        NAME_SPACE.push_scope()
        return self

    def pop_scope(self):
        NAME_SPACE.pop_scope()
        return self

    def marshal_names(self):
        NAME_SPACE.make_function_name(self.name)
        return self


class NodeLambda(NodeFunction):

    tag = 'Lambda'

    def __init__(self, indent, lineno, argnames, defaults, flags, code):
        NodeFunction.__init__(
            self, 
            indent, 
            lineno, 
            None, 
            None, 
            argnames, 
            defaults, 
            flags, 
            None, 
            code, 
            )
        return 

    def put(self, can_split=False):
        self.line_more('lambda ')
        self.push_scope()
        parms = self.pair_up(self.argnames, self.defaults)
        for (arg, default, stars) in parms:
            self.walk(arg, NAME_SPACE.make_formal_param_name)
        for (arg, default, stars) in parms[:1]:
            self.put_parm(arg, default, stars, can_split=False)
        for (arg, default, stars) in parms[1:]:
            self.line_more(FUNCTION_PARAM_SEP, can_break_after=True)
            self.put_parm(arg, default, stars, can_split=False)
        self.line_more(': ', can_break_after=True)
        if DEBUG:
            self.line_more(' /* Function flags:  ')
            self.flags.put()
            self.line_more(' */ ')
        self.code.put()
        self.pop_scope()
        return self

    def get_hi_lineno(self):
        return self.code.get_hi_lineno()

    def marshal_names(self):
        return self


class NodeGenExpr(Node):

    """Generator expression, which needs its own parentheses.

    """

    tag = 'GenExpr'

    def __init__(self, indent, lineno, code):
        Node.__init__(self, indent, lineno)
        self.code = transform(indent, lineno, code)
        self.need_parens = True
        return 

    def put(self, can_split=False):
        if self.need_parens:
            self.line_more('(')
        self.code.put(can_split=True)
        if self.need_parens:
            self.line_more(')')
        return self

    def get_hi_lineno(self):
        return self.code.get_hi_lineno()


class NodeGenExprInner(Node):

    """Generator expression inside parentheses.

    """

    tag = 'GenExprInner'

    def __init__(self, indent, lineno, expr, quals):
        Node.__init__(self, indent, lineno)
        self.expr = transform(indent, lineno, expr)
        self.quals = [transform(indent, lineno, qual) for qual in quals]
        return 

    def put(self, can_split=False):
        self.push_scope()
        self.marshal_names()
        self.expr.put(can_split=can_split)
        for qual in self.quals:
            qual.put(can_split=can_split)
        self.pop_scope()
        return self

    def push_scope(self):
        NAME_SPACE.push_scope()
        return self

    def pop_scope(self):
        NAME_SPACE.pop_scope()
        return self

    def marshal_names(self):
        for qual in self.quals:
            qual.marshal_names()
        return self

    def get_hi_lineno(self):
        lineno = (self.quals)[-1].get_hi_lineno()
        return lineno


class NodeGenExprFor(Node):

    '''"For" of a generator expression.

    '''

    tag = 'GenExprFor'

    def __init__(self, indent, lineno, assign, list, ifs):
        Node.__init__(self, indent, lineno)
        self.assign = transform(indent, lineno, assign)
        self.list = transform(indent, lineno, list)
        self.ifs = [transform(indent, lineno, if_) for if_ in ifs]
        return 

    def put(self, can_split=False):
        self.line_more(SPACE, can_split_after=True)
        self.line_more('for ')
        self.assign.put(can_split=can_split)
        self.line_more(' in ', can_split_after=True)
        self.list.put(can_split=can_split)
        for if_ in self.ifs:
            if_.put(can_split=can_split)
        return self

    def marshal_names(self):
        self.assign.make_local_name()
        return self

    def get_hi_lineno(self):
        lineno = self.list.get_hi_lineno()
        if self.ifs:
            lineno = (self.ifs)[-1].get_hi_lineno()
        return lineno


class NodeGenExprIf(Node):

    '''"If" of a generator expression.

    '''

    tag = 'GenExprIf'

    def __init__(self, indent, lineno, test):
        Node.__init__(self, indent, lineno)
        self.test = transform(indent, lineno, test)
        return 

    def put(self, can_split=False):
        self.line_more(SPACE, can_split_after=True)
        self.line_more('if ')
        self.test.put(can_split=can_split)
        return self

    def get_hi_lineno(self):
        return self.test.get_hi_lineno()


class NodeGetAttr(NodeOpr):

    """Class attribute (method).

    """

    tag = 'GetAttr'

    def __init__(self, indent, lineno, expr, attrname):
        Node.__init__(self, indent, lineno)
        self.expr = transform(indent, lineno, expr)
        self.attrname = transform(indent, lineno, attrname)
        return 

    def put(self, can_split=False):
        if isinstance(self.expr, NodeConst):
            self.line_more('(')
            self.expr.put(can_split=True)
            self.line_more(')')
        else:
            self.put_expr(self.expr, can_split=can_split)
        self.line_more('.')
        self.line_more(NAME_SPACE.make_attr_name(self.expr, self.attrname))
        return self

    def get_hi_lineno(self):
        return self.attrname.get_hi_lineno()


class NodeGlobal(Node):

    tag = 'Global'

    def __init__(self, indent, lineno, names):
        Node.__init__(self, indent, lineno)
        self.names = [transform(indent, lineno, name) for name in names]
        return 

    def put(self, can_split=False):
        self.line_init()
        self.line_more('global ')
        for name in (self.names)[:1]:
            self.line_more(NAME_SPACE.get_name(name))
        for name in (self.names)[1:]:
            self.line_more(LIST_SEP, can_break_after=True)
            self.line_more(NAME_SPACE.get_name(name))
        self.line_term()
        return self

    def marshal_names(self):
        for name in self.names:
            NAME_SPACE.make_global_name(name)
        return self

    def get_hi_lineno(self):
        return (self.names)[-1].get_hi_lineno()


class NodeIf(Node):

    """True/False test.

    """

    tag = 'If'

    def __init__(self, indent, lineno, tests, else_):
        Node.__init__(self, indent, lineno)
        self.tests = [(transform(indent, lineno, expr), transform(indent + 
                      1, lineno, stmt)) for (expr, stmt) in tests]
        self.else_ = transform(indent + 1, lineno, else_)
        return 

    def put(self, can_split=False):
        for (expr, stmt) in (self.tests)[:1]:
            self.line_init()
            self.line_more('if ')
            expr.put(can_split=can_split)
            self.line_more(':')
            self.line_term(stmt.get_lineno() - 1)
            stmt.put()
        for (expr, stmt) in (self.tests)[1:]:
            self.line_init()
            self.line_more('elif ')
            expr.put(can_split=can_split)
            self.line_more(':')
            self.line_term(stmt.get_lineno() - 1)
            stmt.put()
        if self.else_ is None:
            pass
        else:
            self.line_init()
            self.line_more('else:')
            self.line_term(self.else_.get_lineno() - 1)
            self.else_.put()
        return self

    def marshal_names(self):
        for (expr, stmt) in self.tests:
            stmt.marshal_names()
        if self.else_ is None:
            pass
        else:
            self.else_.marshal_names()
        return self

    def get_hi_lineno(self):
        (expr, stmt) = (self.tests)[ZERO]
        return expr.get_hi_lineno()


class NodeIfExp(Node):

    """Conditional assignment.

    """

    tag = 'IfExp'

    def __init__(self, indent, lineno, test, then, else_):
        Node.__init__(self, indent, lineno)
        self.test = transform(indent, lineno, test)
        self.then = transform(indent, lineno, then)
        self.else_ = transform(indent, lineno, else_)
        return 

    def put(self, can_split=False):
        self.then.put(can_split=can_split)
        self.line_more(' if ')
        self.test.put(can_split=can_split)
        self.line_more(' else ')
        self.else_.put()
        return self

    def get_hi_lineno(self):
        return self.else_.get_hi_lineno()


class NodeImport(Node):

    tag = 'Import'

    def __init__(self, indent, lineno, names):
        Node.__init__(self, indent, lineno)
        self.names = [(transform(indent, lineno, identifier), transform(indent, 
                      lineno, name)) for (identifier, name) in names]
        return 

    def put(self, can_split=False):

        def put_name():
            identifier.put(can_split=can_split)
            if name is None:
                pass
            else:
                self.line_more(' as ')
                name.put(can_split=can_split)
            return 

        for (identifier, name) in self.names:
            self.line_init()
            self.line_more('import ')
            put_name()
            self.line_term()
        return self

    def marshal_names(self):
        for (identifier, name) in self.names:
            if name is None:
                pass
            else:
                NAME_SPACE.make_local_name(name)
        return self

    def get_hi_lineno(self):
        (identifier, name) = (self.names)[-1]
        lineno = identifier.get_hi_lineno()
        if name is None:
            pass
        else:
            lineno = name.get_hi_lineno()
        return lineno


class NodeInvert(NodeOpr):

    """Unary bitwise complement.

    """

    tag = 'Invert'

    def __init__(self, indent, lineno, expr):
        Node.__init__(self, indent, lineno)
        self.expr = transform(indent, lineno, expr)
        return 

    def put(self, can_split=False):
        self.line_more('~')
        self.put_expr(self.expr, can_split=can_split)
        return self

    def get_hi_lineno(self):
        return self.expr.get_hi_lineno()


class NodeKeyword(Node):

    """Formal parameter on a function invocation.

    """

    tag = 'Keyword'

    def __init__(self, indent, lineno, name, expr):
        Node.__init__(self, indent, lineno)
        self.name = transform(indent, lineno, name)
        self.expr = transform(indent, lineno, expr)
        return 

    def put(self, can_split=False):
        self.line_more(NAME_SPACE.make_keyword_name(self.name))
        self.line_more(FUNCTION_PARAM_ASSIGNMENT, can_split_after=True)
        self.expr.put(can_split=can_split)
        return self

    def get_hi_lineno(self):
        return self.expr.get_hi_lineno()


class NodeLeftShift(NodeOpr):

    """Bitwise shift left.

    """

    tag = 'LeftShift'
    is_commutative = False

    def __init__(self, indent, lineno, left, right):
        Node.__init__(self, indent, lineno)
        self.left = transform(indent, lineno, left)
        self.right = transform(indent, lineno, right)
        return 

    def put(self, can_split=False):
        self.put_expr(self.left, can_split=can_split)
        self.line_more(' << ', can_split_after=can_split, 
                       can_break_after=True)
        self.put_expr(self.right, can_split=can_split)
        return self

    def get_hi_lineno(self):
        return self.right.get_hi_lineno()


class NodeList(Node):

    """Declaration of a mutable list.

    """

    tag = 'List'

    def __init__(self, indent, lineno, nodes):
        Node.__init__(self, indent, lineno)
        self.nodes = [transform(indent, lineno, node) for node in nodes]
        return 

    def put(self, can_split=False):
        self.line_more('[', tab_set=True)
        if len(self.nodes) > MAX_SEPS_BEFORE_SPLIT_LINE:
            self.line_term()
            self.inc_margin()
            for node in self.nodes:
                self.line_init()
                node.put(can_split=True)
                self.line_more(LIST_SEP)
                self.line_term()
            self.line_init()
            self.dec_margin()
        else:
            for node in (self.nodes)[:1]:
                node.put(can_split=True)
            for node in (self.nodes)[1:]:
                self.line_more(LIST_SEP, can_split_after=True)
                node.put(can_split=True)
        self.line_more(']', tab_clear=True)
        return self

    def get_hi_lineno(self):
        lineno = Node.get_hi_lineno(self)
        if self.nodes:
            lineno = (self.nodes)[-1].get_hi_lineno()
        return lineno


class NodeListComp(Node):

    """List comprehension.

    """

    tag = 'ListComp'

    def __init__(self, indent, lineno, expr, quals):
        Node.__init__(self, indent, lineno)
        self.expr = transform(indent, lineno, expr)
        self.quals = [transform(indent, lineno, qual) for qual in quals]
        return 

    def put(self, can_split=False):
        self.push_scope()
        self.marshal_names()
        self.line_more('[', tab_set=True)
        self.expr.put(can_split=True)
        for qual in self.quals:
            qual.put(can_split=True)
        self.line_more(']', tab_clear=True)
        self.pop_scope()
        return self

    def push_scope(self):
        NAME_SPACE.push_scope()
        return self

    def pop_scope(self):
        NAME_SPACE.pop_scope()
        return self

    def marshal_names(self):
        for qual in self.quals:
            qual.marshal_names()
        return self

    def get_hi_lineno(self):
        lineno = (self.quals)[-1].get_hi_lineno()
        return lineno


class NodeListCompFor(Node):

    '''"For" of a list comprehension.

    '''

    tag = 'ListCompFor'

    def __init__(self, indent, lineno, assign, list, ifs):
        Node.__init__(self, indent, lineno)
        self.assign = transform(indent, lineno, assign)
        self.list = transform(indent, lineno, list)
        self.ifs = [transform(indent, lineno, if_) for if_ in ifs]
        return 

    def put(self, can_split=False):
        self.line_more(SPACE, can_split_after=True)
        self.line_more('for ')
        self.assign.put(can_split=can_split)
        self.line_more(' in ', can_split_after=True)
        self.list.put(can_split=can_split)
        for if_ in self.ifs:
            if_.put(can_split=can_split)
        return self

    def marshal_names(self):
        self.assign.make_local_name()
        return self

    def get_hi_lineno(self):
        lineno = self.list.get_hi_lineno()
        if self.ifs:
            lineno = (self.ifs)[-1].get_hi_lineno()
        return lineno


class NodeListCompIf(Node):

    '''"If" of a list comprehension.

    '''

    tag = 'ListCompIf'

    def __init__(self, indent, lineno, test):
        Node.__init__(self, indent, lineno)
        self.test = transform(indent, lineno, test)
        return 

    def put(self, can_split=False):
        self.line_more(SPACE, can_split_after=True)
        self.line_more('if ')
        self.test.put(can_split=can_split)
        return self

    def get_hi_lineno(self):
        return self.test.get_hi_lineno()


class NodeMod(NodeOpr):

    """Modulus (string formatting) operation.

    """

    tag = 'Mod'
    is_commutative = False

    def __init__(self, indent, lineno, left, right):
        Node.__init__(self, indent, lineno)
        self.left = transform(indent, lineno, left)
        self.right = transform(indent, lineno, right)
        return 

    def put(self, can_split=False):
        self.put_expr(self.left, can_split=can_split)
        self.line_more(' % ', can_split_after=can_split, can_break_after=
                       True)
        self.put_expr(self.right, can_split=can_split)
        return self

    def get_hi_lineno(self):
        return self.right.get_hi_lineno()


class NodeModule(Node):

    """A whole script.
    
    Contains a doc string and a statement.

    """

    tag = 'Module'

    def __init__(self, indent, lineno, doc, node):
        Node.__init__(self, indent, lineno)
        self.doc = transform(indent, lineno, doc)
        self.node = transform(indent, lineno, node)
        return 

    def put(self, can_split=False):
        if self.doc is None:
            pass
        else:
            self.doc.lineno = self.get_lineno()
            self.doc.put_doc()
        self.node.put()
        return self

    def push_scope(self):
        NAME_SPACE.push_scope()
        return self

    def pop_scope(self):
        NAME_SPACE.pop_scope()
        return self

    def marshal_names(self):
        self.node.marshal_names()
        return self

    def get_lineno(self):
        return self.node.get_lineno()


class NodeMul(NodeOpr):

    """Multiply operation.

    """

    tag = 'Mul'
    is_commutative = False  # ... string replication, that is.

    def __init__(self, indent, lineno, left, right):
        Node.__init__(self, indent, lineno)
        self.left = transform(indent, lineno, left)
        self.right = transform(indent, lineno, right)
        return 

    def put(self, can_split=False):
        self.put_expr(self.left, can_split=can_split)
        self.line_more(' * ', can_split_after=can_split, can_break_after=
                       True)
        self.put_expr(self.right, can_split=can_split)
        return self

    def get_hi_lineno(self):
        return self.right.get_hi_lineno()


class NodeName(Node):

    """Variable.

    """

    tag = 'Name'

    def __init__(self, indent, lineno, name):
        Node.__init__(self, indent, lineno)
        self.name = transform(indent, lineno, name)
        return 

    def put(self, can_split=False):
        self.line_more(NAME_SPACE.get_name(self.name))
        return self

    def make_local_name(self):
        if NAME_SPACE.has_name(self.name):
            pass
        else:
            NAME_SPACE.make_local_name(self.name)
        return self

    def get_hi_lineno(self):
        return self.name.get_hi_lineno()


class NodeNot(NodeOpr):

    """Logical negation.

    """

    tag = 'Not'

    def __init__(self, indent, lineno, expr):
        Node.__init__(self, indent, lineno)
        self.expr = transform(indent, lineno, expr)
        return 

    def put(self, can_split=False):
        self.line_more('not ')
        self.put_expr(self.expr, can_split=can_split)
        return self

    def get_hi_lineno(self):
        return self.expr.get_hi_lineno()


class NodeOr(NodeOpr):

    '''Logical "or" operation.

    '''

    tag = 'Or'

    def __init__(self, indent, lineno, nodes):
        Node.__init__(self, indent, lineno)
        self.nodes = [transform(indent, lineno, node) for node in nodes]
        return 

    def put(self, can_split=False):
        for node in (self.nodes)[:1]:
            self.put_expr(node, can_split=can_split)
        for node in (self.nodes)[1:]:
            self.line_more(' or ', can_split_after=can_split, 
                           can_break_after=True)
            self.put_expr(node, can_split=can_split)
        return self

    def get_hi_lineno(self):
        return (self.nodes)[-1].get_hi_lineno()


class NodePass(Node):

    """No-op.

    """

    tag = 'Pass'

    def __init__(self, indent, lineno):
        Node.__init__(self, indent, lineno)
        return 

    def put(self, can_split=False):
        self.line_init()
        self.line_more('pass')
        self.line_term()
        return self


class NodePower(NodeOpr):

    """Exponentiation.

    """

    tag = 'Power'
    is_commutative = False

    def __init__(self, indent, lineno, left, right):
        Node.__init__(self, indent, lineno)
        self.left = transform(indent, lineno, left)
        self.right = transform(indent, lineno, right)
        return 

    def put(self, can_split=False):
        self.put_expr(self.left, can_split=can_split)
        self.line_more(' ** ', can_split_after=can_split, 
                       can_break_after=True)
        self.put_expr(self.right, can_split=can_split)
        return self

    def get_hi_lineno(self):
        return self.right.get_hi_lineno()


class NodePrint(Node):

    """The print statement with optional chevron and trailing comma.

    """

    tag = 'Print'

    def __init__(self, indent, lineno, nodes, dest):
        Node.__init__(self, indent, lineno)
        self.nodes = [transform(indent, lineno, node) for node in nodes]
        self.dest = transform(indent, lineno, dest)
        return 

    def put(self, can_split=False):
        self.line_init()
        self.line_more('print ')
        if self.dest is None:
            pass
        else:
            self.line_more('>> ')
            self.dest.put(can_split=can_split)
            if self.nodes:
                self.line_more(LIST_SEP, can_break_after=True)
        for node in self.nodes:
            node.put(can_split=can_split)
            self.line_more(LIST_SEP, can_break_after=True)
        self.line_term()
        return self

    def get_hi_lineno(self):
        lineno = Node.get_hi_lineno(self)
        if self.dest is None:
            pass
        else:
            lineno = self.dest.get_hi_lineno()
        if self.nodes:
            lineno = (self.nodes)[-1].get_hi_lineno()
        return lineno


class NodePrintnl(Node):

    """The print statement with optional chevron and without trailing comma.

    """

    tag = 'Printnl'

    def __init__(self, indent, lineno, nodes, dest):
        Node.__init__(self, indent, lineno)
        self.nodes = [transform(indent, lineno, node) for node in nodes]
        self.dest = transform(indent, lineno, dest)
        return 

    def put(self, can_split=False):
        self.line_init()
        self.line_more('print ')
        if self.dest is None:
            pass
        else:
            self.line_more('>> ')
            self.dest.put(can_split=can_split)
            if self.nodes:
                self.line_more(LIST_SEP, can_break_after=True)
        for node in (self.nodes)[:-1]:
            node.put(can_split=can_split)
            self.line_more(LIST_SEP, can_break_after=True)
        for node in (self.nodes)[-1:]:
            node.put(can_split=can_split)
        self.line_term()
        return self

    def get_hi_lineno(self):
        lineno = Node.get_hi_lineno(self)
        if self.dest is None:
            pass
        else:
            lineno = self.dest.get_hi_lineno()
        if self.nodes:
            lineno = (self.nodes)[-1].get_hi_lineno()
        return lineno


class NodeRaise(Node):

    """Raise an exception.

    """

    tag = 'Raise'

    def __init__(self, indent, lineno, expr1, expr2, expr3):
        Node.__init__(self, indent, lineno)
        self.expr1 = transform(indent, lineno, expr1)
        self.expr2 = transform(indent, lineno, expr2)
        self.expr3 = transform(indent, lineno, expr3)
        return 

    def put(self, can_split=False):
        self.line_init()
        self.line_more('raise ')
        if self.expr1 is None:
            pass
        else:
            self.expr1.put(can_split=can_split)
            if self.expr2 is None:
                pass
            else:
                self.line_more(LIST_SEP, can_break_after=True)
                self.expr2.put(can_split=can_split)
                if self.expr3 is None:
                    pass
                else:
                    self.line_more(LIST_SEP, can_break_after=True)
                    self.expr3.put(can_split=can_split)
        self.line_term()
        return self

    def get_hi_lineno(self):
        lineno = Node.get_hi_lineno(self)
        if self.expr1 is None:
            pass
        else:
            lineno = self.expr1.get_hi_lineno()
            if self.expr2 is None:
                pass
            else:
                lineno = self.expr2.get_hi_lineno()
                if self.expr3 is None:
                    pass
                else:
                    lineno = self.expr3.get_hi_lineno()
        return lineno


class NodeReturn(Node):

    """Return a value from a function.

    """

    tag = 'Return'

    def __init__(self, indent, lineno, value):
        Node.__init__(self, indent, lineno)
        self.value = transform(indent, lineno, value)
        return 

    def has_value(self):
        return not (isinstance(self.value, NodeConst) and self.value.is_none())

    def put(self, can_split=False):
        self.line_init()
        self.line_more('return ')
        if self.has_value():
            self.value.put(can_split=can_split)
        self.line_term()
        return self

    def get_hi_lineno(self):
        lineno = Node.get_hi_lineno(self)
        if self.has_value:
            lineno = self.value.get_hi_lineno()
        return lineno


class NodeRightShift(NodeOpr):

    """Bitwise shift right.

    """

    tag = 'RightShift'
    is_commutative = False

    def __init__(self, indent, lineno, left, right):
        Node.__init__(self, indent, lineno)
        self.left = transform(indent, lineno, left)
        self.right = transform(indent, lineno, right)
        return 

    def put(self, can_split=False):
        self.put_expr(self.left, can_split=can_split)
        self.line_more(' >> ', can_split_after=can_split, 
                       can_break_after=True)
        self.put_expr(self.right, can_split=can_split)
        return self

    def get_hi_lineno(self):
        return self.right.get_hi_lineno()


class NodeSlice(NodeOpr):

    """A slice of a series.

    """

    tag = 'Slice'

    def __init__(self, indent, lineno, expr, flags, lower, upper):
        Node.__init__(self, indent, lineno)
        self.expr = transform(indent, lineno, expr)
        self.flags = transform(indent, lineno, flags)
        self.lower = transform(indent, lineno, lower)
        self.upper = transform(indent, lineno, upper)
        return 

    def has_value(self, node):
        return not (node is None or isinstance(node, NodeConst) and node.is_none())

    def put(self, can_split=False):
        is_del = self.flags.get_as_str() in ['OP_DELETE']
        if is_del:
            self.line_init()
            self.line_more('del ')
        self.put_expr(self.expr, can_split=can_split)
        self.line_more('[')
        if self.has_value(self.lower):
            self.lower.put(can_split=True)
        self.line_more(SLICE_COLON)
        if self.has_value(self.upper):
            self.upper.put(can_split=True)
        self.line_more(']')
        if DEBUG:
            self.line_more(' /* Subscript flags:  ')
            self.flags.put()
            self.line_more(' */ ')
        if is_del:
            self.line_term()
        return self

    def make_local_name(self):
        self.expr.make_local_name()
        return self

    def get_hi_lineno(self):
        lineno = Node.get_hi_lineno(self)
        if self.has_value(self.lower):
            lineno = self.lower.get_hi_lineno()
        if self.has_value(self.upper):
            lineno = self.upper.get_hi_lineno()
        return lineno


class NodeSliceobj(Node):

    """A subscript range.
    
    This is used for multi-dimensioned arrays.

    """

    tag = 'Sliceobj'

    def __init__(self, indent, lineno, nodes):
        Node.__init__(self, indent, lineno)
        self.nodes = [transform(indent, lineno, node) for node in nodes]
        return 

    def has_value(self, node):
        return not (node is None or isinstance(node, NodeConst) and node.is_none())

    def put(self, can_split=False):
        for node in (self.nodes)[:1]:
            if self.has_value(node):
                node.put(can_split=can_split)
        for node in (self.nodes)[1:]:
            self.line_more(SLICE_COLON, can_split_after=True)
            if self.has_value(node):
                node.put(can_split=can_split)
        return self

    def get_hi_lineno(self):
        lineno = Node.get_hi_lineno(self)
        for node in self.nodes:
            if self.has_value(node):
                lineno = node.get_hi_lineno()
        return lineno


class NodeStmt(Node):

    """A list of nodes..

    """

    tag = 'Stmt'

    def __init__(self, indent, lineno, nodes):
        Node.__init__(self, indent, lineno)
        self.nodes = [transform(indent, lineno, node) for node in nodes]
        return 

    def put(self, can_split=False):
        for node in self.nodes:
            node.put()
        return self

    def get_lineno(self):
        for node in self.nodes:
            result = node.get_lineno()
            if result == ZERO:
                pass
            else:
                return result
        return ZERO

    def marshal_names(self):
        for node in self.nodes:
            node.marshal_names()
        return self


class NodeSub(NodeOpr):

    """Subtract operation.

    """

    tag = 'Sub'
    is_commutative = False

    def __init__(self, indent, lineno, left, right):
        Node.__init__(self, indent, lineno)
        self.left = transform(indent, lineno, left)
        self.right = transform(indent, lineno, right)
        return 

    def put(self, can_split=False):
        self.put_expr(self.left, can_split=can_split)
        self.line_more(' - ', can_split_after=can_split, can_break_after=
                       True)
        self.put_expr(self.right, can_split=can_split)
        return self

    def get_hi_lineno(self):
        return self.right.get_hi_lineno()


class NodeSubscript(NodeOpr):

    """A subscripted sequence.

    """

    tag = 'Subscript'

    def __init__(self, indent, lineno, expr, flags, subs):
        Node.__init__(self, indent, lineno)
        self.expr = transform(indent, lineno, expr)
        self.flags = transform(indent, lineno, flags)
        self.subs = [transform(indent, lineno, sub) for sub in subs]
        return 

    def put(self, can_split=False):
        is_del = self.flags.get_as_str() in ['OP_DELETE']
        if is_del:
            self.line_init()
            self.line_more('del ')
        self.put_expr(self.expr, can_split=can_split)
        if DEBUG:
            self.line_more(' /* Subscript flags:  ')
            self.flags.put()
            self.line_more(' */ ')
        self.line_more('[', tab_set=True)
        for sub in (self.subs)[:1]:
            sub.put(can_split=True)
        for sub in (self.subs)[1:]:
            self.line_more(SUBSCRIPT_SEP, can_split_after=True)
            sub.put(can_split=True)
        self.line_more(']', tab_clear=True)
        if is_del:
            self.line_term()
        return self

    def make_local_name(self):
        self.expr.make_local_name()
        return self

    def get_hi_lineno(self):
        lineno = self.expr.get_hi_lineno()
        if self.subs:
            lineno = (self.subs)[-1].get_hi_lineno()
        return lineno


class NodeTryExcept(Node):

    """Define exception handlers.

    """

    tag = 'TryExcept'

    def __init__(self, indent, lineno, body, handlers, else_):
        Node.__init__(self, indent, lineno)
        self.body = transform(indent + 1, lineno, body)
        self.handlers = [(transform(indent, lineno, expr), transform(indent, 
                         lineno, target), transform(indent + 1, lineno, 
                         suite)) for (expr, target, suite) in handlers]
        self.else_ = transform(indent + 1, lineno, else_)
        self.has_finally = False
        return 

    def put(self, can_split=False):
        if self.has_finally:
            pass
        else:
            self.line_init()
            self.line_more('try:')
            self.line_term(self.body.get_lineno() - 1)
        self.body.put()
        for (expr, target, suite) in self.handlers:
            self.line_init()
            self.line_more('except')
            if expr is None:
                pass
            else:
                self.line_more(SPACE)
                expr.put()
                if target is None:
                    pass
                else:
                    self.line_more(LIST_SEP, can_break_after=True)
                    target.put()
            self.line_more(':')
            self.line_term(suite.get_lineno() - 1)
            suite.put()
        if self.else_ is None:
            pass
        else:
            self.line_init()
            self.line_more('else:')
            self.line_term(self.else_.get_lineno() - 1)
            self.else_.put()
        return self

    def marshal_names(self):
        self.body.marshal_names()
        for (expr, target, suite) in self.handlers:
            suite.marshal_names()
        if self.else_ is None:
            pass
        else:
            self.else_.marshal_names()
        return self


class NodeTryFinally(Node):

    """Force housekeeping code to execute even after an unhandled
    except is raised and before the default handling takes care of it.

    """

    tag = 'TryFinally'

    def __init__(self, indent, lineno, body, final):
        Node.__init__(self, indent, lineno)
        if isinstance(body, compiler.ast.TryExcept):
            self.body = transform(indent, lineno, body)
            self.body.has_finally = True
        else:
            self.body = transform(indent + 1, lineno, body)
        self.final = transform(indent + 1, lineno, final)
        return 

    def put(self, can_split=False):
        self.line_init()
        self.line_more('try:')
        self.line_term(self.body.get_lineno() - 1)
        self.body.put()
        self.line_init()
        self.line_more('finally:')
        self.line_term(self.final.get_lineno() - 1)
        self.final.put()
        return self

    def marshal_names(self):
        self.body.marshal_names()
        self.final.marshal_names()
        return self


class NodeTuple(Node):

    """Declaration of an immutable tuple.

    """

    tag = 'Tuple'

    def __init__(self, indent, lineno, nodes):
        Node.__init__(self, indent, lineno)
        self.nodes = [transform(indent, lineno, node) for node in nodes]
        return 

    def put(self, can_split=False):
        self.line_more('(', tab_set=True)
        if len(self.nodes) > MAX_SEPS_BEFORE_SPLIT_LINE:
            self.line_term()
            self.inc_margin()
            for node in self.nodes:
                self.line_init()
                node.put(can_split=True)
                self.line_more(LIST_SEP)
                self.line_term()
            self.line_init()
            self.dec_margin()
        else:
            for node in (self.nodes)[:1]:
                node.put(can_split=True)
                self.line_more(LIST_SEP, can_split_after=True)
            for node in (self.nodes)[1:2]:
                node.put(can_split=True)
            for node in (self.nodes)[2:]:
                self.line_more(LIST_SEP, can_split_after=True)
                node.put(can_split=True)
        self.line_more(')', tab_clear=True)
        return self

    def get_hi_lineno(self):
        lineno = Node.get_hi_lineno(self)
        if self.nodes:
            lineno = (self.nodes)[-1].get_hi_lineno()
        return lineno


class NodeUnaryAdd(NodeOpr):

    """Algebraic positive.

    """

    tag = 'UnaryAdd'

    def __init__(self, indent, lineno, expr):
        Node.__init__(self, indent, lineno)
        self.expr = transform(indent, lineno, expr)
        return 

    def put(self, can_split=False):
        self.line_more('+')
        self.put_expr(self.expr, can_split=can_split)
        return self

    def get_hi_lineno(self):
        return self.expr.get_hi_lineno()


class NodeUnarySub(NodeOpr):

    """Algebraic negative.

    """

    tag = 'UnarySub'

    def __init__(self, indent, lineno, expr):
        Node.__init__(self, indent, lineno)
        self.expr = transform(indent, lineno, expr)
        return 

    def put(self, can_split=False):
        self.line_more('-')
        self.put_expr(self.expr, can_split=can_split)
        return self

    def get_hi_lineno(self):
        return self.expr.get_hi_lineno()


class NodeWhile(Node):

    """While loop.

    """

    tag = 'While'

    def __init__(self, indent, lineno, test, body, else_):
        Node.__init__(self, indent, lineno)
        self.test = transform(indent, lineno, test)
        self.body = transform(indent + 1, lineno, body)
        self.else_ = transform(indent + 1, lineno, else_)
        return 

    def put(self, can_split=False):
        self.line_init()
        self.line_more('while ')
        self.test.put(can_split=can_split)
        self.line_more(':')
        self.line_term(self.body.get_lineno() - 1)
        self.body.put()
        if self.else_ is None:
            pass
        else:
            self.line_init()
            self.line_more('else:')
            self.line_term(self.else_.get_lineno() - 1)
            self.else_.put()
        return self

    def marshal_names(self):
        self.body.marshal_names()
        if self.else_ is None:
            pass
        else:
            self.else_.marshal_names()
        return 

    def get_hi_lineno(self):
        return self.test.get_hi_lineno()


class NodeWith(Node):

    """Context manager.

    """

    tag = 'With'

    def __init__(self, indent, lineno, expr, vars, body):
        Node.__init__(self, indent, lineno)
        self.expr = transform(indent, lineno, expr)
        self.vars = transform(indent, lineno, vars)
        self.body = transform(indent + 1, lineno, body)
        return 

    def put(self, can_split=False):
        self.line_init()
        self.line_more('with ')
        self.expr.put(can_split=can_split)
        if self.vars is None:
            pass
        else:
            self.line_more(' as ', can_break_after=True)
            self.vars.put(can_split=can_split)
        self.line_more(':')
        self.line_term(self.body.get_lineno() - 1)
        self.body.put()
        return self

    def marshal_names(self):
        if self.vars is None:
            pass
        else:
            self.vars.make_local_name()
        self.body.marshal_names()
        return self

    def get_hi_lineno(self):
        lineno = self.expr.get_hi_lineno()
        if self.vars is None:
            pass
        else:
            lineno = self.vars.get_hi_lineno()
        return lineno


class NodeYield(Node):

    """Yield a generator value.

    """

    tag = 'Yield'

    def __init__(self, indent, lineno, value):
        Node.__init__(self, indent, lineno)
        self.value = transform(indent, lineno, value)
        return 

    def put(self, can_split=False):
        self.line_more('yield ')  # 2006 Dec 13
        self.value.put(can_split=can_split)
        return self

    def get_hi_lineno(self):
        return self.value.get_hi_lineno()


# The abstract syntax tree returns the nodes of arithmetic and logical
# expressions in the correct order for evaluation, but, to reconstruct
# the specifying code in general and to output it correctly, we need
# to insert parentheses to enforce the correct order.

# This is a Python Version Dependency.

OPERATOR_PRECEDENCE = [
    (NodeIfExp, ), 
    (NodeLambda, ), 
    (NodeOr, ), 
    (NodeAnd, ), 
    (NodeNot, ), 
    (NodeCompare, ), 
    (NodeBitOr, ), 
    (NodeBitXor, ), 
    (NodeBitAnd, ), 
    (NodeLeftShift, NodeRightShift), 
    (NodeAdd, NodeSub), 
    (NodeMul, NodeDiv, NodeFloorDiv, NodeMod), 
    (NodeUnaryAdd, NodeUnarySub), 
    (NodeInvert, ), 
    (NodePower, ), 
    (NodeAsgAttr, NodeGetAttr), 
    (NodeSubscript, ), 
    (NodeSlice, ), 
    (NodeCallFunc, ), 
    (NodeTuple, ), 
    (NodeList, ), 
    (NodeDict, ), 
    (NodeBackquote, ), 
    ]
OPERATORS = []
OPERATOR_TRUMPS = {}
OPERATOR_LEVEL = {}
for LEVEL in OPERATOR_PRECEDENCE:
    for OPERATOR in LEVEL:
        OPERATOR_LEVEL[OPERATOR] = LEVEL
        OPERATOR_TRUMPS[OPERATOR] = OPERATORS[:]  # a static copy.
    OPERATORS.extend(LEVEL)


def tidy_up(file_in=sys.stdin, file_out=sys.stdout):  # 2007 Jan 22

    """Clean up, regularize, and reformat the text of a Python script.

    File_in is a file name or a file-like object with a *read* method,
    which contains the input script.

    File_out is a file name or a file-like object with a *write*
    method to contain the output script.

    """

    global INPUT, OUTPUT, COMMENTS, NAME_SPACE
    INPUT = InputUnit(file_in)
    OUTPUT = OutputUnit(file_out)
    COMMENTS = Comments()
    NAME_SPACE = NameSpace()
    module = compiler.parse(str(INPUT))
    module = transform(indent=ZERO, lineno=ZERO, node=module)
    del INPUT
    module.push_scope().marshal_names().put().pop_scope()
    COMMENTS.merge(fin=True)
    OUTPUT.close()
    return

if __name__ == "__main__":  # 2007 Jan 22
    if len(sys.argv) > 1:
        file_in = sys.argv[1]
    else:
        file_in = '-'
    if file_in in ['-']:
        file_in = sys.stdin
    if len(sys.argv) > 2:
        file_out = sys.argv[2]
    else:
        file_out = '-'
    if file_out in ['-']:
        file_out = sys.stdout
    tidy_up(file_in, file_out)

# Fin
