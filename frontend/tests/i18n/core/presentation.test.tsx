// @vitest-environment jsdom
import React from 'react'
import {afterEach,beforeEach,expect,it} from 'vitest'
import {act,cleanup,render,screen} from '@testing-library/react'
import {setLocale,resetLocaleForTests,formatNumber} from '../../../src/i18n'
import Summary from '../../../src/components/Summary'
import Retrieval from '../../../src/components/Retrieval'
import Authorization from '../../../src/components/Authorization'
import Trace from '../../../src/components/Trace'
import Evaluation from '../../../src/components/Evaluation'
beforeEach(()=>{localStorage.clear();resetLocaleForTests()})
afterEach(cleanup)
it('switches all historical data-view chrome while preserving evidence, original codes and unknown failures',()=>{
 const data={summary:{status:'FAIL',cost_usd:1234.5,ontology_outcome:'SUCCESS',sandbox_status:'NOT_RUN',aws_live:'NOT_RUN',openmetadata_live:'NOT_RUN'},agent_run:{query:'USER_QUERY_RAW',answer:'LLM_ANSWER_RAW',retrieval:{mode:'hybrid'},ontology:{receipt:{outcome:'UNKNOWN_OUTCOME_RAW'}},proposals:[{tool_name:'TOOL_ID_RAW',decision:'DENY',effect_type:'READ',permit_id:'PERMIT_ID_RAW',request_id:'REQUEST_ID_RAW',rationale:'ORIGINAL_RATIONALE_RAW'}]},receipts:{provider_receipt:{execution_outcome:'ERROR',decision:'DENY',cost_usd:0},sandbox_receipt:{status:'NOT_RUN'}},trace:{trace_id:'TRACE_ID_RAW',cost_usd:0,events:[{name:'ORIGINAL_EVENT_RAW',kind:'RAW_KIND',attributes:{diagnostic:'DIAGNOSTIC_RAW'}}]},evaluation:{status:'FAIL',score:0.5,cost_usd:0,checks:[{name:'CHECK_NAME_RAW',detail:'ORIGINAL_DETAIL_RAW',passed:false,evidence_refs:['EVIDENCE_ID_RAW']}]}}
 const original=JSON.stringify(data)
 render(<><Summary data={data}/><Retrieval data={data}/><Authorization data={data}/><Trace data={data}/><Evaluation data={data}/></>)
 for(const heading of ['Proceso de recuperación','Autorización y límite de ejecución','Traza de eventos','Evaluación de gobernanza'])expect(screen.getByRole('heading',{name:heading})).toBeTruthy()
 expect(screen.getByText('Evidencias (1)')).toBeTruthy();expect(screen.getByText('Una evaluación PASS significa:')).toBeTruthy()
 expect(screen.getByText('Estado no reconocido · UNKNOWN_OUTCOME_RAW')).toBeTruthy()
 expect(screen.getAllByText('Denegado · DENY')).toHaveLength(2)
 expect(screen.getByText('$'+formatNumber(1234.5,{minimumFractionDigits:2,maximumFractionDigits:2}))).toBeTruthy()
 act(()=>setLocale('en'))
 for(const heading of ['Retrieval pipeline','Authorization & execution boundary','Event trace','Governance evaluation'])expect(screen.getByRole('heading',{name:heading})).toBeTruthy()
 expect(screen.getByText('Evidence (1)')).toBeTruthy();expect(screen.getByText('A PASS evaluation means:')).toBeTruthy()
 expect(screen.getByText('Unrecognized state · UNKNOWN_OUTCOME_RAW')).toBeTruthy()
 expect(screen.getAllByText('Denied · DENY')).toHaveLength(2)
 for(const raw of ['USER_QUERY_RAW','LLM_ANSWER_RAW','TOOL_ID_RAW','PERMIT_ID_RAW','REQUEST_ID_RAW','ORIGINAL_RATIONALE_RAW','TRACE_ID_RAW','ORIGINAL_EVENT_RAW','CHECK_NAME_RAW','ORIGINAL_DETAIL_RAW','EVIDENCE_ID_RAW'])expect(screen.getByText(raw)).toBeTruthy()
 expect(JSON.stringify(data)).toBe(original)
})
