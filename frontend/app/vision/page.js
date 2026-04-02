'use client'
import { useState, useRef, useEffect } from 'react'
import { getApiBaseUrl } from '../../lib/api'
import '../chat/chat.css'

export default function VisionPage() {
  const [image, setImage] = useState(null)
  const [imagePreview, setImagePreview] = useState(null)
  const [response, setResponse] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const fileInputRef = useRef(null)

  const handleImageSelect = (e) => {
    const file = e.target.files?.[0]
    if (!file) return

    if (!file.type.startsWith('image/')) {
      setError('请选择图片文件')
      return
    }

    setImage(file)
    setImagePreview(URL.createObjectURL(file))
    setResponse('')
    setError('')
  }

  const handleDrop = (e) => {
    e.preventDefault()
    const file = e.dataTransfer.files?.[0]
    if (file && file.type.startsWith('image/')) {
      setImage(file)
      setImagePreview(URL.createObjectURL(file))
      setResponse('')
      setError('')
    }
  }

  const handleDragOver = (e) => {
    e.preventDefault()
  }

  const analyzeImage = async () => {
    if (!image || loading) return

    setLoading(true)
    setResponse('')
    setError('')

    try {
      const apiBase = getApiBaseUrl()
      const formData = new FormData()
      formData.append('file', image)

      const res = await fetch(`${apiBase}/api/vision`, {
        method: 'POST',
        body: formData,
      })

      const data = await res.json()

      if (!res.ok) {
        throw new Error(data.detail || '分析失败')
      }

      setResponse(data.content || '没有返回内容')
    } catch (err) {
      setError(err.message || '请求失败')
    } finally {
      setLoading(false)
    }
  }

  const clearImage = () => {
    setImage(null)
    setImagePreview(null)
    setResponse('')
    setError('')
    if (fileInputRef.current) {
      fileInputRef.current.value = ''
    }
  }

  return (
    <div className="chat-page">
      <div className="page-header">
        <h2>AI 视觉识别测试</h2>
        <p>上传图片，测试 AI 视觉理解功能</p>
      </div>

      <div className="chat-container">
        <div className="chat-messages">
          {!imagePreview && !response && !error && (
            <div
              className="chat-bubble-wrap assistant"
              style={{ justifyContent: 'center', alignItems: 'center', padding: '40px 0' }}
            >
              <div className="chat-bubble assistant" style={{ textAlign: 'center', maxWidth: '90%' }}>
                <div style={{ marginBottom: '12px', opacity: 0.7 }}>
                  点击下方按钮选择图片，或拖拽图片到此处
                </div>
                <div style={{ fontSize: '12px', opacity: 0.5 }}>
                  支持 PNG、JPG、GIF、WebP 等格式
                </div>
              </div>
            </div>
          )}

          {imagePreview && (
            <div className="chat-bubble-wrap user">
              <div className="chat-bubble user" style={{ maxWidth: '80%', padding: '8px' }}>
                <img
                  src={imagePreview}
                  alt="Preview"
                  style={{
                    maxWidth: '100%',
                    maxHeight: '300px',
                    borderRadius: '8px',
                    display: 'block'
                  }}
                />
              </div>
            </div>
          )}

          {loading && (
            <div className="chat-bubble-wrap assistant">
              <div className="chat-bubble assistant">
                <span className="chat-typing"><span /><span /><span /></span>
                <span style={{ marginLeft: '8px', opacity: 0.7 }}>AI 正在分析图片...</span>
              </div>
            </div>
          )}

          {error && (
            <div className="chat-bubble-wrap assistant">
              <div className="chat-bubble assistant" style={{ color: '#ef4444' }}>
                {error}
              </div>
            </div>
          )}

          {response && (
            <div className="chat-bubble-wrap assistant">
              <div className="chat-bubble assistant">
                {response}
              </div>
            </div>
          )}
        </div>

        <div className="chat-input-row">
          <input
            ref={fileInputRef}
            type="file"
            accept="image/*"
            onChange={handleImageSelect}
            style={{ display: 'none' }}
          />

          {imagePreview ? (
            <>
              <button
                className="chat-send-btn"
                onClick={analyzeImage}
                disabled={loading}
                style={{ flex: 1 }}
              >
                {loading ? '分析中...' : '开始分析'}
              </button>
              <button
                onClick={clearImage}
                className="chat-send-btn"
                style={{
                  flex: '0 0 auto',
                  background: 'var(--bg-secondary)',
                  border: '1px solid var(--border)',
                  opacity: loading ? 0.5 : 1
                }}
                disabled={loading}
              >
                清除
              </button>
            </>
          ) : (
            <button
              className="chat-send-btn"
              onClick={() => fileInputRef.current?.click()}
              style={{ flex: 1 }}
            >
              选择图片
            </button>
          )}
        </div>

        <div
          style={{
            padding: '12px 20px',
            borderTop: '1px solid var(--border)',
            background: 'var(--glass-bg)',
            fontSize: '12px',
            color: 'var(--text-muted)',
            cursor: 'pointer'
          }}
          onClick={() => fileInputRef.current?.click()}
          onDrop={handleDrop}
          onDragOver={handleDragOver}
        >
          或拖拽图片到此处
        </div>
      </div>
    </div>
  )
}
