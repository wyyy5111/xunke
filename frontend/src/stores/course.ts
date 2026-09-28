import { defineStore } from 'pinia'
import { ref } from 'vue'

export const useAppStore = defineStore('app', () => {
  const currentCourseId = ref<number>(Number(localStorage.getItem('xunkeflow_cid') || 0))
  function setCourse(id: number) {
    currentCourseId.value = id
    localStorage.setItem('xunkeflow_cid', String(id))
  }
  return { currentCourseId, setCourse }
})
