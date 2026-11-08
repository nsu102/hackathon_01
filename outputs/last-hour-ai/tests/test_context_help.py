import base64
import json
import struct
import tempfile
import unittest
import zlib
from pathlib import Path
from unittest.mock import AsyncMock, patch
from last_hour.study import StudyService
from last_hour.context_help import transcribe
from last_hour.config import ModelSettings
from last_hour.openrouter import ProviderError


def png():
    def chunk(kind,data):return struct.pack('>I',len(data))+kind+data+struct.pack('>I',zlib.crc32(kind+data))
    return b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('>IIBBBBB',64,64,8,2,0,0,0))+chunk(b'IDAT',zlib.compress((b'\0'+b'\xff'*192)*64))+chunk(b'IEND',b'')

def request():return dict(audio=base64.b64encode(b'\x1aE\xdf\xa3test').decode(),capture=dict(png=base64.b64encode(png()).decode(),width=64,height=64,display_id=-2,captured_at_ms=1000),target=dict(selection='gaze',calibration_id='calibration-1'),duration_ms=1800,speech_detected=True,consent=True)


class ContextHelpTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.service=StudyService(self.temp.name)
        self.id=self.service.create(dict(goal='조건부 확률',material='',ai_enabled=True))['id']
        self.response={'choices':[{'finish_reason':'stop','message':{'role':'assistant','content':json.dumps(dict(content='분모 B가 기준이에요.',question='조건이 무엇일까요?',answer=''))}}]}
    def tearDown(self):self.temp.cleanup()
    def test_context_uses_transcript_and_frozen_image_but_never_persists_media(self):
        data=request()
        with patch('last_hour.context_help.transcribe',return_value='이거 어렵네 알려줘'),patch('last_hour.context_help.TutorModel.complete',new_callable=AsyncMock,return_value=self.response) as model:
            result=self.service.context_help(self.id,data)
        prompt=model.call_args.args[0]
        self.assertIn('이거 어렵네 알려줘',prompt[-1]['content'][0]['text'])
        self.assertEqual(prompt[-1]['content'][1]['image_url']['url'],'data:image/png;base64,'+data['capture']['png'])
        self.service.feedback(self.id,dict(response_id=result['message']['id'],helpful=True,consent_for_training=True))
        saved=''.join(p.read_text() for p in Path(self.temp.name).rglob('*.json'))
        self.assertNotIn(data['capture']['png'],saved);self.assertNotIn(data['audio'],saved)
        self.assertFalse(list(self.service.root.glob('prompts/*.json')));self.assertFalse(list(self.service.root.glob('approved/*.json')))
        self.assertFalse(self.service.snapshot(self.id)['busy'])
    def test_invalid_silence_and_missing_context_do_not_call_any_model(self):
        for changes in [dict(speech_detected=False),dict(consent=False),dict(duration_ms=20001),dict(audio='bad'),dict(target=dict(selection='gaze',calibration_id=None))]:
            with patch('last_hour.context_help.transcribe') as stt,patch('last_hour.context_help.TutorModel.complete') as model:
                with self.assertRaises(ValueError):self.service.context_help(self.id,{**request(),**changes})
                stt.assert_not_called();model.assert_not_called()
    def test_stt_failure_or_empty_text_never_reaches_vision_and_releases_busy(self):
        for error in [ProviderError('failed'),ValueError('silence')]:
            with patch('last_hour.context_help.transcribe',side_effect=error),patch('last_hour.context_help.TutorModel.complete') as model:
                with self.assertRaises(type(error)):self.service.context_help(self.id,request())
                model.assert_not_called();self.assertFalse(self.service.snapshot(self.id)['busy'])
    def test_focus_only_accepts_bounded_state_summaries(self):
        value=dict(**{'from':'away_pending','to':'away'},reason='offscreen',at_ms=10000,duration_ms=8000,correction=None)
        self.assertTrue(self.service.focus_events(self.id,value)['recorded'])
        with self.assertRaises(ValueError):self.service.focus_events(self.id,{**value,'x':124})
        with self.assertRaises(ValueError):self.service.focus_events(self.id,{**value,'duration_ms':float('nan')})
    def test_typed_screen_question_skips_stt_and_keeps_images_out_of_storage(self):
        data={k:v for k,v in request().items() if k in {'capture','target','consent'}}
        data['message']='분모가 왜 빨간 카드 4장인가요?'
        with patch('last_hour.context_help.transcribe') as stt,patch('last_hour.context_help.TutorModel.complete',new_callable=AsyncMock,return_value=self.response) as model:
            result=self.service.screen_help(self.id,data)
        stt.assert_not_called()
        self.assertIn(data['message'],model.call_args.args[0][-1]['content'][0]['text'])
        self.assertEqual(result['transcript'],data['message'])
        saved=''.join(p.read_text() for p in Path(self.temp.name).rglob('*.json'))
        self.assertNotIn(data['capture']['png'],saved)
        self.assertFalse(result['message']['training_eligible'])
        self.assertFalse(self.service.snapshot(self.id)['busy'])
    def test_typed_screen_question_rejects_missing_consent_bad_image_and_blank_text(self):
        data={k:v for k,v in request().items() if k in {'capture','target','consent'}}
        data['message']='설명해줘'
        for changes in [dict(message=' '),dict(message='a'*4001),dict(consent=False),dict(audio='unexpected'),dict(capture={**data['capture'],'width':128})]:
            with patch('last_hour.context_help.TutorModel.complete') as model:
                with self.assertRaises(ValueError):self.service.screen_help(self.id,{**data,**changes})
                model.assert_not_called()
        self.service.pause(self.id,True)
        with patch('last_hour.context_help.TutorModel.complete') as model:
            with self.assertRaises(ValueError):self.service.screen_help(self.id,data)
            model.assert_not_called()
    def test_full_monitor_voice_does_not_require_pixel_calibration(self):
        data={**request(),'target':{'selection':'screen','calibration_id':None}}
        with patch('last_hour.context_help.transcribe',return_value='이 공식 설명해줘'),patch('last_hour.context_help.TutorModel.complete',new_callable=AsyncMock,return_value=self.response):
            result=self.service.context_help(self.id,data)
        self.assertEqual(result['transcript'],'이 공식 설명해줘')
    def test_material_update_is_in_the_same_multimodal_question(self):
        self.service.update_material(self.id,{'material':'[첨부 자료: notes.pdf] 고유 코드 37'})
        with patch('last_hour.context_help.transcribe',return_value='자료와 화면을 같이 설명해줘'),patch('last_hour.context_help.TutorModel.complete',new_callable=AsyncMock,return_value=self.response) as model:
            self.service.context_help(self.id,request())
        prompt=model.call_args.args[0][-1]['content'];text=json.loads(prompt[0]['text'])
        self.assertIn('고유 코드 37',text['attached_material']);self.assertTrue(prompt[1]['image_url']['url'].startswith('data:image/png;base64,'))
        self.service.end(self.id)
        with self.assertRaises(ValueError):self.service.update_material(self.id,{'material':'new'})
    def test_stt_contract_uses_dedicated_endpoint_without_chat_routing_flags(self):
        class Response:
            def __enter__(self):return self
            def __exit__(self,*_):pass
            def read(self,_):return b'{"text":"hello"}'
        settings=ModelSettings('openrouter','fake-key','test','test','https://openrouter.ai/api/v1')
        with patch('last_hour.context_help.ModelSettings.read',return_value=settings),patch('last_hour.context_help.build_opener') as opener:
            opener.return_value.open.return_value=Response();self.assertEqual(transcribe('YWJj'),'hello')
            req=opener.return_value.open.call_args.args[0];body=json.loads(req.data)
        self.assertTrue(req.full_url.endswith('/audio/transcriptions'));self.assertEqual(body['input_audio'],dict(data='YWJj',format='webm'))
        self.assertEqual(body['language'],'ko');self.assertNotIn('provider',body);self.assertNotIn('reasoning',body)
