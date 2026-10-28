"""Read-only video completion summaries; unknown courses never become 0/0 complete."""
from datetime import datetime, timezone
import math


def _number(value):
    try:
        result = float(value or 0)
        return result if math.isfinite(result) else 0
    except (ValueError, TypeError):
        return 0


def platform_percent(value):
    if not isinstance(value, str) or not value.strip().endswith('%'):
        return None
    try:
        number = float(value.strip()[:-1])
        return number if math.isfinite(number) and 0 <= number <= 100 else None
    except ValueError:
        return None


def video_summary(backend, course, *, force=False):
    kind, cid = course['type'], course['id']
    videos = []
    if kind == 'zhidao':
        context = backend.getZhidaoContext(cid, force=force)
        videos = [str(v.get('watchState')) == '1' for v in context.videos.values()]
    elif kind == 'hike':
        context = backend.getHikeContext(cid, force=force)
        def walk(nodes):
            for node in nodes:
                walk(node.get('childList') or [])
                if str(node.get('dataType')) == '3' and _number(node.get('totalTime')) > 0:
                    videos.append(_number(node.get('studyTime')) >= _number(node.get('totalTime')))
        walk(context.root)
    elif kind == 'polymas':
        context = backend.getPolymasContext(cid.split(':', 1)[1], force=force)
        if context is not None:
            videos = [v.get('isFinished') is True for v in context.videos.values()]
    else:
        return {'status': 'unsupported', 'message': '暂不统计此类课程'}
    stamp = datetime.now(timezone.utc).isoformat()
    if not videos:
        return {'status': 'unavailable', 'message': '平台未提供可统计视频', 'checked_at': stamp}
    done, total = sum(videos), len(videos)
    return {'status': 'ok', 'completed': done, 'total': total, 'percent': done * 100 / total,
            'checked_at': stamp}


def aggregate(courses):
    known = [c['video_progress'] for c in courses if c.get('video_progress', {}).get('status') == 'ok']
    done = sum(p['completed'] for p in known)
    total = sum(p['total'] for p in known)
    return {'completed': done, 'total': total, 'percent': done * 100 / total if total else None,
            'covered': len(known), 'courses': len(courses)}
