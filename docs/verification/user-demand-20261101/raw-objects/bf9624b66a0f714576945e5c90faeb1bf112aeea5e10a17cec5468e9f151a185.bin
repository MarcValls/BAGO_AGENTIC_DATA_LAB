// @vitest-environment jsdom
import React from 'react'
import {afterEach,beforeEach,expect,it,vi} from 'vitest'
import {cleanup,fireEvent,render,screen,waitFor,within} from '@testing-library/react'
import WorkspaceManager from '../../src/components/WorkspaceManager'
import CsvTablePreview from '../../src/components/CsvTablePreview'
import {resetLocaleForTests,setLocale} from '../../src/i18n'
import {folderFixture,workspace} from '../project-folders/fixtures'

beforeEach(()=>{localStorage.clear();resetLocaleForTests();setLocale('es')})
afterEach(()=>{cleanup();vi.unstubAllGlobals()})

async function openFile(text:string,path='datos.csv') {
 const w=workspace();const file={path,text,sha256:'a'.repeat(64),size:text.length}
 const fixture=folderFixture({workspaces:[w],actions:body=>body.operation==='list_files'?{files:[file],excluded:[]}:body.operation==='trash_list'?{items:[]}:body.operation==='read'?file:{}})
 render(<WorkspaceManager proposal={{intent:'files'}}/>)
 await screen.findByRole('option',{name:'PROJECT FIXTURE · selected-project'})
 fireEvent.change(screen.getByLabelText('Proyecto gestionado'),{target:{value:w.id}})
 fireEvent.click(await screen.findByRole('button',{name:path}))
 await screen.findByRole('heading',{name:'Editar archivo'})
 return fixture
}

it('opens CSV as a semantic escaped table, switches with keyboard, and never writes or marks dirty by viewing',async()=>{
 const text='nombre,nota\r\n"A, B","<img src=x onerror=alert(1)>"\r\n'
 const f=await openFile(text)
 const table=await screen.findByRole('table');expect(within(table).getByRole('columnheader',{name:'nombre'})).toBeTruthy()
 expect(within(table).getByRole('cell',{name:'A, B'})).toBeTruthy();expect(within(table).getByRole('cell',{name:'<img src=x onerror=alert(1)>'})).toBeTruthy();expect(table.querySelector('img')).toBeNull()
 expect((screen.getByLabelText('Proyecto gestionado') as HTMLSelectElement).disabled).toBe(false)
 const calls=f.calls.length
 fireEvent.keyDown(screen.getByRole('tab',{name:'Tabla'}),{key:'ArrowRight'})
 const editor=screen.getByLabelText('Contenido') as HTMLTextAreaElement;expect(editor.value).toBe(text.replace(/\r\n/g,'\n'))
 fireEvent.keyDown(screen.getByRole('tab',{name:'Texto'}),{key:'Home'})
 expect(screen.getByRole('table')).toBeTruthy();expect(f.calls).toHaveLength(calls)
 expect(screen.queryByText(/Cambios de edición sin guardar/)).toBeNull()
 // Saving remains a reviewed operation, with the exact original state rather than the textarea DOM normalization.
 fireEvent.click(screen.getByRole('button',{name:'Revisar guardado'}))
 const details=within(screen.getByRole('dialog')).getByText(/expected_sha256/)
 expect(JSON.parse(details.textContent!).text).toBe(text)
 expect(f.calls).toHaveLength(calls)
})
it('reflects edits in the preview without an implicit write and leaves unsaved state intact when switching',async()=>{
 const f=await openFile('name,value\nA,1')
 await screen.findByRole('table');const before=f.calls.length
 fireEvent.click(screen.getByRole('tab',{name:'Texto'}));fireEvent.change(screen.getByLabelText('Contenido'),{target:{value:'name,value\nB,2'}})
 expect(screen.getByText(/Cambios de edición sin guardar/)).toBeTruthy()
 fireEvent.click(screen.getByRole('tab',{name:'Tabla'}));expect(screen.getByRole('cell',{name:'B'})).toBeTruthy();expect(screen.getByRole('cell',{name:'2'})).toBeTruthy()
 expect(f.calls).toHaveLength(before);expect((screen.getByLabelText('Proyecto gestionado') as HTMLSelectElement).disabled).toBe(true)
})
it('keeps plain files in the existing editable text view without CSV tabs',async()=>{
 await openFile('<plain>','notes.txt');expect((screen.getByLabelText('Contenido') as HTMLTextAreaElement).value).toBe('<plain>');expect(screen.queryByRole('tab',{name:'Tabla'})).toBeNull()
})
it('shows errors with Text still available and preserves malformed input unchanged',async()=>{
 await openFile('name\n"unclosed');expect(await screen.findByRole('alert')).toHaveProperty('textContent',expect.stringContaining('comillas sin cerrar'))
 expect(screen.queryByRole('table')).toBeNull();fireEvent.click(screen.getByRole('tab',{name:'Texto'}));expect((screen.getByLabelText('Contenido') as HTMLTextAreaElement).value).toBe('name\n"unclosed')
})
it('renders empty, header-only, ragged and truncated states explicitly',()=>{
 const {rerender}=render(<CsvTablePreview text="" delimiter=","/>);expect(screen.getByText('El archivo está vacío.')).toBeTruthy()
 rerender(<CsvTablePreview text="name,value" delimiter=","/>);expect(screen.getByText('Solo hay encabezados; no hay filas de datos.')).toBeTruthy()
 rerender(<CsvTablePreview text={'name,value\nA\nB,2,extra'} delimiter=","/>);expect(screen.getByText(/distinto número de columnas/)).toBeTruthy();expect(screen.getByRole('cell',{name:'extra'})).toBeTruthy()
 rerender(<CsvTablePreview text={['name',...Array(240).fill('A')].join('\n')} delimiter=","/>);expect(screen.getByText(/Vista previa limitada/)).toBeTruthy();expect(screen.getAllByRole('row')).toHaveLength(201)
})
it('uses the same table/text path for TSV',async()=>{
 await openFile('name\tvalue\n"A\tB"\t1,2','datos.tsv');expect(await screen.findByRole('cell',{name:'1,2'})).toBeTruthy();expect(screen.getAllByRole('columnheader')).toHaveLength(2)
})
