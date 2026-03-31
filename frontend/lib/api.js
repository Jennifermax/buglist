export const OPENAI_MODEL_OPTIONS = [
  { value: 'gpt-5.3', label: 'GPT-5.3' },
  { value: 'gpt-5.3-chat-latest', label: 'GPT-5.3 Chat' },
  { value: 'gpt-5.2-chat-latest', label: 'GPT-5.2 Chat (ChatGPT 当前聊天模型)' },
  { value: 'gpt-5.1-chat-latest', label: 'GPT-5.1 Chat' },
  { value: 'gpt-5-chat-latest', label: 'GPT-5 Chat' },
  { value: 'chatgpt-4o-latest', label: 'ChatGPT-4o' },
  { value: 'gpt-5.2', label: 'GPT-5.2' },
  { value: 'gpt-5.1', label: 'GPT-5.1' },
  { value: 'gpt-5', label: 'GPT-5' },
  { value: 'gpt-5-mini', label: 'GPT-5 mini' },
  { value: 'gpt-5-nano', label: 'GPT-5 nano' },
  { value: 'gpt-4.1', label: 'GPT-4.1' },
  { value: 'gpt-4.1-mini', label: 'GPT-4.1 mini' },
  { value: 'gpt-4.1-nano', label: 'GPT-4.1 nano' },
  { value: 'gpt-4o', label: 'GPT-4o' },
  { value: 'gpt-4o-mini', label: 'GPT-4o mini' },
  { value: 'gpt-4-turbo', label: 'GPT-4 Turbo' },
  { value: 'gpt-3.5-turbo', label: 'GPT-3.5 Turbo' },
]

export function getApiBaseUrl() {
  if (typeof window === 'undefined') {
    return 'http://127.0.0.1:8000'
  }

  const hostname = window.location.hostname
  const resolvedHost = (hostname === 'localhost' || !hostname) ? '127.0.0.1' : hostname
  const protocol = window.location.protocol === 'https:' ? 'https:' : 'http:'
  return `${protocol}//${resolvedHost}:8000`
}

export function getWebSocketBaseUrl() {
  if (typeof window === 'undefined') {
    return 'ws://127.0.0.1:8000'
  }

  const hostname = window.location.hostname
  const resolvedHost = (hostname === 'localhost' || !hostname) ? '127.0.0.1' : hostname
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
  return `${protocol}//${resolvedHost}:8000`
}
