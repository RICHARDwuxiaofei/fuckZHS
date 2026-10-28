#!/usr/bin/env python3
"""Bounded, single-account video-only runner. Never opens a formal exam; only authorized video popup quizzes."""
import argparse
import fcntl
import json
import logging
from logging.handlers import RotatingFileHandler
import os
from pathlib import Path
import subprocess
import sys
import time
from datetime import datetime
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.umask(0o077)
from utils import setProfile
setProfile('nagi')
from fucker import Fucker, Openai, CaptchaException, TimeLimitExceeded, CourseNotStartedException
import requests

DATA = ROOT/'profiles/nagi'
STATE = DATA/'runtime_status.json'
REPORT = ROOT/'docs/FEDORA_RUN_REPORT.md'
log = logging.getLogger('fedora-runner')
log.setLevel(logging.INFO)
DATA.mkdir(mode=0o700, parents=True, exist_ok=True)
handler = RotatingFileHandler(DATA/'runner.log', maxBytes=2*1024*1024, backupCount=3)
handler.setFormatter(logging.Formatter('%(asctime)s %(message)s'))
log.addHandler(handler)
log.addHandler(logging.StreamHandler())


def timestamp():
    return datetime.now(ZoneInfo('Asia/Hong_Kong')).isoformat(timespec='seconds')


def save(state):
    state['updated'] = timestamp()
    temp = STATE.with_suffix('.tmp')
    temp.write_text(json.dumps(state, ensure_ascii=False, indent=2))
    temp.replace(STATE)
    if getattr(save, "last_phase", None) != state.get("phase"):
        log.info("Phase: %s", state.get("phase"))
        save.last_phase = state.get("phase")
    update_report(state)


def update_report(state):
    base = ROOT/'docs/FEDORA_RUN_REPORT_BASE.md'
    if not base.exists():
        return
    text = base.read_text() + '\n## 实际运行状态（自动更新）\n\n'
    text += f"- PARTIAL — 更新时间：{state['updated']}；阶段：{state.get('phase')}；unit：`fuckzhs-nagi.service`。\n"
    text += f"- {state.get('cookie_restore', 'NOT_TESTED')} — 本次保存 Cookie 的真实共享课接口验证。\n"
    text += f"- {state.get('preflight', 'NOT_TESTED')} — 小范围真实视频上报及服务端进度回读。\n"
    text += '- PARTIAL — 运行详情和视频进度见 `profiles/nagi/runtime_status.json`，日志见 `profiles/nagi/runner.log`。\n\n'
    text += '| 类型 | 课程 | ID | 资源结果 |\n|---|---|---|---|\n'
    for c in state.get('courses', []):
        text += f"| {c['type']} | {c['name']} | {c['id']} | {c.get('result','NOT_TESTED')} |\n"
    text += '\n| 视频 | 状态 | 服务端进度 |\n|---|---|---|\n'
    for v in state.get('videos', []):
        text += f"| {v.get('name',v['video'])} | {v['result']} | {v.get('before','')} → {v.get('after','')} |\n"
    text += "\n- PARTIAL — unit 是否仍存活以 systemctl 为准，状态记录不会因为进程退出自动消失。\n"
    REPORT.write_text(text)


def client(live=False):
    conf = json.loads((DATA/'config.json').read_text())
    f = Fucker(cookies=json.loads((DATA/'cookies.json').read_text()),
               proxies=conf.get('proxies'), speed=1.0, end_thre=1.0,
               tree_view=live, progressbar_view=live, aiConfig={'enabled':False})
    f.videos_only = True
    f.allow_learning_quizzes = True
    def answer_popup(q):
        ai = conf.get('ai') or {}
        if not ai.get('enabled'):
            raise ValueError('AI disabled; video quiz requires manual action')
        key_path = DATA/'key'
        key = key_path.read_text().strip() if key_path.exists() else (ai.get('openai') or {}).get('api_key', '')
        text = q.get('content') or q.get('name') or q.get('questionName') or q.get('questionTitle')
        if not text:
            raise ValueError('Video quiz question content missing')
        choices = [{'id': str(o.id), 'content': o.get('content') or o.get('name')} for o in q.questionOptions]
        op = Openai(baseUrl='https://api.deepseek.com/v1', apiKey=key,
                    modelName='deepseek-flash', stream=False,
                    extra={'max_retries': 1, 'max_output_tokens': 2048})
        try:
            prompt = ('Answer only this learning video popup quiz. If you cannot determine the answer, return an empty list. '
                      'Return selected options as JSON objects with id and content, in a ```answer code block.\n'
                      + json.dumps({'question': text, 'options': choices}, ensure_ascii=False))
            return op.generateAnswer(prompt)
        finally:
            op.client.close()
    f.learning_quiz_answerer = answer_popup
    return f


def inventory(f, courses, state):
    jobs = []
    for c in courses:
        record = dict(c)
        state['courses'].append(record)
        cid = c['id']
        try:
            if c['type'] == 'zhidao':
                ctx = f.getZhidaoContext(cid, force=True)
                for vid, v in ctx.videos.items():
                    if str(vid).startswith('-') or not str(vid).isdigit() or float(v.videoSec or 0) <= 0:
                        state['videos'].append({'course':cid,'video':str(vid),'name':v.name,
                                                'result':'PARTIAL video unavailable/placeholder'})
                        continue
                    if v.watchState == 1:
                        state['videos'].append({'course':cid,'video':str(vid),'name':v.name,'result':'PASS already complete'})
                        continue
                    points = [] if f.allow_learning_quizzes else (f.loadVideoPointerInfo(cid,vid).get('questionPoint') or [])
                    if any(q.timeSec > (v.studyTotalTime or 0) for q in points):
                        state['videos'].append({'course':cid,'video':str(vid),'name':v.name,'result':'PARTIAL interactive quiz skipped'})
                        continue
                    jobs.append({'course':cid,'video':vid,'name':v.name,'kind':'zhidao','before':float(v.studyTotalTime or 0),'duration':float(v.videoSec)})
            elif c['type'] == 'hike':
                def walk(node):
                    for child in node.get('childList') or []:
                        walk(child)
                    if not node.get('childList') and node.get('dataType') == 3:
                        total = float(node.get('totalTime') or 0)
                        played = float(node.get('studyTime') or 0)
                        if total > 0 and played >= total:
                            state['videos'].append({'course':cid,'video':str(node.id),'name':node.name,'result':'PASS already complete'})
                        elif total > 0:
                            jobs.append({'course':cid,'video':node.id,'name':node.name,'kind':'hike','before':played,'duration':total})
                for node in f.getHikeContext(cid,force=True).root:
                    walk(node)
            elif c['type'] == 'polymas':
                ctx = f.getPolymasContext(cid.split(':',1)[1],force=True)
                if ctx is None:
                    raise ValueError('No accessible video context')
                for vid,v in ctx.videos.items():
                    d=f.getPolymasResourceDetail(ctx,vid)
                    if d.get('isFinished'):
                        state['videos'].append({'course':cid,'video':str(vid),'name':v.name,'result':'PASS already complete'})
                    else:
                        jobs.append({'course':cid,'video':vid,'name':v.name,'kind':'polymas','before':float(d.get('endWatchTime') or 0),'duration':float(d.get('duration') or v.duration)})
            else:
                record['result']='PARTIAL AI course excluded from video-only run'
                continue
            record['result']='PASS resource inventory'
        except Exception as e:
            record['result']='PARTIAL '+type(e).__name__
            log.info('Course %s inventory skipped: %s',cid,type(e).__name__)
        save(state)
    return jobs


def progress(f,j):
    if j['kind']=='zhidao':
        v=f.getZhidaoContext(j['course'],force=True).videos[j['video']]
        return float(v.studyTotalTime or 0),v.watchState==1
    if j['kind']=='hike':
        result=[]
        def walk(n):
            if str(n.get('id'))==str(j['video']):result.append(n)
            for c in n.get('childList') or []:walk(c)
        for n in f.getHikeContext(j['course'],force=True).root:walk(n)
        if not result:raise ValueError('Video absent in refreshed tree')
        played=float(result[0].get('studyTime') or 0)
        return played,played>=j['duration']
    ctx=f.getPolymasContext(j['course'].split(':',1)[1],force=True)
    d=f.getPolymasResourceDetail(ctx,j['video'])
    return float(d.get('endWatchTime') or 0),bool(d.get('isFinished'))


def playback(f,j):
    if j['kind']=='zhidao':f.fuckZhidaoVideo(j['course'],j['video'])
    elif j['kind']=='hike':f.fuckHikeVideo(j['course'],j['video'],j['before'])
    else:f.fuckPolymasVideo(j['course'].split(':',1)[1],j['video'])


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--preflight-only',action='store_true')
    parser.add_argument('--live', action='store_true', help='Show video names and live progress in this terminal')
    args=parser.parse_args()
    state={'phase':'cookie verification','courses':[],'videos':[],'preflight':'NOT_TESTED'}
    lock=open(DATA/'run.lock','a')
    try:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    except BlockingIOError:
        lock.close()
        print('已有 nagi 任务运行。请先执行 systemctl --user stop fuckzhs-nagi.service。', file=sys.stderr)
        return 4
    save(state)
    f=client(live=args.live)
    f.getZhidaoList()  # Real authenticated access is mandatory.
    state['cookie_restore']='PASS'
    courses=json.loads((DATA/'execution.json').read_text())
    state['phase']='resource inventory'
    jobs=inventory(f,courses,state)
    jobs.sort(key=lambda j:j['duration']-j['before'])
    state['eligible_videos']=len(jobs)
    if not jobs:
        state['phase']='stopped: no accessible unfinished videos'
        save(state)
        return 0
    # Prove a real progress increase before allowing a sustained run.
    state['phase']='small real playback test'
    save(state)
    tested=None
    for job in jobs[:3]:
        entry={'course':job['course'],'video':str(job['video']),'name':job['name'],'before':job['before'],'result':'NOT_TESTED'}
        state['videos'].append(entry)
        save(state)
        f.playback_deadline=time.monotonic()+90
        try:
            try:playback(f,job)
            except TimeLimitExceeded:pass  # Stop after a small bounded segment.
            time.sleep(3)
            after,finished=progress(f,job)
            entry['after']=after
            if after <= job['before'] and not finished:
                raise ValueError('Server did not confirm progress')
            entry['result']='PASS test progress confirmed'
            state['preflight']='PASS'
            tested=job
            break
        except Exception as e:
            entry['result']='FAIL '+type(e).__name__
            log.info('Preflight %s failed: %s',job['video'],type(e).__name__)
        finally:
            f.playback_deadline=None
            save(state)
    if tested is None:
        state['phase']='stopped: preflight failed'
        state['preflight']='FAIL'
        save(state)
        return 1
    if args.preflight_only:
        state['phase']='preflight complete; awaiting sustained service launch'
        save(state)
        return 0
    state['phase']='sustained videos and authorized popup quizzes'
    save(state)
    end=time.monotonic()+9*3600
    affected=set()
    for job in jobs:
        if time.monotonic()>=end:break
        if job['course'] in affected:continue
        log.info('当前视频：%s；剩余队列按服务端进度跳过已完成视频', job['name'])
        entry={'course':job['course'],'video':str(job['video']),'name':job['name'],'result':'PARTIAL running'}
        state['videos'].append(entry)
        save(state)
        try:
            before,complete=progress(f,job)
            job['before']=before
            entry['before']=before
            if complete:
                entry['result']='PASS already complete'
                continue
            f.playback_deadline=min(end,time.monotonic()+min(3*3600,(job['duration']-before)*2+900))
            for attempt in range(2):
                try:
                    playback(f,job)
                    break
                except (requests.Timeout,requests.ConnectionError):
                    if attempt==1:raise
                    time.sleep(15)
                    job['before'],_=progress(f,job)
            after,complete=progress(f,job)
            entry['after']=after
            entry['result']='PASS complete' if complete else 'PARTIAL progress confirmed' if after>before else 'FAIL no confirmed progress'
        except Exception as e:
            entry['result']='PARTIAL '+type(e).__name__
            if isinstance(e, CaptchaException):
                entry['error_endpoint'] = getattr(e, 'endpoint', None)
                entry['api_code'] = getattr(e, 'api_code', None)
                state['requires_manual_verification'] = True
                state['blocker'] = {'type': 'CaptchaException', 'course': job['course'],
                                    'video': str(job['video']), 'endpoint': entry['error_endpoint'],
                                    'api_code': entry['api_code']}
            affected.add(job['course'])
            log.info('Video %s stopped; course excluded: %s',job['video'],type(e).__name__)
            # Authentication failure stops the account rather than trying another login.
            f.courses["zhidao"] = None
            try:f.getZhidaoList()
            except Exception:
                state['phase']='stopped: authentication or service unavailable'
                save(state)
                return 2
        finally:
            f.playback_deadline=None
            save(state)
    if state.get('requires_manual_verification'):
        state['phase']='stopped: manual slider verification required'
        save(state)
        return 3
    state['phase']='finished bounded run; see individual video results'
    save(state)
    return 0

if __name__=='__main__':
    try:
        sys.exit(main())
    except Exception as e:
        log.error('Runner stopped: %s',type(e).__name__)
        if STATE.exists():
            s=json.loads(STATE.read_text());s['phase']='stopped: '+type(e).__name__;save(s)
        sys.exit(1)
