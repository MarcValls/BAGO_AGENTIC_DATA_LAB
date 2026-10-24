import {useI18n} from './index'
export default function LanguageSelector({compact=false}:{compact?:boolean}){
 const {t,locale,setLocale,storageUnavailable}=useI18n()
 return <div className={`language-selector${compact?' language-selector--compact':''}`}>
  <label><span>{t('common.language')}</span><select aria-label={t('common.language')} value={locale} onChange={event=>setLocale(event.target.value==='en'?'en':'es')}><option value="es">Español</option><option value="en">English</option></select></label>
  {storageUnavailable&&<small role="status">{t('common.storageUnavailable')}</small>}
 </div>
}
