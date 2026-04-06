'use client'
import { useEffect, useRef, useState } from 'react'
import { App, Drawer, Table } from 'antd'
import * as XLSX from 'xlsx'
import { getApiBaseUrl, getWebSocketBaseUrl } from '../lib/api'

const STEPS = ['生成文案用例', '生成执行用例', '测试报告']
const STEP_THREE_TABS = ['执行用例列表', '手动输入测试用例']
const WORKFLOW_CACHE_KEY = 'buglist-workflow-cache'

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

function normalizeBatch(batch = {}) {
  return {
    id: batch.id || '',
    created_at: batch.created_at || '',
    source_name: batch.source_name || '未命名批次',
    source_document: batch.source_document || '',
    generated_count: Number(batch.generated_count || 0),
    status: batch.status || 'completed',
    cases: normalizeGeneratedCases(Array.isArray(batch.cases) ? batch.cases : []),
  }
}

function sortBatchesByCreatedAt(batches = []) {
  return [...batches].sort((a, b) => {
    const timeA = a?.created_at ? new Date(a.created_at).getTime() : 0
    const timeB = b?.created_at ? new Date(b.created_at).getTime() : 0
    if (timeA !== timeB) return timeB - timeA
    return String(b?.id || '').localeCompare(String(a?.id || ''))
  })
}

function buildExecutionHistoryBatchFromSource(batch = {}) {
  const normalized = normalizeBatch(batch)
  return {
    ...normalized,
    id: `EXEC-HIST-${normalized.id}`,
    status: 'ready',
    source_batch_id: normalized.id,
  }
}

function buildStepText(steps = []) {
  if (!Array.isArray(steps) || steps.length === 0) return ''
  return steps
    .map((step, index) => `${index + 1}. ${step.description || step.action || ''}${step.value ? `：${step.value}` : ''}`)
    .join('\n')
}

function parseStepText(text = '') {
  if (!text || typeof text !== 'string') return []
  return text
    .split('\n')
    .map(line => line.trim())
    .filter(line => line)
    .map(line => {
      const match = line.match(/^\d+\.\s*(.+?)(?:：(.+))?$/)
      if (match) {
        return {
          action: match[1].trim(),
          value: match[2] ? match[2].trim() : '',
          description: match[1].trim()
        }
      }
      return { action: line, value: '', description: line }
    })
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

function isBrowserAuthRuntimeIssue(message = '') {
  const lowered = String(message || '').toLowerCase()
  return (
    lowered.includes('target page, context or browser has been closed') ||
    lowered.includes('浏览器被关闭') ||
    lowered.includes('页面上下文已失效') ||
    lowered.includes('专用浏览器') ||
    lowered.includes('登录态')
  )
}

export default function Home() {
  const { message, modal } = App.useApp()
  const [currentStep, setCurrentStep] = useState(1)
  const [stepThreeTab, setStepThreeTab] = useState('执行用例列表')
  const [isLoadingSavedCases, setIsLoadingSavedCases] = useState(false)
  const [manualCaseInput, setManualCaseInput] = useState(MANUAL_CASE_TEMPLATE)
  const [testcases, setTestcases] = useState([])
  const [testcaseBatches, setTestcaseBatches] = useState([])
  const [selectedBatchId, setSelectedBatchId] = useState('')
  const [isBatchDrawerOpen, setIsBatchDrawerOpen] = useState(false)
  const [executionBatches, setExecutionBatches] = useState([])
  const [selectedExecutionBatchId, setSelectedExecutionBatchId] = useState('')
  const [isExecutionBatchDrawerOpen, setIsExecutionBatchDrawerOpen] = useState(false)
  const [selectedExecutionCaseIndex, setSelectedExecutionCaseIndex] = useState(0)
  const [progress, setProgress] = useState(null)
  const [isExecuting, setIsExecuting] = useState(false)
  const [executionError, setExecutionError] = useState('')
  const [latestStepResult, setLatestStepResult] = useState(null)
  const [reportItems, setReportItems] = useState([])
  const [isSubmittingZentao, setIsSubmittingZentao] = useState(false)
  const [previewImage, setPreviewImage] = useState(null)
  const [browserAuthStatus, setBrowserAuthStatus] = useState(null)
  const [browserAuthBusy, setBrowserAuthBusy] = useState(false)
  const [config, setConfig] = useState(null)
  const [apiBaseUrl, setApiBaseUrl] = useState('http://127.0.0.1:8000')
  const [wsBaseUrl, setWsBaseUrl] = useState('ws://127.0.0.1:8000')

  const testcaseFileInputRef = useRef(null)

  const loadSavedTestcases = async (baseUrlOverride, preferredBatchId = '') => {
    const baseUrl = baseUrlOverride || apiBaseUrl
    if (!baseUrl) return []

    setIsLoadingSavedCases(true)
    try {
      const res = await fetch(`${baseUrl}/api/testcases/batches`)
      const data = await res.json().catch(() => [])
      if (!res.ok) {
        throw new Error(data.detail || '获取已保存用例失败')
      }

      const normalized = sortBatchesByCreatedAt((Array.isArray(data) ? data : []).map(normalizeBatch))
      setTestcaseBatches(normalized)
      const targetBatchId = preferredBatchId || selectedBatchId
      const nextSelectedBatchId = normalized.find(batch => batch.id === targetBatchId)?.id || normalized[0]?.id || ''
      setSelectedBatchId(nextSelectedBatchId)
      const selectedBatch = normalized.find(batch => batch.id === nextSelectedBatchId)
      const nextCases = selectedBatch?.cases || []
      setTestcases(nextCases)
      setSelectedExecutionCaseIndex(prev => (
        nextCases.length === 0 ? 0 : Math.min(prev, nextCases.length - 1)
      ))
      return normalized
    } catch (error) {
      console.error(error)
      return []
    } finally {
      setIsLoadingSavedCases(false)
    }
  }

  useEffect(() => {
    const baseUrl = getApiBaseUrl()
    const wsUrl = getWebSocketBaseUrl()
    setApiBaseUrl(baseUrl)
    setWsBaseUrl(wsUrl)

    let cachedSelectedBatchId = ''
    try {
      const cachedRaw = localStorage.getItem(WORKFLOW_CACHE_KEY)
      if (cachedRaw) {
        const cached = JSON.parse(cachedRaw)
        cachedSelectedBatchId = String(cached.selectedBatchId || '')
        setCurrentStep(Number(cached.currentStep || 1))
        setStepThreeTab(String(cached.stepThreeTab || '执行用例列表'))
        setSelectedBatchId(cachedSelectedBatchId)
        setIsBatchDrawerOpen(Boolean(cached.isBatchDrawerOpen))
        setExecutionBatches(sortBatchesByCreatedAt(Array.isArray(cached.executionBatches) ? cached.executionBatches.map(normalizeBatch) : []))
        setSelectedExecutionBatchId(String(cached.selectedExecutionBatchId || ''))
        setIsExecutionBatchDrawerOpen(Boolean(cached.isExecutionBatchDrawerOpen))
        setManualCaseInput(String(cached.manualCaseInput || MANUAL_CASE_TEMPLATE))
        setTestcases(normalizeGeneratedCases(Array.isArray(cached.testcases) ? cached.testcases : []))
        setSelectedExecutionCaseIndex(Number(cached.selectedExecutionCaseIndex || 0))
        setProgress(cached.progress || null)
        setReportItems(Array.isArray(cached.reportItems) ? cached.reportItems : [])
      }
    } catch {}

    fetch(`${baseUrl}/api/config/ai`)
      .then(r => r.json())
      .then(setConfig)
      .catch(() => {})

    fetch(`${baseUrl}/api/browser-auth/status`)
      .then(r => r.json())
      .then(setBrowserAuthStatus)
      .catch(() => {})

    loadSavedTestcases(baseUrl, cachedSelectedBatchId).catch(() => {})
  }, [])

  useEffect(() => {
    try {
      localStorage.setItem(WORKFLOW_CACHE_KEY, JSON.stringify({
        currentStep,
        stepThreeTab,
        selectedBatchId,
        isBatchDrawerOpen,
        executionBatches,
        selectedExecutionBatchId,
        isExecutionBatchDrawerOpen,
        manualCaseInput,
        testcases,
        selectedExecutionCaseIndex,
        progress,
        reportItems,
      }))
    } catch {}
  }, [
    currentStep,
    stepThreeTab,
    selectedBatchId,
    isBatchDrawerOpen,
    executionBatches,
    selectedExecutionBatchId,
    isExecutionBatchDrawerOpen,
    manualCaseInput,
    testcases,
    selectedExecutionCaseIndex,
    progress,
    reportItems,
  ])

  useEffect(() => {
    if (testcaseBatches.length === 0) {
      setTestcases([])
      setSelectedExecutionCaseIndex(0)
      return
    }

    const selectedBatch = testcaseBatches.find(batch => batch.id === selectedBatchId) || testcaseBatches[0]
    if (selectedBatch.id !== selectedBatchId) {
      setSelectedBatchId(selectedBatch.id)
    }
    setTestcases(selectedBatch.cases || [])
    setSelectedExecutionCaseIndex(prev => (
      (selectedBatch.cases || []).length === 0 ? 0 : Math.min(prev, (selectedBatch.cases || []).length - 1)
    ))
  }, [selectedBatchId, testcaseBatches])

  useEffect(() => {
    if (testcaseBatches.length === 0) return

    setExecutionBatches(prev => {
      const existingIds = new Set(prev.map(batch => String(batch.id || '')))
      const derivedHistory = testcaseBatches
        .map(buildExecutionHistoryBatchFromSource)
        .filter(batch => !existingIds.has(batch.id))

      if (derivedHistory.length === 0) {
        return prev
      }

      return sortBatchesByCreatedAt([...prev, ...derivedHistory])
    })
  }, [testcaseBatches])

  useEffect(() => {
    if (executionBatches.length === 0) {
      setSelectedExecutionCaseIndex(0)
      return
    }

    const nextSelectedBatch = executionBatches.find(batch => batch.id === selectedExecutionBatchId) || executionBatches[0]
    if (nextSelectedBatch.id !== selectedExecutionBatchId) {
      setSelectedExecutionBatchId(nextSelectedBatch.id)
    }

    setSelectedExecutionCaseIndex(prev => (
      (nextSelectedBatch.cases || []).length === 0 ? 0 : Math.min(prev, (nextSelectedBatch.cases || []).length - 1)
    ))
  }, [executionBatches, selectedExecutionBatchId])

  const getStepClass = (stepNum) => {
    if (stepNum < currentStep) return 'step-complete'
    if (stepNum === currentStep) return 'step-active'
    return 'step-pending'
  }

  const canNavigateToStep = (stepNum) => {
    return stepNum >= 1 && stepNum <= 3
  }

  const handleStepClick = (stepNum) => {
    if (!canNavigateToStep(stepNum)) return
    setCurrentStep(stepNum)
  }

  const openBatchDrawer = (batchId) => {
    if (!batchId) return
    setSelectedBatchId(batchId)
    setIsBatchDrawerOpen(true)
  }

  const createExecutionBatchRecord = ({ sourceBatchId = '', sourceName = '执行用例批次', cases = [] } = {}) => {
    const normalizedCases = normalizeGeneratedCases(Array.isArray(cases) ? cases : [])
    if (normalizedCases.length === 0) {
      return null
    }

    const nextBatch = {
      id: `EXEC${Date.now()}`,
      created_at: new Date().toISOString(),
      source_name: sourceName,
      source_document: '',
      generated_count: normalizedCases.length,
      status: 'ready',
      source_batch_id: sourceBatchId,
      cases: normalizedCases,
    }

    setExecutionBatches(prev => sortBatchesByCreatedAt([nextBatch, ...prev]))
    setSelectedExecutionBatchId(nextBatch.id)
    setSelectedExecutionCaseIndex(0)
    return nextBatch
  }

  const goToExecutionStepFromBatch = (batchId) => {
    const sourceBatch = testcaseBatches.find(batch => batch.id === batchId) || null
    if (!sourceBatch) return

    setSelectedBatchId(sourceBatch.id)

    // Check if cases are empty
    const normalizedCases = normalizeGeneratedCases(sourceBatch.cases || [])
    if (normalizedCases.length === 0) {
      message.warning('当前批次没有可生成的执行用例')
      return
    }

    setStepThreeTab('执行用例列表')
    setIsBatchDrawerOpen(false)
    setCurrentStep(2)

    setTimeout(() => {
      // Find the automatically generated EXEC-HIST batch for this source batch
      const execHistId = `EXEC-HIST-${sourceBatch.id}`
      setSelectedExecutionBatchId(execHistId)
      setSelectedExecutionCaseIndex(0)
    }, 0)
  }

  const openExecutionBatchDrawer = (batchId) => {
    if (!batchId) return
    setSelectedExecutionBatchId(batchId)
    setSelectedExecutionCaseIndex(0)
    setIsExecutionBatchDrawerOpen(true)
  }

  const deleteGeneratedBatch = async (batchId) => {
    if (!batchId || !apiBaseUrl) return

    modal.confirm({
      title: '确认删除',
      content: '确定要永久删除这个文案生成批次吗？',
      okText: '确定',
      cancelText: '取消',
      okButtonProps: { danger: true },
      onOk: async () => {
        try {
          const res = await fetch(`${apiBaseUrl}/api/testcases/batches/${batchId}`, {
            method: 'DELETE',
          })
          const data = await res.json().catch(() => ({}))
          if (!res.ok) {
            throw new Error(data.detail || '删除批次失败')
          }

          setExecutionBatches(prev => {
            const next = prev.filter(batch => batch.source_batch_id !== batchId && batch.id !== `EXEC-HIST-${batchId}`)
            const hasSelected = next.some(batch => batch.id === selectedExecutionBatchId)
            setSelectedExecutionBatchId(hasSelected ? selectedExecutionBatchId : (next[0]?.id || ''))
            if (next.length === 0) {
              setIsExecutionBatchDrawerOpen(false)
              setSelectedExecutionCaseIndex(0)
            }
            return sortBatchesByCreatedAt(next)
          })

          setIsBatchDrawerOpen(false)
          await loadSavedTestcases(apiBaseUrl)
          message.success('删除成功')
        } catch (error) {
          message.error(error.message || '删除批次失败')
          throw error
        }
      },
    })
  }

  const deleteExecutionBatch = (batchId) => {
    if (!batchId) return

    modal.confirm({
      title: '确认删除',
      content: '确定要永久删除这个执行批次吗？',
      okText: '确定',
      cancelText: '取消',
      okButtonProps: { danger: true },
      onOk: () => {
        setExecutionBatches(prev => {
          const next = prev.filter(batch => batch.id !== batchId)
          const nextSelectedBatchId = next.find(batch => batch.id === selectedExecutionBatchId)?.id || next[0]?.id || ''
          setSelectedExecutionBatchId(nextSelectedBatchId)
          setSelectedExecutionCaseIndex(0)
          if (batchId === selectedExecutionBatchId || next.length === 0) {
            setIsExecutionBatchDrawerOpen(false)
          }
          return sortBatchesByCreatedAt(next)
        })
        message.success('删除成功')
      },
    })
  }

  const selectExecutionCaseInDrawer = (index) => {
    if (typeof index !== 'number' || index < 0) return
    setSelectedExecutionCaseIndex(index)
  }

  const handleTestcaseUpload = async (e) => {
    const file = e.target.files?.[0]
    if (!file) return

    let parsedCases = []
    let fileName = file.name

    if (file.name.endsWith('.json')) {
      const text = await file.text()
      try {
        const cases = JSON.parse(text)
        if (Array.isArray(cases)) {
          parsedCases = cases
        }
      } catch {}
    }

    if (file.name.endsWith('.xlsx') || file.name.endsWith('.xls')) {
      try {
        const buffer = await file.arrayBuffer()
        const workbook = XLSX.read(buffer, { type: 'array' })
        const firstSheet = workbook.Sheets[workbook.SheetNames[0]]
        const rows = XLSX.utils.sheet_to_json(firstSheet)

        parsedCases = rows.map((row, index) => ({
          case_no: row['用例编号'] || String(index + 1).padStart(4, '0'),
          priority: row['优先级'] || 'P1',
          name: row['用例名称'] || '',
          precondition: row['前置条件'] || '',
          test_data: row['测试数据'] || '',
          steps: parseStepText(row['测试步骤'] || ''),
          expected_result: row['预期结果'] || '',
          status: row['是否通过'] === '通过' ? 'passed' : row['是否通过'] === '不通过' ? 'failed' : '',
          owner: row['负责人'] || '',
          remarks: row['备注'] || '',
        }))
      } catch (err) {
        console.error('Excel parse error:', err)
        e.target.value = ''
        message.warning('Excel 文件解析失败，请检查文件格式')
        return
      }
    }

    if (parsedCases.length === 0) {
      e.target.value = ''
      message.warning('仅支持 JSON 或 Excel 格式的测试用例文件')
      return
    }

    const normalizedCases = normalizeGeneratedCases(parsedCases)
    const casesWithIds = normalizedCases.map((c, index) => ({
      ...c,
      id: c.id || `TC${Date.now()}_${index}`
    }))

    const newBatch = {
      id: `BATCH${Date.now()}`,
      created_at: new Date().toISOString(),
      source_name: `上传文件: ${fileName}`,
      source_document: '',
      generated_count: casesWithIds.length,
      status: 'completed',
      cases: casesWithIds,
    }

    try {
      const res = await fetch(`${apiBaseUrl}/api/testcases/batches`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(newBatch),
      })

      if (!res.ok) {
        throw new Error('保存批次失败')
      }

      message.success(`成功导入 ${casesWithIds.length} 条测试用例`)
      await loadSavedTestcases(apiBaseUrl, newBatch.id)
    } catch (err) {
      console.error('Save batch error:', err)
      message.error('保存测试用例批次失败')
    } finally {
      e.target.value = ''
    }
  }

  const applyManualCases = () => {
    try {
      const parsed = JSON.parse(manualCaseInput)
      if (!Array.isArray(parsed)) {
        throw new Error('invalid')
      }

      setTestcases(normalizeGeneratedCases(parsed))
      setSelectedBatchId('')
      const createdBatch = createExecutionBatchRecord({
        sourceName: '手动输入执行用例',
        cases: parsed,
      })
      if (createdBatch) {
        setSelectedExecutionBatchId(createdBatch.id)
      }
      setStepThreeTab('手动输入测试用例')
      return true
    } catch {
      message.warning('手动输入的测试用例必须是合法的 JSON 数组')
      return false
    }
  }

  const downloadCasesAsExcel = () => {
    if (testcases.length === 0) {
      message.warning('当前没有可下载的测试用例')
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

  const selectedExecutionBatch = executionBatches.find(batch => batch.id === selectedExecutionBatchId) || null
  const selectedExecutionCase = selectedExecutionBatch?.cases?.[selectedExecutionCaseIndex] || null
  const selectedBatch = testcaseBatches.find(batch => batch.id === selectedBatchId) || null
  const failedReportItems = reportItems.filter(item => item?.result === 'failed')
  const browserAuthIssueMessage = [
    executionError,
    latestStepResult?.reason,
    ...reportItems.map(item => item?.reason || ''),
  ].find(isBrowserAuthRuntimeIssue) || ''
  const browserAuthBadgeClass = browserAuthIssueMessage
    ? 'badge-danger'
    : browserAuthStatus?.browser_open && browserAuthStatus?.state_ready
      ? 'badge-success'
      : 'badge-warning'
  const browserAuthBadgeText = browserAuthIssueMessage
    ? '登录态异常'
    : browserAuthStatus?.browser_open && browserAuthStatus?.state_ready
      ? '已保存登录态'
      : browserAuthStatus?.state_ready
        ? '登录态未验证'
        : '未保存登录态'
  const getAssetUrl = (path) => {
    if (!path) return ''
    if (/^https?:\/\//i.test(path)) return path
    return `${apiBaseUrl}${path}`
  }

  const executeTests = async (casesOverride = null) => {
    const casesToExecute = normalizeGeneratedCases(
      Array.isArray(casesOverride)
        ? casesOverride
        : Array.isArray(selectedExecutionBatch?.cases) && selectedExecutionBatch.cases.length > 0
          ? selectedExecutionBatch.cases
          : testcases
    )

    if (!config?.api_key) {
      message.warning('请先在设置页面配置 AI API')
      return
    }

    if (casesToExecute.length === 0) {
      message.warning('没有可执行的测试用例')
      return
    }

    setTestcases(casesToExecute)
    setIsExecuting(true)
    setExecutionError('')
    setLatestStepResult(null)
    setReportItems([])
    setProgress({
      current_step: 0,
      total_steps: casesToExecute.length,
      current_testcase: '准备启动执行...',
      passed: 0,
      failed: 0,
      status: 'running',
    })
    setCurrentStep(3)

    try {
      const ws = new WebSocket(`${wsBaseUrl}/ws/execute/test1`)

      ws.onopen = () => {
        ws.send(JSON.stringify({
          testcases: casesToExecute,
          ai_config: config,
          execution_mode: 'auto',
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
          setCurrentStep(3)
          setIsExecuting(false)
          ws.close()
        }
      }

      ws.onerror = () => {
        message.error('WebSocket 连接失败')
        setIsExecuting(false)
      }

      ws.onclose = () => {
        setIsExecuting(false)
      }
    } catch (err) {
      console.error(err)
      message.error('执行失败，请检查后端服务')
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
      message.success(data.message || '操作成功')
    } catch (error) {
      message.error(error.message || '操作失败')
    } finally {
      setBrowserAuthBusy(false)
    }
  }

  const submitFailedResultsToZentao = async () => {
    if (reportItems.length === 0) {
      message.info('当前还没有测试报告，先执行测试后再提交禅道')
      return
    }

    if (failedReportItems.length === 0) {
      message.info('当前报告里没有失败用例，所以这次不会提交到禅道')
      return
    }

    setIsSubmittingZentao(true)
    try {
      const res = await fetch(`${apiBaseUrl}/api/zentao/bugs/submit-failures`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          report_items: failedReportItems,
          testcases,
          artifact_base_url: apiBaseUrl,
        }),
      })
      const data = await res.json().catch(() => ({}))
      if (!res.ok) {
        throw new Error(data.detail || data.message || '提交禅道失败')
      }

      if (data.failed_count > 0) {
        message.warning(data.message || '部分提交成功')
      } else {
        message.success(data.message || '已提交到禅道')
      }

      modal.info({
        title: '禅道提交结果',
        width: 720,
        content: (
          <div style={{ marginTop: 12 }}>
            <div style={{ marginBottom: 12 }}>
              共提交 {data.submitted || 0} 条失败用例，成功 {data.created_count || 0} 条，失败 {data.failed_count || 0} 条。
            </div>
            {Array.isArray(data.created) && data.created.length > 0 && (
              <div style={{ marginBottom: 16 }}>
                <strong>创建成功</strong>
                <div style={{ marginTop: 8, display: 'grid', gap: 8 }}>
                  {data.created.map(item => (
                    <div key={`${item.testcase_id}-${item.bug_id}`} style={{ padding: 10, border: '1px solid var(--border)', borderRadius: 'var(--radius)' }}>
                      <div>{item.testcase_name || item.testcase_id}</div>
                      <div style={{ color: 'var(--text-secondary)', fontSize: 13 }}>
                        Bug ID: {item.bug_id || '-'} | 产品 ID: {item.product_id || '-'}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
            {Array.isArray(data.failed) && data.failed.length > 0 && (
              <div>
                <strong>提交失败</strong>
                <div style={{ marginTop: 8, display: 'grid', gap: 8 }}>
                  {data.failed.map(item => (
                    <div key={`${item.testcase_id}-${item.bug_title}`} style={{ padding: 10, border: '1px solid var(--border)', borderRadius: 'var(--radius)' }}>
                      <div>{item.testcase_name || item.testcase_id}</div>
                      <div style={{ color: 'var(--danger)', fontSize: 13 }}>
                        {item.message || '创建失败'}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        ),
      })
    } catch (error) {
      message.error(error.message || '提交禅道失败')
    } finally {
      setIsSubmittingZentao(false)
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
        accept=".json,.xlsx,.xls"
        onChange={handleTestcaseUpload}
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
        <div className="animate-fadeIn">
          <div className="card" style={{ marginBottom: 24 }}>
            <div className="card-header">
              <h3 className="card-title">文案生成批次管理 ({testcaseBatches.length} 个批次)</h3>
              <div className="card-actions">
                <button
                  type="button"
                  className="btn btn-secondary btn-sm"
                  onClick={() => loadSavedTestcases()}
                  disabled={isLoadingSavedCases}
                >
                  {isLoadingSavedCases ? '刷新中...' : '刷新已保存用例'}
                </button>
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
              <div style={{
                padding: 16,
                background: 'var(--bg-primary)',
                borderRadius: 'var(--radius)',
                fontSize: 14,
                color: 'var(--text-secondary)',
                lineHeight: 1.7,
              }}>
                每次生成都会形成一条独立批次记录，使用生成时间作为唯一标识。默认不展开 Excel 明细，你可以点击下方任意批次，从右侧抽屉查看该批的详细文案用例，并基于该批次继续执行测试。
              </div>

              {testcaseBatches.length > 0 && (
                <>
                  <Table
                    rowKey="id"
                    dataSource={testcaseBatches}
                    pagination={false}
                    size="middle"
                    rowSelection={{
                      type: 'radio',
                      selectedRowKeys: selectedBatchId ? [selectedBatchId] : [],
                      onChange: keys => openBatchDrawer(String(keys[0] || '')),
                    }}
                    columns={[
                      {
                        title: '批次时间',
                        dataIndex: 'created_at',
                        key: 'created_at',
                        render: value => value ? new Date(value).toLocaleString() : '-',
                      },
                      {
                        title: '批次 ID',
                        dataIndex: 'id',
                        key: 'id',
                      },
                      {
                        title: '来源',
                        dataIndex: 'source_name',
                        key: 'source_name',
                      },
                      {
                        title: '用例数',
                        dataIndex: 'generated_count',
                        key: 'generated_count',
                      },
                      {
                        title: '状态',
                        dataIndex: 'status',
                        key: 'status',
                      },
                      {
                        title: '操作',
                        key: 'actions',
                        render: (_, record) => (
                          <button
                            type="button"
                            className="btn btn-secondary btn-sm"
                            onClick={e => {
                              e.stopPropagation()
                              deleteGeneratedBatch(record.id)
                            }}
                          >
                            删除
                          </button>
                        ),
                      },
                    ]}
                    onRow={record => ({
                      onClick: () => openBatchDrawer(record.id),
                    })}
                  />
                </>
              )}
            </div>

          </div>

          <div style={{ display: 'flex', gap: 12 }}>
            <button
              className="btn btn-primary"
              onClick={() => setCurrentStep(2)}
              disabled={testcases.length === 0}
            >
              下一步：生成执行用例 →
            </button>
          </div>

          <Drawer
            title={selectedBatch ? `批次明细：${deriveSheetGroupLabel(selectedBatch.source_name)}` : '批次明细'}
            placement="right"
            width="72vw"
            onClose={() => setIsBatchDrawerOpen(false)}
            open={isBatchDrawerOpen && !!selectedBatch}
            destroyOnClose={false}
            extra={selectedBatch ? (
              <button
                type="button"
                className="btn btn-primary btn-sm"
                onClick={() => goToExecutionStepFromBatch(selectedBatch.id)}
              >
                去生成执行用例
              </button>
            ) : null}
          >
            {selectedBatch ? (
              <div className="cases-sheet-wrap" style={{ marginTop: 0 }}>
                <div style={{
                  padding: '12px 16px',
                  fontSize: 14,
                  color: 'var(--text-secondary)',
                  borderBottom: '1px solid var(--border-color)',
                  background: 'var(--bg-secondary)',
                }}>
                  当前查看批次：{new Date(selectedBatch.created_at).toLocaleString()} · {selectedBatch.source_name} · {selectedBatch.generated_count} 条
                </div>
                <table className="cases-sheet-table">
                  <thead>
                    <tr className="cases-sheet-group-row">
                      <th colSpan="10">{deriveSheetGroupLabel(selectedBatch.source_name)}</th>
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
                    {selectedBatch.cases.map((tc, index) => (
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
            ) : null}
          </Drawer>
        </div>
      )}

      {currentStep === 2 && (
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
                    <span className={`badge ${browserAuthBadgeClass}`}>
                      {browserAuthBadgeText}
                    </span>
                  </div>

                  <div className="browser-auth-meta">
                    <span>浏览器状态：{browserAuthStatus?.browser_open ? '已打开' : '未打开'}</span>
                    <span>目标地址：{browserAuthStatus?.login_url || '未获取'}</span>
                    <span>最近保存：{browserAuthStatus?.last_updated || '暂无'}</span>
                  </div>

                  {browserAuthIssueMessage ? (
                    <div style={{
                      marginTop: 10,
                      padding: '10px 12px',
                      borderRadius: 'var(--radius-sm)',
                      background: 'var(--danger-bg)',
                      color: 'var(--danger)',
                      fontSize: 13,
                      lineHeight: 1.6,
                    }}>
                      登录态/浏览器上下文最近一次执行异常：{browserAuthIssueMessage}
                    </div>
                  ) : null}

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

                <div style={{
                  padding: 16,
                  background: 'var(--bg-primary)',
                  borderRadius: 'var(--radius)',
                  marginBottom: 20,
                  fontSize: 14,
                  color: 'var(--text-secondary)',
                  lineHeight: 1.7,
                }}>
                  每次从第 2 步选择批次进入这里，都会生成一条独立的执行批次记录。执行批次按时间倒序显示，点击任意时间批次后，会从右侧抽屉展示该时间下的多个执行用例，并可继续执行测试。
                </div>

                {executionBatches.length > 0 ? (
                  <>
                    <Table
                      rowKey="id"
                      dataSource={executionBatches}
                      pagination={false}
                      size="middle"
                      rowSelection={{
                        type: 'radio',
                        selectedRowKeys: selectedExecutionBatchId ? [selectedExecutionBatchId] : [],
                        onChange: keys => {
                          const nextBatchId = String(keys[0] || '')
                          if (nextBatchId) {
                            openExecutionBatchDrawer(nextBatchId)
                          }
                        },
                      }}
                      columns={[
                        {
                          title: '批次时间',
                          dataIndex: 'created_at',
                          key: 'created_at',
                          render: value => value ? new Date(value).toLocaleString() : '-',
                        },
                        {
                          title: '执行批次 ID',
                          dataIndex: 'id',
                          key: 'id',
                        },
                        {
                          title: '来源',
                          dataIndex: 'source_name',
                          key: 'source_name',
                        },
                        {
                          title: '执行用例数',
                          dataIndex: 'generated_count',
                          key: 'generated_count',
                        },
                        {
                          title: '状态',
                          dataIndex: 'status',
                          key: 'status',
                          render: value => value || 'ready',
                        },
                        {
                          title: '操作',
                          key: 'actions',
                          render: (_, record) => (
                            <button
                              type="button"
                              className="btn btn-secondary btn-sm"
                              onClick={e => {
                                e.stopPropagation()
                                deleteExecutionBatch(record.id)
                              }}
                            >
                              删除
                            </button>
                          ),
                        },
                      ]}
                      onRow={record => ({
                        onClick: () => openExecutionBatchDrawer(record.id),
                      })}
                    />

                    <Drawer
                      title={selectedExecutionBatch ? `执行批次详情：${deriveSheetGroupLabel(selectedExecutionBatch.source_name)}` : '执行批次详情'}
                      placement="right"
                      width="72vw"
                      onClose={() => setIsExecutionBatchDrawerOpen(false)}
                      open={isExecutionBatchDrawerOpen && !!selectedExecutionBatch}
                      destroyOnClose={false}
                      extra={selectedExecutionBatch ? (
                        <button
                          type="button"
                          className="btn btn-primary btn-sm"
                          onClick={() => {
                            setIsExecutionBatchDrawerOpen(false)
                            executeTests(selectedExecutionBatch.cases || [])
                          }}
                        >
                          去执行测试
                        </button>
                      ) : null}
                    >
                      {selectedExecutionBatch ? (
                        <div className="stack-lg">
                          <div style={{
                            padding: '12px 16px',
                            fontSize: 14,
                            color: 'var(--text-secondary)',
                            border: '1px solid var(--border-color)',
                            borderRadius: 'var(--radius)',
                            background: 'var(--bg-secondary)',
                          }}>
                            当前查看执行批次：{new Date(selectedExecutionBatch.created_at).toLocaleString()} · {selectedExecutionBatch.source_name} · {selectedExecutionBatch.generated_count} 条
                          </div>

                          <Table
                            rowKey={record => record.id || `execution-detail-${record.executionIndex}`}
                            dataSource={(selectedExecutionBatch.cases || []).map((tc, index) => ({
                              ...tc,
                              executionIndex: index,
                            }))}
                            pagination={false}
                            size="small"
                            rowSelection={{
                              type: 'radio',
                              selectedRowKeys: selectedExecutionCase ? [selectedExecutionCase.id || `execution-detail-${selectedExecutionCaseIndex}`] : [],
                              onChange: (_keys, rows) => {
                                const nextIndex = rows[0]?.executionIndex
                                if (typeof nextIndex === 'number') {
                                  selectExecutionCaseInDrawer(nextIndex)
                                }
                              },
                            }}
                            columns={[
                              {
                                title: '用例编号',
                                key: 'case_no',
                                render: (_, record) => record.case_no || String(record.executionIndex + 1).padStart(4, '0'),
                              },
                              {
                                title: '用例名称',
                                dataIndex: 'name',
                                key: 'name',
                                render: value => value || '-',
                              },
                              {
                                title: '步骤数',
                                key: 'steps_count',
                                render: (_, record) => `${record.steps?.length || 0} 步`,
                              },
                              {
                                title: '状态',
                                dataIndex: 'status',
                                key: 'status',
                                render: value => value === 'passed' ? '通过' : value === 'failed' ? '失败' : '待执行',
                              },
                            ]}
                            onRow={record => ({
                              onClick: () => selectExecutionCaseInDrawer(record.executionIndex),
                            })}
                          />

                          {selectedExecutionCase ? (
                            <>
                              <div style={{
                                padding: 16,
                                background: 'var(--bg-primary)',
                                borderRadius: 'var(--radius)',
                                fontSize: 14,
                                color: 'var(--text-secondary)',
                                lineHeight: 1.8,
                              }}>
                                <div><strong>用例编号：</strong>{selectedExecutionCase.case_no || String(selectedExecutionCaseIndex + 1).padStart(4, '0')}</div>
                                <div><strong>优先级：</strong>{selectedExecutionCase.priority || 'P1'}</div>
                                <div><strong>前置条件：</strong>{selectedExecutionCase.precondition || '-'}</div>
                                <div><strong>测试数据：</strong>{selectedExecutionCase.test_data || '-'}</div>
                                <div><strong>预期结果：</strong>{selectedExecutionCase.expected_result || '-'}</div>
                              </div>

                              <div className="execution-case-detail">
                                <div className="execution-case-detail-header">
                                  <div>
                                    <div className="execution-case-detail-title">执行代码内容</div>
                                    <div className="execution-case-detail-subtitle">
                                      当前抽屉展示的是这条执行用例的完整 JSON 明细
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
                                        message.success('已复制执行用例代码')
                                      } catch {
                                        message.error('复制失败，请手动复制')
                                      }
                                    }}
                                  >
                                    复制代码
                                  </button>
                                </div>

                                <pre className="execution-case-code">
                                  <code>{buildExecutionCaseCode(selectedExecutionCase, selectedExecutionCaseIndex)}</code>
                                </pre>
                              </div>
                            </>
                          ) : null}
                        </div>
                      ) : null}
                    </Drawer>
                  </>
                ) : (
                  <div className="empty-state">
                    <h3>还没有执行批次</h3>
                    <p>请先回到第 2 步选择某个时间批次并进入第 3 步，这里会按时间倒序记录每一批执行用例。</p>
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
            <button className="btn btn-secondary" onClick={() => setCurrentStep(1)}>
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

      {currentStep === 3 && (
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
                    const visionReason = item.vision_details?.map(detail => detail.reason).join('；') || '本次结果主要根据执行步骤与页面状态判定，未返回额外 AI 断言说明'
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
              <button
                className="btn btn-primary"
                onClick={submitFailedResultsToZentao}
                disabled={isSubmittingZentao}
              >
                {isSubmittingZentao
                  ? '提交中...'
                  : failedReportItems.length > 0
                    ? `提交失败到禅道 (${failedReportItems.length})`
                    : '提交禅道'}
              </button>
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
