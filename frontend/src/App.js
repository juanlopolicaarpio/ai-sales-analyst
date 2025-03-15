import React from 'react';
import { BrowserRouter as Router, Routes, Route, Link } from 'react-router-dom';
import { FaChartLine, FaShoppingCart, FaTachometerAlt, FaCog, FaSignOutAlt } from 'react-icons/fa';
import './App.css';

// Import pages
import Dashboard from './pages/Dashboard';
import Orders from './pages/Orders';
import Products from './pages/Products';
import Analytics from './pages/Analytics';
import Settings from './pages/Settings';

function App() {
  return (
    <Router>
      <div className="app">
        <aside className="sidebar">
          <div className="sidebar-header">
            <h1>AI Sales Analyst</h1>
          </div>
          <nav className="sidebar-nav">
            <ul>
              <li>
                <Link to="/" className="nav-link">
                  <FaTachometerAlt className="nav-icon" />
                  <span>Dashboard</span>
                </Link>
              </li>
              <li>
                <Link to="/orders" className="nav-link">
                  <FaShoppingCart className="nav-icon" />
                  <span>Orders</span>
                </Link>
              </li>
              <li>
                <Link to="/products" className="nav-link">
                  <FaShoppingCart className="nav-icon" />
                  <span>Products</span>
                </Link>
              </li>
              <li>
                <Link to="/analytics" className="nav-link">
                  <FaChartLine className="nav-icon" />
                  <span>Analytics</span>
                </Link>
              </li>
              <li>
                <Link to="/settings" className="nav-link">
                  <FaCog className="nav-icon" />
                  <span>Settings</span>
                </Link>
              </li>
            </ul>
          </nav>
          <div className="sidebar-footer">
            <Link to="/logout" className="nav-link">
              <FaSignOutAlt className="nav-icon" />
              <span>Logout</span>
            </Link>
          </div>
        </aside>
        
        <main className="main-content">
          <div className="content-wrapper">
            <Routes>
              <Route path="/" element={<Dashboard />} />
              <Route path="/orders" element={<Orders />} />
              <Route path="/products" element={<Products />} />
              <Route path="/analytics" element={<Analytics />} />
              <Route path="/settings" element={<Settings />} />
            </Routes>
          </div>
        </main>
      </div>
    </Router>
  );
}

export default App;