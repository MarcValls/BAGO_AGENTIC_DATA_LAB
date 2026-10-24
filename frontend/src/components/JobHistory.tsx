import {useI18n,t,localMessage,errorMessage,apiError,formatDate,formatNumber} from '../i18n'
import './JobHistory.css'
import './WindowsSurface.css'
import { useState, useEffect } from 'react'
import DataGrid, { DataGridRow } from './DataGrid'
import TabStrip from './TabStrip'

interface Job {
  job_id: string
  agent_id: string | null
  job_type: string
  status: string
  created_at: string
  completed_at: string | null
  duration_ms: number | null
  exit_code: number | null
  stdout: string
  stderr: string
  cost_usd: number
  metrics: Record<string, any> | null
}

interface JobHistoryProps {
  onJobSelect?: (job: Job) => void
  inline?: boolean
}

type JobFilter = 'all' | 'demo' | 'agent'

export default function JobHistory({ onJobSelect, inline = false }: JobHistoryProps) {
  useI18n()

  const [jobs, setJobs] = useState<Job[]>([])
  const [loading, setLoading] = useState(true)
  const [selectedJob, setSelectedJob] = useState<Job | null>(null)
  const [filter, setFilter] = useState<JobFilter>('all')

  useEffect(() => {
    fetchJobs()
    const interval = setInterval(fetchJobs, 5000) // Refresh every 5s
    return () => clearInterval(interval)
  }, [])

  const fetchJobs = async () => {
    try {
      const response = await fetch('/api/jobs/list')
      const data = await response.json()
      setJobs(data.jobs || [])
    } catch (error) {
      console.error('Error fetching jobs:', error)
    } finally {
      setLoading(false)
    }
  }

  const filteredJobs = filter === 'all' ? jobs : jobs.filter((j) => j.job_type === filter)
  const selectJob = (job: Job) => {
    setSelectedJob(job)
    onJobSelect?.(job)
  }

  const getStatusBadge = (status: string) => {
    const badges: Record<string, string> = {
      running: '🟡',
      success: '🟢',
      failed: '🔴',
      timeout: '⏱️',
    }
    return badges[status] || '⚪'
  }

  const formatDuration = (ms: number | null) => {
    if (!ms) return '-'
    if (ms < 1000) return `${formatNumber(ms)} ms`
    return `${formatNumber(ms/1000,{minimumFractionDigits:2,maximumFractionDigits:2})} s`
  }


  const gridRows: DataGridRow[] = filteredJobs.map((job) => ({
    id: job.job_id,
    cells: [
      <span className="status-cell" key="status"><span className="status-icon">{getStatusBadge(job.status)}</span>{observedStateLabel(job.status)}</span>,
      <span className="type-cell" key="type">{observedStateLabel(job.job_type)}</span>,
      <span className="id-cell" key="id" title={job.job_id}>{job.job_id.substring(0, 12)}...</span>,
      <span className="duration-cell" key="duration">{formatDuration(job.duration_ms)}</span>,
      <span className="cost-cell" key="cost">${formatNumber(job.cost_usd,{minimumFractionDigits:4,maximumFractionDigits:4})}</span>,
      <span className="date-cell" key="created">{formatDate(job.created_at)}</span>,
    ],
  }))

  return (
    <div className={`job-history${inline ? ' job-history-inline' : ''}`}>
      <div className="history-header">
        <h2>{t("core.JobHistory.job_history_17be0b")}</h2>
        <TabStrip<JobFilter>
          label={t("core.JobHistory.job_type_filter_40c7a8")}
          value={filter}
          onChange={setFilter}
          items={[
            { id: 'all', label: t('agents.aux.JobHistory.all_p0',{p0:formatNumber(jobs.length)}) },
            { id: 'demo', label: t('agents.aux.JobHistory.demo_p0',{p0:formatNumber(jobs.filter((j) => j.job_type === 'demo').length)}) },
            { id: 'agent', label: t('agents.aux.JobHistory.agent_p0',{p0:formatNumber(jobs.filter((j) => j.job_type === 'agent').length)}) },
          ]}
        />
      </div>

      {loading ? (
        <div className="loading">{t("core.JobHistory.loading_job_history_a7396e")}</div>
      ) : filteredJobs.length === 0 ? (
        <div className="empty-state">{t("core.JobHistory.no_jobs_yet_run_a_demo_or_6874b2")}</div>
      ) : (
        <div className="jobs-grid">
          <div className="jobs-list">
            <DataGrid
              label={t("core.JobHistory.job_history_85d5ed")}
              columns={[t('agents.aux.JobHistory.status'), t('agents.aux.JobHistory.type'), t('agents.aux.JobHistory.id'), t('agents.aux.JobHistory.duration'), t('agents.aux.JobHistory.cost'), t('agents.aux.JobHistory.created')]}
              rows={gridRows}
              selectedId={selectedJob?.job_id}
              onSelect={(id) => {
                const job = filteredJobs.find((item) => item.job_id === id)
                if (job) selectJob(job)
              }}
            />
          </div>

          {selectedJob && (
            <div className="job-detail">
              <h3>{t("core.JobHistory.job_details_6cfe85")}</h3>

              <div className="detail-section">
                <div className="detail-row">
                  <strong>{t("core.JobHistory.job_id_e29dcd")}</strong>
                  <code>{selectedJob.job_id}</code>
                </div>
                <div className="detail-row">
                  <strong>{t("core.JobHistory.type_6cc5ad")}</strong>
                  <span>{observedStateLabel(selectedJob.job_type)}</span>
                </div>
                <div className="detail-row">
                  <strong>{t("core.JobHistory.status_755c8b")}</strong>
                  <span className={`badge badge-${observedStateLabel(selectedJob.status)}`}>
                    {observedStateLabel(selectedJob.status)}
                  </span>
                </div>
                {selectedJob.agent_id && (
                  <div className="detail-row">
                    <strong>{t("core.JobHistory.agent_687ebf")}</strong>
                    <code>{selectedJob.agent_id}</code>
                  </div>
                )}
                <div className="detail-row">
                  <strong>{t("core.JobHistory.created_22d435")}</strong>
                  <span>{formatDate(selectedJob.created_at)}</span>
                </div>
                {selectedJob.completed_at && (
                  <div className="detail-row">
                    <strong>{t("core.JobHistory.completed_7e10a6")}</strong>
                    <span>{formatDate(selectedJob.completed_at)}</span>
                  </div>
                )}
                <div className="detail-row">
                  <strong>{t("core.JobHistory.duration_298d6c")}</strong>
                  <span>{formatDuration(selectedJob.duration_ms)}</span>
                </div>
                <div className="detail-row">
                  <strong>{t("core.JobHistory.exit_code_115a00")}</strong>
                  <code>{selectedJob.exit_code ?? t('agents.aux.JobHistory.n_a')}</code>
                </div>
                <div className="detail-row">
                  <strong>{t("core.JobHistory.cost_97c94e")}</strong>
                  <span>${formatNumber(selectedJob.cost_usd,{minimumFractionDigits:4,maximumFractionDigits:4})}</span>
                </div>
              </div>

              {selectedJob.metrics && Object.keys(selectedJob.metrics).length > 0 && (
                <div className="detail-section">
                  <h4>{t("core.JobHistory.metrics_a58da7")}</h4>
                  {Object.entries(selectedJob.metrics).map(([key, value]) => (
                    <div key={key} className="detail-row">
                      <strong>{key}:</strong>
                      <span>{JSON.stringify(value)}</span>
                    </div>
                  ))}
                </div>
              )}

              {selectedJob.stdout && (
                <div className="detail-section">
                  <h4>{t("core.JobHistory.output_b2439b")}</h4>
                  <div className="log-panel">
                    {selectedJob.stdout.split('\n').map((line, idx) => (
                      <div key={idx} className="log-line">
                        {line}
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {selectedJob.stderr && (
                <div className="detail-section">
                  <h4>{t("core.JobHistory.error_54a0e8")}</h4>
                  <div className="log-panel error">
                    {selectedJob.stderr.split('\n').map((line, idx) => (
                      <div key={idx} className="log-line">
                        {line}
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  )
}

/** Presentation only: preserve the exact observed protocol value alongside its label. */
function observedStateLabel(value: string): string {
  const labels: Record<string, () => string> = {
"running":()=>t('agents.aux.state.running'),
"success":()=>t('agents.aux.state.success'),
"failed":()=>t('agents.aux.state.failed'),
"timeout":()=>t('agents.aux.state.timeout'),
"demo":()=>t('agents.aux.state.demo'),
"agent":()=>t('agents.aux.state.agent'),
"PROPOSED":()=>t('agents.aux.state.PROPOSED'),
"VERIFIED":()=>t('agents.aux.state.VERIFIED'),
"PENDING_REVIEW":()=>t('agents.aux.state.PENDING_REVIEW'),
"CANCELLED":()=>t('agents.aux.state.CANCELLED'),
"EXPIRED":()=>t('agents.aux.state.EXPIRED'),
"AVAILABLE":()=>t('agents.aux.state.AVAILABLE'),
"UNAVAILABLE":()=>t('agents.aux.state.UNAVAILABLE'),
"READY":()=>t('agents.aux.state.READY'),
"NOT_READY":()=>t('agents.aux.state.NOT_READY'),
"AWAITING_APPROVAL":()=>t('agents.aux.state.AWAITING_APPROVAL'),
"APPROVED":()=>t('agents.aux.state.APPROVED'),
"REJECTED":()=>t('agents.aux.state.REJECTED'),
"SUCCEEDED":()=>t('agents.aux.state.SUCCEEDED'),
"FAILED":()=>t('agents.aux.state.FAILED'),
"REVOKED":()=>t('agents.aux.state.REVOKED'),
"UNKNOWN":()=>t('agents.aux.state.UNKNOWN'),
"PASS":()=>t('agents.aux.state.PASS'),
"FAIL":()=>t('agents.aux.state.FAIL'),
"ERROR":()=>t('agents.aux.state.ERROR'),
"healthy":()=>t('agents.aux.state.healthy'),
"unavailable":()=>t('agents.aux.state.unavailable'),
"ALLOW":()=>t('agents.aux.state.ALLOW'),
"DENY":()=>t('agents.aux.state.DENY'),
"REQUIRE_HUMAN":()=>t('agents.aux.state.REQUIRE_HUMAN'),
"SUCCESS":()=>t('agents.aux.state.SUCCESS'),
"DENIED":()=>t('agents.aux.state.DENIED'),
"configured":()=>t('agents.aux.state.configured'),
"connected":()=>t('agents.aux.state.connected'),
"present":()=>t('agents.aux.state.present'),
"absent":()=>t('agents.aux.state.absent')
  }
  return Object.prototype.hasOwnProperty.call(labels,value) ? `${labels[value]()} (${value})` : t('agents.aux.state.unknownCode',{value})
}
