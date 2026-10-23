import {setLocale,t} from '../../../src/i18n'
import {beforeEach as beforeLocaleExpectation} from 'vitest'
beforeLocaleExpectation(() => setLocale('es'))
// @vitest-environment jsdom
import React from 'react'
import { afterEach, expect, it, vi } from 'vitest'
import { cleanup, fireEvent, render, screen } from '@testing-library/react'

vi.mock('axios',()=>({default:{get:vi.fn(async()=>({data:{}}))}}))
vi.mock('../../../src/components/AgentChat',()=>({default:({onManageAgents}:any)=><div>Chat global<button onClick={onManageAgents}>Gestionar agentes desde Chat</button></div>}))
vi.mock('../../../src/components/AgentManagement',()=>({default:({onTest,onCreate,onEvaluate}:any)=><div>Biblioteca única<button onClick={onCreate}>Preparar perfil</button><button onClick={()=>onTest('agent_12345678')}>Probar seleccionado</button><button onClick={()=>onEvaluate('agent_12345678')}>Evaluar seleccionado</button></div>}))
vi.mock('../../../src/components/AgentBuilder',()=>({default:({onBack}:any)=><div>Builder existente<button onClick={onBack}>Volver</button></div>}))
vi.mock('../../../src/components/AgentTasks',()=>({default:({initialAgentId}:any)=><div>Tarea existente {initialAgentId}</div>}))
vi.mock('../../../src/components/AgentEvaluationLab',()=>({default:({initialAgentId}:any)=><div>Laboratorio existente {initialAgentId}</div>}))
import App from '../../../src/App'
afterEach(()=>{cleanup();vi.restoreAllMocks()})

it('groups four destinations in the sidebar while retaining one global Chat and one management route',async()=>{
  render(<App />)
  expect(screen.getByText('Chat global')).toBeTruthy()
  expect(screen.queryByRole('button',{name:'Mis agentes'})).toBeNull()
  expect(screen.queryByRole('button',{name:'Agent Builder'})).toBeNull()
  fireEvent.click(screen.getByRole('button',{name:t('agents.AgentManagement.agentes')}))
  fireEvent.click(screen.getByRole('button',{name:'Mis agentes'}))
  expect(screen.getByText('Biblioteca única')).toBeTruthy()
  fireEvent.click(screen.getByRole('button',{name:'Probar seleccionado'}))
  expect(screen.getByText('Tarea existente agent_12345678')).toBeTruthy()
  expect(screen.getByRole('button',{name:'Ejecutar / Probar'}).getAttribute('aria-current')).toBe('page')
  fireEvent.click(screen.getByRole('button',{name:t('core.App.chat_460b3a')}))
  expect(screen.getByText('Chat global')).toBeTruthy()
  fireEvent.click(screen.getByRole('button',{name:'Gestionar agentes desde Chat'}))
  expect(screen.getByText('Biblioteca única')).toBeTruthy()
  fireEvent.click(screen.getByRole('button',{name:'Preparar perfil'}))
  expect(screen.getByText('Builder existente')).toBeTruthy()
  fireEvent.click(screen.getByRole('button',{name:t('agents.AgentBuilder.back')}))
  expect(screen.getByText('Biblioteca única')).toBeTruthy()
  fireEvent.click(screen.getByRole('button',{name:'Evaluar seleccionado'}))
  expect(screen.getByText('Laboratorio existente agent_12345678')).toBeTruthy()
})
