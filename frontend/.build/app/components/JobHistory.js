import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import './JobHistory.css';
import './WindowsSurface.css';
import { useState, useEffect } from 'react';
import DataGrid from './DataGrid';
import TabStrip from './TabStrip';
export default function JobHistory({ onJobSelect }) {
    const [jobs, setJobs] = useState([]);
    const [loading, setLoading] = useState(true);
    const [selectedJob, setSelectedJob] = useState(null);
    const [filter, setFilter] = useState('all');
    useEffect(() => {
        fetchJobs();
        const interval = setInterval(fetchJobs, 5000); // Refresh every 5s
        return () => clearInterval(interval);
    }, []);
    const fetchJobs = async () => {
        try {
            const response = await fetch('/api/jobs/list');
            const data = await response.json();
            setJobs(data.jobs || []);
        }
        catch (error) {
            console.error('Error fetching jobs:', error);
        }
        finally {
            setLoading(false);
        }
    };
    const filteredJobs = filter === 'all' ? jobs : jobs.filter((j) => j.job_type === filter);
    const selectJob = (job) => {
        setSelectedJob(job);
        onJobSelect?.(job);
    };
    const getStatusBadge = (status) => {
        const badges = {
            running: '🟡',
            success: '🟢',
            failed: '🔴',
            timeout: '⏱️',
        };
        return badges[status] || '⚪';
    };
    const formatDuration = (ms) => {
        if (!ms)
            return '-';
        if (ms < 1000)
            return `${ms}ms`;
        return `${(ms / 1000).toFixed(2)}s`;
    };
    const formatDate = (dateStr) => {
        const date = new Date(dateStr);
        return date.toLocaleTimeString();
    };
    const gridRows = filteredJobs.map((job) => ({
        id: job.job_id,
        cells: [
            _jsxs("span", { className: "status-cell", children: [_jsx("span", { className: "status-icon", children: getStatusBadge(job.status) }), job.status] }, "status"),
            _jsx("span", { className: "type-cell", children: job.job_type }, "type"),
            _jsxs("span", { className: "id-cell", title: job.job_id, children: [job.job_id.substring(0, 12), "..."] }, "id"),
            _jsx("span", { className: "duration-cell", children: formatDuration(job.duration_ms) }, "duration"),
            _jsxs("span", { className: "cost-cell", children: ["$", job.cost_usd.toFixed(4)] }, "cost"),
            _jsx("span", { className: "date-cell", children: formatDate(job.created_at) }, "created"),
        ],
    }));
    return (_jsxs("div", { className: "job-history", children: [_jsxs("div", { className: "history-header", children: [_jsx("h2", { children: "Job History" }), _jsx(TabStrip, { label: "Job type filter", value: filter, onChange: setFilter, items: [
                            { id: 'all', label: `All (${jobs.length})` },
                            { id: 'demo', label: `Demo (${jobs.filter((j) => j.job_type === 'demo').length})` },
                            { id: 'agent', label: `Agent (${jobs.filter((j) => j.job_type === 'agent').length})` },
                        ] })] }), loading ? (_jsx("div", { className: "loading", children: "Loading job history..." })) : filteredJobs.length === 0 ? (_jsx("div", { className: "empty-state", children: "No jobs yet. Run a demo or agent to see history." })) : (_jsxs("div", { className: "jobs-grid", children: [_jsx("div", { className: "jobs-list", children: _jsx(DataGrid, { label: "Job history", columns: ['Status', 'Type', 'ID', 'Duration', 'Cost', 'Created'], rows: gridRows, selectedId: selectedJob?.job_id, onSelect: (id) => {
                                const job = filteredJobs.find((item) => item.job_id === id);
                                if (job)
                                    selectJob(job);
                            } }) }), selectedJob && (_jsxs("div", { className: "job-detail", children: [_jsx("h3", { children: "Job Details" }), _jsxs("div", { className: "detail-section", children: [_jsxs("div", { className: "detail-row", children: [_jsx("strong", { children: "Job ID:" }), _jsx("code", { children: selectedJob.job_id })] }), _jsxs("div", { className: "detail-row", children: [_jsx("strong", { children: "Type:" }), _jsx("span", { children: selectedJob.job_type })] }), _jsxs("div", { className: "detail-row", children: [_jsx("strong", { children: "Status:" }), _jsx("span", { className: `badge badge-${selectedJob.status}`, children: selectedJob.status })] }), selectedJob.agent_id && (_jsxs("div", { className: "detail-row", children: [_jsx("strong", { children: "Agent:" }), _jsx("code", { children: selectedJob.agent_id })] })), _jsxs("div", { className: "detail-row", children: [_jsx("strong", { children: "Created:" }), _jsx("span", { children: new Date(selectedJob.created_at).toLocaleString() })] }), selectedJob.completed_at && (_jsxs("div", { className: "detail-row", children: [_jsx("strong", { children: "Completed:" }), _jsx("span", { children: new Date(selectedJob.completed_at).toLocaleString() })] })), _jsxs("div", { className: "detail-row", children: [_jsx("strong", { children: "Duration:" }), _jsx("span", { children: formatDuration(selectedJob.duration_ms) })] }), _jsxs("div", { className: "detail-row", children: [_jsx("strong", { children: "Exit Code:" }), _jsx("code", { children: selectedJob.exit_code ?? 'N/A' })] }), _jsxs("div", { className: "detail-row", children: [_jsx("strong", { children: "Cost:" }), _jsxs("span", { children: ["$", selectedJob.cost_usd.toFixed(4)] })] })] }), selectedJob.metrics && Object.keys(selectedJob.metrics).length > 0 && (_jsxs("div", { className: "detail-section", children: [_jsx("h4", { children: "Metrics" }), Object.entries(selectedJob.metrics).map(([key, value]) => (_jsxs("div", { className: "detail-row", children: [_jsxs("strong", { children: [key, ":"] }), _jsx("span", { children: JSON.stringify(value) })] }, key)))] })), selectedJob.stdout && (_jsxs("div", { className: "detail-section", children: [_jsx("h4", { children: "Output" }), _jsx("div", { className: "log-panel", children: selectedJob.stdout.split('\n').map((line, idx) => (_jsx("div", { className: "log-line", children: line }, idx))) })] })), selectedJob.stderr && (_jsxs("div", { className: "detail-section", children: [_jsx("h4", { children: "Error" }), _jsx("div", { className: "log-panel error", children: selectedJob.stderr.split('\n').map((line, idx) => (_jsx("div", { className: "log-line", children: line }, idx))) })] }))] }))] }))] }));
}
