import {t, useI18n} from '../i18n'
import Markdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import type {Components} from 'react-markdown'
import './AssistantMarkdown.css'

/** Presentation only: Markdown never becomes an application action or raw HTML. */
function publicLink(value:string|undefined):string|undefined {
  if(!value)return undefined
  try {
    const url=new URL(value)
    return ['https:','http:'].includes(url.protocol)&&!url.username&&!url.password?url.href:undefined
  } catch {return undefined}
}
const components:Components={
  a:({href,children,title})=>{const safe=publicLink(href);return safe?<a href={safe} title={title} target="_blank" rel="noopener noreferrer">{children}</a>:<span>{children}</span>},
  img:({alt})=><span className="assistant-markdown-image-omitted">{t('commerce.image_omitted')}{alt?`: ${alt}`:''}</span>,
  table:({children})=><div className="assistant-markdown-table-scroll" role="region" aria-label={t('commerce.response_table')} tabIndex={0}><table>{children}</table></div>,
  th:({children})=><th scope="col">{children}</th>,
  input:({checked})=><span aria-label={checked?t('commerce.checked_task_in_text'):t('commerce.unchecked_task_in_text')}>{checked?'☑':'☐'}</span>,
}
const allowed=['p','strong','em','del','blockquote','ul','ol','li','h1','h2','h3','h4','h5','h6','pre','code','hr','br','a','img','table','thead','tbody','tr','th','td','input','section','sup']
export default function AssistantMarkdown({content}:{content:string}){
  useI18n()

  return <div className="assistant-markdown"><Markdown remarkPlugins={[remarkGfm]} skipHtml allowedElements={allowed} urlTransform={(url,key)=>key==='href'?publicLink(url):undefined} components={components}>{content}</Markdown></div>
}
