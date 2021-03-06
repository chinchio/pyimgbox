import io
import json
import sys
from unittest.mock import Mock, call, patch

from pyimgbox import _cli


class MockSubmission(dict):
    def __getattr__(self, name):
        return self[name]


class MockIO():
    def __init__(self, stdin=''):
        self._stdout = io.StringIO()
        self._stderr = io.StringIO()
        self._stdin = io.StringIO(stdin)

    def __enter__(self):
        sys.stdout = self._stdout
        sys.stderr = self._stderr
        sys.stdin = self._stdin
        return self

    def __exit__(self, _, __, ___):
        sys.stdout = sys.__stdout__
        sys.stderr = sys.__stderr__
        sys.stdin = sys.__stdin__

    @property
    def stdout(self):
        self._stdout.seek(0)
        return self._stdout.read()

    @property
    def stderr(self):
        self._stderr.seek(0)
        return self._stderr.read()


@patch('pyimgbox.Gallery')
@patch('pyimgbox._cli._text_output')
def test_run_reads_files_from_stdin(mock_text_output, mock_Gallery):
    mock_text_output.return_value = 0
    files = ('The Foo.jpg', 'The Bar.jpg', 'The Fugly.png')
    with MockIO(stdin='\n'.join(files)):
        assert _cli.run(['--title', 'Foo, Bar, Fugly']) == 0
    assert mock_Gallery.call_args_list == [
        call(title='Foo, Bar, Fugly',
             adult=False, comments_enabled=False,
             square_thumbs=False, thumb_width=100)
    ]

@patch('pyimgbox.Gallery')
@patch('pyimgbox._cli._text_output')
def test_run_passes_arguments_to_Gallery(mock_text_output, mock_Gallery):
    mock_text_output.return_value = 0
    assert _cli.run(['foo.jpg', 'bar.jpg', '--title', 'Foo and Bar',
                     '--adult', '--comments',
                     '--square-thumbs', '--thumb-width', '500']) == 0
    assert mock_Gallery.call_args_list == [
        call(title='Foo and Bar',
             adult=True, comments_enabled=True,
             square_thumbs=True, thumb_width=500)
    ]

@patch('pyimgbox.Gallery')
@patch('pyimgbox._cli._text_output')
def test_run_handles_RuntimeError_from_text_output(mock_text_output, mock_Gallery):
    mock_text_output.side_effect = RuntimeError('Argh')
    with MockIO() as cap:
        assert _cli.run(['foo.jpg']) == 100
    assert mock_text_output.call_args_list == [call(mock_Gallery(), ['foo.jpg'])]
    assert cap.stdout == ''
    assert cap.stderr.endswith('Please report this as a bug: '
                               'https://github.com/plotski/pyimgbox/issues\n')


@patch('pyimgbox.Gallery')
@patch('pyimgbox._cli._json_output')
def test_run_handles_RuntimeError_from_json_output(mock_json_output, mock_Gallery):
    mock_json_output.side_effect = RuntimeError('Argh')
    with MockIO() as cap:
        assert _cli.run(['--json', 'foo.jpg']) == 100
    assert mock_json_output.call_args_list == [call(mock_Gallery(), ['foo.jpg'])]
    assert cap.stderr.endswith('Please report this as a bug: '
                               'https://github.com/plotski/pyimgbox/issues\n')
    assert cap.stdout == ''


def test_text_output_handles_ConnectionError_from_creation():
    mock_gallery = Mock()
    mock_gallery.create.side_effect = ConnectionError('Oops')
    with MockIO() as cap:
        assert _cli._text_output(mock_gallery, ['foo.jpg']) == 1
    assert cap.stderr == 'Oops\n'
    assert cap.stdout == ''

def test_text_output_handles_error_from_addition():
    mock_gallery = Mock(url='<Gallery URL>', edit_url='<Edit URL>')
    mock_gallery.add.return_value = (
        MockSubmission(filename='foo.jpg', success=False, error='Oops'),
    )
    with MockIO() as cap:
        assert _cli._text_output(mock_gallery, ['foo.jpg']) == 2
    assert cap.stderr == ''
    assert cap.stdout == ('Gallery: <Gallery URL>\n'
                          '   Edit: <Edit URL>\n'
                          '* foo.jpg\n'
                          '  Oops\n')

def test_text_output_prints_submissions():
    mock_gallery = Mock(url='<Gallery URL>', edit_url='<Edit URL>')
    mock_gallery.add.return_value = (
        MockSubmission(filename='foo.jpg', success=True, error=None,
                       image_url='img/foo', thumbnail_url='thumb/foo', web_url='web/foo'),
        MockSubmission(filename='bar.jpg', success=True, error=None,
                       image_url='img/bar', thumbnail_url='thumb/bar', web_url='web/bar'),
    )
    with MockIO() as cap:
        assert _cli._text_output(mock_gallery, ['foo.jpg', 'bar.jpg']) == 0
    assert cap.stderr == ''
    assert cap.stdout == ('Gallery: <Gallery URL>\n'
                          '   Edit: <Edit URL>\n'
                          '* foo.jpg\n'
                          '      Image: img/foo\n'
                          '  Thumbnail: thumb/foo\n'
                          '    Webpage: web/foo\n'
                          '* bar.jpg\n'
                          '      Image: img/bar\n'
                          '  Thumbnail: thumb/bar\n'
                          '    Webpage: web/bar\n')


def test_json_output_handles_ConnectionError_from_creation():
    mock_gallery = Mock()
    mock_gallery.create.side_effect = ConnectionError('Oops')
    with MockIO() as cap:
        assert _cli._json_output(mock_gallery, ['foo.jpg']) == 1
    assert cap.stderr == ''
    assert json.loads(cap.stdout) == {
        'success': False,
        'error': 'Oops',
        'gallery_url': None,
        'edit_url': None,
        'images': [],
    }

def test_json_output_handles_error_from_addition(capsys):
    mock_gallery = Mock(url='<Gallery URL>', edit_url='<Edit URL>')
    mock_gallery.add.return_value = (
        MockSubmission(filename='foo.jpg', success=False, error='Oops'),
    )
    with MockIO() as cap:
        assert _cli._json_output(mock_gallery, ['foo.jpg']) == 2
    assert cap.stderr == ''
    assert json.loads(cap.stdout) == {
        'success': True,
        'error': None,
        'gallery_url': '<Gallery URL>',
        'edit_url': '<Edit URL>',
        'images': [
            MockSubmission(filename='foo.jpg', success=False, error='Oops')
        ],
    }

def test_json_output_prints_submissions(capsys):
    mock_gallery = Mock(url='<Gallery URL>', edit_url='<Edit URL>')
    mock_gallery.add.return_value = (
        MockSubmission(filename='foo.jpg', success=True, error=None,
                       image_url='img/foo', thumbnail_url='thumb/foo', web_url='web/foo'),
        MockSubmission(filename='bar.jpg', success=True, error=None,
                       image_url='img/bar', thumbnail_url='thumb/bar', web_url='web/bar'),
    )
    with MockIO() as cap:
        assert _cli._json_output(mock_gallery, ['foo.jpg', 'bar.jpg']) == 0
    assert cap.stderr == ''
    assert json.loads(cap.stdout) == {
        'success': True,
        'error': None,
        'gallery_url': '<Gallery URL>',
        'edit_url': '<Edit URL>',
        'images': [
            MockSubmission(filename='foo.jpg', success=True, error=None,
                           image_url='img/foo',
                           thumbnail_url='thumb/foo',
                           web_url='web/foo'),
            MockSubmission(filename='bar.jpg', success=True, error=None,
                           image_url='img/bar',
                           thumbnail_url='thumb/bar',
                           web_url='web/bar'),
        ],
    }
