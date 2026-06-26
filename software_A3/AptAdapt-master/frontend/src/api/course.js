import api from './index'

export function fetchCourses() {
  return api.get('/courses/')
}

export function getCourseDetail(courseId) {
  return api.get(`/courses/${courseId}`)
}
