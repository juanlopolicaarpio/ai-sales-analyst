import axios from 'axios';

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000/api';

const api = axios.create({
  baseURL: API_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

api.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('token');
    if (token) {
      config.headers['Authorization'] = `Bearer ${token}`;
    }
    return config;
  },
  (error) => Promise.reject(error)
);

api.interceptors.response.use(
  (response) => response,
  async (error) => {
    if (error.response && error.response.status === 401) {
      localStorage.removeItem('token');
      localStorage.removeItem('user');
      window.location.href = '/login';
    }
    return Promise.reject(error);
  }
);

export const authAPI = {
  login: async (email, password) => {
    const formData = new FormData();
    formData.append('username', email);
    formData.append('password', password);
    const response = await axios.post(`${API_URL}/token`, formData);
    return response.data;
  },
  register: async (userData) => {
    const response = await api.post('/register', userData);
    return response.data;
  },
  getCurrentUser: async () => {
    const response = await api.get('/users/me');
    return response.data;
  }
};

export const storesAPI = {
  getStores: async () => {
    const response = await api.get('/stores');
    return response.data;
  },
  getStore: async (storeId) => {
    const response = await api.get(`/stores/${storeId}`);
    return response.data;
  },
  createStore: async (storeData) => {
    const response = await api.post('/stores', storeData);
    return response.data;
  },
  updateStore: async (storeId, storeData) => {
    const response = await api.put(`/stores/${storeId}`, storeData);
    return response.data;
  },
  testConnection: async (storeId) => {
    const response = await api.post(`/stores/${storeId}/test-connection`);
    return response.data;
  }
};

export const preferencesAPI = {
  getPreferences: async () => {
    const response = await api.get('/preferences');
    return response.data;
  },
  updatePreferences: async (preferencesData) => {
    const response = await api.put('/preferences', preferencesData);
    return response.data;
  },
  testNotification: async () => {
    const response = await api.post('/preferences/test-notification');
    return response.data;
  }
};

export default api;
