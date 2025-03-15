import React, { useState, useEffect } from 'react';
import { Line } from 'react-chartjs-2';
import { FaDollarSign, FaShoppingCart, FaUsers, FaArrowUp, FaArrowDown, FaExclamationTriangle, FaChartLine, FaLightbulb } from 'react-icons/fa';
import { Chart, CategoryScale, LinearScale, PointElement, LineElement, Title, Tooltip, Legend } from 'chart.js';
import axios from 'axios';

// Register Chart.js components
Chart.register(CategoryScale, LinearScale, PointElement, LineElement, Title, Tooltip, Legend);

const Dashboard = () => {
  const [timeRange, setTimeRange] = useState('last_7_days');
  const [dashboardData, setDashboardData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  // Mock data - replace with API calls in production
  useEffect(() => {
    // Simulate API call
    const fetchDashboardData = async () => {
      setLoading(true);
      try {
        // In production, use a real API call:
        // const response = await axios.get(`/api/dashboard?timeRange=${timeRange}`);
        // const data = response.data;
        
        // Mock data for development
        const mockData = {
          stats: {
            revenue: {
              value: 25890.75,
              change: 0.12
            },
            orders: {
              value: 128,
              change: 0.05
            },
            customers: {
              value: 85,
              change: -0.03
            },
            aov: {
              value: 202.27,
              change: 0.08
            }
          },
          salesChart: {
            labels: ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'],
            datasets: [
              {
                label: 'Revenue',
                data: [3200, 2800, 3500, 4200, 3800, 4500, 3900],
                borderColor: '#27ae60',
                backgroundColor: 'rgba(39, 174, 96, 0.1)',
                tension: 0.4
              },
              {
                label: 'Orders',
                data: [20, 18, 22, 25, 23, 28, 24],
                borderColor: '#e74c3c',
                backgroundColor: 'rgba(231, 76, 60, 0.1)',
                tension: 0.4
              }
            ]
          },
          topProducts: [
            { name: 'Premium T-Shirt', revenue: 3500, quantity: 50 },
            { name: 'Wireless Headphones', revenue: 2800, quantity: 20 },
            { name: 'Phone Case', revenue: 1950, quantity: 65 },
            { name: 'Fitness Tracker', revenue: 1520, quantity: 10 },
            { name: 'Sunglasses', revenue: 1200, quantity: 15 }
          ],
          insights: [
            {
              id: 1,
              type: 'anomaly',
              title: 'Unusual drop in orders',
              text: 'Orders decreased by 25% on Wednesday compared to average.',
              severity: 'high'
            },
            {
              id: 2,
              type: 'trend',
              title: 'Rising AOV',
              text: 'Average order value has increased by 8% this week.',
              severity: 'medium'
            },
            {
              id: 3,
              type: 'insight',
              title: 'Top product change',
              text: 'Premium T-Shirt has overtaken Wireless Headphones as the top-selling product.',
              severity: 'low'
            }
          ]
        };
        
        setDashboardData(mockData);
        setLoading(false);
      } catch (err) {
        setError('Failed to load dashboard data');
        setLoading(false);
        console.error(err);
      }
    };

    fetchDashboardData();
  }, [timeRange]);

  const handleTimeRangeChange = (e) => {
    setTimeRange(e.target.value);
  };

  // Chart options
  const chartOptions = {
    responsive: true,
    maintainAspectRatio: false,
    scales: {
      y: {
        beginAtZero: true,
        grid: {
          color: 'rgba(0, 0, 0, 0.05)'
        }
      },
      x: {
        grid: {
          display: false
        }
      }
    },
    plugins: {
      legend: {
        position: 'top',
      },
      title: {
        display: false
      }
    }
  };

  // Loading state
  if (loading) {
    return <div className="loading">Loading dashboard data...</div>;
  }

  // Error state
  if (error) {
    return <div className="error">{error}</div>;
  }

  return (
    <div className="dashboard">
      <div className="dashboard-header">
        <h2 className="dashboard-title">Dashboard</h2>
        <div className="date-filter">
          <select value={timeRange} onChange={handleTimeRangeChange}>
            <option value="today">Today</option>
            <option value="yesterday">Yesterday</option>
            <option value="last_7_days">Last 7 Days</option>
            <option value="last_30_days">Last 30 Days</option>
            <option value="this_month">This Month</option>
            <option value="last_month">Last Month</option>
          </select>
        </div>
      </div>

      {/* Stats Cards */}
      <div className="stats-container">
        <div className="stat-card">
          <div className="stat-card-header">
            <span className="stat-card-title">Revenue</span>
            <div className="stat-card-icon icon-revenue">
              <FaDollarSign />
            </div>
          </div>
          <div className="stat-card-value">${dashboardData.stats.revenue.value.toLocaleString()}</div>
          <div className={`stat-card-change ${dashboardData.stats.revenue.change >= 0 ? 'change-positive' : 'change-negative'}`}>
            {dashboardData.stats.revenue.change >= 0 ? <FaArrowUp /> : <FaArrowDown />}
            <span>{Math.abs(dashboardData.stats.revenue.change * 100).toFixed(1)}% vs previous</span>
          </div>
        </div>

        <div className="stat-card">
          <div className="stat-card-header">
            <span className="stat-card-title">Orders</span>
            <div className="stat-card-icon icon-orders">
              <FaShoppingCart />
            </div>
          </div>
          <div className="stat-card-value">{dashboardData.stats.orders.value}</div>
          <div className={`stat-card-change ${dashboardData.stats.orders.change >= 0 ? 'change-positive' : 'change-negative'}`}>
            {dashboardData.stats.orders.change >= 0 ? <FaArrowUp /> : <FaArrowDown />}
            <span>{Math.abs(dashboardData.stats.orders.change * 100).toFixed(1)}% vs previous</span>
          </div>
        </div>

        <div className="stat-card">
          <div className="stat-card-header">
            <span className="stat-card-title">Customers</span>
            <div className="stat-card-icon icon-customers">
              <FaUsers />
            </div>
          </div>
          <div className="stat-card-value">{dashboardData.stats.customers.value}</div>
          <div className={`stat-card-change ${dashboardData.stats.customers.change >= 0 ? 'change-positive' : 'change-negative'}`}>
            {dashboardData.stats.customers.change >= 0 ? <FaArrowUp /> : <FaArrowDown />}
            <span>{Math.abs(dashboardData.stats.customers.change * 100).toFixed(1)}% vs previous</span>
          </div>
        </div>

        <div className="stat-card">
          <div className="stat-card-header">
            <span className="stat-card-title">Avg. Order Value</span>
            <div className="stat-card-icon icon-aov">
              <FaDollarSign />
            </div>
          </div>
          <div className="stat-card-value">${dashboardData.stats.aov.value.toFixed(2)}</div>
          <div className={`stat-card-change ${dashboardData.stats.aov.change >= 0 ? 'change-positive' : 'change-negative'}`}>
            {dashboardData.stats.aov.change >= 0 ? <FaArrowUp /> : <FaArrowDown />}
            <span>{Math.abs(dashboardData.stats.aov.change * 100).toFixed(1)}% vs previous</span>
          </div>
        </div>
      </div>

      {/* Charts and Insights */}
      <div className="charts-container">
        <div className="chart-card">
          <div className="chart-card-header">
            <h3 className="chart-card-title">Sales Trend</h3>
          </div>
          <div className="chart-wrapper">
            <Line data={dashboardData.salesChart} options={chartOptions} />
          </div>
        </div>

        <div className="insights-card">
          <div className="insights-card-header">
            <h3 className="insights-card-title">AI Insights</h3>
          </div>
          <ul className="insights-list">
            {dashboardData.insights.map(insight => (
              <li key={insight.id} className="insight-item">
                <div className="insight-title">
                  {insight.type === 'anomaly' && <FaExclamationTriangle className="insight-icon" style={{ color: '#e74c3c' }} />}
                  {insight.type === 'trend' && <FaChartLine className="insight-icon" style={{ color: '#3498db' }} />}
                  {insight.type === 'insight' && <FaLightbulb className="insight-icon" style={{ color: '#f39c12' }} />}
                  {insight.title}
                </div>
                <div className="insight-text">
                  {insight.text}
                </div>
              </li>
            ))}
          </ul>
        </div>
      </div>

      {/* Top Products Table */}
      <div className="table-container">
        <div className="table-header">
          <h3 className="table-title">Top Products</h3>
        </div>
        <table className="data-table">
          <thead>
            <tr>
              <th>Product</th>
              <th>Revenue</th>
              <th>Quantity</th>
              <th>Avg. Price</th>
            </tr>
          </thead>
          <tbody>
            {dashboardData.topProducts.map((product, index) => (
              <tr key={index}>
                <td>{product.name}</td>
                <td>${product.revenue.toLocaleString()}</td>
                <td>{product.quantity}</td>
                <td>${(product.revenue / product.quantity).toFixed(2)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
};

export default Dashboard;