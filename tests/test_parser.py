import unittest
import textwrap

from AtlasCodeSearch import parser


class ParseQueryTest(unittest.TestCase):

    def assertParse(self, search, query=None, file=None, case=True):
        expected = parser.Search(query=query, file=file, case=case)
        actual = parser.parse_query(search)
        self.assertEquals(expected, actual)

    def test_parse_with_simple_query(self):
        self.assertParse('someVariableName', query=['someVariableName'])

    def test_parse_with_unicode_query(self):
        self.assertParse('Hello, 世界. Done', query=['Hello,', '世界.', 'Done'])

    def test_regex(self):
        self.assertParse(r'some.*variable.*name',
                         query=[r'some.*variable.*name'])

    def test_quoted_string(self):
        self.assertParse(r'"Hello, \"World\"" printf',
                         query=[r'Hello, \"World\"', 'printf'])

    def test_quoted_string_without_closing_quote(self):
        self.assertParse(r'"Hello', query=['Hello'])

    def test_with_file(self):
        self.assertParse(r'"Hello, World" file:.*py$',
                         query=[r'Hello, World'], file='.*py$')

    def test_case_insensitive(self):
        self.assertParse(r'someVariableName case:no',
                         query=['someVariableName'], case=False)

    def test_regex_with_space(self):
        self.assertParse(r'name\ *=\ *foo', query=[r'name\ *=\ *foo'])

    def test_keyword_looking_value(self):
        self.assertParse(r'foo:bar', query=['foo:bar'])

    def test_parse_with_escape_parens(self):
        self.assertParse(r'method\(', query=[r'method\('])


class SearchTest(unittest.TestCase):

    def test_args_simple(self):
        self.assertEquals(parser.Search(query=['hello']).args(), ['hello'])

    def test_args_with_file(self):
        self.assertEquals(parser.Search(query=['hello'], file='.*py$').args(),
                          ['-f', '.*py$', 'hello'])

    def test_args_with_case_insensitive(self):
        self.assertEquals(parser.Search(query=['hello'], case=False).args(),
                          ['-i', 'hello'])

    def test_args_with_multiple_queries(self):
        self.assertEquals(parser.Search(query=['hello', 'world']).args(),
                          ['(hello|world)'])

    def test_args_with_quoted_string(self):
        self.assertEquals(parser.Search(query=['Hello, world']).args(),
                          ['Hello, world'])


class ParseSearchOutputTest(unittest.TestCase):

    def test_parse(self):
        output = textwrap.dedent("""\
            a.txt:1:Too many cooks
            a.txt:2:TOO MANY cooks
            b.txt:34:How to cook
        """)
        expected = [
            parser.FileResults('a.txt', [(1, 'Too many cooks'),
                                         (2, 'TOO MANY cooks')]),
            parser.FileResults('b.txt', [(34, 'How to cook')])
        ]
        actual = parser.parse_search_output(output)
        self.assertEquals(expected, actual)

    def test_parse_single_line(self):
        expected = [parser.FileResults('a.txt', [(1, 'Too many cooks')])]
        actual = parser.parse_search_output('a.txt:1:Too many cooks')
        self.assertEquals(expected, actual)

    def test_parse_with_no_results(self):
        actual = parser.parse_search_output('')
        self.assertEquals([], actual)

    def test_parse_exception(self):
        with self.assertRaises(parser._LexerException):
            parser.parse_search_output('I am a bad line.')

    def test_parse_exception_with_bad_linenum(self):
        with self.assertRaises(parser._LexerException):
            parser.parse_search_output('a.txt:12bleh:Match')


class FileResultsTest(unittest.TestCase):

    def test_str(self):
        res = parser.FileResults('a.txt', [(1, 'Too many cooks'),
                                           (2, 'TOO MANY cooks'),
                                           (500, '    C.O.O.K.S'),
                                           (502, 'Too many cooks')])
        expected = textwrap.dedent("""\
            a.txt:
                1: Too many cooks
                2: TOO MANY cooks
                .
              500:     C.O.O.K.S
              ...
              502: Too many cooks""")
        actual = str(res)
        self.assertEquals(expected, actual)
