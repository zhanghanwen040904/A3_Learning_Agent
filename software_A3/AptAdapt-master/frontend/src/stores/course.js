import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { fetchCourses } from '../api/course'

export const useCourseStore = defineStore('course', () => {
  const courses = ref([])
  const currentId = ref(localStorage.getItem('currentCourse') || 'computer_organization')
  const loaded = ref(false)

  const currentCourse = computed(() =>
    courses.value.find(c => c.id === currentId.value) || courses.value[0]
  )

  async function loadCourses() {
    if (loaded.value && courses.value.length > 0) return
    try {
      const res = await fetchCourses()
      courses.value = res.data.courses || []
      loaded.value = true
      // 如果当前课程不在列表中，切到默认
      if (!courses.value.find(c => c.id === currentId.value)) {
        currentId.value = res.data.default || courses.value[0]?.id
      }
    } catch (e) {
      console.error('加载课程列表失败:', e)
    }
  }

  function switchCourse(courseId) {
    if (courses.value.find(c => c.id === courseId)) {
      currentId.value = courseId
      localStorage.setItem('currentCourse', courseId)
    }
  }

  return { courses, currentId, currentCourse, loaded, loadCourses, switchCourse }
})
