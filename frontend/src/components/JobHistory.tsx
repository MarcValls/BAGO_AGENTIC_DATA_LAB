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
    if (ms < 1000) return `${ms}ms`
    return `${(ms / 1000).toFixed(2)}s`
  }

  const formatDate = (dateStr: string) => {
    const date = new Date(dateStr)
    return date.toLocaleTimeString()
  }

  const gridRows: DataGridRow[] = filteredJobs.map((job) => ({
    id: job.job_id,
    cells: [
      <span className="status-cell" key="status"><span className="status-icon">{getStatusBadge(job.status)}</span>{job.status}</span>,
      <span className="type-cell" key="type">{job.job_type}</span>,
      <span className="id-cell" key="id" title={job.job_id}>{job.job_id.substring(0, 12)}...</span>,
      <span className="duration-cell" key="duration">{formatDuration(job.duration_ms)}</span>,
      <span className="cost-cell" key="cost">${job.cost_usd.toFixed(4)}</span>,
      <span className="date-cell" key="created">{formatDate(job.created_at)}</span>,
    ],
  }))

  return (
    <div className={`job-history${inline ? ' job-history-inline' : ''}`}>
      <div className="history-header">
        <h2>Job History</h2>
        <TabStrip<JobFilter>
          label="Job type filter"
          value={filter}
          onChange={setFilter}
          items={[
            { id: 'all', label: `All (${jobs.length})` },
            { id: 'demo', label: `Demo (${jobs.filter((j) => j.job_type === 'demo').length})` },
            { id: 'agent', label: `Agent (${jobs.filter((j) => j.job_type === 'agent').length})` },
          ]}
        />
      </div>

      {loading ? (
        <div className="loading">Loading job history...</div>
      ) : filteredJobs.length === 0 ? (
        <div className="empty-state">No jobs yet. Run a demo or agent to see history.</div>
      ) : (
        <div className="jobs-grid">
          <div className="jobs-list">
            <DataGrid
              label="Job history"
              columns={['Status', 'Type', 'ID', 'Duration', 'Cost', 'Created']}
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
              <h3>Job Details</h3>

              <div className="detail-section">
                <div className="detail-row">
                  <strong>Job ID:</strong>
                  <code>{selectedJob.job_id}</code>
                </div>
                <div className="detail-row">
                  <strong>Type:</strong>
                  <span>{selectedJob.job_type}</span>
                </div>
                <div className="detail-row">
                  <strong>Status:</strong>
                  <span className={`badge badge-${selectedJob.status}`}>
                    {selectedJob.status}
                  </span>
                </div>
                {selectedJob.agent_id && (
                  <div className="detail-row">
                    <strong>Agent:</strong>
                    <code>{selectedJob.agent_id}</code>
                  </div>
                )}
                <div className="detail-row">
                  <strong>Created:</strong>
                  <span>{new Date(selectedJob.created_at).toLocaleString()}</span>
                </div>
                {selectedJob.completed_at && (
                  <div className="detail-row">
                    <strong>Completed:</strong>
                    <span>{new Date(selectedJob.completed_at).toLocaleString()}</span>
                  </div>
                )}
                <div className="detail-row">
                  <strong>Duration:</strong>
                  <span>{formatDuration(selectedJob.duration_ms)}</span>
                </div>
                <div className="detail-row">
                  <strong>Exit Code:</strong>
                  <code>{selectedJob.exit_code ?? 'N/A'}</code>
                </div>
                <div className="detail-row">
                  <strong>Cost:</strong>
                  <span>${selectedJob.cost_usd.toFixed(4)}</span>
                </div>
              </div>

              {selectedJob.metrics && Object.keys(selectedJob.metrics).length > 0 && (
                <div className="detail-section">
                  <h4>Metrics</h4>
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
                  <h4>Output</h4>
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
                  <h4>Error</h4>
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
