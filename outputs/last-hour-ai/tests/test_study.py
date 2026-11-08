import asyncio
from datetime import datetime, timezone
import http.client
from http.server import ThreadingHTTPServer
import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch, AsyncMock

from last_hour.study import StudyService
from last_hour.heart_feed import HeartRateFeed, HeartRelay, parse_sample, relay_handler
from last_hour.tutor_model import TutorModel


def sample(at, bpm=72, source='apple_watch', uid=None):
    return dict(bpm=bpm,timestamp=datetime.fromtimestamp(at,timezone.utc).isoformat(),source=source,sample_id=uid or str(at))


def observation(**changes):
    return dict(source='webcam',samples=50,window_seconds=10,on_ratio=.3,away_ratio=.7,unknown_ratio=0,calibrated=True,**changes) if not changes else {**observation(),**changes}


class StudyTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.now=0
        self.study=StudyService(self.tmp.name,clock=lambda:self.now)
        self.session=self.study.create(dict(goal='조건부 확률',material='P(A|B)=P(A∩B)/P(B)',ai_enabled=False))
        self.id=self.session['id']
    def tearDown(self):
        self.study.heart.stop();self.tmp.cleanup()
    def test_pause_preserves_elapsed_and_end_is_idempotent(self):
        self.now=10;self.study.pause(self.id,True);self.now=100
        self.assertEqual(self.study.snapshot(self.id)['elapsed_seconds'],10)
        self.study.pause(self.id,False);self.now=105
        self.assertEqual(self.study.end(self.id)['summary']['studied_seconds'],15)
        self.now=500;self.assertEqual(self.study.end(self.id)['elapsed_seconds'],15)
    def test_unknown_uncalibrated_and_demo_cannot_trigger_checkin(self):
        self.now=200
        for value in [observation(source='demo'),observation(calibrated=False),observation(on_ratio=0,away_ratio=0,unknown_ratio=1)]:
            self.assertIsNone(self.study.observe(self.id,value)['suggestion'])
        with self.assertRaises(ValueError):self.study.observe(self.id,{**observation(),'landmarks':[]})
    def test_aggregate_observations_do_not_duplicate_local_focus_notifications(self):
        self.now=200
        self.assertIsNone(self.study.observe(self.id,observation())['suggestion'])
        self.study.checkin(self.id,{'state':'thinking'})
        self.assertEqual(self.study.get(self.id)['self_report'],'thinking')
    def test_heart_alone_does_not_infer_state(self):
        self.study.heart.running=True
        for i in range(15):self.study.heart.accept(sample(__import__('time').time()-15+i))
        self.study.heart.accept(sample(__import__('time').time(),110))
        self.now=200
        self.assertIsNone(self.study.observe(self.id,observation(on_ratio=1,away_ratio=0))['suggestion'])
    def test_demo_feedback_never_becomes_training_data(self):
        entry=self.study.assist(self.id,{'mode':'hint','message':''})
        self.assertEqual(entry['source'],'demo')
        self.study.feedback(self.id,dict(response_id=entry['id'],helpful=True,consent_for_training=True))
        result=self.study.export(Path(self.tmp.name)/'export')
        self.assertEqual(result['train']+result['validation'],0)
        self.assertFalse(result['weights_trained'])
    def test_tutor_receives_text_context_without_sensor_payload(self):
        self.study.get(self.id)['ai_enabled']=True
        self.study.observe(self.id,observation())
        model=TutorModel('compatible','test','http://127.0.0.1:8001/v1','')
        reply={'choices':[{'finish_reason':'stop','message':{'role':'assistant','content':json.dumps(dict(content='분모를 보세요',question='기준 사건은?',answer=''))}}]}
        with patch.object(TutorModel,'read',return_value=model),patch.object(TutorModel,'complete',new_callable=AsyncMock,return_value=reply) as complete:
            entry=self.study.assist(self.id,{'mode':'hint','message':'분모가 궁금해'})
        context=json.loads(complete.call_args.args[0][-1]['content'])
        self.assertEqual(set(context),{'goal','material','mode','message','user_self_report','preferred_mode'})
        self.assertNotIn('bpm',json.dumps(context))
        # An invalid correction must not consume feedback or modify preferences.
        with self.assertRaises(ValueError):self.study.feedback(self.id,dict(response_id=entry['id'],helpful=True,correction={'content':''}))
        self.assertEqual(self.study.get(self.id)['feedback'],[])
        self.study.feedback(self.id,dict(response_id=entry['id'],helpful=True))
        self.assertEqual(len(list((self.study.root/'approved').glob('*.json'))),0)
        with patch.object(TutorModel,'read',return_value=model),patch.object(TutorModel,'complete',new_callable=AsyncMock,return_value=reply) as followup:
            second=self.study.assist(self.id,{'mode':'quiz','message':''})
        previous=json.loads(next(m['content'] for m in followup.call_args.args[0] if m['role']=='assistant'))
        self.assertEqual(previous['question'],'기준 사건은?')
        self.study.feedback(self.id,dict(response_id=second['id'],helpful=True,consent_for_training=True))
        result=self.study.export(Path(self.tmp.name)/'export')
        self.assertEqual(result['train']+result['validation'],1)
        self.assertFalse(result['uploaded'])


class HeartTests(unittest.TestCase):
    def test_parser_rejects_stale_future_untimed_and_extra_data(self):
        at=1800000000
        for value in [sample(at-61),sample(at+11),sample(at,bpm=True),sample(at,bpm=float('nan')),{**sample(at),'timestamp':'2026-01-01T00:00:00'},{**sample(at),'raw':[]}]:
            with self.assertRaises(ValueError):parse_sample(value,at)
    def test_duplicate_poll_does_not_refresh_freshness_or_baseline(self):
        now=[1800000000];f=HeartRateFeed(clock=lambda:now[0]);f.running=True
        value=sample(now[0]);self.assertTrue(f.accept(value))
        now[0]+=19;self.assertFalse(f.accept(value));self.assertTrue(f.status()['connected'])
        now[0]+=2;self.assertIsNone(f.status()['bpm']);self.assertFalse(f.status()['connected'])
        self.assertIsNone(f.status()['baseline_bpm'])
    def test_source_switch_clears_demo_baseline(self):
        now=1800000000;f=HeartRateFeed(clock=lambda:now);f.running=True
        for i in range(15):f.accept(sample(now-15+i,source='demo'))
        self.assertIsNotNone(f.status()['baseline_bpm'])
        f.accept(sample(now));self.assertEqual(f.status()['sample_count'],1)
        self.assertIsNone(f.status()['baseline_bpm'])
    def test_relay_auth_separates_ingest_and_read_and_retries_are_idempotent(self):
        relay=HeartRelay();server=ThreadingHTTPServer(('127.0.0.1',0),relay_handler(relay,'write-token','read-token'))
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        def request(method,path,token,body=None,origin=None):
            c=http.client.HTTPConnection('127.0.0.1',server.server_port,timeout=2)
            headers={'Authorization':'Bearer '+token,'Content-Type':'application/json'}
            if origin:headers['Origin']=origin
            c.request(method,path,json.dumps(body) if body else None,headers)
            r=c.getresponse();result=r.status,json.loads(r.read());c.close();return result
        try:
            self.assertEqual(request('POST','/heart-rate','read-token',sample(__import__('time').time()))[0],401)
            value=sample(__import__('time').time(),source='demo')
            self.assertTrue(request('POST','/heart-rate','write-token',value)[1]['accepted'])
            self.assertFalse(request('POST','/heart-rate','write-token',value)[1]['accepted'])
            self.assertEqual(request('GET','/heart-rate/latest','read-token')[1]['source'],'demo')
            self.assertEqual(request('GET','/heart-rate/latest','read-token',origin='https://unrelated.test')[0],401)
        finally:server.shutdown();server.server_close();thread.join()


class TutorTransportTests(unittest.TestCase):
    def test_compatible_transport_has_no_hosted_provider_parameters(self):
        captured={}
        class Response:
            def __enter__(self):return self
            def __exit__(self,*_):pass
            def read(self,*_):return b'{"choices":[]}'
        class Opener:
            def open(self,request,timeout):captured.update(json.loads(request.data));return Response()
        with patch('last_hour.tutor_model.build_opener',return_value=Opener()):
            asyncio.run(TutorModel('compatible','study-tutor','http://127.0.0.1:8001/v1','').complete([dict(role='user',content='hi')]))
        self.assertEqual(set(captured),{'model','messages','stream','max_tokens','response_format'})
    def test_remote_cleartext_and_missing_remote_auth_are_rejected(self):
        for endpoint in ['http://gpu.example/v1','https://gpu.example/v1?key=secret','https://gpu.example/v1']:
            with self.assertRaises(ValueError):TutorModel('compatible','test',endpoint,'').require()
