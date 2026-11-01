import {useMemo} from 'react'
import {t, formatNumber} from '../i18n'
import {parseDelimitedPreview} from '../utils/delimitedText'
import './CsvTablePreview.css'

export default function CsvTablePreview({text, delimiter}: {text: string; delimiter: ',' | '\t'}) {
  const preview = useMemo(() => parseDelimitedPreview(text, delimiter), [text, delimiter])
  const [header = [], ...body] = preview.rows
  const width = Math.max(0, ...preview.rows.map(row => row.length))
  return <div className="wm-csv-preview">
    <p className="wm-csv-note">{t('commerce.csv.read_only')}</p>
    {preview.error && <p role="alert" className="wm-error">{t(`commerce.csv.${preview.error}`)}</p>}
    {preview.truncated && <p role="status">{t('commerce.csv.limited')}</p>}
    {preview.ragged && <p role="status">{t('commerce.csv.ragged')}</p>}
    {!preview.error && (preview.rows.length ? <>
      <div className="wm-csv-scroll" role="region" aria-label={t('commerce.csv.preview')} tabIndex={0}>
        <table><caption>{t('commerce.csv.caption', {count: formatNumber(body.length)})}</caption>
          <thead><tr>{Array.from({length: width}, (_, column) => <th scope="col" key={column}>{header[column] || t('commerce.csv.column', {number: formatNumber(column + 1)})}</th>)}</tr></thead>
          <tbody>{body.map((row, index) => <tr key={index}>{Array.from({length: width}, (_, column) => <td key={column}>{row[column] ?? ''}</td>)}</tr>)}</tbody>
        </table>
      </div>
      {!body.length && <p>{t('commerce.csv.no_records')}</p>}
    </> : <p>{t(preview.truncated ? 'commerce.csv.no_complete_records' : 'commerce.csv.empty')}</p>)}
  </div>
}
