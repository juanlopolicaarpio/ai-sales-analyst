import React, { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { RegisterForm } from '../components/AuthForms';
import Layout from '../components/Layout';

const RegisterPage = () => {
  const [isLoading, setIsLoading] = useState(false);
  const { register } = useAuth();
  const navigate = useNavigate();

  const handleRegister = async (userData) => {
    setIsLoading(true);
    const success = await register(userData);
    setIsLoading(false);
    if (success) {
      navigate('/dashboard');
    }
  };

  return (
    <Layout>
      <div className="max-w-md mx-auto">
        <div className="text-center mb-8">
          <h1 className="text-3xl font-bold text-gray-900">Create your account</h1>
          <p className="mt-2 text-sm text-gray-600">
            Already have an account?{' '}
            <Link to="/login" className="font-medium text-primary-600 hover:text-primary-500">
              Sign in instead
            </Link>
          </p>
        </div>
        <div className="bg-white py-8 px-6 shadow rounded-lg">
          <RegisterForm onSubmit={handleRegister} isLoading={isLoading} />
        </div>
      </div>
    </Layout>
  );
};

export default RegisterPage;