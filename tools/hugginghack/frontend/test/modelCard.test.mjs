import assert from 'node:assert/strict'
import test from 'node:test'
import React from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import ReactMarkdown from 'react-markdown'
import rehypeKatex from 'rehype-katex'
import rehypeRaw from 'rehype-raw'
import rehypeSanitize from 'rehype-sanitize'
import remarkGfm from 'remark-gfm'
import remarkMath from 'remark-math'
import {
  modelCardHeadingId,
  modelCardSanitizeSchema,
  prepareModelCardMarkdown,
  resolveModelCardUrl,
  stripModelCardFrontmatter,
} from '../src/modelCard.ts'

test('removes only line-delimited YAML frontmatter', () => {
  const source = '---\ntitle: A --- B\ntags:\n  - demo\n---\n# Card'
  assert.equal(stripModelCardFrontmatter(source), '# Card')
  assert.equal(stripModelCardFrontmatter('---\ntitle: Demo\n...\nBody'), 'Body')
  assert.equal(stripModelCardFrontmatter('---\nA horizontal rule'), '---\nA horizontal rule')
})

test('normalizes LaTeX delimiters without changing code or currency', () => {
  const source = [
    'Costs $5 and $10. Inline \\(x + y\\).',
    '',
    '`\\(inline code\\)`',
    '',
    '~~~python',
    'print(\"\\[fenced\\]\")',
    '~~~',
    '',
    '    \\(indented code\\)',
  ].join('\n')
  const prepared = prepareModelCardMarkdown(source)
  assert.match(prepared, /Costs \$5 and \$10\. Inline \$\$x \+ y\$\$\./)
  assert.match(prepared, /`\\\(inline code\\\)`/)
  assert.match(prepared, /print\("\\\[fenced\\\]"\)/)
  assert.match(prepared, /    \\\(indented code\\\)/)
})

test('resolves repository assets and links through the correct Hub routes', () => {
  const sourceUrl = 'https://huggingface.co/acme/model'
  assert.equal(
    resolveModelCardUrl('./assets/chart.png', 'src', sourceUrl, 'main'),
    'https://huggingface.co/acme/model/resolve/main/assets/chart.png',
  )
  assert.equal(
    resolveModelCardUrl('docs/usage.md', 'href', sourceUrl, 'refs/pr/2'),
    'https://huggingface.co/acme/model/blob/refs/pr/2/docs/usage.md',
  )
  assert.equal(resolveModelCardUrl('#usage', 'href', sourceUrl, 'main'), '#usage')
  assert.equal(resolveModelCardUrl('javascript:alert(1)', 'href', sourceUrl, 'main'), null)
})

test('creates stable readable heading ids', () => {
  assert.equal(modelCardHeadingId('Model Details & Usage'), 'model-details-usage')
  assert.equal(modelCardHeadingId('Café weights'), 'cafe-weights')
})

test('sanitizes embedded HTML while preserving readable Markdown and math', () => {
  const source = prepareModelCardMarkdown(
    '# Safe\n\n<strong>Readable</strong><iframe src=\"https://evil.example\"></iframe>' +
      '<form action=\"https://evil.example\"><input name=\"secret\"></form>\n\n\\(x^2\\)',
  )
  const html = renderToStaticMarkup(
    React.createElement(
      ReactMarkdown,
      {
        remarkPlugins: [remarkGfm, [remarkMath, { singleDollarTextMath: false }]],
        rehypePlugins: [
          rehypeRaw,
          [rehypeSanitize, modelCardSanitizeSchema],
          rehypeKatex,
        ],
      },
      source,
    ),
  )
  assert.match(html, /<strong>Readable<\/strong>/)
  assert.match(html, /class="katex"/)
  assert.doesNotMatch(html, /<(?:iframe|form)\b/)
})
