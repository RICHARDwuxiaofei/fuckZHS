import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

class FedoraSafetyTests(unittest.TestCase):
    def test_help_has_no_profile_or_log_side_effects(self):
        with tempfile.TemporaryDirectory() as d:
            result = subprocess.run([sys.executable, str(ROOT/'main.py'), '-h'], cwd=d, capture_output=True)
            self.assertEqual(result.returncode, 0)
            self.assertEqual(list(Path(d).iterdir()), [])

    def test_profile_rejects_path_traversal(self):
        from utils import setProfile
        for name in ('../other', '/tmp/other', 'a/b'):
            with self.assertRaises(ValueError):
                setProfile(name)

    def test_cookie_identity_roundtrip(self):
        from fucker import Fucker
        from utils import cookie_jar_to_list, setProfile
        from urllib.parse import quote
        with tempfile.TemporaryDirectory() as d, patch('utils.getDir', return_value=d):
            setProfile('test')
            f = Fucker()
            f.cookies = [{'name': 'CASLOGC', 'value': quote(json.dumps({'uuid':'test-identity'})), 'domain': '.zhihuishu.com'}]
            saved = cookie_jar_to_list(f.cookies)
            f.cookies = saved
            self.assertEqual(f.uuid, 'test-identity')
            with self.assertRaises(ValueError):
                f.cookies = [{'name':'invalid', 'value':'invalid'}]

    def test_ai_list_string_status_and_invalid_response(self):
        from fucker import Fucker
        from ObjDict import ObjDict
        f = Fucker()
        f.cookies = {'CASLOGC': '%7B%22uuid%22%3A%22test%22%7D'}
        with patch.object(f, 'zhidaoQuery', return_value=ObjDict({'status':'200','rt':[]})):
            self.assertEqual(f.getZhidaoAiList(), [])
        with patch.object(f, 'zhidaoQuery', return_value=ObjDict({'status':'401','rt':[]})):
            with self.assertRaises(ValueError):
                f.getZhidaoAiList()

    def test_error_log_redacts_login_and_api_tokens(self):
        from logger import RedactingFormatter
        import logging
        fmt = RedactingFormatter('%(message)s')
        record = logging.LogRecord('test', logging.ERROR, '', 0,
                                   'qrToken=secret_qr api_key=sk-secretkey https://example.test/?pwd=one_time_secret', (), None)
        rendered = fmt.format(record)
        for secret in ('secret_qr','sk-secretkey','one_time_secret'):
            self.assertNotIn(secret, rendered)

    def test_placeholder_api_keys_fail_before_client_creation(self):
        from fucker import Openai
        with patch('fucker.OpenAI') as client:
            for key in ('', 'sk-', 'none', 'sk-your-deepseek-key'):
                with self.assertRaises(ValueError):
                    Openai(apiKey=key)
            client.assert_not_called()

    def test_popup_explicit_answer_does_not_call_ai(self):
        from fucker import Fucker
        f = Fucker()
        f.learning_quiz_answerer = lambda q: self.fail('AI must not run for an explicit answer')
        self.assertEqual(f.answerZhidao({'questionOptions':[{'id':1,'result':'1'},{'id':2,'result':'0'}]}), '1')

    def test_popup_unknown_or_invalid_answer_is_rejected(self):
        from fucker import Fucker
        f = Fucker()
        q = {'questionOptions':[{'id':1,'result':'0'}]}
        with self.assertRaises(ValueError):
            f.answerZhidao(q)
        f.allow_learning_quizzes = True
        f.learning_quiz_answerer = lambda q: ['not-an-option']
        with self.assertRaises(ValueError):
            f.answerZhidao(q)
        f.learning_quiz_answerer = lambda q: ['1']
        self.assertEqual(f.answerZhidao(q),'1')

    def test_captcha_retains_endpoint_and_code(self):
        from fucker import Fucker, CaptchaException
        from ObjDict import ObjDict
        f = Fucker()
        endpoint = 'https://studyservice-api.zhihuishu.com/gateway/t/v1/learning/saveDatabaseIntervalTimeV2'
        with patch.object(f, '_apiQuery', return_value=ObjDict({'code': -12, 'message': '需要弹出滑块验证'})):
            with self.assertRaises(CaptchaException) as error:
                f.zhidaoQuery(endpoint, {})
            self.assertEqual(error.exception.api_code, -12)
            self.assertEqual(error.exception.endpoint, '/gateway/t/v1/learning/saveDatabaseIntervalTimeV2')

    def test_debug_payload_is_never_written_and_logs_are_bounded(self):
        from logger import MonoLogger
        with tempfile.TemporaryDirectory() as d:
            log = MonoLogger('test-private', path=d, level='DEBUG', to_console=False)
            log.debug('COOKIE_SECRET_TEST')
            log.info('safe status')
            self.assertNotIn('COOKIE_SECRET_TEST', (Path(d)/'debug.log').read_text())
            self.assertIn('safe status', (Path(d)/'info.log').read_text())
            self.assertEqual(log._info_hdlr.maxBytes, 2*1024*1024)
            self.assertEqual(log._info_hdlr.backupCount, 2)
            log.close()
            self.assertFalse(log._info.handlers)

if __name__ == '__main__':
    unittest.main()
