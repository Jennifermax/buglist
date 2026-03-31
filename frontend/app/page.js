'use client'
import { useEffect, useRef, useState } from 'react'
import * as XLSX from 'xlsx'
import { getApiBaseUrl, getWebSocketBaseUrl } from '../lib/api'

const STEPS = ['产品文档上传', '生成文案用例', '生成执行用例', '测试报告']
const STEP_THREE_TABS = ['执行用例列表', '手动输入测试用例']

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

function normalizeGeneratedCases(cases = []) {
  return cases.map((tc, index) => ({
    id: tc.id || `TC${index + 1}`,
    case_no: tc.case_no || String(index + 1).padStart(4, '0'),
    priority: tc.priority || 'P1',
    name: tc.name || `未命名用例 ${index + 1}`,
    precondition: tc.precondition || '',
    test_data: tc.test_data || '',
    expected_result: tc.expected_result || '',
    owner: tc.owner || '',
    remarks: tc.remarks || '',
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

function buildStepText(steps = []) {
  if (!Array.isArray(steps) || steps.length === 0) return ''
  return steps
    .map((step, index) => `${index + 1}. ${step.description || step.action || ''}${step.value ? `：${step.value}` : ''}`)
    .join('\n')
}

function buildExcelRowsFromCases(cases = []) {
  return cases.map((tc, index) => ({
    '用例编号': tc.case_no || String(index + 1).padStart(4, '0'),
    '优先级': tc.priority || 'P1',
    '用例名称': tc.name || '',
    '前置条件': tc.precondition || '',
    '测试数据': tc.test_data || '',
    '测试步骤': buildStepText(tc.steps),
    '预期结果': tc.expected_result || '',
    '是否通过': tc.status === 'passed' ? '通过' : tc.status === 'failed' ? '不通过' : '',
    '负责人': tc.owner || '',
    '备注': tc.remarks || '',
  }))
}

function deriveSheetGroupLabel(documentName = '') {
  const baseName = documentName
    .replace(/\.[^.]+$/, '')
    .trim()

  return baseName || '测试用例'
}

export default function Home() {
  const [currentStep, setCurrentStep] = useState(1)
  const [uploadType, setUploadType] = useState('file')
  const [stepThreeTab, setStepThreeTab] = useState('执行用例列表')
  const [document, setDocument] = useState(`登录功能需求文档

功能描述：
用户通过用户名和密码登录系统。登录页面地址：https://example.com/login

正常流程：
1. 用户打开登录页面
2. 输入正确的用户名和密码
3. 点击登录按钮
4. 系统验证成功后跳转到首页

异常场景：
- 用户名或密码为空时，提示"请输入用户名/密码"
- 密码错误时，提示"用户名或密码错误"
- 连续失败5次后，账号锁定30分钟
- 用户名不存在时，提示"用户名或密码错误"

其他说明：
- 支持记住登录状态（勾选"记住我"）
- 提供"忘记密码"入口
- 页面需展示产品 Logo 和版权信息`)
  const [documentFileName, setDocumentFileName] = useState('')
  const [documentPreview, setDocumentPreview] = useState('')
  const [documentPreviewUrl, setDocumentPreviewUrl] = useState('')
  const [documentPreviewMode, setDocumentPreviewMode] = useState('text')
  const [documentUrl, setDocumentUrl] = useState('')
  const [manualDocImages, setManualDocImages] = useState([])
  const [isFetchingDocumentUrl, setIsFetchingDocumentUrl] = useState(false)
  const [isGeneratingCases, setIsGeneratingCases] = useState(false)
  const [generationError, setGenerationError] = useState('')
  const [generationJob, setGenerationJob] = useState(null)
  const [manualCaseInput, setManualCaseInput] = useState(MANUAL_CASE_TEMPLATE)
  const [testcases, setTestcases] = useState([])
  const [selectedExecutionCaseIndex, setSelectedExecutionCaseIndex] = useState(0)
  const [progress, setProgress] = useState(null)
  const [isExecuting, setIsExecuting] = useState(false)
  const [executionError, setExecutionError] = useState('')
  const [latestStepResult, setLatestStepResult] = useState(null)
  const [reportItems, setReportItems] = useState([])
  const [previewImage, setPreviewImage] = useState(null)
  const [browserAuthStatus, setBrowserAuthStatus] = useState(null)
  const [browserAuthBusy, setBrowserAuthBusy] = useState(false)
  const [executionMode, setExecutionMode] = useState('auto')
  const [config, setConfig] = useState(null)
  const [apiBaseUrl, setApiBaseUrl] = useState('http://127.0.0.1:8000')
  const [wsBaseUrl, setWsBaseUrl] = useState('ws://127.0.0.1:8000')

  const testcaseFileInputRef = useRef(null)
  const documentFileInputRef = useRef(null)
  const manualImageInputRef = useRef(null)

  useEffect(() => {
    const baseUrl = getApiBaseUrl()
    const wsUrl = getWebSocketBaseUrl()
    setApiBaseUrl(baseUrl)
    setWsBaseUrl(wsUrl)

    fetch(`${baseUrl}/api/config/ai`)
      .then(r => r.json())
      .then(setConfig)
      .catch(() => {})

    fetch(`${baseUrl}/api/browser-auth/status`)
      .then(r => r.json())
      .then(setBrowserAuthStatus)
      .catch(() => {})
  }, [])

  const getStepClass = (stepNum) => {
    if (stepNum < currentStep) return 'step-complete'
    if (stepNum === currentStep) return 'step-active'
    return 'step-pending'
  }

  const canNavigateToStep = (stepNum) => {
    return stepNum >= 1 && stepNum <= 4
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
    const isExcel = lowerName.endsWith('.xlsx') || lowerName.endsWith('.xls')
    const isPdf = lowerName.endsWith('.pdf')
    const isWord = lowerName.endsWith('.docx') || lowerName.endsWith('.doc')

    if (!isExcel && !isPdf && !isWord) {
      e.target.value = ''
      alert('请上传 Excel、PDF 或 Word 文档')
      return
    }

    try {
      if (documentPreviewUrl) {
        URL.revokeObjectURL(documentPreviewUrl)
        setDocumentPreviewUrl('')
      }

      if (isExcel) {
        const arrayBuffer = await file.arrayBuffer()
        const workbook = XLSX.read(arrayBuffer, { type: 'array' })
        const parsedDocument = buildDocumentFromWorkbook(file.name, workbook)

        setDocument(parsedDocument)
        setDocumentFileName(file.name)
        setDocumentPreview(parsedDocument)
        setDocumentPreviewMode('text')
        setDocumentPreviewUrl('')
      } else {
        const formData = new FormData()
        formData.append('file', file)

        const res = await fetch(`${apiBaseUrl}/api/documents/parse`, {
          method: 'POST',
          body: formData,
        })
        const data = await res.json()
        if (!res.ok) {
          throw new Error(data.detail || '文档解析失败')
        }

        setDocument(data.document || '')
        setDocumentFileName(data.file_name || file.name)
        setDocumentPreview(data.document || '')
        if (isPdf) {
          setDocumentPreviewMode('pdf')
          setDocumentPreviewUrl(URL.createObjectURL(file))
        } else {
          setDocumentPreviewMode('text')
          setDocumentPreviewUrl('')
        }
      }
    } catch (error) {
      console.error(error)
      alert(error.message || '文档解析失败，请检查文件内容')
    } finally {
      e.target.value = ''
    }
  }

  const generateTestcasesFromDocument = async (source) => {
    const payload = typeof source === 'string' ? { document: source } : (source || {})
    const sourceDocument = String(payload.document || '')
    const images = Array.isArray(payload.images) ? payload.images : []

    if (!sourceDocument.trim() && images.length === 0) {
      alert('请先提供文档内容或图片')
      return false
    }

    if (!config?.api_key) {
      alert('请先在设置页面配置 AI API')
      return false
    }

    setIsGeneratingCases(true)
    setGenerationError('')
    setTestcases([])
    setGenerationJob(null)
    try {
      const res = await fetch(`${apiBaseUrl}/api/testcase-jobs`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          document: sourceDocument,
          images,
        }),
      })

      const data = await res.json().catch(() => ({}))
      if (!res.ok) {
        throw new Error(data.detail || '生成失败，请稍后重试')
      }
      setGenerationJob(data)
      return true
    } catch (err) {
      console.error(err)
      const nextMessage = err.message || '生成失败，请检查后端服务'
      setGenerationError(nextMessage)
      alert(nextMessage)
      return false
    }
  }

  useEffect(() => {
    if (!generationJob?.job_id || !isGeneratingCases) return

    let stopped = false
    const poll = async () => {
      while (!stopped) {
        try {
          const res = await fetch(`${apiBaseUrl}/api/testcase-jobs/${generationJob.job_id}`)
          const data = await res.json()
          if (!res.ok) {
            throw new Error(data.detail || '获取生成进度失败')
          }

          setGenerationJob(data)
          if (Array.isArray(data.cases)) {
            setTestcases(normalizeGeneratedCases(data.cases))
          }

          if (data.status === 'completed') {
            setIsGeneratingCases(false)
            return
          }

          if (data.status === 'failed') {
            setGenerationError(data.error || '生成失败')
            setIsGeneratingCases(false)
            return
          }
        } catch (error) {
          setGenerationError(error.message || '获取生成进度失败')
          setIsGeneratingCases(false)
          return
        }

        await new Promise(resolve => setTimeout(resolve, 1500))
      }
    }

    poll()
    return () => {
      stopped = true
    }
  }, [apiBaseUrl, generationJob?.job_id, isGeneratingCases])

  const fetchDocumentFromUrl = async () => {
    if (!documentUrl.trim()) {
      alert('请先输入产品文档 URL')
      return null
    }

    setIsFetchingDocumentUrl(true)
    try {
      const res = await fetch(`${apiBaseUrl}/api/documents/fetch`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ url: documentUrl.trim() }),
      })

      const data = await res.json()
      if (!res.ok) {
        throw new Error(data.detail || '抓取失败')
      }

      const nextDocument = data.document || ''
      const nextName = data.url || documentUrl.trim()
      setDocument(nextDocument)
      setDocumentPreview(nextDocument)
      setDocumentFileName(nextName)
      return {
        document: nextDocument,
        sourceName: nextName,
      }
    } catch (error) {
      console.error(error)
      alert(error.message || '文档 URL 抓取失败，请检查链接')
      return null
    } finally {
      setIsFetchingDocumentUrl(false)
    }
  }

  const handleManualImageUpload = async (e) => {
    const files = Array.from(e.target.files || [])
    if (files.length === 0) return

    await appendManualImages(files)

    e.target.value = ''
  }

  const appendManualImages = async (files) => {
    const imageFiles = Array.from(files || [])
      .filter(file => file?.type?.startsWith('image/'))
      .slice(0, 4)

    if (imageFiles.length === 0) return

    const nextImages = await Promise.all(
      imageFiles.map(file => new Promise(resolve => {
        const reader = new FileReader()
        reader.onload = () => {
          resolve({
            id: `${file.name}-${file.lastModified}-${file.size}`,
            name: file.name,
            mime_type: file.type || 'image/png',
            data_url: String(reader.result || ''),
          })
        }
        reader.readAsDataURL(file)
      }))
    )

    setManualDocImages(prev => {
      const merged = [...prev, ...nextImages]
      const deduped = []
      const seen = new Set()
      for (const item of merged) {
        if (!item?.data_url || seen.has(item.id)) continue
        seen.add(item.id)
        deduped.push(item)
      }
      return deduped.slice(0, 4)
    })
  }

  const handleManualDocumentPaste = async (e) => {
    const clipboardItems = Array.from(e.clipboardData?.items || [])
    const imageFiles = clipboardItems
      .filter(item => item.type?.startsWith('image/'))
      .map(item => item.getAsFile())
      .filter(Boolean)

    if (imageFiles.length === 0) return

    e.preventDefault()
    await appendManualImages(imageFiles)
  }

  const removeManualImage = (imageId) => {
    setManualDocImages(prev => prev.filter(image => image.id !== imageId))
  }

  const applyManualCases = () => {
    try {
      const parsed = JSON.parse(manualCaseInput)
      if (!Array.isArray(parsed)) {
        throw new Error('invalid')
      }

      setTestcases(normalizeGeneratedCases(parsed))
      setStepThreeTab('手动输入测试用例')
      return true
    } catch {
      alert('手动输入的测试用例必须是合法的 JSON 数组')
      return false
    }
  }

  const goToStepTwoWithGeneratedCases = async (sourceDocument, sourceName, options = {}) => {
    const nextDocument = String(sourceDocument || '')
    const nextImages = Array.isArray(options.images) ? options.images : []

    if (!nextDocument.trim() && nextImages.length === 0) {
      alert('请先提供产品文档内容或图片')
      return
    }

    setDocument(nextDocument)
    setDocumentPreview(nextDocument)
    setDocumentFileName(sourceName)
    setCurrentStep(2)
    await generateTestcasesFromDocument({
      document: nextDocument,
      images: nextImages.map(image => ({
        name: image.name,
        mime_type: image.mime_type,
        data_url: image.data_url,
      })),
    })
  }

  const downloadCasesAsExcel = () => {
    if (testcases.length === 0) {
      alert('当前没有可下载的测试用例')
      return
    }

    const rows = buildExcelRowsFromCases(testcases)
    const worksheet = XLSX.utils.json_to_sheet(rows)
    const workbook = XLSX.utils.book_new()
    XLSX.utils.book_append_sheet(workbook, worksheet, '测试用例')
    XLSX.writeFile(workbook, 'generated-testcases.xlsx')
  }

  const buildExecutionCaseCode = (testcase, index) => {
    if (!testcase) return ''

    const payload = {
      id: testcase.id || `TC${index + 1}`,
      case_no: testcase.case_no || String(index + 1).padStart(4, '0'),
      priority: testcase.priority || 'P1',
      name: testcase.name || '',
      precondition: testcase.precondition || '',
      test_data: testcase.test_data || '',
      expected_result: testcase.expected_result || '',
      owner: testcase.owner || '',
      remarks: testcase.remarks || '',
      status: testcase.status || 'pending',
      steps: Array.isArray(testcase.steps) ? testcase.steps : [],
    }

    return JSON.stringify(payload, null, 2)
  }

  const selectedExecutionCase = testcases[selectedExecutionCaseIndex] || null
  const getAssetUrl = (path) => {
    if (!path) return ''
    if (/^https?:\/\//i.test(path)) return path
    return `${apiBaseUrl}${path}`
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
    setLatestStepResult(null)
    setReportItems([])
    setProgress({
      current_step: 0,
      total_steps: testcases.length,
      current_testcase: '准备启动执行...',
      passed: 0,
      failed: 0,
      status: 'running',
    })
    setCurrentStep(4)

    try {
      const ws = new WebSocket(`${wsBaseUrl}/ws/execute/test1`)

      ws.onopen = () => {
        ws.send(JSON.stringify({
          testcases,
          ai_config: config,
          execution_mode: executionMode,
        }))
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
        } else if (msg.type === 'step_complete') {
          setLatestStepResult(msg.data)
          setReportItems(prev => [...prev, msg.data])
        } else if (msg.type === 'error') {
          setExecutionError(msg.data?.message || '测试执行失败')
          setProgress(prev => ({
            ...(prev || {}),
            status: 'error',
          }))
          setIsExecuting(false)
          ws.close()
        } else if (msg.type === 'all_complete') {
          setProgress(prev => ({
            ...(prev || {}),
            total: msg.data.total,
            total_steps: msg.data.total,
            current_step: msg.data.total,
            current_testcase: '执行完成',
            passed: msg.data.passed,
            failed: msg.data.failed,
            status: 'complete',
          }))
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

  const refreshBrowserAuthStatus = async () => {
    try {
      const res = await fetch(`${apiBaseUrl}/api/browser-auth/status`)
      const data = await res.json()
      if (res.ok) {
        setBrowserAuthStatus(data)
      }
    } catch {}
  }

  const handleBrowserAuthAction = async (action) => {
    setBrowserAuthBusy(true)
    try {
      const res = await fetch(`${apiBaseUrl}/api/browser-auth/${action}`, {
        method: 'POST',
      })
      const data = await res.json().catch(() => ({}))
      if (!res.ok) {
        throw new Error(data.detail || '操作失败')
      }
      setBrowserAuthStatus(data)
      alert(data.message || '操作成功')
    } catch (error) {
      alert(error.message || '操作失败')
    } finally {
      setBrowserAuthBusy(false)
    }
  }

  const getStatusIcon = (stepNum) => {
    if (stepNum < currentStep) return '✓'
    return stepNum
  }

  useEffect(() => {
    return () => {
      if (documentPreviewUrl) {
        URL.revokeObjectURL(documentPreviewUrl)
      }
    }
  }, [documentPreviewUrl])

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
        accept=".xlsx,.xls,.pdf,.doc,.docx,application/pdf,application/msword,application/vnd.openxmlformats-officedocument.wordprocessingml.document,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet,application/vnd.ms-excel"
        onChange={handleDocumentUpload}
        style={{ display: 'none' }}
      />
      <input
        ref={manualImageInputRef}
        type="file"
        accept="image/*"
        multiple
        onChange={handleManualImageUpload}
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
              上传产品文档
            </button>
            <button
              className={`tab ${uploadType === 'text' ? 'active' : ''}`}
              onClick={() => setUploadType('text')}
            >
              手动输入产品文档
            </button>
            <button
              className={`tab ${uploadType === 'url' ? 'active' : ''}`}
              onClick={() => setUploadType('url')}
            >
              输入产品文档 URL
            </button>
          </div>

          {uploadType === 'file' ? (
            <div className="stack-lg">
              {!documentPreview && (
                <div
                  className="upload-area"
                  onClick={() => documentFileInputRef.current?.click()}
                >
                  <div className="upload-icon">⇪</div>
                  <h3>上传产品文档</h3>
                  <p>支持 Excel、PDF、Word 文档，上传后进入第 2 步生成文案用例；也可以直接跳到第 2 步手动上传测试用例</p>
                </div>
              )}

              {documentPreview && (
                <div className="upload-summary">
                  <div>
                    <strong>已上传产品文档</strong>
                    <p>{documentFileName || '未命名文档'} · 已完成解析，可进入下一步生成文案用例</p>
                  </div>
                  <span className="badge badge-success">已准备继续</span>
                </div>
              )}

              {documentPreview && (
                <div className="preview-panel">
                  <div className="preview-header">
                    <strong>文档预览</strong>
                    <span>{documentFileName}</span>
                  </div>
                  {documentPreviewMode === 'pdf' && documentPreviewUrl ? (
                    <iframe
                      className="preview-embed"
                      src={documentPreviewUrl}
                      title={documentFileName || 'PDF 预览'}
                    />
                  ) : (
                    <pre className="preview-content">{documentPreview}</pre>
                  )}
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
                  onClick={() => goToStepTwoWithGeneratedCases(document, documentFileName || '上传文档')}
                  disabled={!document.trim()}
                >
                  下一步 →
                </button>
              </div>
            </div>
          ) : uploadType === 'text' ? (
            <div className="stack-lg">
              <div className="form-group">
                <label className="form-label">产品文档内容</label>
                <div className="manual-doc-input-wrap">
                  <textarea
                    className="form-input manual-doc-textarea"
                    value={document}
                    onChange={e => setDocument(e.target.value)}
                    onPaste={handleManualDocumentPaste}
                    placeholder="粘贴产品需求文档内容，也可以直接在这里粘贴截图或点击右下角上传图片"
                  />
                  <div className="manual-doc-toolbar">
                    <span className="manual-doc-toolbar-tip">
                      支持粘贴图片 / 上传图片，最多 4 张
                    </span>
                    <button
                      type="button"
                      className="btn btn-secondary btn-sm"
                      onClick={() => manualImageInputRef.current?.click()}
                    >
                      上传图片
                    </button>
                  </div>
                </div>
                {manualDocImages.length > 0 && (
                  <div className="manual-image-grid">
                    {manualDocImages.map(image => (
                      <div key={image.id} className="manual-image-card">
                        <img src={image.data_url} alt={image.name} className="manual-image-preview" />
                        <div className="manual-image-meta">
                          <span title={image.name}>{image.name}</span>
                          <button
                            type="button"
                            className="manual-image-remove"
                            onClick={() => removeManualImage(image.id)}
                          >
                            删除
                          </button>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>

              {documentPreview && (
                <div className="preview-panel">
                  <div className="preview-header">
                    <strong>文档预览</strong>
                    <span>{documentFileName || '手动输入文档'}</span>
                  </div>
                  <pre className="preview-content">{documentPreview}</pre>
                </div>
              )}

              <div style={{ display: 'flex', gap: 12 }}>
                <button
                  type="button"
                  className="btn btn-primary"
                  onClick={() => goToStepTwoWithGeneratedCases(document, '手动输入文档', {
                    images: manualDocImages,
                  })}
                  disabled={!document.trim() && manualDocImages.length === 0}
                >
                  下一步 →
                </button>
              </div>
            </div>
          ) : (
            <div className="stack-lg">
              <div className="form-group">
                <label className="form-label">产品文档 URL</label>
                <input
                  type="url"
                  className="form-input"
                  value={documentUrl}
                  onChange={e => setDocumentUrl(e.target.value)}
                  placeholder="https://example.com/prd"
                />
              </div>

              <div style={{ display: 'flex', gap: 12 }}>
                <button
                  type="button"
                  className="btn btn-primary"
                  onClick={async () => {
                    const fetched = await fetchDocumentFromUrl()
                    if (!fetched) return
                    await goToStepTwoWithGeneratedCases(fetched.document, fetched.sourceName)
                  }}
                  disabled={!documentUrl.trim() || isFetchingDocumentUrl}
                >
                  {isFetchingDocumentUrl ? '处理中...' : '下一步 →'}
                </button>
              </div>
            </div>
          )}
        </div>
      )}

      {currentStep === 2 && (
        <div className="animate-fadeIn">
          <div className="card" style={{ marginBottom: 24 }}>
            <div className="card-header">
              <h3 className="card-title">文案用例生成与导入 ({testcases.length} 个)</h3>
              <div className="card-actions">
                <button
                  type="button"
                  className="btn btn-secondary btn-sm"
                  onClick={() => testcaseFileInputRef.current?.click()}
                >
                  上传测试用例
                </button>
                <button
                  type="button"
                  className="btn btn-primary btn-sm"
                  onClick={downloadCasesAsExcel}
                  disabled={testcases.length === 0}
                >
                  下载表格
                </button>
              </div>
            </div>

            <div className="stack-lg">
              {!document.trim() && !documentPreview && (
                <div className="empty-state">
                  <h3>还没有产品文档</h3>
                  <p>你可以回到第 1 步上传产品文档，或者直接使用右上角按钮上传测试用例，跳过产品文档生成流程。</p>
                </div>
              )}

              {isGeneratingCases && (
                <div className="cases-generating">
                  <div className="cases-generating-badge">
                    <span className="cases-generating-dot" />
                    AI 正在生成测试用例
                  </div>
                  <h3>正在根据产品文档生成测试用例</h3>
                  <p>
                    {generationJob?.total_chunks
                      ? `当前进度：第 ${generationJob.current_chunk || 0}/${generationJob.total_chunks} 段，已生成 ${testcases.length} 条用例`
                      : '系统正在拆分文档并逐段生成测试用例，请稍等。'}
                  </p>
                  <div className="cases-generating-bar">
                    <div className="cases-generating-bar-fill" />
                  </div>
                </div>
              )}

              {!isGeneratingCases && testcases.length > 0 && (
                <div className="cases-sheet-wrap">
                  <table className="cases-sheet-table">
                    <thead>
                      <tr className="cases-sheet-group-row">
                        <th colSpan="10">{deriveSheetGroupLabel(documentFileName)}</th>
                      </tr>
                      <tr>
                        <th>用例编号</th>
                        <th>优先级</th>
                        <th>用例名称</th>
                        <th>前置条件</th>
                        <th>测试数据</th>
                        <th>测试步骤</th>
                        <th>预期结果</th>
                        <th>是否通过</th>
                        <th>负责人</th>
                        <th>备注</th>
                      </tr>
                    </thead>
                    <tbody>
                      {testcases.map((tc, index) => (
                        <tr key={tc.id || index}>
                          <td className="mono">{tc.case_no || String(index + 1).padStart(4, '0')}</td>
                          <td>{tc.priority || 'P1'}</td>
                          <td>{tc.name || '-'}</td>
                          <td>{tc.precondition || '-'}</td>
                          <td>{tc.test_data || '-'}</td>
                          <td className="cases-sheet-multiline">{buildStepText(tc.steps) || '-'}</td>
                          <td className="cases-sheet-multiline">{tc.expected_result || '-'}</td>
                          <td>{tc.status === 'passed' ? '通过' : tc.status === 'failed' ? '不通过' : ''}</td>
                          <td>{tc.owner || '-'}</td>
                          <td className="cases-sheet-multiline">{tc.remarks || '-'}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}

              {!isGeneratingCases && testcases.length === 0 && (document.trim() || documentPreview) && (
                <div className="empty-state">
                  <h3>{generationError ? '生成失败' : '还没有生成文案用例'}</h3>
                  <p>{generationError || '如果你不想基于产品文档生成，也可以直接使用右上角按钮上传测试用例。'}</p>
                </div>
              )}
            </div>

          </div>

          <div style={{ display: 'flex', gap: 12 }}>
            <button className="btn btn-secondary" onClick={() => setCurrentStep(1)}>
              ← 上一步
            </button>
            <button
              className="btn btn-primary"
              onClick={() => setCurrentStep(3)}
              disabled={testcases.length === 0}
            >
              下一步：生成执行用例 →
            </button>
          </div>
        </div>
      )}

      {currentStep === 3 && (
        <div className="animate-fadeIn">
          <div className="card" style={{ marginBottom: 24 }}>
            <div className="card-header">
              <h3 className="card-title">生成执行用例</h3>
              <span className={`badge ${testcases.length > 0 ? 'badge-success' : 'badge-warning'}`}>
                {testcases.length > 0 ? '已生成可执行用例' : '暂无可执行用例'}
              </span>
            </div>

            <div className="tabs">
              {STEP_THREE_TABS.map(tab => (
                <button
                  key={tab}
                  type="button"
                  className={`tab ${stepThreeTab === tab ? 'active' : ''}`}
                  onClick={() => setStepThreeTab(tab)}
                >
                  {tab}
                </button>
              ))}
            </div>

            {stepThreeTab === '执行用例列表' && (
              <>
                <div className="browser-auth-panel">
                  <div className="browser-auth-panel-header">
                    <div>
                      <div className="browser-auth-title">测试专用浏览器登录态</div>
                      <div className="browser-auth-subtitle">
                        打开专用浏览器后手动登录一次，保存登录态，后续执行测试会自动复用该登录状态。
                      </div>
                    </div>
                    <span className={`badge ${browserAuthStatus?.state_ready ? 'badge-success' : 'badge-warning'}`}>
                      {browserAuthStatus?.state_ready ? '已保存登录态' : '未保存登录态'}
                    </span>
                  </div>

                  <div className="browser-auth-meta">
                    <span>浏览器状态：{browserAuthStatus?.browser_open ? '已打开' : '未打开'}</span>
                    <span>目标地址：{browserAuthStatus?.login_url || '未获取'}</span>
                    <span>最近保存：{browserAuthStatus?.last_updated || '暂无'}</span>
                  </div>

                  <div className="browser-auth-actions">
                    <button
                      type="button"
                      className="btn btn-secondary btn-sm"
                      onClick={() => handleBrowserAuthAction('open')}
                      disabled={browserAuthBusy}
                    >
                      打开测试专用浏览器
                    </button>
                    <button
                      type="button"
                      className="btn btn-secondary btn-sm"
                      onClick={() => handleBrowserAuthAction('save')}
                      disabled={browserAuthBusy}
                    >
                      保存当前登录态
                    </button>
                    <button
                      type="button"
                      className="btn btn-secondary btn-sm"
                      onClick={() => handleBrowserAuthAction('close')}
                      disabled={browserAuthBusy}
                    >
                      关闭专用浏览器
                    </button>
                    <button
                      type="button"
                      className="btn btn-secondary btn-sm"
                      onClick={refreshBrowserAuthStatus}
                      disabled={browserAuthBusy}
                    >
                      刷新状态
                    </button>
                  </div>
                </div>

                <div className="browser-auth-panel">
                  <div className="browser-auth-panel-header">
                    <div>
                      <div className="browser-auth-title">执行浏览器模式</div>
                      <div className="browser-auth-subtitle">
                        已登录测试就直接复用当前打开的测试专用浏览器；未登录测试则使用全新匿名浏览器。
                      </div>
                    </div>
                  </div>
                  <div className="browser-auth-actions">
                    <button
                      type="button"
                      className={`btn btn-sm ${executionMode === 'auto' ? 'btn-primary' : 'btn-secondary'}`}
                      onClick={() => setExecutionMode('auto')}
                    >
                      自动判断
                    </button>
                    <button
                      type="button"
                      className={`btn btn-sm ${executionMode === 'logged' ? 'btn-primary' : 'btn-secondary'}`}
                      onClick={() => setExecutionMode('logged')}
                    >
                      使用已登录专用浏览器
                    </button>
                    <button
                      type="button"
                      className={`btn btn-sm ${executionMode === 'anonymous' ? 'btn-primary' : 'btn-secondary'}`}
                      onClick={() => setExecutionMode('anonymous')}
                    >
                      使用匿名浏览器
                    </button>
                  </div>
                </div>

                <div style={{
                  padding: 16,
                  background: 'var(--bg-primary)',
                  borderRadius: 'var(--radius)',
                  marginBottom: 20,
                  fontSize: 14,
                  color: 'var(--text-secondary)',
                  lineHeight: 1.7,
                }}>
                  当前文案用例会直接作为执行用例使用。你可以在这里确认清单，或者切换到“手动输入测试用例”继续补充 JSON。
                </div>

                {testcases.length > 0 ? (
                  <div className="execution-cases-layout">
                    <div className="testcase-list">
                      {testcases.map((tc, index) => (
                        <button
                          key={tc.id || index}
                          type="button"
                          className={`testcase-item ${selectedExecutionCaseIndex === index ? 'active' : ''}`}
                          onClick={() => setSelectedExecutionCaseIndex(index)}
                        >
                          <span className="testcase-id">{tc.id || `TC${index + 1}`}</span>
                          <div className="testcase-content">
                            <div className="testcase-name">{tc.name}</div>
                            <div className="testcase-steps">
                              {tc.steps?.length || 0} 个步骤 · {tc.precondition || '无前置条件'}
                            </div>
                          </div>
                          <span className="testcase-status pending">待执行</span>
                        </button>
                      ))}
                    </div>

                    <div className="execution-case-detail">
                      <div className="execution-case-detail-header">
                        <div>
                          <div className="execution-case-detail-title">执行用例详情</div>
                          <div className="execution-case-detail-subtitle">
                            点击左侧列表即可查看当前执行用例对应的代码内容
                          </div>
                        </div>
                        <button
                          type="button"
                          className="btn btn-secondary btn-sm"
                          onClick={async () => {
                            const code = buildExecutionCaseCode(selectedExecutionCase, selectedExecutionCaseIndex)
                            if (!code) return
                            try {
                              await navigator.clipboard.writeText(code)
                              alert('已复制执行用例代码')
                            } catch {
                              alert('复制失败，请手动复制')
                            }
                          }}
                          disabled={!selectedExecutionCase}
                        >
                          复制代码
                        </button>
                      </div>

                      {selectedExecutionCase ? (
                        <>
                          <div className="execution-case-meta">
                            <span className="testcase-id">{selectedExecutionCase.id || `TC${selectedExecutionCaseIndex + 1}`}</span>
                            <span className="execution-case-meta-name">{selectedExecutionCase.name}</span>
                          </div>
                          <pre className="execution-case-code">
                            <code>{buildExecutionCaseCode(selectedExecutionCase, selectedExecutionCaseIndex)}</code>
                          </pre>
                        </>
                      ) : (
                        <div className="empty-state">
                          <h3>还没有可查看的执行用例</h3>
                          <p>当左侧列表有数据后，点击任意一条即可查看对应代码。</p>
                        </div>
                      )}
                    </div>
                  </div>
                ) : (
                  <div className="empty-state">
                    <h3>还没有可执行用例</h3>
                    <p>请先回到第 2 步生成或上传文案用例，或者切换到“手动输入测试用例”直接补充 JSON。</p>
                  </div>
                )}
              </>
            )}

            {stepThreeTab === '手动输入测试用例' && (
              <div className="stack-lg">
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
            )}
          </div>

          <div style={{ display: 'flex', gap: 12 }}>
            <button className="btn btn-secondary" onClick={() => setCurrentStep(2)}>
              ← 上一步
            </button>
            <button
              className="btn btn-primary btn-lg"
              onClick={() => {
                if (stepThreeTab === '手动输入测试用例') {
                  const ok = applyManualCases()
                  if (!ok) return
                }
                executeTests()
              }}
              disabled={stepThreeTab === '执行用例列表' ? testcases.length === 0 : !manualCaseInput.trim()}
            >
              开始执行并进入测试报告 →
            </button>
          </div>
        </div>
      )}

      {currentStep === 4 && (
        <div className="animate-fadeIn">
          <div className="progress-stats">
            <div className="stat-card">
              <div className="stat-value total">{progress?.total || testcases.length || 0}</div>
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

          <div className="card" style={{ marginBottom: 24 }}>
            <div className="card-header">
              <h3 className="card-title">执行进度</h3>
              <span className={`badge ${progress?.status === 'complete' ? 'badge-success' : 'badge-warning'}`}>
                {progress?.status === 'complete' ? '✓ 测试完成' : isExecuting ? '执行中' : '待执行'}
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
                  width: `${progress?.total_steps ? ((progress.current_step || 0) / progress.total_steps) * 100 : 0}%`,
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
              ) : progress?.status === 'complete' ? (
                <p>✓ 执行完成，可在下方查看完整测试报告</p>
              ) : (
                <p>点击“开始执行测试”后，这里会显示实时执行进度</p>
              )}
            </div>

            {latestStepResult && (
              <div className="execution-result">
                <div className="execution-result-header">
                  <strong>{latestStepResult.testcase_name}</strong>
                  <span className={`testcase-status ${latestStepResult.result}`}>
                    {latestStepResult.result === 'passed' ? '通过' : '失败'}
                  </span>
                </div>
                <p className="execution-result-reason">{latestStepResult.reason}</p>
                {latestStepResult.vision_details?.length > 0 && (
                  <div className="execution-result-details">
                    {latestStepResult.vision_details.map((detail, index) => (
                      <div key={index} className="execution-result-detail">
                        <div className={`badge ${detail.passed ? 'badge-success' : 'badge-danger'}`}>
                          {detail.passed ? 'AI 判定通过' : 'AI 判定失败'}
                        </div>
                        <p>{detail.reason}</p>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}
          </div>

          <div className="card">
            <div className="card-header">
              <h3 className="card-title">测试报告</h3>
              <div className="card-actions">
                <span className={`badge ${progress?.status === 'complete' ? 'badge-success' : 'badge-warning'}`}>
                  {progress?.status === 'complete' ? '已生成报告' : '报告更新中'}
                </span>
                <button
                  type="button"
                  className="btn btn-primary btn-sm"
                  onClick={executeTests}
                  disabled={isExecuting || testcases.length === 0}
                >
                  {progress?.status === 'complete' ? '重新执行' : '开始执行测试'}
                </button>
              </div>
            </div>

            <div style={{ textAlign: 'center', padding: '32px 0' }}>
              <div style={{
                fontSize: 48,
                fontFamily: "'JetBrains Mono', monospace",
                fontWeight: 700,
                color: progress?.status === 'complete'
                  ? ((progress?.passed || 0) === (progress?.total || 0) ? 'var(--success)' : 'var(--warning)')
                  : 'var(--text-muted)',
                marginBottom: 8,
              }}>
                {progress?.status === 'complete' && progress?.total
                  ? `${Math.round((progress.passed / progress.total) * 100)}%`
                  : '--'}
              </div>
              <p style={{ color: 'var(--text-secondary)' }}>
                {progress?.status === 'complete'
                  ? `通过率 · ${progress.passed} 通过 / ${progress.failed} 失败`
                  : '当前还没有执行结果，先展示测试报告布局'}
              </p>
            </div>

            <div className="report-table-wrap">
              <table className="report-table">
                <thead>
                  <tr>
                    <th>用例 ID</th>
                    <th>用例名称</th>
                    <th>结果</th>
                    <th>执行说明</th>
                    <th>AI 判定</th>
                    <th>执行截图</th>
                  </tr>
                </thead>
                <tbody>
                  {reportItems.map((item, index) => {
                    const visionReason = item.vision_details?.map(detail => detail.reason).join('；') || '-'
                    return (
                      <tr key={`${item.testcase_id || index}-${index}`}>
                        <td className="mono">{item.testcase_id || '-'}</td>
                        <td>{item.testcase_name || '-'}</td>
                        <td>
                          <span className={`testcase-status ${item.result === 'passed' ? 'passed' : 'failed'}`}>
                            {item.result === 'passed' ? '通过' : '失败'}
                          </span>
                        </td>
                        <td>{item.reason || '-'}</td>
                        <td>{visionReason}</td>
                        <td>
                          {item.screenshots?.length > 0 ? (
                            <div className="report-screenshot-list">
                              {item.screenshots.map((shot, shotIndex) => (
                                <button
                                  key={`${shot.url}-${shotIndex}`}
                                  type="button"
                                  className="report-screenshot-thumb"
                                  onClick={() => setPreviewImage({
                                    url: getAssetUrl(shot.url),
                                    title: shot.description || shot.name || '执行截图',
                                  })}
                                >
                                  <img
                                    src={getAssetUrl(shot.url)}
                                    alt={shot.description || shot.name || '执行截图'}
                                  />
                                  <span>{shot.action || `截图 ${shotIndex + 1}`}</span>
                                </button>
                              ))}
                            </div>
                          ) : (
                            '-'
                          )}
                        </td>
                      </tr>
                    )
                  })}
                  {reportItems.length === 0 && (
                    <tr>
                      <td colSpan="6" className="report-empty">
                        {progress?.status === 'complete' ? '暂无可展示的测试结果' : '执行后这里会展示逐条测试报告'}
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
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

      {previewImage && (
        <div className="image-preview-modal" onClick={() => setPreviewImage(null)}>
          <div className="image-preview-dialog" onClick={(e) => e.stopPropagation()}>
            <div className="image-preview-header">
              <strong>{previewImage.title || '执行截图'}</strong>
              <button
                type="button"
                className="btn btn-secondary btn-sm"
                onClick={() => setPreviewImage(null)}
              >
                关闭
              </button>
            </div>
            <img className="image-preview-full" src={previewImage.url} alt={previewImage.title || '执行截图'} />
          </div>
        </div>
      )}
    </>
  )
}
