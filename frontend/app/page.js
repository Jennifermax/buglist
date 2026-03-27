'use client'
import { useState, useEffect, useRef } from 'react'
import Link from 'next/link'

const STEPS = ['文件上传', '生成用例', '执行测试', '测试报告']

export default function Home() {
  const [currentStep, setCurrentStep] = useState(1)
  const [uploadType, setUploadType] = useState('file')
  const [document, setDocument] = useState('')
  const [testcases, setTestcases] = useState([])
  const [progress, setProgress] = useState(null)
  const [isExecuting, setIsExecuting] = useState(false)
  const [config, setConfig] = useState(null)
  const fileInputRef = useRef(null)

  // 加载配置
  useEffect(() => {
    fetch('http://localhost:8000/api/config/ai')
      .then(r => r.json())
      .then(setConfig)
      .catch(() => {})
  }, [])

  const getStepClass = (stepNum) => {
    if (stepNum < currentStep) return 'step-complete'
    if (stepNum === currentStep) return 'step-active'
    return 'step-pending'
  }

  const handleFileUpload = async (e) => {
    const file = e.target.files?.[0]
    if (!file) return

    if (file.name.endsWith('.json')) {
      const text = await file.text()
      try {
        const cases = JSON.parse(text)
        if (Array.isArray(cases)) {
          setTestcases(cases)
          setCurrentStep(2)
          return
        }
      } catch {}
    }
    alert('仅支持 JSON 格式的测试用例文件')
  }

  const generateTestcases = async () => {
    if (!document.trim()) {
      alert('请输入产品文档内容')
      return
    }

    if (!config?.api_key) {
      alert('请先在设置页面配置 AI API')
      return
    }

    try {
      const res = await fetch('http://localhost:8000/api/testcases/generate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(document)
      })
      const data = await res.json()
      setTestcases(data.cases || [])
      setCurrentStep(2)
    } catch (err) {
      console.error(err)
      alert('生成失败，请检查后端服务')
    }
  }

  const executeTests = async () => {
    if (!config?.api_key) {
      alert('请先在设置页面配置 AI API')
      return
    }

    if (testcases.length === 0) {
      alert('没有可执行的测试用例')
      return
    }

    setIsExecuting(true)

    try {
      const ws = new WebSocket('ws://localhost:8000/ws/execute/test1')

      ws.onopen = () => {
        ws.send(JSON.stringify({
          testcases: testcases,
          ai_config: config
        }))
        setCurrentStep(3)
      }

      ws.onmessage = (event) => {
        const msg = JSON.parse(event.data)

        if (msg.type === 'progress') {
          setProgress({
            current_step: msg.data.current_step,
            total_steps: msg.data.total_steps,
            current_testcase: msg.data.current_testcase,
            passed: msg.data.passed,
            failed: msg.data.failed,
            status: 'running'
          })
        } else if (msg.type === 'step_complete') {
          // 单个用例完成
        } else if (msg.type === 'all_complete') {
          setProgress({
            total: msg.data.total,
            passed: msg.data.passed,
            failed: msg.data.failed,
            status: 'complete'
          })
          setCurrentStep(4)
          setIsExecuting(false)
          ws.close()
        }
      }

      ws.onerror = () => {
        alert('WebSocket 连接失败')
        setIsExecuting(false)
      }

      ws.onclose = () => {
        setIsExecuting(false)
      }
    } catch (err) {
      console.error(err)
      alert('执行失败，请检查后端服务')
      setIsExecuting(false)
    }
  }

  const getStatusIcon = (stepNum) => {
    if (stepNum < currentStep) return '✓'
    if (stepNum === currentStep) return stepNum
    return stepNum
  }

  return (
    <>
      <div className="page-header">
        <h2>自动化测试平台</h2>
        <p>基于 AI 的自动化 UI 测试系统</p>
      </div>

      {/* Stepper */}
      <div className="stepper">
        {STEPS.map((label, index) => {
          const stepNum = index + 1
          return (
            <div key={stepNum} className={`step ${getStepClass(stepNum)}`}>
              <div className="step-circle">
                {getStatusIcon(stepNum)}
              </div>
              <span className="step-label">{label}</span>
              {stepNum < STEPS.length && (
                <div className="step-line">
                  <div
                    className="step-line-fill"
                    style={{ width: stepNum < currentStep ? '100%' : '0%' }}
                  />
                </div>
              )}
            </div>
          )
        })}
      </div>

      {/* Step 1: 文件上传 */}
      {currentStep === 1 && (
        <div className="card animate-fadeIn">
          <div className="tabs">
            <button
              className={`tab ${uploadType === 'file' ? 'active' : ''}`}
              onClick={() => setUploadType('file')}
            >
              文件上传
            </button>
            <button
              className={`tab ${uploadType === 'text' ? 'active' : ''}`}
              onClick={() => setUploadType('text')}
            >
              手动输入
            </button>
          </div>

          {uploadType === 'file' ? (
            <div
              className="upload-area"
              onClick={() => fileInputRef.current?.click()}
            >
              <input
                ref={fileInputRef}
                type="file"
                accept=".json"
                onChange={handleFileUpload}
                style={{ display: 'none' }}
              />
              <div className="upload-icon">↑</div>
              <h3>拖拽或点击上传</h3>
              <p>支持 JSON 格式的测试用例文件 · 可直接跳过 AI 生成步骤</p>
            </div>
          ) : (
            <div>
              <div className="form-group">
                <label className="form-label">产品文档内容</label>
                <textarea
                  className="form-input"
                  value={document}
                  onChange={e => setDocument(e.target.value)}
                  placeholder="粘贴产品需求文档内容，AI 将根据此内容生成测试用例..."
                />
              </div>
              <button className="btn btn-primary" onClick={generateTestcases}>
                生成测试用例 →
              </button>
            </div>
          )}
        </div>
      )}

      {/* Step 2: 用例管理 */}
      {currentStep === 2 && (
        <div className="animate-fadeIn">
          <div className="card" style={{ marginBottom: 24 }}>
            <div className="card-header">
              <h3 className="card-title">生成的测试用例 ({testcases.length} 个)</h3>
              <span className="badge badge-success">
                ✓ 已生成
              </span>
            </div>
            <p style={{ color: 'var(--text-secondary)', fontSize: 13, marginBottom: 20 }}>
              请审核测试用例，确认无误后开始执行。如需修改，可直接编辑 JSON 数据。
            </p>

            <div className="testcase-list">
              {testcases.map((tc, index) => (
                <div key={tc.id || index} className="testcase-item">
                  <span className="testcase-id">{tc.id || `TC${index + 1}`}</span>
                  <div className="testcase-content">
                    <div className="testcase-name">{tc.name}</div>
                    <div className="testcase-steps">
                      {tc.steps?.length || 0} 个步骤 · {tc.precondition || '无前置条件'}
                    </div>
                  </div>
                  <span className="testcase-status pending">待执行</span>
                </div>
              ))}
            </div>
          </div>

          <div style={{ display: 'flex', gap: 12 }}>
            <button className="btn btn-secondary" onClick={() => setCurrentStep(1)}>
              ← 上一步
            </button>
            <button className="btn btn-primary btn-lg" onClick={executeTests}>
              开始执行测试 →
            </button>
          </div>
        </div>
      )}

      {/* Step 3: 执行测试 */}
      {currentStep === 3 && (
        <div className="animate-fadeIn">
          <div className="progress-stats">
            <div className="stat-card">
              <div className="stat-value total">{progress?.total_steps || testcases.length}</div>
              <div className="stat-label">总用例数</div>
            </div>
            <div className="stat-card">
              <div className="stat-value passed">{progress?.passed || 0}</div>
              <div className="stat-label">已通过</div>
            </div>
            <div className="stat-card">
              <div className="stat-value failed">{progress?.failed || 0}</div>
              <div className="stat-label">已失败</div>
            </div>
          </div>

          <div className="card">
            <div className="card-header">
              <h3 className="card-title">执行进度</h3>
              <span className="badge badge-warning">
                <span className="loading-dots">●</span> 执行中
              </span>
            </div>

            <div style={{ marginBottom: 16 }}>
              <div style={{
                display: 'flex',
                justifyContent: 'space-between',
                fontSize: 13,
                color: 'var(--text-secondary)',
                marginBottom: 8
              }}>
                <span>正在执行: {progress?.current_testcase || '等待开始...'}</span>
                <span>{progress?.current_step || 0} / {progress?.total_steps || testcases.length}</span>
              </div>
              <div style={{
                height: 8,
                background: 'var(--border)',
                borderRadius: 4,
                overflow: 'hidden'
              }}>
                <div style={{
                  height: '100%',
                  width: `${progress ? (progress.current_step / progress.total_steps) * 100 : 0}%`,
                  background: 'linear-gradient(90deg, var(--accent), var(--accent-light))',
                  borderRadius: 4,
                  transition: 'width 0.3s ease'
                }} />
              </div>
            </div>

            <div style={{
              padding: 16,
              background: 'var(--bg-primary)',
              borderRadius: 'var(--radius)',
              fontFamily: "'JetBrains Mono', monospace",
              fontSize: 13,
              color: 'var(--text-secondary)'
            }}>
              {isExecuting ? (
                <p>▶ Playwright 浏览器启动中...</p>
              ) : (
                <p>等待执行...</p>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Step 4: 测试报告 */}
      {currentStep === 4 && progress?.status === 'complete' && (
        <div className="animate-fadeIn">
          <div className="progress-stats">
            <div className="stat-card">
              <div className="stat-value total">{progress.total}</div>
              <div className="stat-label">总用例数</div>
            </div>
            <div className="stat-card">
              <div className="stat-value passed">{progress.passed}</div>
              <div className="stat-label">已通过</div>
            </div>
            <div className="stat-card">
              <div className="stat-value failed">{progress.failed}</div>
              <div className="stat-label">已失败</div>
            </div>
          </div>

          <div className="card">
            <div className="card-header">
              <h3 className="card-title">测试报告</h3>
              <span className="badge badge-success">
                ✓ 测试完成
              </span>
            </div>

            <div style={{
              textAlign: 'center',
              padding: '32px 0'
            }}>
              <div style={{
                fontSize: 48,
                fontFamily: "'JetBrains Mono', monospace",
                fontWeight: 700,
                color: progress.passed === progress.total ? 'var(--success)' : 'var(--warning)',
                marginBottom: 8
              }}>
                {Math.round((progress.passed / progress.total) * 100)}%
              </div>
              <p style={{ color: 'var(--text-secondary)' }}>
                通过率 · {progress.passed} 通过 / {progress.failed} 失败
              </p>
            </div>

            <div style={{
              display: 'flex',
              gap: 12,
              justifyContent: 'center',
              marginTop: 24
            }}>
              <button className="btn btn-secondary" onClick={() => window.location.reload()}>
                重新开始
              </button>
              <button className="btn btn-primary">
                提交禅道 (预留)
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  )
}
