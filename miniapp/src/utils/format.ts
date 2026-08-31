export const formatTime = (iso?: string): string => {
  if (!iso) return ''
  return iso.slice(0, 16).replace('T', ' ')
}

export const formatDate = (iso?: string): string => {
  if (!iso) return ''
  return iso.slice(0, 10)
}

export const shortText = (text: string, len = 36): string => {
  if (!text) return ''
  return text.length > len ? text.slice(0, len) + '...' : text
}

export const truncate = (text: string, len = 80): string => {
  if (!text) return ''
  return text.length > len ? text.slice(0, len) + '…' : text
}
