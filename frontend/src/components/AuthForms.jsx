import React, { useState } from 'react';

export const LoginForm = ({ onSubmit, isLoading }) => {
  const [formData, setFormData] = useState({ email: '', password: '' });
  const handleChange = (e) => {
    const { name, value } = e.target;
    setFormData(prev => ({ ...prev, [name]: value }));
  };
  const handleSubmit = (e) => {
    e.preventDefault();
    onSubmit(formData.email, formData.password);
  };
  return (
    <form onSubmit={handleSubmit} className="space-y-6">
      <div>
        <label htmlFor="email" className="form-label">Email address</label>
        <input id="email" name="email" type="email" autoComplete="email" required className="form-input" value={formData.email} onChange={handleChange} />
      </div>
      <div>
        <label htmlFor="password" className="form-label">Password</label>
        <input id="password" name="password" type="password" autoComplete="current-password" required className="form-input" value={formData.password} onChange={handleChange} />
      </div>
      <div>
        <button type="submit" className="w-full btn btn-primary" disabled={isLoading}>
          {isLoading ? 'Signing in...' : 'Sign in'}
        </button>
      </div>
    </form>
  );
};

export const RegisterForm = ({ onSubmit, isLoading }) => {
  const [formData, setFormData] = useState({ email: '', password: '', full_name: '', slack_user_id: '', whatsapp_number: '' });
  const handleChange = (e) => {
    const { name, value } = e.target;
    setFormData(prev => ({ ...prev, [name]: value }));
  };
  const handleSubmit = (e) => {
    e.preventDefault();
    onSubmit(formData);
  };
  return (
    <form onSubmit={handleSubmit} className="space-y-6">
      <div>
        <label htmlFor="full_name" className="form-label">Full Name</label>
        <input id="full_name" name="full_name" type="text" autoComplete="name" required className="form-input" value={formData.full_name} onChange={handleChange} />
      </div>
      <div>
        <label htmlFor="email" className="form-label">Email address</label>
        <input id="email" name="email" type="email" autoComplete="email" required className="form-input" value={formData.email} onChange={handleChange} />
      </div>
      <div>
        <label htmlFor="password" className="form-label">Password</label>
        <input id="password" name="password" type="password" autoComplete="new-password" required className="form-input" value={formData.password} onChange={handleChange} />
      </div>
      <div className="border-t border-gray-200 pt-4 mt-4">
        <p className="text-sm text-gray-500 mb-4">Optional Contact Information</p>
        <div className="mb-4">
          <label htmlFor="slack_user_id" className="form-label">Slack User ID</label>
          <input id="slack_user_id" name="slack_user_id" type="text" className="form-input" value={formData.slack_user_id} onChange={handleChange} placeholder="U01ABC123DEF" />
          <p className="mt-1 text-xs text-gray-500">For receiving notifications via Slack</p>
        </div>
        <div>
          <label htmlFor="whatsapp_number" className="form-label">WhatsApp Number</label>
          <input id="whatsapp_number" name="whatsapp_number" type="text" className="form-input" value={formData.whatsapp_number} onChange={handleChange} placeholder="+1234567890" />
          <p className="mt-1 text-xs text-gray-500">Include country code (e.g., +1 for US)</p>
        </div>
      </div>
      <div>
        <button type="submit" className="w-full btn btn-primary" disabled={isLoading}>
          {isLoading ? 'Creating account...' : 'Create account'}
        </button>
      </div>
    </form>
  );
};
