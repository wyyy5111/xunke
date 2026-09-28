import request from './request'

export const auth = {
  register: (data: any) => request.post<any>('/auth/register', data),
  login: (data: any) => request.post<any>('/auth/login', data),
  me: () => request.get<any>('/auth/me'),
  updateMe: (data: any) => request.put<any>('/auth/me', data),
  settings: () => request.get<any>('/auth/me/settings'),
  updateSettings: (data: any) => request.put<any>('/auth/me/settings', data)
}

export const course = {
  list: (keyword = '', includeArchived = false) => request.get<any[]>('/courses', { params: { keyword, include_archived: includeArchived } }),
  create: (data: any) => request.post<any>('/courses', data),
  update: (id: number, data: any) => request.put<any>(`/courses/${id}`, data),
  remove: (id: number) => request.delete<any>(`/courses/${id}`),
  chapters: (id: number) => request.get<any[]>(`/courses/${id}/chapters`),
  addChapter: (id: number, data: any) => request.post<any>(`/courses/${id}/chapters`, data),
  updateChapter: (id: number, chapterId: number, data: any) => request.put<any>(`/courses/${id}/chapters/${chapterId}`, data),
  removeChapter: (id: number, chapterId: number) => request.delete<any>(`/courses/${id}/chapters/${chapterId}`),
  enroll: (data: any) => request.post<any>('/courses/enroll', data),
  mine: () => request.get<any[]>('/courses/mine/enrolled')
}

export const fileApi = {
  upload: (courseId: number, file: File) => {
    const fd = new FormData()
    fd.append('file', file)
    return request.post<any>(`/files/upload/${courseId}`, fd, {
      headers: { 'Content-Type': 'multipart/form-data' }
    })
  },
  list: (courseId: number) => request.get<any[]>(`/files/course/${courseId}`),
  remove: (id: number) => request.delete<any>(`/files/${id}`),
  retry: (id: number) => request.post<any>(`/files/${id}/retry`),
  parseStatus: (id: number, silent = false) => request.get<any>(`/files/${id}/parse_status`, { silent })
}

export const kp = {
  list: (courseId: number) => request.get<any[]>(`/knowledge/course/${courseId}`),
  add: (data: any) => request.post('/knowledge', data),
  update: (id: number, data: any) => request.put(`/knowledge/${id}`, data),
  remove: (id: number) => request.delete(`/knowledge/${id}`),
  graph: (courseId: number) => request.get<any>(`/knowledge/graph/${courseId}`),
  relation: (data: any) => request.post('/knowledge/relation', data),
  updateRelation: (id: number, data: any) => request.put(`/knowledge/relation/${id}`, data),
  removeRelation: (id: number) => request.delete(`/knowledge/relation/${id}`)
}

export const test = {
  pre: (courseId: number, count = 10, testType: 'pre' | 'post' | 'practice' = 'practice') => request.get<any[]>(`/tests/pre/${courseId}`, { params: { count, test_type: testType } }),
  submit: (data: any) => request.post<any>('/tests/submit', data),
  exerciseSubmit: (data: any) => request.post<any>('/tests/practice/submit', data, { silent: true }),
  compare: (courseId: number, silent = false) => request.get<any>(`/tests/compare/${courseId}`, { silent })
}

export const profile = {
  get: (courseId: number) => request.get<any>(`/profiles/${courseId}`),
  mastery: (courseId: number) => request.get<any[]>(`/profiles/${courseId}/mastery`),
  path: (courseId: number) => request.get<any>(`/profiles/${courseId}/path`),
  plan: (courseId: number) => request.post<any>(`/profiles/${courseId}/plan`),
  updatePathProgress: (courseId: number, data: any) => request.post<any>(`/profiles/${courseId}/path/progress`, data, { silent: true })
}

export const resource = {
  list: (params: any) => request.get<any[]>('/resources', { params }),
  detail: (id: number) => request.get<any>(`/resources/${id}`),
  generate: (data: any) => request.post<any>('/resources/generate', data)
}

export const agent = {
  run: (data: any) => request.post<any>('/agents/run', data),
  retry: (runId: number) => request.post<any>(`/agents/runs/${runId}/retry`),
  runs: (courseId?: number | string) => request.get<any[]>('/agents/runs', { params: courseId ? { course_id: courseId } : {} }),
  detail: (id: number) => request.get<any>(`/agents/runs/${id}`),
  byTrace: (trace: string) => request.get<any>(`/agents/trace/${trace}`),
  commandCenter: (courseId?: number | string, silent = false) => request.get<any>('/agents/command_center', { params: courseId ? { course_id: courseId } : {}, silent })
}

export const review = {
  pending: (courseId: number) => request.get(`/review/pending`, { params: { course_id: courseId } }),
  decide: (id: number, data: any) => request.post(`/review/${id}`, data),
  publish: (id: number) => request.post(`/review/${id}/publish`),
  unpublish: (id: number) => request.post(`/review/${id}/unpublish`)
}

export const wrong = {
  list: (courseId: number) => request.get(`/wrong/${courseId}`),
  resolve: (id: number) => request.post(`/wrong/${id}/resolve`)
}

export const question = {
  list: (params: any, silent = false) => request.get<any[]>('/questions', { params, silent }),
  add: (data: any) => request.post<any>('/questions', data),
  update: (id: number, data: any) => request.put<any>(`/questions/${id}`, data, { silent: true }),
  remove: (id: number, silent = false) => request.delete<any>(`/questions/${id}`, { silent })
}

export const stats = {
  teacher: (courseId: number) => request.get(`/stats/teacher/${courseId}`),
  experiment: (courseId: number) => request.get(`/stats/experiment/${courseId}`)
}

export const admin = {
  users: () => request.get('/admin/users'),
  updateUser: (id: number, data: any) => request.put(`/admin/users/${id}`, data),
  updateRole: (id: number, role: 'student' | 'teacher' | 'admin') => request.patch(`/admin/users/${id}/role`, { role }),
  exportSnapshot: () => request.get<Blob>('/admin/data-snapshot', { responseType: 'blob' }),
  configs: () => request.get('/admin/configs'),
  upsertConfig: (data: any) => request.post('/admin/configs', data),
  llmLogs: () => request.get('/admin/llm_logs'),
  dashboard: () => request.get('/admin/dashboard')
}

export const reports = {
  studentMd: (courseId: number) => request.get<string>(`/reports/student/${courseId}.md`, { responseType: 'text' }),
  studentFile: (courseId: number, type: 'md' | 'pdf') =>
    request.get<Blob>(`/reports/student/${courseId}.${type}`, { responseType: 'blob' }),
  classFile: (courseId: number, type: 'md' | 'pdf') =>
    request.get<Blob>(`/reports/class/${courseId}.${type}`, { responseType: 'blob' })
}

export const system = {
  health: () => request.get('/health'),
  info: () => request.get('/system/info')
}
