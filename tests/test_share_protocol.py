import json
from pathlib import Path
import tempfile
import unittest

from share_protocol import EventReader, EventSink, profile_path, validate_profile


class ProtocolTests(unittest.TestCase):
    def test_profile_paths_are_contained_and_windows_safe(self):
        for name in ('../nagi', 'a/b', 'C:\\tmp', '.', '', 'CON', 'nul', 'LPT1', 'x' * 41):
            with self.assertRaises(ValueError, msg=name):
                validate_profile(name)
        self.assertEqual(profile_path('/tmp', 'shared-2'), Path('/tmp/profiles/shared-2'))

    def test_partial_events_are_not_lost_or_repeated(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'events'
            reader = EventReader(path)
            self.assertEqual(reader.read(), [])
            path.write_bytes(b'{"event":"status","message":"ok"}')
            self.assertEqual(reader.read(), [])
            with path.open('ab') as stream:
                stream.write(b'\ninvalid\n{"event":"done"}\n')
            self.assertEqual([e['event'] for e in reader.read()], ['status', 'done'])
            self.assertEqual(reader.read(), [])

    def test_sink_bounds_disk_and_keeps_terminal_events(self):
        with tempfile.TemporaryDirectory() as directory:
            for i in range(5):
                sink = EventSink(directory, f'gui-{i:032x}.jsonl')
                sink.emit('status', message='x' * (1024 * 1024))
                sink.emit('status', message='not written')
                sink.emit('done', message='complete')
                sink.close()
            paths = list(Path(directory).glob('*.jsonl'))
            self.assertEqual(len(paths), 3)
            records = [json.loads(line) for line in sink.path.read_text().splitlines()]
            self.assertEqual([r['event'] for r in records], ['status', 'done'])
