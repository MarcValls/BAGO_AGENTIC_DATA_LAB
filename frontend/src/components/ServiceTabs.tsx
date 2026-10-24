import type {KeyboardEvent} from 'react'
interface Item<T extends string> {id:T;label:string}
interface Props<T extends string> {id:string;label:string;items:Item<T>[];value:T;onChange:(value:T)=>void}
/** Native buttons with the WAI tab keyboard pattern; business state stays in the owner. */
export default function ServiceTabs<T extends string>({id,label,items,value,onChange}:Props<T>){
 function key(event:KeyboardEvent<HTMLButtonElement>,index:number){
  let next:number
  if(event.key==='ArrowRight')next=(index+1)%items.length
  else if(event.key==='ArrowLeft')next=(index+items.length-1)%items.length
  else if(event.key==='Home')next=0
  else if(event.key==='End')next=items.length-1
  else return
  event.preventDefault();onChange(items[next].id)
  const tabs=event.currentTarget.parentElement?.querySelectorAll<HTMLButtonElement>('[role="tab"]')
  tabs?.[next]?.focus()
 }
 return <div className="service-tabs" role="tablist" aria-label={label}>{items.map((item,index)=><button type="button" role="tab" id={`${id}-tab-${item.id}`} aria-controls={`${id}-panel-${item.id}`} aria-selected={value===item.id} tabIndex={value===item.id?0:-1} key={item.id} onClick={()=>onChange(item.id)} onKeyDown={event=>key(event,index)}>{item.label}</button>)}</div>
}
