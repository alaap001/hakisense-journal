"""Offline deployment regression checks: no database or provider connections."""
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

from backend.config import Config


class DeploymentConfiguration(unittest.TestCase):
    def production(self, **overrides):
        values = dict(environment='production',
                      database_url='postgresql://hakisense_app:fixture@db.example.invalid/postgres',
                      origin='https://journal.onrender.com',
                      allowed_hosts='journal.onrender.com,127.0.0.1')
        return Config(**(values | overrides))

    def test_render_and_custom_domain_configuration(self):
        self.production().validate()
        self.production(origin='https://journal.example.com',
                        allowed_hosts='journal.example.com,journal.onrender.com,127.0.0.1').validate()
        self.production(origin='https://journal.example.com:8443',
                        allowed_hosts='journal.example.com,127.0.0.1').validate()

    def test_missing_production_settings_identify_the_variable(self):
        for values, expected in [
            ({'database_url': ''}, 'DATABASE_URL'),
            ({'origin': 'http://127.0.0.1:5173'}, 'APP_ORIGIN'),
            ({'allowed_hosts': ''}, 'ALLOWED_HOSTS'),
            # The old local-host default passed validation but rejected public requests.
            ({'allowed_hosts': '127.0.0.1,localhost,testserver'}, 'ALLOWED_HOSTS'),
        ]:
            with self.subTest(values=values), self.assertRaisesRegex(RuntimeError, expected):
                self.production(**values).validate()

    def test_origin_and_host_formats(self):
        for origin in ('https://', 'https://journal.onrender.com/login',
                       'https://journal.onrender.com?redirect=other',
                       'https://journal.onrender.com#fragment',
                       'https://journal.onrender.com:invalid'):
            with self.subTest(origin=origin), self.assertRaisesRegex(RuntimeError, 'APP_ORIGIN'):
                self.production(origin=origin).validate()
        for hosts in ('*', '*.onrender.com', 'https://journal.onrender.com',
                      'journal.onrender.com:10000', 'journal.onrender.com/path', ', ,',
                      'journal.onrender.com another.example.com'):
            with self.subTest(hosts=hosts), self.assertRaisesRegex(RuntimeError, 'ALLOWED_HOSTS'):
                self.production(allowed_hosts=hosts).validate()

    def test_privileged_pooler_credentials_are_rejected_without_logging_secrets(self):
        for username in ('postgres', 'postgres.projectref', 'supabase_admin.projectref'):
            with self.subTest(username=username), self.assertRaises(RuntimeError) as error:
                self.production(database_url=f'postgresql://{username}:private-password@pooler.example.invalid/postgres').validate()
            self.assertIn('restricted application login', str(error.exception))
            self.assertNotIn('private-password', str(error.exception))
        with self.assertRaises(RuntimeError) as error:
            self.production(origin='https://user:private-password@journal.onrender.com').validate()
        self.assertNotIn('private-password', str(error.exception))
        self.production(database_url='postgresql://hakisense_app.projectref:fixture@pooler.example.invalid/postgres').validate()

    def test_local_development_does_not_require_a_public_origin(self):
        Config(environment='development', database_url='', origin='http://127.0.0.1:5173',
               allowed_hosts='127.0.0.1,localhost').validate()

    def test_container_command_uses_runtime_port_and_process_count(self):
        dockerfile = (Path(__file__).resolve().parents[1] / 'Dockerfile').read_text()
        command = json.loads(next(line[4:] for line in dockerfile.splitlines() if line.startswith('CMD ')))
        with tempfile.TemporaryDirectory() as directory:
            # Replace only the executable; exercise the real container command's
            # environment expansion without starting an API or touching credentials.
            executable = Path(directory) / 'python'
            executable.write_text('#!/bin/sh\nprintf "%s\\n" "$@"\n')
            executable.chmod(0o700)
            for supplied, port, workers in [({}, '8000', '1'),
                                            ({'PORT': '10000', 'WEB_CONCURRENCY': '1'}, '10000', '1'),
                                            ({'PORT': '9000', 'WEB_CONCURRENCY': '3'}, '9000', '3')]:
                with self.subTest(supplied=supplied):
                    result = subprocess.run(['/bin/sh', *command[1:]], env={'PATH': directory, **supplied},
                                            text=True, capture_output=True, check=True)
                    args = result.stdout.splitlines()
                    self.assertEqual(args[:3], ['-m', 'uvicorn', 'backend.main:app'])
                    self.assertEqual(args[args.index('--host') + 1], '0.0.0.0')
                    self.assertEqual(args[args.index('--port') + 1], port)
                    self.assertEqual(args[args.index('--workers') + 1], workers)

    def test_container_healthcheck_follows_the_runtime_port(self):
        import shlex
        from unittest.mock import patch
        dockerfile = (Path(__file__).resolve().parents[1] / 'Dockerfile').read_text()
        line = next(line for line in dockerfile.splitlines() if line.startswith('HEALTHCHECK '))
        code = shlex.split(line.split(' CMD ', 1)[1])[2]
        for port, expected in [('', '8000'), ('10000', '10000')]:
            with self.subTest(port=port), patch.dict(os.environ, {'PORT': port}), \
                    patch('urllib.request.urlopen') as request:
                exec(code, {})
                request.assert_called_once_with(f'http://127.0.0.1:{expected}/api/ready', timeout=4)
