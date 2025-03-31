import React from 'react';
import { Link } from 'react-router-dom';
import Layout from '../components/Layout';
import { FiAlertCircle } from 'react-icons/fi';

const NotFoundPage = () => {
  return (
    <Layout>
      <div className="flex flex-col items-center justify-center py-12">
        <FiAlertCircle className="h-24 w-24 text-primary-500 mb-6" />
        <h1 className="text-4xl font-bold text-gray-900 mb-4">404</h1>
        <h2 className="text-2xl font-semibold text-gray-800 mb-2">Page Not Found</h2>
        <p className="text-gray-600 text-center max-w-md mb-8">
          The page you are looking for doesn't exist or has been moved.
        </p>
        <Link to="/" className="btn btn-primary">
          Return to Home
        </Link>
      </div>
    </Layout>
  );
};

export default NotFoundPage;