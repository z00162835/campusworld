import MarkdownIt from 'markdown-it'
import DOMPurify from 'dompurify'

const md = new MarkdownIt({
  html: false,
  linkify: true,
  breaks: true,
})

const defaultLinkOpen =
  md.renderer.rules.link_open
  ?? ((tokens, idx, options, _env, self) => self.renderToken(tokens, idx, options))

md.renderer.rules.link_open = (tokens, idx, options, env, self) => {
  const token = tokens[idx]
  if (token.attrIndex('target') < 0) {
    token.attrPush(['target', '_blank'])
  }
  if (token.attrIndex('rel') < 0) {
    token.attrPush(['rel', 'noopener noreferrer'])
  }
  return defaultLinkOpen(tokens, idx, options, env, self)
}

/** Render assistant markdown to sanitized HTML for in-app display. */
export function renderMarkdownToHtml(source: string): string {
  const rendered = md.render(source || '')
  return DOMPurify.sanitize(rendered, {
    USE_PROFILES: { html: true },
    ADD_ATTR: ['target'],
  })
}
