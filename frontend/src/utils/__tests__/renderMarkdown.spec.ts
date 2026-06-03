import { describe, it, expect } from 'vitest'
import { renderMarkdownToHtml } from '../renderMarkdown'

describe('renderMarkdownToHtml', () => {
  it('renders headings and lists instead of raw markdown', () => {
    const html = renderMarkdownToHtml('## Title\n\n- one\n- two')
    expect(html).toContain('<h2>')
    expect(html).toContain('<ul>')
    expect(html).toContain('<li>')
    expect(html).not.toContain('## Title')
  })

  it('renders fenced code blocks', () => {
    const html = renderMarkdownToHtml('```js\nconst x = 1\n```')
    expect(html).toContain('<pre><code')
  })

  it('strips script tags from output', () => {
    const html = renderMarkdownToHtml('<script>alert(1)</script>\n\n**bold**')
    expect(html).not.toContain('<script')
    expect(html).toContain('<strong>')
  })

  it('opens links in a new tab safely', () => {
    const html = renderMarkdownToHtml('[docs](https://example.com)')
    expect(html).toContain('target="_blank"')
    expect(html).toContain('rel="noopener noreferrer"')
  })
})
