import {expect,it} from 'vitest'
import {delimitedFile,parseDelimitedPreview,PREVIEW_CHARACTERS,PREVIEW_COLUMNS,PREVIEW_ROWS} from '../../src/utils/delimitedText'

it('decodes quoted delimiters, escaped quotes, exact CRLF inside fields and trailing empty fields',()=>{
 const text='nombre,nota,fin\r\n"A, B","Dice ""hola""\r\ny adiós",\r\n'
 expect(parseDelimitedPreview(text)).toEqual({rows:[['nombre','nota','fin'],['A, B','Dice "hola"\r\ny adiós','']],error:null,ragged:false,truncated:false})
 expect(text).toBe('nombre,nota,fin\r\n"A, B","Dice ""hola""\r\ny adiós",\r\n')
})
it('preserves empty fields and explicit blank records without adding a phantom terminal record',()=>{
 expect(parseDelimitedPreview('')).toEqual({rows:[],error:null,ragged:false,truncated:false})
 expect(parseDelimitedPreview(',\n\n')).toMatchObject({rows:[['',''],['']],ragged:true})
 expect(parseDelimitedPreview('"",')).toMatchObject({rows:[['','']]})
 expect(parseDelimitedPreview('a\r\nb\r\nc')).toMatchObject({rows:[['a'],['b'],['c']]})
})
it('accepts BOM and TSV without converting tabs or comma content',()=>{
 expect(delimitedFile('REPORT.CSV')).toBe(',');expect(delimitedFile('datos.tsv')).toBe('\t');expect(delimitedFile('notes.txt')).toBeNull()
 expect(parseDelimitedPreview('\ufeff"name"\tvalue\n"A\tB"\t1,2','\t')).toMatchObject({rows:[['name','value'],['A\tB','1,2']],error:null})
})
it.each([['a\n"broken','unclosed_quote'],['a\nb"c','unexpected_quote'],['a\n"b"x','after_quote']])('reports malformed quoted input %s without a misleading partial table',(text,error)=>{
 expect(parseDelimitedPreview(text)).toMatchObject({rows:[],error})
})
it('preserves ragged records for a visible width warning',()=>{
 expect(parseDelimitedPreview('a,b\n1\n2,3,4')).toMatchObject({rows:[['a','b'],['1'],['2','3','4']],ragged:true,error:null})
})
it('bounds rows, columns and character scanning without calling an unfinished bounded field invalid',()=>{
 const rows=parseDelimitedPreview(['header',...Array.from({length:PREVIEW_ROWS+20},(_,i)=>String(i))].join('\n'))
 expect(rows.rows).toHaveLength(PREVIEW_ROWS+1);expect(rows.truncated).toBe(true)
 const wide=parseDelimitedPreview(Array(PREVIEW_COLUMNS+10).fill('cell').join(','));expect(wide.rows[0]).toHaveLength(PREVIEW_COLUMNS);expect(wide.truncated).toBe(true)
 const huge=parseDelimitedPreview('header\n"'+'x'.repeat(PREVIEW_CHARACTERS+10));expect(huge.rows).toEqual([['header']]);expect(huge.error).toBeNull();expect(huge.truncated).toBe(true)
})
