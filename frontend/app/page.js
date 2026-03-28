'use client'
import { useEffect, useRef, useState } from 'react'
import * as XLSX from 'xlsx'
import { getApiBaseUrl, getWebSocketBaseUrl } from '../lib/api'

const STEPS = ['文件上传', '生成用例', '执行测试', '测试报告']
const STEP_TWO_TABS = ['上传文档', '上传测试用例', '手动输入测试用例']

const MANUAL_CASE_TEMPLATE = `[
  {
    "name": "登录页基础验证",
    "precondition": "测试环境可访问",
    "steps": [
      {
        "action": "打开页面",
        "description": "打开登录页面",
        "value": "https://example.com/login"
      },
      {
        "action": "输入",
        "description": "输入用户名",
        "value": "demo-user"
      },
      {
        "action": "输入",
        "description": "输入密码",
        "value": "demo-password"
      },
      {
        "action": "点击",
        "description": "点击登录按钮",
        "value": ""
      },
      {
        "action": "验证",
        "description": "页面应显示登录成功后的内容",
        "value": ""
      }
    ]
  }
]`

const DOCUMENT_TYPE_TEMPLATES = {
  excel: `表名：登录测试
列：模块 | 场景 | 前置条件 | 步骤 | 预期结果
行1：认证 | 用户名密码登录 | 已创建有效账号 | 打开登录页；输入用户名；输入密码；点击登录 | 登录成功并进入首页
行2：认证 | 错误密码提示 | 已创建有效账号 | 打开登录页；输入用户名；输入错误密码；点击登录 | 页面提示用户名或密码错误`,
  prd: `模块：登录
功能点：用户名密码登录
前置条件：用户已注册
正常流程：
1. 打开登录页
2. 输入用户名和密码
3. 点击登录
预期结果：进入首页

异常流程：
1. 输入错误密码
2. 点击登录
预期结果：显示错误提示`,
  testcase: `模块：登录
用例名称：登录成功
前置条件：已存在可用账号
步骤：
1. 打开登录页面
2. 输入正确用户名
3. 输入正确密码
4. 点击登录按钮
预期结果：跳转首页并显示用户信息`,
}

function normalizeGeneratedCases(cases = []) {
  return cases.map((tc, index) => ({
    id: tc.id || `TC${index + 1}`,
    name: tc.name || `未命名用例 ${index + 1}`,
    precondition: tc.precondition || '',
    steps: Array.isArray(tc.steps) ? tc.steps : [],
    status: tc.status || 'pending',
  }))
}

function buildDocumentFromWorkbook(fileName, workbook) {
  const sheetSummaries = workbook.SheetNames.map(sheetName => {
    const sheet = workbook.Sheets[sheetName]
    const rows = XLSX.utils.sheet_to_json(sheet, { header: 1, defval: '' })
    const previewRows = rows
      .slice(0, 20)
      .map(row => row.join(' | '))
      .join('\n')

    return `工作表：${sheetName}\n${previewRows}`.trim()
  }).filter(Boolean)

  return `文件名：${fileName}\n文档类型：Excel\n\n${sheetSummaries.join('\n\n')}`.trim()
}

export default function Home() {
  const [currentStep, setCurrentStep] = useState(1)
  const [uploadType, setUploadType] = useState('file')
  const [stepTwoTab, setStepTwoTab] = useState('上传文档')
  const [document, setDocument] = useState('')
  const [documentFileName, setDocumentFileName] = useState('')
  const [documentPreview, setDocumentPreview] = useState('')
  const [manualDocumentType, setManualDocumentType] = useState('excel')
  const [manualCaseInput, setManualCaseInput] = useState(MANUAL_CASE_TEMPLATE)
  const [manualDocumentInput, setManualDocumentInput] = useState(DOCUMENT_TYPE_TEMPLATES.excel)
  const [testcases, setTestcases] = useState([])
  const [progress, setProgress] = useState(null)
  const [isExecuting, setIsExecuting] = useState(false)
  const [executionError, setExecutionError] = useState('')
  const [config, setConfig] = useState(null)
  const [apiBaseUrl, setApiBaseUrl] = useState('http://127.0.0.1:8000')
  const [wsBaseUrl, setWsBaseUrl] = useState('ws://127.0.0.1:8000')

  const testcaseFileInputRef = useRef(null)
  const documentFileInputRef = useRef(null)

  useEffect(() => {
    const baseUrl = getApiBaseUrl()
    const wsUrl = getWebSocketBaseUrl()
    setApiBaseUrl(baseUrl)
    setWsBaseUrl(wsUrl)

    fetch(`${baseUrl}/api/config/ai`)
      .then(r => r.json())
      .then(setConfig)
      .catch(() => {})
  }, [])

  const getStepClass = (stepNum) => {
    if (stepNum < currentStep) return 'step-complete'
    if (stepNum === currentStep) return 'step-active'
    return 'step-pending'
  }

  const canNavigateToStep = (stepNum) => {
    if (stepNum === 1) return true
    if (stepNum === 2) return true
    if (stepNum === 3) return testcases.length > 0
    if (stepNum === 4) return progress?.status === 'complete'
    return false
  }

  const handleStepClick = (stepNum) => {
    if (!canNavigateToStep(stepNum)) return
    setCurrentStep(stepNum)
  }

  const handleTestcaseUpload = async (e) => {
    const file = e.target.files?.[0]
    if (!file) return

    if (file.name.endsWith('.json')) {
      const text = await file.text()
      try {
        const cases = JSON.parse(text)
        if (Array.isArray(cases)) {
          setTestcases(normalizeGeneratedCases(cases))
          setCurrentStep(2)
          setStepTwoTab('上传测试用例')
          e.target.value = ''
          return
        }
      } catch {}
    }

    e.target.value = ''
    alert('仅支持 JSON 格式的测试用例文件')
  }

  const handleDocumentUpload = async (e) => {
    const file = e.target.files?.[0]
    if (!file) return

    const lowerName = file.name.toLowerCase()
    if (!lowerName.endsWith('.xlsx') && !lowerName.endsWith('.xls')) {
      e.target.value = ''
      alert('请上传 Excel 文档（.xlsx 或 .xls）')
      return
    }

    try {
      const arrayBuffer = await file.arrayBuffer()
      const workbook = XLSX.read(arrayBuffer, { type: 'array' })
      const parsedDocument = buildDocumentFromWorkbook(file.name, workbook)

      setDocument(parsedDocument)
      setDocumentFileName(file.name)
      setDocumentPreview(parsedDocument)
      setCurrentStep(2)
      setStepTwoTab('上传文档')
    } catch (error) {
      console.error(error)
      alert('Excel 文档解析失败，请检查文件内容')
    } finally {
      e.target.value = ''
    }
  }

  const generateTestcasesFromDocument = async (sourceDocument) => {
    if (!sourceDocument.trim()) {
      alert('请先提供文档内容')
      return
    }

    if (!config?.api_key) {
      alert('请先在设置页面配置 AI API')
      return
    }

    try {
      const res = await fetch(`${apiBaseUrl}/api/testcases/generate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(sourceDocument)
      })
      const data = await res.json()
      setTestcases(normalizeGeneratedCases(data.cases || []))
      setCurrentStep(2)
    } catch (err) {
      console.error(err)
      alert('生成失败，请检查后端服务')
    }
  }

  const handleManualCaseImport = () => {
    try {
      const parsed = JSON.parse(manualCaseInput)
      if (!Array.isArray(parsed)) {
        throw new Error('invalid')
      }

      setTestcases(normalizeGeneratedCases(parsed))
      setCurrentStep(2)
      setStepTwoTab('手动输入测试用例')
    } catch {
      alert('手动输入的测试用例必须是合法的 JSON 数组')
    }
  }

  const handleManualDocumentGenerate = async () => {
    const sourceDocument = `文档类型：${manualDocumentType}\n\n${manualDocumentInput}`.trim()
    await generateTestcasesFromDocument(sourceDocument)
    setStepTwoTab('手动输入测试用例')
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
    setExecutionError('')

    try {
      const ws = new WebSocket(`${wsBaseUrl}/ws/execute/test1`)

      ws.onopen = () => {
        ws.send(JSON.stringify({
          testcases,
          ai_config: config,
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
            status: 'running',
          })
        } else if (msg.type === 'error') {
          setExecutionError(msg.data?.message || '测试执行失败')
          setProgress(prev => ({
            ...(prev || {}),
            status: 'error',
          }))
          setIsExecuting(false)
          ws.close()
        } else if (msg.type === 'all_complete') {
          setProgress({
            total: msg.data.total,
            passed: msg.data.passed,
            failed: msg.data.failed,
            status: 'complete',
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
    return stepNum
  }

  return (
    <>
      <input
        ref={testcaseFileInputRef}
        type="file"
        accept=".json"
        onChange={handleTestcaseUpload}
        style={{ display: 'none' }}
      />
      <input
        ref={documentFileInputRef}
        type="file"
        accept=".xlsx,.xls,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet,application/vnd.ms-excel"
        onChange={handleDocumentUpload}
        style={{ display: 'none' }}
      />

      <div className="page-header">
        <h2>自动化测试平台</h2>
        <p>基于 AI 的自动化 UI 测试系统</p>
      </div>

      <div className="stepper">
        {STEPS.map((label, index) => {
          const stepNum = index + 1
          const isClickable = canNavigateToStep(stepNum)
          return (
            <div
              key={stepNum}
              className={`step ${getStepClass(stepNum)} ${isClickable ? 'step-clickable' : 'step-locked'}`}
            >
              <button
                type="button"
                className="step-button"
                onClick={() => handleStepClick(stepNum)}
                disabled={!isClickable}
                aria-current={stepNum === currentStep ? 'step' : undefined}
              >
                <div className="step-circle">{getStatusIcon(stepNum)}</div>
                <span className="step-label">{label}</span>
              </button>
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

      {currentStep === 1 && (
        <div className="card animate-fadeIn">
          <div className="tabs">
            <button
              className={`tab ${uploadType === 'file' ? 'active' : ''}`}
              onClick={() => setUploadType('file')}
            >
              上传测试用例
            </button>
            <button
              className={`tab ${uploadType === 'text' ? 'active' : ''}`}
              onClick={() => setUploadType('text')}
            >
              手动输入文档
            </button>
          </div>

          {uploadType === 'file' ? (
            <div
              className="upload-area"
              onClick={() => testcaseFileInputRef.current?.click()}
            >
              <div className="upload-icon">↑</div>
              <h3>拖拽或点击上传测试用例</h3>
              <p>支持 JSON 格式的测试用例文件，可直接进入第 2 步审核和执行</p>
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
              <button className="btn btn-primary" onClick={() => generateTestcasesFromDocument(document)}>
                生成测试用例 →
              </button>
            </div>
          )}
        </div>
      )}

      {currentStep === 2 && (
        <div className="animate-fadeIn">
          <div className="card" style={{ marginBottom: 24 }}>
            <div className="card-header">
              <h3 className="card-title">用例导入与录入 ({testcases.length} 个)</h3>
              <div className="card-actions">
                <span className={`badge ${testcases.length > 0 ? 'badge-success' : 'badge-warning'}`}>
                  {testcases.length > 0 ? '✓ 已就绪' : '等待导入'}
                </span>
              </div>
            </div>

            <div className="tabs">
              {STEP_TWO_TABS.map(tab => (
                <button
                  key={tab}
                  type="button"
                  className={`tab ${stepTwoTab === tab ? 'active' : ''}`}
                  onClick={() => setStepTwoTab(tab)}
                >
                  {tab}
                </button>
              ))}
            </div>

            {stepTwoTab === '上传文档' && (
              <div className="stack-lg">
                <div
                  className="upload-area"
                  onClick={() => documentFileInputRef.current?.click()}
                >
                  <div className="upload-icon">⇪</div>
                  <h3>上传 Excel 文档</h3>
                  <p>支持 `.xlsx` / `.xls`，系统会提取表格内容并用于生成测试用例</p>
                </div>

                {documentPreview && (
                  <div className="preview-panel">
                    <div className="preview-header">
                      <strong>已上传文档</strong>
                      <span>{documentFileName}</span>
                    </div>
                    <pre className="preview-content">{documentPreview}</pre>
                  </div>
                )}

                <div style={{ display: 'flex', gap: 12 }}>
                  <button
                    type="button"
                    className="btn btn-secondary"
                    onClick={() => documentFileInputRef.current?.click()}
                  >
                    重新上传文档
                  </button>
                  <button
                    type="button"
                    className="btn btn-primary"
                    onClick={() => generateTestcasesFromDocument(document)}
                    disabled={!document.trim()}
                  >
                    根据文档生成测试用例
                  </button>
                </div>
              </div>
            )}

            {stepTwoTab === '上传测试用例' && (
              <div className="stack-lg">
                <div
                  className="upload-area"
                  onClick={() => testcaseFileInputRef.current?.click()}
                >
                  <div className="upload-icon">↑</div>
                  <h3>上传 JSON 测试用例</h3>
                  <p>适合已经有结构化测试用例的场景，上传后可直接审核并执行</p>
                </div>

                {testcases.length > 0 ? (
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
                ) : (
                  <div className="empty-state">
                    <h3>还没有导入测试用例</h3>
                    <p>点击上方区域上传 JSON 文件，或者切换到其他 tab 通过文档生成、手动录入。</p>
                  </div>
                )}
              </div>
            )}

            {stepTwoTab === '手动输入测试用例' && (
              <div className="stack-lg">
                <div className="form-group">
                  <label className="form-label">文档类型</label>
                  <select
                    className="form-input form-select"
                    value={manualDocumentType}
                    onChange={e => {
                      const nextType = e.target.value
                      setManualDocumentType(nextType)
                      setManualDocumentInput(DOCUMENT_TYPE_TEMPLATES[nextType])
                    }}
                  >
                    <option value="excel">Excel 用例表</option>
                    <option value="prd">需求文档</option>
                    <option value="testcase">测试用例文档</option>
                  </select>
                </div>

                <div className="grid-2">
                  <div className="form-group">
                    <label className="form-label">根据文档类型手动输入文档</label>
                    <textarea
                      className="form-input"
                      value={manualDocumentInput}
                      onChange={e => setManualDocumentInput(e.target.value)}
                      placeholder="按左侧文档类型填写结构化内容"
                    />
                  </div>

                  <div className="form-group">
                    <label className="form-label">手动输入测试用例 JSON</label>
                    <textarea
                      className="form-input mono"
                      value={manualCaseInput}
                      onChange={e => setManualCaseInput(e.target.value)}
                      placeholder="输入测试用例 JSON 数组"
                    />
                  </div>
                </div>

                <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap' }}>
                  <button
                    type="button"
                    className="btn btn-secondary"
                    onClick={handleManualCaseImport}
                  >
                    导入手动输入的测试用例
                  </button>
                  <button
                    type="button"
                    className="btn btn-primary"
                    onClick={handleManualDocumentGenerate}
                    disabled={!manualDocumentInput.trim()}
                  >
                    根据手动输入文档生成测试用例
                  </button>
                </div>
              </div>
            )}
          </div>

          <div style={{ display: 'flex', gap: 12 }}>
            <button className="btn btn-secondary" onClick={() => setCurrentStep(1)}>
              ← 上一步
            </button>
            <button
              className="btn btn-primary btn-lg"
              onClick={executeTests}
              disabled={testcases.length === 0}
            >
              开始执行测试 →
            </button>
          </div>
        </div>
      )}

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
                marginBottom: 8,
              }}>
                <span>正在执行: {progress?.current_testcase || '等待开始...'}</span>
                <span>{progress?.current_step || 0} / {progress?.total_steps || testcases.length}</span>
              </div>
              <div style={{
                height: 8,
                background: 'var(--border)',
                borderRadius: 4,
                overflow: 'hidden',
              }}>
                <div style={{
                  height: '100%',
                  width: `${progress ? (progress.current_step / progress.total_steps) * 100 : 0}%`,
                  background: 'linear-gradient(90deg, var(--accent), var(--accent-light))',
                  borderRadius: 4,
                  transition: 'width 0.3s ease',
                }} />
              </div>
            </div>

            <div style={{
              padding: 16,
              background: 'var(--bg-primary)',
              borderRadius: 'var(--radius)',
              fontFamily: "'JetBrains Mono', monospace",
              fontSize: 13,
              color: 'var(--text-secondary)',
            }}>
              {executionError ? (
                <p style={{ color: 'var(--danger)' }}>✕ {executionError}</p>
              ) : isExecuting ? (
                <p>▶ Playwright 浏览器启动中...</p>
              ) : (
                <p>等待执行...</p>
              )}
            </div>
          </div>
        </div>
      )}

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
              <span className="badge badge-success">✓ 测试完成</span>
            </div>

            <div style={{ textAlign: 'center', padding: '32px 0' }}>
              <div style={{
                fontSize: 48,
                fontFamily: "'JetBrains Mono', monospace",
                fontWeight: 700,
                color: progress.passed === progress.total ? 'var(--success)' : 'var(--warning)',
                marginBottom: 8,
              }}>
                {Math.round((progress.passed / progress.total) * 100)}%
              </div>
              <p style={{ color: 'var(--text-secondary)' }}>
                通过率 · {progress.passed} 通过 / {progress.failed} 失败
              </p>
            </div>

            <div style={{ display: 'flex', gap: 12, justifyContent: 'center', marginTop: 24 }}>
              <button className="btn btn-secondary" onClick={() => window.location.reload()}>
                重新开始
              </button>
              <button className="btn btn-primary">提交禅道 (预留)</button>
            </div>
          </div>
        </div>
      )}
    </>
  )
}
