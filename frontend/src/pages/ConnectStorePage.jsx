import React, { useState, useEffect } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import api, { storesAPI } from '../utils/api';import Layout from '../components/Layout';
import toast from 'react-hot-toast';
import { FiShoppingBag, FiPlus, FiCheck, FiAlertCircle, FiX } from 'react-icons/fi';

const ConnectStorePage = () => {
  const [stores, setStores] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [showForm, setShowForm] = useState(false);
  const [showShopifyModal, setShowShopifyModal] = useState(false);
  const [shopUrlInput, setShopUrlInput] = useState('');
  const [formData, setFormData] = useState({
    name: '',
    platform: 'shopify',
    api_key: '',
    api_secret: '',
    store_url: ''
  });
  const [formLoading, setFormLoading] = useState(false);
  const [shopifyConnecting, setShopifyConnecting] = useState(false);
  const navigate = useNavigate();
  const location = useLocation();

  useEffect(() => {
    fetchStores();

    const queryParams = new URLSearchParams(location.search);
    const shopParam = queryParams.get('shop');
    const tokenParam = queryParams.get('token');
    const storeIdParam = queryParams.get('store_id');

    if (shopParam && tokenParam && storeIdParam) {
      toast.success(`Successfully connected ${shopParam}`);
      fetchStores();
      navigate('/connect-store', { replace: true });
    }
  }, [location]);

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
      await storesAPI.testConnection(storeId);
      toast.success('Connection successful!');
    } catch (err) {
      console.error('Connection test failed:', err);
      toast.error(err.response?.data?.detail || 'Connection test failed. Please check your store settings.');
    }
  };

// In ConnectStorePage.jsx, update the handleShopifyRedirect function:

const handleShopifyRedirect = () => {
    // Add at the top of your handleShopifyRedirect function
console.log("Token in localStorage:", localStorage.getItem('token'));
console.log("API headers:", api.defaults.headers);


    let cleanShopUrl = shopUrlInput.trim().replace(/^https?:\/\//, '');
    if (!cleanShopUrl.includes('.')) {
      cleanShopUrl = `${cleanShopUrl}.myshopify.com`;
    }
    
    setShopifyConnecting(true);
    
    // Use the API client which automatically includes the token
    api.get(`/shopify/auth?shop=${encodeURIComponent(cleanShopUrl)}`, {
      headers: {
        'Accept': 'application/json'
      }
    })
      .then(response => {
        console.log("Shopify auth response:", response.data);
        if (response.data && response.data.redirect_url) {
          window.location.href = response.data.redirect_url;
        } else {
          throw new Error("No redirect URL received");
        }
      })
      .catch(error => {
        setShopifyConnecting(false);
        console.error("Error connecting to Shopify:", error);
        toast.error("Failed to connect to Shopify. Please try again.");
      });
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
      {/* Shopify URL Modal */}
      {showShopifyModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm">
          <div className="bg-white rounded-2xl shadow-lg w-full max-w-md p-6 relative">
            <button
              className="absolute top-3 right-3 text-gray-400 hover:text-gray-600"
              onClick={() => setShowShopifyModal(false)}
            >
              <FiX className="w-5 h-5" />
            </button>
            <h2 className="text-xl font-semibold text-gray-800 mb-4">Enter Your Shopify Store URL</h2>
            <input
              type="text"
              className="form-input w-full"
              placeholder="your-store.myshopify.com"
              value={shopUrlInput}
              onChange={(e) => setShopUrlInput(e.target.value)}
            />
            <div className="mt-4 flex justify-end space-x-2">
              <button
                className="btn btn-secondary"
                onClick={() => setShowShopifyModal(false)}
              >
                Cancel
              </button>
              <button
                className="btn btn-primary"
                onClick={handleShopifyRedirect}
                disabled={!shopUrlInput}
              >
                Connect
              </button>
            </div>
          </div>
        </div>
      )}

      <div className="mb-6 flex justify-between items-center">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Connect Your Store</h1>
          <p className="text-gray-600 mt-1">Integrate your e-commerce platform for AI-powered analytics</p>
        </div>
        <div className="flex space-x-3">
          <button
            onClick={() => setShowShopifyModal(true)}
            className="btn btn-primary flex items-center"
            disabled={shopifyConnecting}
          >
            <FiShoppingBag className="mr-2" />
            {shopifyConnecting ? 'Connecting...' : 'Connect with Shopify'}
          </button>
          <button
            onClick={() => setShowForm(!showForm)}
            className="btn btn-secondary flex items-center"
          >
            <FiPlus className="mr-2" />
            {showForm ? 'Cancel' : 'Add Manually'}
          </button>
        </div>
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

      <div className="bg-blue-50 border-l-4 border-blue-400 p-4 mb-6">
        <div className="flex">
          <div className="flex-shrink-0">
            <FiShoppingBag className="h-5 w-5 text-blue-400" />
          </div>
          <div className="ml-3">
            <p className="text-sm text-blue-700">
              <strong>Recommended:</strong> Use the "Connect with Shopify" button for a secure, OAuth-based connection.
              This doesn't require you to manually enter API credentials.
            </p>
          </div>
        </div>
      </div>

      {showForm && (
        <div className="bg-white rounded-lg shadow-md p-6 mb-8">
          <h2 className="text-lg font-semibold mb-4">Connect a Store Manually</h2>
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
              <div className="flex justify-center space-x-4">
                <button
                  onClick={() => setShowShopifyModal(true)}
                  className="btn btn-primary"
                  disabled={shopifyConnecting}
                >
                  <FiShoppingBag className="mr-2 inline" />
                  Connect with Shopify
                </button>
                <button
                  onClick={() => setShowForm(true)}
                  className="btn btn-secondary"
                >
                  Connect Manually
                </button>
              </div>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="min-w-full divide-y divide-gray-200">
                <thead className="bg-gray-50">
                  <tr>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Store Name</th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Platform</th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Status</th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">URL</th>
                    <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">Actions</th>
                  </tr>
                </thead>
                <tbody className="bg-white divide-y divide-gray-200">
                  {stores.map((store) => (
                    <tr key={store.id}>
                      <td className="px-6 py-4 whitespace-nowrap">
                        <div className="font-medium text-gray-900">{store.name}</div>
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap capitalize text-sm text-gray-500">
                        {store.platform}
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
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">{store.store_url}</td>
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
