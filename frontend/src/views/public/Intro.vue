<template>
  <div class="page intro-page">
    <header class="intro-head">
      <span>XunkeFlow · 循课</span>
      <h1>面向高校课程的学习资源生产与成效评估平台</h1>
      <p>把教师课程资料、学生个体差异、学习资源、审核与前后测结果统一到一个可追踪的课程工作台。</p>
      <div class="toolbar-actions"><el-button type="primary" @click="$router.push('/login')">进入平台</el-button><el-button @click="$router.push('/register')">注册学生账号</el-button></div>
    </header>

    <section class="value-grid">
      <article><span><el-icon><Files /></el-icon></span><div><b>课程资料成为可用资产</b><p>支持教师上传资料、整理知识点、构建课程关系并保留原文引用。</p></div></article>
      <article><span><el-icon><User /></el-icon></span><div><b>每位学生获得不同路径</b><p>通过前测与掌握度识别薄弱点，安排讲义、练习和补救内容。</p></div></article>
      <article><span><el-icon><Checked /></el-icon></span><div><b>内容经过质量与教师审核</b><p>生成内容进入质量校验和人工审核，发布后学生才能查看。</p></div></article>
    </section>

    <section class="workflow-section">
      <div><span>课程闭环</span><h2>从资料准备到学习报告，环节清晰可验收</h2><p>每一步都有业务结果，而不是孤立的页面或按钮。</p></div>
      <div class="workflow-list"><article v-for="(item, index) in workflow" :key="item.title"><span>{{ index + 1 }}</span><div><b>{{ item.title }}</b><p>{{ item.desc }}</p></div></article></div>
    </section>

    <section class="roles-section">
      <header><h2>三类角色，共用同一套课程数据</h2><p>学生学习、教师生产审核、管理员运营治理互相衔接。</p></header>
      <div><article><el-icon><User /></el-icon><b>学生</b><p>前测、画像、路径、讲义、练习、错题、后测与报告。</p></article><article><el-icon><Reading /></el-icon><b>教师</b><p>课程、资料、知识点、资源生成、质量审核与班级看板。</p></article><article><el-icon><Setting /></el-icon><b>管理员</b><p>用户、课程资产、智能服务健康和任务运行治理。</p></article></div>
    </section>
  </div>
</template>

<script setup lang="ts">
const workflow = [
  { title: '准备课程', desc: '创建课程并上传教学资料。' },
  { title: '形成课程知识', desc: '解析正文、知识点和知识关系。' },
  { title: '诊断学生', desc: '通过前测形成画像与薄弱点。' },
  { title: '生成学习资源', desc: '按画像生成讲义、导图与练习。' },
  { title: '审核发布', desc: '核对引用、质量和发布建议。' },
  { title: '评估提升', desc: '后测、错题补救和报告形成闭环。' }
]
</script>

<style scoped>
.intro-head { max-width: 900px; padding: 46px 0 54px; }.intro-head > span { color: var(--primary); font-size: 12px; font-weight: 800; letter-spacing: .08em; }.intro-head h1 { max-width: 820px; margin: 13px 0 16px; font-size: clamp(36px, 5vw, 62px); line-height: 1.08; letter-spacing: -.055em; }.intro-head p { max-width: 760px; color: var(--text-secondary); font-size: 16px; line-height: 1.8; }.intro-head .toolbar-actions { margin-top: 24px; }
.value-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 14px; }.value-grid article { display: grid; grid-template-columns: 46px 1fr; gap: 13px; padding: 20px 0; border-top: 2px solid var(--primary); }.value-grid article > span { width: 42px; height: 42px; display: grid; place-items: center; border-radius: 11px; color: var(--primary); background: var(--primary-bg); font-size: 19px; }.value-grid b { display: block; font-size: 15px; }.value-grid p { margin-top: 5px; color: var(--text-secondary); line-height: 1.7; }
.workflow-section { display: grid; grid-template-columns: minmax(280px, .7fr) minmax(0, 1.3fr); gap: 50px; margin-top: 64px; padding: 34px; border: 1px solid var(--border); border-radius: var(--radius-xl); background: #fff; box-shadow: var(--shadow-sm); }.workflow-section > div:first-child > span { color: var(--primary); font-size: 11px; font-weight: 800; }.workflow-section h2 { margin: 8px 0 10px; font-size: 27px; line-height: 1.3; }.workflow-section > div:first-child p { color: var(--text-secondary); }.workflow-list { display: grid; grid-template-columns: repeat(2, 1fr); gap: 8px; }.workflow-list article { display: grid; grid-template-columns: 30px 1fr; gap: 10px; padding: 13px; background: var(--bg-secondary); }.workflow-list article > span { width: 28px; height: 28px; display: grid; place-items: center; border-radius: 8px; color: var(--primary); background: var(--primary-bg); font-weight: 800; }.workflow-list b { font-size: 13px; }.workflow-list p { color: var(--text-secondary); font-size: 11px; }
.roles-section { margin-top: 64px; }.roles-section header { margin-bottom: 18px; }.roles-section h2 { font-size: 26px; }.roles-section header p { color: var(--text-secondary); }.roles-section > div { display: grid; grid-template-columns: repeat(3, 1fr); gap: 1px; overflow: hidden; border: 1px solid var(--border); border-radius: var(--radius-lg); background: var(--border); }.roles-section article { padding: 24px; background: #fff; }.roles-section article .el-icon { margin-bottom: 10px; color: var(--primary); font-size: 23px; }.roles-section b, .roles-section p { display: block; }.roles-section p { margin-top: 6px; color: var(--text-secondary); }
@media (max-width: 860px) { .value-grid, .workflow-section, .roles-section > div { grid-template-columns: 1fr; }.workflow-section { gap: 28px; }.workflow-list { grid-template-columns: 1fr; } }
</style>
