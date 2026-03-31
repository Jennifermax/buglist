'use client'
import { useState, useEffect } from 'react'
import { OPENAI_MODEL_OPTIONS, getApiBaseUrl } from '../../lib/api'

export default function Settings() {
  const [aiConfig, setAiConfig] = useState({
    provider: 'openai',
    api_url: '',
    api_key: '',
    model: 'gpt-5.3'
  })
  const [zentaoConfig, setZentaoConfig] = useState({
    url: '',
    account: '',
    password: '',
    token: ''
  })
  const [customModel, setCustomModel] = useState('')
  const [saving, setSaving] = useState(false)
  const [message, setMessage] = useState(null)
  const [apiBaseUrl, setApiBaseUrl] = useState('http://127.0.0.1:8000')
  const [zentaoTesting, setZentaoTesting] = useState(false)
  const [zentaoProducts, setZentaoProducts] = useState([])
  const [loadingProducts, setLoadingProducts] = useState(false)
  const [connectionStatus, setConnectionStatus] = useState(null)

  useEffect(() => {
    const baseUrl = getApiBaseUrl()
    setApiBaseUrl(baseUrl)

    fetch(`${baseUrl}/api/config/ai`)
      .then(r => r.json())
      .then(data => {
        const isKnownModel = data.model && OPENAI_MODEL_OPTIONS.some(option => option.value === data.model)
        setAiConfig({
          ...data,
          model: isKnownModel ? data.model : '__custom__'
        })
        if (data.model && !isKnownModel) {
          setCustomModel(data.model)
        }
      })
      .catch(() => {})

    fetch(`${baseUrl}/api/config/zentao`)
      .then(r => r.json())
      .then(data => {
        setZentaoConfig(data)
        if (data.url && data.account && data.token) {
          testZentaoConnection(baseUrl, data)
        }
      })
      .catch(() => {})
  }, [])

  const showMessage = (text, type = 'success') => {
    setMessage({ text, type })
    setTimeout(() => setMessage(null), 3000)
   }

  const saveAiConfig = async () => {
    setSaving(true)
    try {
      const res = await fetch(`${apiBaseUrl}/api/config/ai`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(aiConfig)
      })
      if (res.ok) {
        showMessage('AI 配置已保存')
      } else {
        showMessage('保存失败', 'error')
      }
    } catch {
      showMessage('保存失败，请检查后端服务', 'error')
    }
    setSaving(false)
  }

  const saveZentaoConfig = async () => {
    setSaving(true)
    try {
      const res = await fetch(`${apiBaseUrl}/api/config/zentao`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(zentaoConfig)
      })
      if (res.ok) {
        showMessage('禅道配置已保存')
        testZentaoConnection(apiBaseUrl, zentaoConfig)
      } else {
        showMessage('保存失败', 'error')
      }
    } catch {
      showMessage('保存失败，请检查后端服务', 'error')
    }
    setSaving(false)
  }

  const testZentaoConnection = async (baseUrl, config = zentaoConfig) => {
    if (!config.url || !config.account) {
      setConnectionStatus(null)
      return
    }

    setZentaoTesting(true)
    try {
      const res = await fetch(`${baseUrl}/api/zentao/test-connection`, {
        method: 'POST'
      })
      const data = await res.json()
      setConnectionStatus(data)
      if (data.success) {
        loadZentaoProducts(baseUrl)
      }
    } catch (e) {
      setConnectionStatus({ success: false, message: '连接失败: ' + e.message })
    }
    setZentaoTesting(false)
  }

  const loadZentaoProducts = async (baseUrl) => {
    setLoadingProducts(true)
    try {
      const res = await fetch(`${baseUrl}/api/zentao/products`)
      const data = await res.json()
      if (data.success) {
        setZentaoProducts(data.data || [])
      } else {
        setZentaoProducts([])
      }
    } catch {
      setZentaoProducts([])
    }
    setLoadingProducts(false)
  }

  return (
    <>
      <div className="page-header">
        <h2>系统设置</h2>
        <p>配置 AI API 和禅道集成</p>
      </div>

      {message && (
        <div style={{
          padding: '12px 16px',
          borderRadius: 'var(--radius)',
          marginBottom: 24,
          background: message.type === 'error' ? 'var(--danger-bg)' : 'var(--success-bg)',
          color: message.type === 'error' ? 'var(--danger)' : 'var(--success)',
          fontSize: 14,
          fontWeight: 500
        }}>
          {message.text}
        </div>
      )}

      <div className="grid-2">
        {/* AI 配置 */}
        <div className="card">
          <div className="card-header">
            <h3 className="card-title">AI 配置</h3>
            <span className="badge badge-success">OpenAI 兼容</span>
          </div>

          <div className="form-group">
            <label className="form-label">API 提供商</label>
            <select
              className="form-input form-select"
              value={aiConfig.provider}
              onChange={e => setAiConfig({ ...aiConfig, provider: e.target.value })}
            >
              <option value="openai">OpenAI / 中转 API</option>
              <option value="azure-openai">Azure OpenAI</option>
              <option value="custom-openai-compatible">自定义 OpenAI 兼容服务</option>
            </select>
          </div>

          <div className="form-group">
            <label className="form-label">API 地址</label>
            <input
              type="text"
              className="form-input"
              value={aiConfig.api_url}
              onChange={e => setAiConfig({ ...aiConfig, api_url: e.target.value })}
              placeholder="https://api.openai.com/v1 或中转地址"
            />
          </div>

          <div className="form-group">
            <label className="form-label">API Key</label>
            <input
              type="password"
              className="form-input"
              value={aiConfig.api_key}
              onChange={e => setAiConfig({ ...aiConfig, api_key: e.target.value })}
              placeholder="sk-..."
            />
          </div>

          <div className="form-group">
            <label className="form-label">模型</label>
            <select
              className="form-input form-select"
              value={aiConfig.model}
              onChange={e => {
                const value = e.target.value
                setAiConfig({ ...aiConfig, model: value })
                if (value !== '__custom__') {
                  setCustomModel('')
                }
              }}
            >
              {OPENAI_MODEL_OPTIONS.map(option => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
              <option value="__custom__">自定义模型</option>
            </select>
          </div>

          {(aiConfig.model === '__custom__' || customModel) && (
            <div className="form-group">
              <label className="form-label">自定义模型名</label>
              <input
                type="text"
                className="form-input"
                value={aiConfig.model === '__custom__' ? customModel : aiConfig.model}
                onChange={e => {
                  const value = e.target.value
                  setCustomModel(value)
                  setAiConfig({ ...aiConfig, model: value })
                }}
                placeholder="例如：gpt-5.2-chat-latest"
              />
            </div>
          )}

          <button
            className="btn btn-primary"
            onClick={saveAiConfig}
            disabled={saving}
            style={{ width: '100%' }}
          >
            {saving ? '保存中...' : '保存 AI 配置'}
          </button>
        </div>

        {/* 禅道配置 */}
        <div className="card">
          <div className="card-header">
            <h3 className="card-title">禅道配置</h3>
            {connectionStatus && (
              <span className={`badge ${connectionStatus.success ? 'badge-success' : 'badge-danger'}`}>
                {connectionStatus.success ? '已连接' : '未连接'}
              </span>
            )}
          </div>

          {connectionStatus && connectionStatus.message && (
            <div style={{
              padding: 12,
              background: connectionStatus.success ? 'var(--success-bg)' : 'var(--danger-bg)',
              borderRadius: 'var(--radius)',
              marginBottom: 20,
              fontSize: 13,
              color: connectionStatus.success ? 'var(--success)' : 'var(--danger)'
            }}>
              {connectionStatus.message}
            </div>
          )}

          <div className="form-group">
            <label className="form-label">禅道地址</label>
            <input
              type="text"
              className="form-input"
              value={zentaoConfig.url}
              onChange={e => setZentaoConfig({ ...zentaoConfig, url: e.target.value })}
              placeholder="https://your-zentao.com"
            />
          </div>

          <div className="form-group">
            <label className="form-label">账号</label>
            <input
              type="text"
              className="form-input"
              value={zentaoConfig.account}
              onChange={e => setZentaoConfig({ ...zentaoConfig, account: e.target.value })}
              placeholder="username"
            />
          </div>

          <div className="form-group">
            <label className="form-label">密码</label>
            <input
              type="password"
              className="form-input"
              value={zentaoConfig.password}
              onChange={e => setZentaoConfig({ ...zentaoConfig, password: e.target.value })}
              placeholder="禅道登录密码"
            />
          </div>

          <div className="form-group">
            <label className="form-label">Token (可选)</label>
            <input
              type="password"
              className="form-input"
              value={zentaoConfig.token}
              onChange={e => setZentaoConfig({ ...zentaoConfig, token: e.target.value })}
              placeholder="API Token (在禅道个人设置中获取)"
            />
            <small style={{ color: 'var(--text-secondary)', fontSize: 12, marginTop: 4, display: 'block' }}>
              填入密码后会自动获取 Token
            </small>
          </div>

          <div style={{ display: 'flex', gap: 12, marginBottom: 12 }}>
            <button
              className="btn btn-secondary"
              onClick={saveZentaoConfig}
              disabled={saving}
              style={{ flex: 1 }}
            >
              保存配置
            </button>
            <button
              className="btn btn-outline"
              onClick={() => testZentaoConnection(apiBaseUrl)}
              disabled={zentaoTesting || !zentaoConfig.url || !zentaoConfig.account}
              style={{ flex: 1 }}
            >
              {zentaoTesting ? '测试中...' : '测试连接'}
            </button>
          </div>

          {loadingProducts ? (
            <div style={{ textAlign: 'center', padding: 20, color: 'var(--text-secondary)' }}>
              加载产品列表...
            </div>
          ) : zentaoProducts.length > 0 ? (
            <div>
              <label className="form-label">产品列表</label>
              <div style={{
                maxHeight: 200,
                overflowY: 'auto',
                border: '1px solid var(--border)',
                borderRadius: 'var(--radius)',
                padding: 8
              }}>
                {zentaoProducts.map((product, index) => (
                  <div key={index} style={{
                    padding: '8px 12px',
                    borderBottom: '1px solid var(--border)',
                    fontSize: 13
                  }}>
                    <div style={{ fontWeight: 500 }}>{product.name || product.title}</div>
                    <div style={{ color: 'var(--text-secondary)', fontSize: 12 }}>
                      ID: {product.id}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          ) : null}
        </div>
      </div>
    </>
  )
}
