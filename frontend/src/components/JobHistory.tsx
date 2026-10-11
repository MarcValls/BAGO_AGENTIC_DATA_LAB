import { useState, useEffect } from 'react'
import './JobHistory.css'

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
}

export default function JobHistory({ onJobSelect }: JobHistoryProps) {
  const [jobs, setJobs] = useState<Job[]>([])
  const [loading, setLoading] = useState(true)
  const [selectedJob, setSelectedJob] = useState<Job | null>(null)
  const [filter, setFilter] = useState<'all' | 'demo' | 'agent'>('all')

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

  return (
    <div className="job-history">
      <div className="history-header">
        <h2>📊 Job History</h2>
        <div className="filter-tabs">
          <button
            className={`filter-btn ${filter === 'all' ? 'active' : ''}`}
            onClick={() => setFilter('all')}
          >
            All ({jobs.length})
          </button>
          <button
            className={`filter-btn ${filter === 'demo' ? 'active' : ''}`}
            onClick={() => setFilter('demo')}
          >
            Demo ({jobs.filter((j) => j.job_type === 'demo').length})
          </button>
          <button
            className={`filter-btn ${filter === 'agent' ? 'active' : ''}`}
            onClick={() => setFilter('agent')}
          >
            Agent ({jobs.filter((j) => j.job_type === 'agent').length})
          </button>
        </div>
      </div>

      {loading ? (
        <div className="loading">Loading job history...</div>
      ) : filteredJobs.length === 0 ? (
        <div className="empty-state">No jobs yet. Run a demo or agent to see history.</div>
      ) : (
        <div className="jobs-grid">
          <div className="jobs-list">
            <table className="jobs-table">
              <thead>
                <tr>
                  <th>Status</th>
                  <th>Type</th>
                  <th>ID</th>
                  <th>Duration</th>
                  <th>Cost</th>
                  <th>Created</th>
                </tr>
              </thead>
              <tbody>
                {filteredJobs.map((job) => (
                  <tr
                    key={job.job_id}
                    className={`job-row ${selectedJob?.job_id === job.job_id ? 'selected' : ''}`}
                    onClick={() => setSelectedJob(job)}
                  >
                    <td className="status-cell">
                      <span className="status-icon">{getStatusBadge(job.status)}</span>
                      {job.status}
                    </td>
                    <td className="type-cell">{job.job_type}</td>
                    <td className="id-cell" title={job.job_id}>
                      {job.job_id.substring(0, 12)}...
                    </td>
                    <td className="duration-cell">{formatDuration(job.duration_ms)}</td>
                    <td className="cost-cell">${job.cost_usd.toFixed(4)}</td>
                    <td className="date-cell">{formatDate(job.created_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
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
