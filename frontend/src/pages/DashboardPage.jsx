import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { storesAPI } from '../utils/api';
import Layout from '../components/Layout';
import { FiShoppingCart, FiTrendingUp, FiAlertCircle, FiPackage } from 'react-icons/fi';

const DashboardPage = () => {
  const { user } = useAuth();
  const [stores, setStores] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    const fetchStores = async () => {
      try {
        const storesData = await storesAPI.getStores();
        setStores(storesData);
        setLoading(false);
      } catch (err) {
        console.error('Failed to fetch stores:', err);
        setError('Failed to load store data. Please try again later.');
        setLoading(false);
      }
    };

    fetchStores();
  }, []);

  const StatCard = ({ title, value, icon, color }) => (
    <div className="bg-white rounded-lg shadow p-5">
      <div className="flex items-center">
        <div className={`rounded-full p-3 ${color}`}>
          {icon}
        </div>
        <div className="ml-4">
          <h3 className="text-gray-500 text-sm font-medium">{title}</h3>
          <p className="text-2xl font-semibold">{value}</p>
        </div>
      </div>
    </div>
  );

  if (loading) {
    return (
      <Layout>
        <div className="flex justify-center items-center h-64">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary-600"></div>
        </div>
      </Layout>
    );
  }

  if (error) {
    return (
      <Layout>
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
        <div className="flex justify-center mt-4">
          <button
            onClick={() => window.location.reload()}
            className="btn btn-primary"
          >
            Try Again
          </button>
        </div>
      </Layout>
    );
  }

  return (
    <Layout>
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-gray-900">Welcome, {user?.full_name || 'User'}!</h1>
        <p className="text-gray-600 mt-1">Here's an overview of your store analytics</p>
      </div>

      {stores.length === 0 ? (
        <div className="bg-white rounded-lg shadow p-6 text-center">
          <FiShoppingCart className="h-12 w-12 text-primary-500 mx-auto mb-4" />
          <h2 className="text-xl font-semibold mb-2">No stores connected yet</h2>
          <p className="text-gray-600 mb-4">
            Connect your e-commerce store to start receiving AI-powered sales analytics.
          </p>
          <Link to="/connect-store" className="btn btn-primary">
            Connect a Store
          </Link>
        </div>
      ) : (
        <>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
            <StatCard
              title="Total Revenue"
              value="$12,845.00"
              icon={<FiTrendingUp className="h-6 w-6 text-white" />}
              color="bg-green-500"
            />
            <StatCard
              title="Orders This Month"
              value="156"
              icon={<FiPackage className="h-6 w-6 text-white" />}
              color="bg-blue-500"
            />
            <StatCard
              title="Average Order Value"
              value="$82.34"
              icon={<FiShoppingCart className="h-6 w-6 text-white" />}
              color="bg-purple-500"
            />
            <StatCard
              title="Connected Stores"
              value={stores.length.toString()}
              icon={<FiShoppingCart className="h-6 w-6 text-white" />}
              color="bg-primary-500"
            />
          </div>

          <div className="bg-white rounded-lg shadow overflow-hidden">
            <div className="px-6 py-4 border-b border-gray-200">
              <h2 className="font-semibold text-lg">Your Connected Stores</h2>
            </div>
            <div className="p-6">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {stores.map((store) => (
                  <div
                    key={store.id}
                    className="border border-gray-200 rounded-lg p-4 hover:shadow-md transition-shadow"
                  >
                    <h3 className="font-medium text-lg">{store.name}</h3>
                    <p className="text-gray-600 text-sm mt-1">{store.platform}</p>
                    <div className="flex mt-3">
                      <span className={`px-2 py-1 text-xs rounded-full ${
                        store.status === 'active' 
                          ? 'bg-green-100 text-green-800' 
                          : 'bg-yellow-100 text-yellow-800'
                      }`}>
                        {store.status}
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </>
      )}
    </Layout>
  );
};

export default DashboardPage;