"""Worker for the sharing GUI: one account, ordinary videos, no paid AI/exams."""
import argparse
import contextlib
import json
import os
from pathlib import Path
import time

from share_policy import ShareExpiredError, require_access
from share_protocol import EventSink, profile_path, validate_profile


def run(argv):
    require_access()
    parser = argparse.ArgumentParser()
    parser.add_argument("--action", choices=("fetch", "learn"), required=True)
    parser.add_argument("--profile", required=True)
    parser.add_argument("--events", required=True)
    parser.add_argument("--course", action="append", default=[])
    parser.add_argument("--minutes", type=int, default=120)
    args = parser.parse_args(argv)
    validate_profile(args.profile)
    if not 10 <= args.minutes <= 240:
        parser.error("运行时长需要在 10 到 240 分钟之间")
    os.umask(0o077)
    from utils import getDir, setProfile, cookie_jar_to_list
    from profile_lock import acquire_profile_lock
    from fucker import Fucker, CaptchaException, TimeLimitExceeded, CourseNotStartedException
    import requests

    setProfile(args.profile)
    directory = profile_path(getDir(), args.profile)
    directory.mkdir(parents=True, mode=0o700, exist_ok=True)
    sink = EventSink(directory / "gui-events", args.events)
    lock = None
    deadline = time.monotonic() + args.minutes * 60

    class SharedFucker(Fucker):
        def _checkTimeLimit(self, cid):
            require_access()
            if time.monotonic() >= deadline:
                raise TimeLimitExceeded("运行时长已到")
            return super()._checkTimeLimit(cid)

        def saveDatabaseIntervalTimeV2(self, cid, vid, played, *a, **kw):
            ret = super().saveDatabaseIntervalTimeV2(cid, vid, played, *a, **kw)
            v = self.getZhidaoContext(cid).videos[vid]
            sink.emit("progress", name=v.name, seconds=int(played), duration=int(v.videoSec))
            return ret

        def saveStuStudyRecord(self, cid, vid, played, *a, **kw):
            ret = super().saveStuStudyRecord(cid, vid, played, *a, **kw)
            sink.emit("progress", name="视频学习", seconds=int(ret), duration=0)
            return ret

        def savePolymasStudyRecord(self, ctx, vid, start, end, *a, **kw):
            ret = super().savePolymasStudyRecord(ctx, vid, start, end, *a, **kw)
            sink.emit("progress", name=ctx.videos[vid].name, seconds=int(end), duration=int(ctx.videos[vid].duration))
            return ret

    def save_json(name, value):
        temp = directory / (name + ".tmp")
        temp.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
        os.chmod(temp, 0o600)
        temp.replace(directory / name)

    try:
        lock = acquire_profile_lock(directory / "run.lock")
        # Only proxy settings are read. Keys, passwords and notification services are not used.
        config_path = directory / "config.json"
        config = json.loads(config_path.read_text(encoding="utf-8")) if config_path.exists() else {}
        f = SharedFucker(proxies=config.get("proxies"), speed=1.0, end_thre=1.0,
                         tree_view=False, progressbar_view=False, aiConfig={"enabled": False})
        f.videos_only = True
        f.allow_learning_quizzes = True  # Only answers explicitly returned by the platform.
        request = f.session.request

        def guarded_request(*a, **kw):
            require_access()
            result = request(*a, **kw)
            require_access()
            return result
        f.session.request = guarded_request

        authenticated = False
        cookie_path = directory / "cookies.json"
        if cookie_path.exists():
            try:
                f.cookies = json.loads(cookie_path.read_text(encoding="utf-8"))
                f.getZhidaoList()
                authenticated = True
            except requests.RequestException:
                raise
            except Exception:
                f.cookies = {}
                f.session.cookies.clear()
        if not authenticated:
            if args.action != "fetch":
                sink.emit("error", code="login", message="登录已失效，请先点击扫码登录。")
                return 2
            def qr_callback(data):
                require_access()
                qr = directory / "qr-login.png"
                qr.write_bytes(data)
                os.chmod(qr, 0o600)
                sink.emit("qr", file=qr.name)
            sink.emit("status", message="正在获取登录二维码…")
            f.login(use_qr=True, qr_callback=qr_callback)
            f.courses.zhidao = []
            f.getZhidaoList()  # Authenticate against the server before reporting success.
        save_json("cookies.json", cookie_jar_to_list(f.cookies))
        sink.emit("authenticated", message="登录成功，会话已验证。")

        if args.action == "fetch":
            courses = []
            sources = (("zhidao", f.getZhidaoList), ("hike", f.getHikeList),
                       ("ai", f.getZhidaoAiList), ("polymas", f.getPolymasList))
            for kind, fetch in sources:
                require_access()
                try:
                    rows = fetch()
                    if not isinstance(rows, list):
                        raise ValueError("Invalid course response")
                    for row in rows:
                        cid = str(row.secret if kind == "zhidao" else row.courseId)
                        courses.append({"id": "polymas:" + cid if kind == "polymas" else cid,
                                        "name": row.courseName, "type": kind})
                    sink.emit("status", message=f"已读取 {len(rows)} 门{dict(zhidao='共享课', hike='校内课', ai='AI 课', polymas='Polymas 课程')[kind]}。")
                except Exception as error:
                    sink.emit("warning", message=f"部分课程暂时无法读取（{type(error).__name__}），其他课程可继续使用。")
            save_json("execution.json", courses)
            sink.emit("courses", courses=courses)
            sink.emit("done", message="课程列表已更新，请选择要学习的课程。")
            return 0

        all_courses = json.loads((directory / "execution.json").read_text(encoding="utf-8"))
        selected = [c for c in all_courses if c["id"] in args.course and c["type"] != "ai"]
        if not selected:
            raise ValueError("No selected ordinary course")
        completed = 0
        for course in selected:
            require_access()
            cid = course["id"]
            sink.emit("course", id=cid, status="读取进度…")
            jobs = []
            try:
                if course["type"] == "zhidao":
                    ctx = f.getZhidaoContext(cid, force=True)
                    for vid, v in ctx.videos.items():
                        if str(vid).isdigit() and float(v.videoSec or 0) > 0 and v.watchState != 1:
                            jobs.append((vid, v.name, float(v.studyTotalTime or 0)))
                elif course["type"] == "hike":
                    def walk(node):
                        for child in node.get("childList") or []:
                            walk(child)
                        if node.get("dataType") == 3 and float(node.get("totalTime") or 0) > float(node.get("studyTime") or 0):
                            jobs.append((node.id, node.name, float(node.get("studyTime") or 0)))
                    for node in f.getHikeContext(cid, force=True).root:
                        walk(node)
                elif course["type"] == "polymas":
                    ctx = f.getPolymasContext(cid.split(":", 1)[1], force=True)
                    if ctx is None:
                        raise ValueError("No accessible resource tree")
                    for vid, v in ctx.videos.items():
                        detail = f.getPolymasResourceDetail(ctx, vid)
                        if not detail.get("isFinished"):
                            jobs.append((vid, v.name, float(detail.get("endWatchTime") or 0)))
                sink.emit("course", id=cid, status=f"{len(jobs)} 个待学视频")
                for index, (vid, name, before) in enumerate(jobs):
                    f._checkTimeLimit(cid)
                    sink.emit("video", name=name, index=index + 1, total=len(jobs), course=course["name"])
                    if course["type"] == "zhidao":
                        f.fuckZhidaoVideo(cid, vid)
                        verified = f.getZhidaoContext(cid, force=True).videos[vid].watchState == 1
                    elif course["type"] == "hike":
                        f.fuckHikeVideo(cid, vid, before)
                        def completed_node(nodes):
                            for node in nodes:
                                if str(node.get("id")) == str(vid):
                                    total = float(node.get("totalTime") or 0)
                                    return total > 0 and float(node.get("studyTime") or 0) >= total
                                if completed_node(node.get("childList") or []):
                                    return True
                            return False
                        verified = completed_node(f.getHikeContext(cid, force=True).root)
                    else:
                        f.fuckPolymasVideo(cid.split(":", 1)[1], vid)
                        verified = bool(f.getPolymasResourceDetail(ctx, vid).get("isFinished"))
                    completed += int(verified)
                    sink.emit("video_done", name=name, verified=verified, confirmed=completed)
                sink.emit("course", id=cid, status="本次处理结束" if jobs else "暂无待学视频")
            except CourseNotStartedException:
                sink.emit("course", id=cid, status="尚未开课")
        sink.emit("done", message=f"本次任务已结束，服务端确认完成 {completed} 个视频。")
        return 0
    except ShareExpiredError:
        return 0
    except BlockingIOError:
        sink.emit("error", code="busy", message="同一账号已有任务运行，请先关闭另一个窗口。")
        return 1
    except CaptchaException:
        sink.emit("error", code="captcha", message="平台要求滑块验证。请在知到 App 或网页完成验证后再继续。")
        return 3
    except TimeLimitExceeded:
        sink.emit("done", message="已达到本次运行时长，任务已停止，进度保留。")
        return 0
    except requests.RequestException:
        sink.emit("error", code="network", message="网络请求失败，任务已停止。请检查网络后重试。")
        return 1
    except Exception as error:
        message = "任务已停止，请刷新课程或重新登录后重试。"
        if "quiz" in str(error).lower():
            message = "随堂题没有可确认的答案，请本人处理后再继续。程序不会随机作答。"
        sink.emit("error", code=type(error).__name__, message=message)
        return 1
    finally:
        if lock:
            lock.close()
        sink.close()


def main(argv):
    try:
        require_access()
    except ShareExpiredError:
        return 0
    # Backend diagnostic prints never reach a user's console or expose request data.
    with open(os.devnull, "w", encoding="utf-8") as quiet, contextlib.redirect_stdout(quiet), contextlib.redirect_stderr(quiet):
        return run(argv)
