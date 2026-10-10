import { strict as assert } from 'node:assert'
import { test } from 'node:test'
import { renderToStaticMarkup } from 'react-dom/server'
import AgentEvaluationLab from '../../../src/components/AgentEvaluationLab'

test('evaluation workspace renders an accessible loading state before its API data arrives', () => {
  const html = renderToStaticMarkup(<AgentEvaluationLab />)
  assert.match(html, /role="status"/)
  assert.match(html, /Loading evaluation workspace/)
})
