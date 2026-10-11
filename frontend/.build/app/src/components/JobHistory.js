import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import { useState, useEffect } from 'react';
import './JobHistory.css';
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
    return (_jsxs("div", { className: "job-history", children: [_jsxs("div", { className: "history-header", children: [_jsx("h2", { children: "\uD83D\uDCCA Job History" }), _jsxs("div", { className: "filter-tabs", children: [_jsxs("button", { className: `filter-btn ${filter === 'all' ? 'active' : ''}`, onClick: () => setFilter('all'), children: ["All (", jobs.length, ")"] }), _jsxs("button", { className: `filter-btn ${filter === 'demo' ? 'active' : ''}`, onClick: () => setFilter('demo'), children: ["Demo (", jobs.filter((j) => j.job_type === 'demo').length, ")"] }), _jsxs("button", { className: `filter-btn ${filter === 'agent' ? 'active' : ''}`, onClick: () => setFilter('agent'), children: ["Agent (", jobs.filter((j) => j.job_type === 'agent').length, ")"] })] })] }), loading ? (_jsx("div", { className: "loading", children: "Loading job history..." })) : filteredJobs.length === 0 ? (_jsx("div", { className: "empty-state", children: "No jobs yet. Run a demo or agent to see history." })) : (_jsxs("div", { className: "jobs-grid", children: [_jsx("div", { className: "jobs-list", children: _jsxs("table", { className: "jobs-table", children: [_jsx("thead", { children: _jsxs("tr", { children: [_jsx("th", { children: "Status" }), _jsx("th", { children: "Type" }), _jsx("th", { children: "ID" }), _jsx("th", { children: "Duration" }), _jsx("th", { children: "Cost" }), _jsx("th", { children: "Created" })] }) }), _jsx("tbody", { children: filteredJobs.map((job) => (_jsxs("tr", { className: `job-row ${selectedJob?.job_id === job.job_id ? 'selected' : ''}`, onClick: () => setSelectedJob(job), children: [_jsxs("td", { className: "status-cell", children: [_jsx("span", { className: "status-icon", children: getStatusBadge(job.status) }), job.status] }), _jsx("td", { className: "type-cell", children: job.job_type }), _jsxs("td", { className: "id-cell", title: job.job_id, children: [job.job_id.substring(0, 12), "..."] }), _jsx("td", { className: "duration-cell", children: formatDuration(job.duration_ms) }), _jsxs("td", { className: "cost-cell", children: ["$", job.cost_usd.toFixed(4)] }), _jsx("td", { className: "date-cell", children: formatDate(job.created_at) })] }, job.job_id))) })] }) }), selectedJob && (_jsxs("div", { className: "job-detail", children: [_jsx("h3", { children: "Job Details" }), _jsxs("div", { className: "detail-section", children: [_jsxs("div", { className: "detail-row", children: [_jsx("strong", { children: "Job ID:" }), _jsx("code", { children: selectedJob.job_id })] }), _jsxs("div", { className: "detail-row", children: [_jsx("strong", { children: "Type:" }), _jsx("span", { children: selectedJob.job_type })] }), _jsxs("div", { className: "detail-row", children: [_jsx("strong", { children: "Status:" }), _jsx("span", { className: `badge badge-${selectedJob.status}`, children: selectedJob.status })] }), selectedJob.agent_id && (_jsxs("div", { className: "detail-row", children: [_jsx("strong", { children: "Agent:" }), _jsx("code", { children: selectedJob.agent_id })] })), _jsxs("div", { className: "detail-row", children: [_jsx("strong", { children: "Created:" }), _jsx("span", { children: new Date(selectedJob.created_at).toLocaleString() })] }), selectedJob.completed_at && (_jsxs("div", { className: "detail-row", children: [_jsx("strong", { children: "Completed:" }), _jsx("span", { children: new Date(selectedJob.completed_at).toLocaleString() })] })), _jsxs("div", { className: "detail-row", children: [_jsx("strong", { children: "Duration:" }), _jsx("span", { children: formatDuration(selectedJob.duration_ms) })] }), _jsxs("div", { className: "detail-row", children: [_jsx("strong", { children: "Exit Code:" }), _jsx("code", { children: selectedJob.exit_code ?? 'N/A' })] }), _jsxs("div", { className: "detail-row", children: [_jsx("strong", { children: "Cost:" }), _jsxs("span", { children: ["$", selectedJob.cost_usd.toFixed(4)] })] })] }), selectedJob.metrics && Object.keys(selectedJob.metrics).length > 0 && (_jsxs("div", { className: "detail-section", children: [_jsx("h4", { children: "Metrics" }), Object.entries(selectedJob.metrics).map(([key, value]) => (_jsxs("div", { className: "detail-row", children: [_jsxs("strong", { children: [key, ":"] }), _jsx("span", { children: JSON.stringify(value) })] }, key)))] })), selectedJob.stdout && (_jsxs("div", { className: "detail-section", children: [_jsx("h4", { children: "Output" }), _jsx("div", { className: "log-panel", children: selectedJob.stdout.split('\n').map((line, idx) => (_jsx("div", { className: "log-line", children: line }, idx))) })] })), selectedJob.stderr && (_jsxs("div", { className: "detail-section", children: [_jsx("h4", { children: "Error" }), _jsx("div", { className: "log-panel error", children: selectedJob.stderr.split('\n').map((line, idx) => (_jsx("div", { className: "log-line", children: line }, idx))) })] }))] }))] }))] }));
}
