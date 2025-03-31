import React, { createContext, useState, useEffect, useContext } from 'react';
import { authAPI } from '../utils/api';
import toast from 'react-hot-toast';

const AuthContext = createContext();

export const useAuth = () => useContext(AuthContext);

export const AuthProvider = ({ children }) => {
  const [user, setUser] = useState(null);
  const [token, setToken] = useState(localStorage.getItem('token'));
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const initAuth = async () => {
      if (token) {
        try {
          const userData = await authAPI.getCurrentUser();
          setUser(userData);
        } catch (error) {
          console.error('Failed to get current user:', error);
          localStorage.removeItem('token');
          setToken(null);
        }
      }
      setLoading(false);
    };
    initAuth();
  }, [token]);

  const login = async (email, password) => {
    try {
      setLoading(true);
      const data = await authAPI.login(email, password);
      localStorage.setItem('token', data.access_token);
      setToken(data.access_token);
      const userData = await authAPI.getCurrentUser();
      setUser(userData);
      toast.success('Login successful!');
      return true;
    } catch (error) {
      const detail = error.response?.data?.detail;
  
      if (Array.isArray(detail)) {
        // If backend sends an array of error messages
        detail.forEach((msg, i) => toast.error(`(${i + 1}) ${msg}`));
      } else if (typeof detail === 'string') {
        toast.error(detail);
      } else if (error.response?.data) {
        const data = error.response.data;
        Object.entries(data).forEach(([field, message]) => {
          toast.error(`${field}: ${message}`);
        });
      } else {
        toast.error('Login failed. Please check your credentials.');
      }
  
      return false;
    } finally {
      setLoading(false);
    }
  };
  
  const register = async (userData) => {
    try {
      setLoading(true);
      const data = await authAPI.register(userData);
      localStorage.setItem('token', data.access_token);
      setToken(data.access_token);
      const userDetails = await authAPI.getCurrentUser();
      setUser(userDetails);
      toast.success('Registration successful!');
      return true;
    } catch (error) {
      const detail = error.response?.data?.detail;
  
      if (Array.isArray(detail)) {
        detail.forEach((msg, i) => toast.error(`(${i + 1}) ${msg}`));
      } else if (typeof detail === 'string') {
        toast.error(detail);
      } else if (error.response?.data) {
        const data = error.response.data;
        Object.entries(data).forEach(([field, message]) => {
          toast.error(`${field}: ${message}`);
        });
      } else {
        toast.error('Registration failed. Please try again.');
      }
  
      return false;
    } finally {
      setLoading(false);
    }
  };
  
  const logout = () => {
    localStorage.removeItem('token');
    setToken(null);
    setUser(null);
    toast.success('Logged out successfully');
  };

  const updateUserData = async () => {
    try {
      const userData = await authAPI.getCurrentUser();
      setUser(userData);
      return userData;
    } catch (error) {
      console.error('Failed to update user data:', error);
      return null;
    }
  };

  const value = {
    token,
    user,
    loading,
    login,
    register,
    logout,
    updateUserData,
    isAuthenticated: !!token && !!user,
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
};
