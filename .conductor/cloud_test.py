"""Run with python3 .conductor/cloud_test.py; no app/database imports needed."""
import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import cloud


class CloudSetupTest(unittest.TestCase):
    def test_snapshot_requires_matching_database_version_and_architecture(self) -> None:
        manifest = {'format': 1, 'mariadb': '11.8', 'architecture': 'x86_64'}
        with patch.object(cloud, 'version', return_value='11.8'), patch.object(cloud.platform, 'machine', return_value='x86_64'):
            cloud.validate_manifest(manifest)
            for key, value in [('format', 2), ('mariadb', '11.4'), ('architecture', 'aarch64')]:
                with self.subTest(key=key), self.assertRaises(RuntimeError):
                    cloud.validate_manifest({**manifest, key: value})

    def test_incomplete_database_is_not_overwritten(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory)
            sentinel = state / 'user-data'
            sentinel.write_text('keep me')
            with patch.object(cloud, 'STATE', state), self.assertRaisesRegex(RuntimeError, 'no data has been overwritten'):
                cloud.restore()
            self.assertEqual(sentinel.read_text(), 'keep me')

    def test_config_reconciles_database_settings_and_preserves_other_preferences(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / 'config.json'
            path.write_text(json.dumps({'mysql_passwd': 'stale', 'mysql_host': 'localhost', 'always_show_rotation': True}))
            with patch.object(cloud, 'ROOT', root), patch.object(cloud, 'STATE', root / 'db'):
                cloud.configure()
                first = json.loads(path.read_text())
                cloud.configure()
                self.assertEqual(json.loads(path.read_text()), first)
            self.assertEqual(first['mysql_passwd'], cloud.PASSWORD)
            self.assertEqual(first['mysql_host'], '127.0.0.1')
            self.assertEqual(first['mysql_port'], 3307)
            self.assertTrue(first['always_show_rotation'])
            self.assertFalse(first['production'])
            self.assertFalse(first['create_github_issues'])

    def test_corrupt_download_is_rejected_before_extraction(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / 'download'
            source.mkdir()
            (source / cloud.ASSET).write_bytes(b'corrupted archive')
            (source / 'manifest.json').write_text('{}')
            (source / 'SHA256SUMS').write_text('0' * 64 + '  ' + cloud.ASSET + '\n')
            state = root / 'state'
            with patch.object(cloud, 'STATE', state), patch.dict(os.environ, {'PD_CLOUD_SNAPSHOT_DIR': str(source)}):
                with self.assertRaises(subprocess.CalledProcessError):
                    cloud.restore()
            self.assertFalse(state.exists())

    def test_local_setup_does_nothing(self) -> None:
        result = subprocess.run(['bash', str(cloud.ROOT / '.conductor/setup.sh')],
                                env={**os.environ, 'CONDUCTOR_IS_LOCAL': '1'}, capture_output=True)
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout, b'')


if __name__ == '__main__':
    unittest.main()
