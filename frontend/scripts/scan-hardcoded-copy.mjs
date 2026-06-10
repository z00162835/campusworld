#!/usr/bin/env node
import { readdirSync, readFileSync, statSync } from 'node:fs'
import { join, relative } from 'node:path'

const root = new URL('..', import.meta.url).pathname
const srcRoot = join(root, 'src')

const excludedPathParts = [
  '/locales/',
  '/test/',
  '/styles/',
  '/node_modules/',
]

const excludedFilePatterns = [
  /\.spec\.ts$/,
  /\.d\.ts$/,
]

const uiCallPattern = /\b(ElMessage|ElMessageBox)\.(success|error|warning|info|confirm)\(\s*(['"`])([^'"`]*)\2/g
const vueTextPattern = />\s*([^<>{}\n]+?)\s*</g
const propPattern = /\s(?:aria-label|title|sub-title|label|placeholder|description)=["']([^"']*)["']/g
const alphaPattern = /[A-Za-z]{2,}/
const chinesePattern = /[\u4e00-\u9fff]/
const copyAllowlist = new Set([
  'AICO',
  'CampusWorld',
  'Command',
  'ID:',
  'N',
])

function isLikelyCopy(text) {
  const clean = text.replace(/\s+/g, ' ').trim()
  if (!clean || copyAllowlist.has(clean)) return false
  if (/^[\d\s%:./_-]+$/.test(clean)) return false
  if (/^[A-Z0-9_./:-]+$/.test(clean)) return false
  return chinesePattern.test(clean) || alphaPattern.test(clean)
}

function walk(dir) {
  const entries = readdirSync(dir)
  return entries.flatMap(entry => {
    const path = join(dir, entry)
    const stat = statSync(path)
    if (stat.isDirectory()) return walk(path)
    return [path]
  })
}

function isExcluded(path) {
  const normalized = path.replaceAll('\\', '/')
  return excludedPathParts.some(part => normalized.includes(part)) ||
    excludedFilePatterns.some(pattern => pattern.test(normalized))
}

function stripComments(source) {
  return source
    .replace(/<!--[\s\S]*?-->/g, '')
    .replace(/\/\*[\s\S]*?\*\//g, '')
    .replace(/^\s*\/\/.*$/gm, '')
}

function templateSource(source) {
  const match = source.match(/<template>([\s\S]*?)<\/template>/)
  return match?.[1] || ''
}

const candidates = []

for (const file of walk(srcRoot)) {
  if (!/\.(vue|ts)$/.test(file) || isExcluded(file)) continue
  const source = stripComments(readFileSync(file, 'utf8'))
  const isVue = file.endsWith('.vue')
  const template = isVue ? templateSource(source) : ''
  const relativePath = relative(root, file)

  const scanTargets = [
    ...(isVue ? [
      ['template-text', vueTextPattern, template],
      ['ui-prop', propPattern, template],
    ] : []),
    ['ui-message', uiCallPattern, source],
  ]

  for (const [label, pattern, scanSource] of scanTargets) {
    pattern.lastIndex = 0
    let match
    while ((match = pattern.exec(scanSource)) !== null) {
      const text = (label === 'ui-message' ? match[3] : match[1] || '').trim()
      if (!isLikelyCopy(text)) continue
      const line = source.slice(0, source.indexOf(scanSource) + match.index).split('\n').length
      candidates.push({ file: relativePath, line, label, text })
    }
  }
}

if (!candidates.length) {
  console.log('No hardcoded i18n copy candidates found.')
  process.exit(0)
}

console.log('Hardcoded i18n copy candidates (non-blocking):')
for (const candidate of candidates) {
  console.log(`${candidate.file}:${candidate.line} [${candidate.label}] ${candidate.text}`)
}
process.exit(0)
