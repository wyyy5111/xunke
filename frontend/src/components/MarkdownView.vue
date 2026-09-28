<template>
  <div ref="root" class="markdown-body md-surface" v-html="html"></div>
</template>

<script setup lang="ts">
import { computed, nextTick, onMounted, ref, watch } from 'vue'
import { marked } from 'marked'
import DOMPurify from 'dompurify'
import mermaid from 'mermaid'
import { normalizeMermaidSource } from '@/utils/mermaid'
import 'github-markdown-css/github-markdown-light.css'

const props = defineProps<{ content: string }>()
const root = ref<HTMLElement | null>(null)

marked.setOptions({ breaks: true, gfm: true })
mermaid.initialize({
  startOnLoad: false,
  securityLevel: 'strict',
  theme: 'base',
  themeVariables: {
    primaryColor: '#eff6ff',
    primaryTextColor: '#0f172a',
    primaryBorderColor: '#60a5fa',
    lineColor: '#94a3b8',
    secondaryColor: '#ecfeff',
    tertiaryColor: '#ffffff',
    fontFamily: 'PingFang SC, Microsoft YaHei, Inter, sans-serif'
  }
})

const html = computed(() => {
  const parsed = marked.parse(props.content || '')
  return DOMPurify.sanitize(String(parsed), {
    // Uploaded documents and model output are untrusted. Keep the sanitized
    // Markdown HTML-only; Mermaid receives plain text and creates its strict
    // SVG after this boundary, so arbitrary source SVG never needs admission.
    USE_PROFILES: { html: true },
    FORBID_TAGS: ['style', 'iframe', 'object', 'embed', 'form', 'input', 'button', 'textarea', 'select'],
    FORBID_ATTR: ['style', 'srcdoc', 'formaction', 'xlink:href'],
    ALLOW_DATA_ATTR: false
  })
})

async function renderMermaid() {
  await nextTick()
  if (!root.value) return
  const codeBlocks = Array.from(root.value.querySelectorAll('pre code.language-mermaid, code.language-mermaid'))
  const nodes: HTMLElement[] = []
  codeBlocks.forEach((code, index) => {
    const pre = code.closest('pre')
    if (!pre || pre.classList.contains('mermaid-source')) return
    const holder = document.createElement('div')
    holder.className = 'mermaid mermaid-chart'
    holder.id = `mermaid-${Date.now()}-${index}`
    holder.textContent = normalizeMermaidSource(code.textContent || '')
    pre.replaceWith(holder)
    nodes.push(holder)
  })
  if (!nodes.length) return
  try {
    await mermaid.run({ nodes })
  } catch {
    nodes.forEach((node) => {
      const fallback = document.createElement('pre')
      fallback.className = 'mermaid-fallback'
      fallback.textContent = node.textContent || 'Mermaid 渲染失败'
      node.replaceWith(fallback)
    })
  }
}

watch(html, renderMermaid, { flush: 'post' })
onMounted(renderMermaid)
</script>

<style scoped>
.md-surface {
  background: transparent;
  color: var(--text);
  font-size: 14px;
}
.md-surface :deep(pre) {
  border-radius: 10px;
}
.md-surface :deep(.mermaid-chart) {
  margin: 16px 0;
  padding: 16px;
  border: 1px solid var(--border);
  border-radius: 12px;
  background: linear-gradient(180deg, #fff, #f8fafc);
  overflow-x: auto;
}
.md-surface :deep(.mermaid-chart svg) {
  max-width: 100%;
  height: auto;
}
.md-surface :deep(.mermaid-fallback) {
  white-space: pre-wrap;
  background: #fff7ed;
  color: #9a3412;
}
</style>
