<template>
  <div class="markdown-content" v-html="html" />
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { renderMarkdownToHtml } from '@/utils/renderMarkdown'

const props = defineProps<{
  source: string
}>()

const html = computed(() => renderMarkdownToHtml(props.source))
</script>

<style scoped>
.markdown-content {
  color: var(--text-primary);
  line-height: 1.55;
  word-break: break-word;
}

.markdown-content :deep(> :first-child) {
  margin-top: 0;
}

.markdown-content :deep(> :last-child) {
  margin-bottom: 0;
}

.markdown-content :deep(p) {
  margin: 0.5em 0;
}

.markdown-content :deep(h1),
.markdown-content :deep(h2),
.markdown-content :deep(h3),
.markdown-content :deep(h4) {
  margin: 0.75em 0 0.35em;
  font-weight: var(--font-weight-semibold, 600);
  color: var(--text-primary);
  line-height: 1.35;
}

.markdown-content :deep(h1) {
  font-size: 1.25rem;
}

.markdown-content :deep(h2) {
  font-size: 1.1rem;
}

.markdown-content :deep(h3),
.markdown-content :deep(h4) {
  font-size: 1rem;
}

.markdown-content :deep(ul),
.markdown-content :deep(ol) {
  margin: 0.5em 0;
  padding-left: 1.35em;
}

.markdown-content :deep(li) {
  margin: 0.2em 0;
}

.markdown-content :deep(li > p) {
  margin: 0.15em 0;
}

.markdown-content :deep(code) {
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
  font-size: 0.9em;
  background: rgba(255, 255, 255, 0.08);
  padding: 0.12em 0.35em;
  border-radius: 4px;
}

.markdown-content :deep(pre) {
  margin: 0.65em 0;
  padding: var(--spacing-sm) var(--spacing-md);
  background: #101318;
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
  overflow-x: auto;
}

.markdown-content :deep(pre code) {
  padding: 0;
  background: transparent;
}

.markdown-content :deep(blockquote) {
  margin: 0.5em 0;
  padding: 0.25em 0 0.25em 0.75em;
  border-left: 3px solid var(--color-primary);
  color: var(--text-secondary);
}

.markdown-content :deep(a) {
  color: var(--color-primary);
  text-decoration: none;
}

.markdown-content :deep(a:hover) {
  text-decoration: underline;
}

.markdown-content :deep(hr) {
  margin: 0.75em 0;
  border: 0;
  border-top: 1px solid var(--border-color);
}

.markdown-content :deep(table) {
  width: 100%;
  margin: 0.5em 0;
  border-collapse: collapse;
  font-size: 0.92em;
}

.markdown-content :deep(th),
.markdown-content :deep(td) {
  border: 1px solid var(--border-color);
  padding: 0.35em 0.55em;
  text-align: left;
}

.markdown-content :deep(th) {
  background: rgba(255, 255, 255, 0.06);
}
</style>
