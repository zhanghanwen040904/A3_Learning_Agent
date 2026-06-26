import api from './index'

export function sendMessage(message, course = 'computer_organization', chapter = '') {
  return api.post('/chat/send', { message, course, chapter })
}

export function getProfile(userId = 'demo_user') {
  return api.get('/profile/get', { params: { user_id: userId } })
}

export function generateResource(knowledgePoint, resourceTypes, course = 'computer_organization') {
  return api.post('/resource/generate', {
    knowledge_point: knowledgePoint,
    resource_types: resourceTypes,
    course
  })
}
