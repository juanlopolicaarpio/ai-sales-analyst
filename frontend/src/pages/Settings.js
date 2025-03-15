import React from 'react';

const Settings = () => {
  return (
    <div className="page-container">
      <h2 className="page-title">Settings</h2>
      <p>Configure your store connections, notification preferences, and user profile.</p>
      
      <div className="settings-section">
        <h3>Store Connection</h3>
        <div className="form-group">
          <label className="form-label">Platform</label>
          <select className="form-select">
            <option value="shopify">Shopify</option>
            <option value="woocommerce">WooCommerce</option>
            <option value="magento">Magento</option>
          </select>
        </div>
        
        <div className="form-group">
          <label className="form-label">Store URL</label>
          <input type="text" className="form-input" placeholder="your-store.myshopify.com" />
        </div>
        
        <div className="form-group">
          <label className="form-label">API Key</label>
          <input type="text" className="form-input" placeholder="API Key" />
        </div>
        
        <div className="form-group">
          <label className="form-label">API Secret</label>
          <input type="password" className="form-input" placeholder="API Secret" />
        </div>
        
        <button className="btn btn-primary">Save Store Settings</button>
      </div>
      
      <div className="settings-section">
        <h3>Notification Preferences</h3>
        
        <div className="form-group">
          <label className="form-label">Preferred Channel</label>
          <select className="form-select">
            <option value="slack">Slack</option>
            <option value="whatsapp">WhatsApp</option>
            <option value="email">Email</option>
          </select>
        </div>
        
        <div className="form-group">
          <label className="form-label">Slack User ID (if using Slack)</label>
          <input type="text" className="form-input" placeholder="U12345678" />
        </div>
        
        <div className="form-group">
          <label className="form-label">WhatsApp Number (if using WhatsApp)</label>
          <input type="text" className="form-input" placeholder="+1234567890" />
        </div>
        
        <div className="form-group">
          <label className="form-label">Email Address (if using Email)</label>
          <input type="email" className="form-input" placeholder="you@example.com" />
        </div>
        
        <h4>Alert Types</h4>
        <div className="form-group">
          <div className="checkbox-group">
            <input type="checkbox" id="sales-alerts" defaultChecked />
            <label htmlFor="sales-alerts">Sales Alerts</label>
          </div>
          
          <div className="checkbox-group">
            <input type="checkbox" id="anomaly-detection" defaultChecked />
            <label htmlFor="anomaly-detection">Anomaly Detection</label>
          </div>
          
          <div className="checkbox-group">
            <input type="checkbox" id="daily-summary" defaultChecked />
            <label htmlFor="daily-summary">Daily Summary</label>
          </div>
        </div>
        
        <button className="btn btn-primary">Save Notification Settings</button>
      </div>
    </div>
  );
};

export default Settings;
