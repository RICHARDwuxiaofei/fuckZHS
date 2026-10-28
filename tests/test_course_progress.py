import unittest
from unittest.mock import Mock
from ObjDict import ObjDict
from course_progress import aggregate, platform_percent, video_summary


class CourseProgressTests(unittest.TestCase):
    def test_unknown_course_not_reported_as_complete(self):
        backend = Mock()
        backend.getZhidaoContext.return_value = ObjDict({'videos': {}})
        result = video_summary(backend, {'type':'zhidao','id':'one'})
        self.assertEqual(result['status'], 'unavailable')
        self.assertNotIn('percent', result)
        self.assertIsNone(aggregate([{'video_progress':result}])['percent'])

    def test_aggregate_weights_by_videos_and_reports_coverage(self):
        courses = [
            {'video_progress':{'status':'ok','completed':1,'total':2}},
            {'video_progress':{'status':'ok','completed':2,'total':8}},
            {'video_progress':{'status':'error'}}]
        result = aggregate(courses)
        self.assertEqual(result['percent'], 30)
        self.assertEqual((result['covered'], result['courses']), (2,3))

    def test_server_watch_state_and_hike_string_type(self):
        backend = Mock()
        backend.getZhidaoContext.return_value = ObjDict({'videos': {
            '1':{'watchState':'1'},'2':{'watchState':2}}})
        self.assertEqual(video_summary(backend, {'type':'zhidao','id':'one'})['completed'], 1)
        backend.getHikeContext.return_value = ObjDict({'root':[
            {'childList':[{'dataType':'3','totalTime':60,'studyTime':60},
                          {'dataType':3,'totalTime':0,'studyTime':0}]}]})
        result = video_summary(backend, {'type':'hike','id':'one'})
        self.assertEqual((result['completed'],result['total']), (1,1))

    def test_platform_percent_requires_known_units(self):
        self.assertEqual(platform_percent('32.3%'), 32.3)
        for value in (None, 'unknown', '0.3', 'nan%', '101%', '-1%'):
            self.assertIsNone(platform_percent(value))
