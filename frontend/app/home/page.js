import Link from 'next/link'
import styles from './home.module.css'

const painPoints = [
  '过度依赖 DOM、CSS 选择器和页面结构，页面小改就导致脚本失效',
  '测试需求天然是自然语言，传统规则表达成本高且容易偏离测试意图',
  '页面结果判定比页面操作更难，纯文本断言容易出现误判',
  '登录态、弹窗、新标签页、外链跳转让脚本稳定性快速下降',
  '执行与缺陷提报割裂，自动化执行后仍需大量人工整理和提交'
]

const designPillars = [
  {
    title: 'AI 负责理解',
    body: '把“顶部报名按钮”“分享弹窗中的 Twitter 图标”这类语义目标转成可执行动作。'
  },
  {
    title: 'Playwright 负责执行',
    body: '浏览器打开、点击、输入、等待、切换上下文交给稳定自动化引擎处理。'
  },
  {
    title: 'AI 负责判定',
    body: '基于截图、URL、标题和页面语义做单步骤判断与最终终态校验。'
  },
  {
    title: '系统负责闭环',
    body: '自动收敛失败结果、保留关键截图与原因，并支持一键提交到禅道。'
  }
]

const comparisonRows = [
  {
    dimension: '步骤表达',
    traditional: '需要人工转成规则',
    buglist: '可直接使用自然语言测试步骤',
  },
  {
    dimension: '元素定位',
    traditional: '依赖 XPath / CSS / DOM',
    buglist: 'AI 语义定位 + 候选元素选择',
  },
  {
    dimension: '跳转场景',
    traditional: '新标签页容易丢上下文',
    buglist: 'AI 决定切页并验证目标页',
  },
  {
    dimension: '结果判断',
    traditional: '多依赖文本或规则断言',
    buglist: 'AI 视觉判定 + 页面级验证',
  },
  {
    dimension: '结果闭环',
    traditional: '失败后通常人工整理并手工提缺陷',
    buglist: '自动报告、截图和原因收敛，可一键提交禅道',
  },
]

const fitScenes = [
  '高变化页面：活动页、营销页、分享页、交易页',
  '需求和页面迭代很快的团队，需要高灵活度自动化能力',
  '黑客松、PoC、内部分享等需要展示 AI + 工程结合能力的场景',
]

export default function HomeLandingPage() {
  return (
    <div className={styles.landing}>
      <section className={styles.hero}>
        <span className={styles.eyebrow}>Why Buglist Exists</span>
        <h1>AI语义化自动测试平台</h1>
        <p className={styles.heroNote}>24 小时测试机器人</p>
        <p>
          Buglist 的目标不是再做一个“脚本执行工具”，而是把自动化测试从规则驱动升级为
          <strong> 语义驱动 + 视觉驱动 + 浏览器执行 + 结果闭环 </strong>
          的新范式。
        </p>
        <div className={styles.heroActions}>
          <Link href="/" className={styles.primaryBtn}>进入主工作台</Link>
          <a href="#comparison" className={styles.secondaryBtn}>查看能力对比</a>
        </div>
      </section>

      <section className={styles.section}>
        <div className={styles.sectionTitle}>
          <h2>传统自动化为什么越来越难维护</h2>
          <p>在真实 UI 场景里，问题往往不是“不能执行”，而是“难以稳定理解和判断”。</p>
        </div>
        <div className={styles.cardGrid}>
          {painPoints.map((item) => (
            <article key={item} className={styles.infoCard}>
              <h3>核心痛点</h3>
              <p>{item}</p>
            </article>
          ))}
        </div>
      </section>

      <section className={styles.section}>
        <div className={styles.sectionTitle}>
          <h2>Buglist 的设计原则</h2>
          <p>不是否定传统自动化，而是重新分工，让各自擅长的能力在同一条链路协同。</p>
        </div>
        <div className={styles.cardGrid}>
          {designPillars.map((pillar) => (
            <article key={pillar.title} className={styles.pillarCard}>
              <h3>{pillar.title}</h3>
              <p>{pillar.body}</p>
            </article>
          ))}
        </div>
      </section>

      <section id="comparison" className={styles.section}>
        <div className={styles.sectionTitle}>
          <h2>与传统方案的关键差异</h2>
          <p>Buglist 不是“只生成用例”，而是让 AI 直接参与执行和判定过程。</p>
        </div>
        <div className={styles.tableWrap}>
          <table className={styles.compareTable}>
            <thead>
              <tr>
                <th>对比维度</th>
                <th>传统自动化</th>
                <th>Buglist</th>
              </tr>
            </thead>
            <tbody>
              {comparisonRows.map((row) => (
                <tr key={row.dimension}>
                  <td>{row.dimension}</td>
                  <td>{row.traditional}</td>
                  <td>{row.buglist}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <section className={styles.section}>
        <div className={styles.sectionTitle}>
          <h2>最适合的团队和业务场景</h2>
        </div>
        <div className={styles.sceneList}>
          {fitScenes.map((scene) => (
            <div key={scene} className={styles.sceneItem}>{scene}</div>
          ))}
        </div>
      </section>

      <section className={styles.finalSection}>
        <h2>一句话总结</h2>
        <p>
          Buglist 不是在替代测试人员写脚本，而是在让自动化测试第一次具备接近人工测试的理解能力。
        </p>
      </section>
    </div>
  )
}
