import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { storesAPI } from '../utils/api';
import Layout from '../components/Layout';
import toast from 'react-hot-toast';
import { FiShoppingBag, FiPlus, FiCheck, FiAlertCircle } from 'react-icons/fi';

const ConnectStorePage = () => {
  const [stores, setStores] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [showForm, setShowForm] = useState(false);
  const [formData, setFormData] = useState({
    name: '',
    platform: 'shopify',
    api_key: '',
    api_secret: '',
    store_url: ''
  });
  const [formLoading, setFormLoading] = useState(false);
  const navigate = useNavigate();

  useEffect(() => {
    fetchStores();
  }, []);

  const fetchStores = async () => {
    try {
      setLoading(true);
      const storesData = await storesAPI.getStores();
      setStores(storesData);
      setError(null);
    } catch (err) {
      console.error('Failed to fetch stores:', err);
      setError('Failed to load store data. Please try again later.');
    } finally {
      setLoading(false);
    }
  };

  const handleInputChange = (e) => {
    const { name, value } = e.target;
    setFormData((prev) => ({ ...prev, [name]: value }));
  };

  const resetForm = () => {
    setFormData({
      name: '',
      platform: 'shopify',
      api_key: '',
      api_secret: '',
      store_url: ''
    });
    setShowForm(false);
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    
    try {
      setFormLoading(true);
      await storesAPI.createStore(formData);
      toast.success('Store connected successfully!');
      resetForm();
      fetchStores();
    } catch (err) {
      console.error('Failed to connect store:', err);
      toast.error(err.response?.data?.detail || 'Failed to connect store. Please check your details.');
    } finally {
      setFormLoading(false);
    }
  };

  const testConnection = async (storeId) => {
    try {
      const result = await storesAPI.testConnection(storeId);
      toast.success('Connection successful!');
    } catch (err) {
      console.error('Connection test failed:', err);
      toast.error(err.response?.data?.detail || 'Connection test failed. Please check your store settings.');
    }
  };

  if (loading) {
    return (
      <Layout>
        <div className="flex justify-center items-center h-64">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary-600"></div>
        </div>
      </Layout>
    );
  }

  return (
    <Layout>
      <div className="mb-6 flex justify-between items-center">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Connect Your Store</h1>
          <p className="text-gray-600 mt-1">Integrate your e-commerce platform for AI-powered analytics</p>
        </div>
        <button
          onClick={() => setShowForm(!showForm)}
          className="btn btn-primary flex items-center"
        >
          <FiPlus className="mr-2" />
          {showForm ? 'Cancel' : 'Add New Store'}
        </button>
      </div>

      {error && (
        <div className="bg-red-50 border-l-4 border-red-400 p-4 mb-6">
          <div className="flex">
            <div className="flex-shrink-0">
              <FiAlertCircle className="h-5 w-5 text-red-400" />
            </div>
            <div className="ml-3">
              <p className="text-sm text-red-700">{error}</p>
            </div>
          </div>
        </div>
      )}

      {showForm && (
        <div className="bg-white rounded-lg shadow-md p-6 mb-8">
          <h2 className="text-lg font-semibold mb-4">Connect a New Store</h2>
          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label htmlFor="name" className="form-label">Store Name</label>
              <input
                id="name"
                name="name"
                type="text"
                required
                className="form-input"
                value={formData.name}
                onChange={handleInputChange}
                placeholder="My Awesome Store"
              />
            </div>
            
            <div>
              <label htmlFor="platform" className="form-label">Platform</label>
              <select
                id="platform"
                name="platform"
                className="form-input"
                value={formData.platform}
                onChange={handleInputChange}
              >
                <option value="shopify">Shopify</option>
                <option value="woocommerce">WooCommerce</option>
                <option value="magento">Magento</option>
                <option value="bigcommerce">BigCommerce</option>
              </select>
            </div>
            
            <div>
              <label htmlFor="store_url" className="form-label">Store URL</label>
              <input
                id="store_url"
                name="store_url"
                type="url"
                required
                className="form-input"
                value={formData.store_url}
                onChange={handleInputChange}
                placeholder="https://your-store.myshopify.com"
              />
            </div>
            
            <div>
              <label htmlFor="api_key" className="form-label">API Key</label>
              <input
                id="api_key"
                name="api_key"
                type="text"
                required
                className="form-input"
                value={formData.api_key}
                onChange={handleInputChange}
                placeholder="your-api-key"
              />
            </div>
            
            <div>
              <label htmlFor="api_secret" className="form-label">API Secret</label>
              <input
                id="api_secret"
                name="api_secret"
                type="password"
                required
                className="form-input"
                value={formData.api_secret}
                onChange={handleInputChange}
                placeholder="••••••••"
              />
            </div>
            
            <div className="flex justify-end pt-4">
              <button
                type="button"
                onClick={resetForm}
                className="btn btn-secondary mr-3"
                disabled={formLoading}
              >
                Cancel
              </button>
              <button
                type="submit"
                className="btn btn-primary"
                disabled={formLoading}
              >
                {formLoading ? 'Connecting...' : 'Connect Store'}
              </button>
            </div>
          </form>
        </div>
      )}

      <div className="bg-white rounded-lg shadow-md overflow-hidden">
        <div className="px-6 py-4 border-b border-gray-200">
          <h2 className="font-semibold text-lg">Your Connected Stores</h2>
        </div>
        <div className="p-6">
          {stores.length === 0 ? (
            <div className="text-center py-8">
              <FiShoppingBag className="h-12 w-12 text-gray-400 mx-auto mb-4" />
              <h3 className="text-lg font-medium text-gray-900 mb-1">No stores connected yet</h3>
              <p className="text-gray-500 mb-4">Get started by connecting your first store</p>
              <button
                onClick={() => setShowForm(true)}
                className="btn btn-primary"
              >
                Connect a Store
              </button>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="min-w-full divide-y divide-gray-200">
                <thead className="bg-gray-50">
                  <tr>
                    <th scope="col" className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Store Name
                    </th>
                    <th scope="col" className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Platform
                    </th>
                    <th scope="col" className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Status
                    </th>
                    <th scope="col" className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      URL
                    </th>
                    <th scope="col" className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Actions
                    </th>
                  </tr>
                </thead>
                <tbody className="bg-white divide-y divide-gray-200">
                  {stores.map((store) => (
                    <tr key={store.id}>
                      <td className="px-6 py-4 whitespace-nowrap">
                        <div className="font-medium text-gray-900">{store.name}</div>
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap">
                        <div className="text-sm text-gray-500 capitalize">{store.platform}</div>
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap">
                        <span className={`px-2 py-1 text-xs rounded-full ${
                          store.status === 'active' 
                            ? 'bg-green-100 text-green-800' 
                            : 'bg-yellow-100 text-yellow-800'
                        }`}>
                          {store.status}
                        </span>
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap">
                        <div className="text-sm text-gray-500">{store.store_url}</div>
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-right text-sm font-medium">
                        <button
                          onClick={() => testConnection(store.id)}
                          className="text-primary-600 hover:text-primary-900 mr-4"
                        >
                          Test Connection
                        </button>
                        <button
                          onClick={() => navigate(`/settings?store=${store.id}`)}
                          className="text-gray-600 hover:text-gray-900"
                        >
                          Edit
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>
    </Layout>
  );
};

export default ConnectStorePage;