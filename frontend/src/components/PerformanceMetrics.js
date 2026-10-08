import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import { useEffect, useState } from 'react';
import './PerformanceMetrics.css';
export default function PerformanceMetrics({ agentId }) {
    const [metrics, setMetrics] = useState(null);
    const [loading, setLoading] = useState(true);
    useEffect(() => {
        fetchMetrics();
        const interval = setInterval(fetchMetrics, 10000); // Refresh every 10s
        return () => clearInterval(interval);
    }, [agentId]);
    const fetchMetrics = async () => {
        try {
            const response = await fetch(`/api/agents/${agentId}/metrics`);
            const data = await response.json();
            setMetrics(data);
        }
        catch (error) {
            console.error('Error fetching metrics:', error);
        }
        finally {
            setLoading(false);
        }
    };
    if (loading || !metrics) {
        return _jsx("div", { className: "metrics-loading", children: "Loading metrics..." });
    }
    const successPercent = Math.round(metrics.success_rate * 100);
    const failurePercent = 100 - successPercent;
    return (_jsxs("div", { className: "performance-metrics", children: [_jsx("h3", { children: "Performance Metrics" }), _jsxs("div", { className: "metrics-grid", children: [_jsxs("div", { className: "metric-card", children: [_jsx("div", { className: "metric-label", children: "Total Runs" }), _jsx("div", { className: "metric-value", children: metrics.total_runs })] }), _jsxs("div", { className: "metric-card", children: [_jsx("div", { className: "metric-label", children: "Success Rate" }), _jsxs("div", { className: "metric-value", children: [successPercent, "%"] }), _jsxs("div", { className: "metric-bar", children: [_jsx("div", { className: "metric-bar-fill success", style: { width: `${successPercent}%` } }), _jsx("div", { className: "metric-bar-fill error", style: { width: `${failurePercent}%` } })] }), _jsxs("div", { className: "metric-detail", children: [metrics.successful_runs, " success, ", metrics.failed_runs, " failed"] })] }), _jsxs("div", { className: "metric-card", children: [_jsx("div", { className: "metric-label", children: "Avg Duration" }), _jsxs("div", { className: "metric-value", children: [(metrics.avg_duration_ms / 1000).toFixed(2), "s"] })] }), _jsxs("div", { className: "metric-card", children: [_jsx("div", { className: "metric-label", children: "Total Cost" }), _jsxs("div", { className: "metric-value", children: ["$", metrics.total_cost_usd.toFixed(4)] })] })] })] }));
}
