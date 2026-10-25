// @vitest-environment jsdom
import React from 'react'
import {afterEach,beforeEach,expect,it,vi} from 'vitest'
import {cleanup,fireEvent,render,screen,within} from '@testing-library/react'
import {DecisionInspector,type DecisionInspectorArtifacts} from '../../../src/features/decision-inspector/integration/DecisionInspector'
import {InspectorShell} from '../../../src/features/decision-inspector/shell/InspectorShell'
import {resetLocaleForTests,setLocale,t} from '../../../src/i18n'
const artifacts:DecisionInspectorArtifacts={summary:{status:'PASS'},agent_run:{run_id:'run-single-owned',status:'COMPLETED',query:'Question from fixture',answer:'ONE COMPLETE ORIGINAL ANSWER',retrieval:{hits:[]},proposals:[],decision_receipts:[],mcp_receipts:[]},receipts:{},trace:{trace_id:'trace-fixture',run_id:'run-single-owned',events:[{event_id:'event-fixture',trace_id:'trace-fixture',sequence:0,name:'agent.run',kind:'workflow',status:'SUCCESS',attributes:{},evidence_refs:[]}]},evaluation:{}}
beforeEach(()=>{localStorage.clear();resetLocaleForTests();setLocale('en')})
afterEach(()=>{cleanup();vi.restoreAllMocks()})
it('embedded demo has one context identity and full answer once while retaining all inner navigation',()=>{
 const view=render(<><h2>Host Inspector</h2><DecisionInspector artifacts={artifacts} embedded/></>)
 expect(view.container.querySelectorAll('h1')).toHaveLength(0);expect(screen.getAllByText('ONE COMPLETE ORIGINAL ANSWER')).toHaveLength(1)
 expect(screen.getAllByText('run-single-owned')).toHaveLength(1);expect(screen.queryByRole('navigation',{name:t('agents.InspectorShell.select_a_conclusion')})).toBeNull()
 const details=screen.getByText('run-single-owned').closest('details')!;expect(details.open).toBe(false)
 const nav=screen.getByRole('navigation',{name:t('agents.DecisionInspector.inspector_views')})
 fireEvent.click(within(nav).getByRole('button',{name:t('agents.DecisionInspector.trace')}));expect(screen.getByText('event-fixture')).toBeTruthy()
 fireEvent.click(within(nav).getByRole('button',{name:t('agents.DecisionInspector.actions')}));expect(screen.getByText(t('agents.ActionReview.this_run_has_no_proposed_actions'))).toBeTruthy()
 fireEvent.click(within(nav).getByRole('button',{name:t('agents.DecisionInspector.decision')}));expect(screen.getAllByText('ONE COMPLETE ORIGINAL ANSWER')).toHaveLength(1)
})
it('standalone inspector and shell retain their own accessible headings',()=>{
 const view=render(<DecisionInspector artifacts={artifacts}/>);expect(screen.getAllByRole('heading',{name:t('agents.DecisionInspector.decision_inspector')})).toHaveLength(1)
 view.unmount();render(<InspectorShell conclusions={[]} />);expect(screen.getByRole('heading',{name:t('agents.DecisionInspector.decision_inspector')})).toBeTruthy()
})
it('embedded shell preserves multi-conclusion selection instead of hiding the function',()=>{
 const conclusions=['first','second'].map(id=>({id,text:id,runId:'run-'+id,claims:[]}))
 const choose=vi.fn();render(<InspectorShell embedded conclusions={conclusions} onConclusionSelect={choose}/>)
 const nav=screen.getByRole('navigation',{name:t('agents.InspectorShell.select_a_conclusion')})
 fireEvent.click(within(nav).getByRole('button',{name:'second'}));expect(choose).toHaveBeenCalledExactlyOnceWith('second')
 expect(screen.getByRole('heading',{name:t('agents.InspectorShell.conclusion')})).toBeTruthy()
})
it('trace mismatch stays an explicit warning rather than an invented timeline',()=>{
 render(<DecisionInspector artifacts={{...artifacts,trace:{...artifacts.trace,run_id:'wrong-run'}}} embedded/>)
 expect(screen.getByRole('status').textContent).toContain('does not match')
 const nav=screen.getByRole('navigation',{name:t('agents.DecisionInspector.inspector_views')});fireEvent.click(within(nav).getByRole('button',{name:t('agents.DecisionInspector.trace')}))
 expect(screen.queryByText('event-fixture')).toBeNull()
})
