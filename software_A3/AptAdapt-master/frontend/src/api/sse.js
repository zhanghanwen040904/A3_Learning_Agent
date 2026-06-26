/**
 * SSE 流式连接工具
 * 用于 /chat/send 接口的流式响应
 */
export function createSSEConnection(url, callbacks) {
  const token = localStorage.getItem('token')
  const fullUrl = `/api${url}`

  const eventSource = new EventSource(fullUrl, {
    // Note: EventSource doesn't support custom headers,
    // token is passed via query param or cookie
  })

  eventSource.onmessage = (event) => {
    try {
      const data = JSON.parse(event.data)
      switch (data.event) {
        case 'agent_status':
          callbacks.onAgentStatus?.(data)
          break
        case 'content':
          callbacks.onContent?.(data)
          break
        case 'resource_card':
          callbacks.onResource?.(data)
          break
        case 'review_result':
          callbacks.onReview?.(data)
          break
        case 'error':
          callbacks.onError?.(data)
          break
        case 'done':
          callbacks.onDone?.()
          eventSource.close()
          break
      }
    } catch (e) {
      console.error('SSE parse error:', e)
    }
  }

  eventSource.onerror = (err) => {
    callbacks.onError?.({ message: 'SSE 连接错误' })
    eventSource.close()
  }

  return eventSource
}
