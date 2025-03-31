import React, { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';

const Navbar = () => {
  const [isMenuOpen, setIsMenuOpen] = useState(false);
  const { user, isAuthenticated, logout } = useAuth();
  const navigate = useNavigate();
  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  return (
    <nav className="bg-white shadow-sm">
      <div className="container mx-auto px-4">
        <div className="flex justify-between h-16">
          <div className="flex">
            <div className="flex-shrink-0 flex items-center">
            <Link to="/" className="text-xl font-bold">
  AgentiSales
  <span className="text-indigo-600"> AI</span>
</Link>
            </div>
            <div className="hidden sm:ml-6 sm:flex sm:space-x-8">
              {isAuthenticated && (
                <>
                  <Link to="/dashboard" className="border-transparent text-gray-500 hover:border-primary-500 hover:text-primary-700 inline-flex items-center px-1 pt-1 border-b-2 text-sm font-medium">
                    Dashboard
                  </Link>
                  <Link to="/connect-store" className="border-transparent text-gray-500 hover:border-primary-500 hover:text-primary-700 inline-flex items-center px-1 pt-1 border-b-2 text-sm font-medium">
                    Connect Store
                  </Link>
                  <Link to="/settings" className="border-transparent text-gray-500 hover:border-primary-500 hover:text-primary-700 inline-flex items-center px-1 pt-1 border-b-2 text-sm font-medium">
                    Settings
                  </Link>
                </>
              )}
            </div>
          </div>
          <div className="hidden sm:ml-6 sm:flex sm:items-center">
            {isAuthenticated ? (
              <div className="relative ml-3">
                <div className="flex items-center">
                  <span className="text-sm font-medium text-gray-700 mr-2">
                    {user?.full_name || user?.email}
                  </span>
                  <button onClick={handleLogout} className="bg-gray-100 p-1 rounded-full text-gray-600 hover:text-primary-600 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-primary-500 px-3 py-2 text-sm">
                    Logout
                  </button>
                </div>
              </div>
            ) : (
              <div className="flex space-x-4">
                <Link to="/login" className="text-gray-600 hover:text-primary-600 px-3 py-2 rounded-md text-sm font-medium">Login</Link>
                <Link to="/register" className="bg-primary-600 text-white hover:bg-primary-700 px-3 py-2 rounded-md text-sm font-medium">Register</Link>
              </div>
            )}
          </div>
          <div className="flex items-center sm:hidden">
            <button type="button" className="inline-flex items-center justify-center p-2 rounded-md text-gray-400 hover:text-gray-500 hover:bg-gray-100 focus:outline-none focus:ring-2 focus:ring-inset focus:ring-primary-500" aria-expanded="false" onClick={() => setIsMenuOpen(!isMenuOpen)}>
              <span className="sr-only">Open main menu</span>
              {isMenuOpen ? (
                <svg className="block h-6 w-6" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              ) : (
                <svg className="block h-6 w-6" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
                </svg>
              )}
            </button>
          </div>
        </div>
      </div>
      {isMenuOpen && (
        <div className="sm:hidden">
          <div className="pt-2 pb-3 space-y-1">
            {isAuthenticated ? (
              <>
                <Link to="/dashboard" className="border-transparent text-gray-600 hover:bg-gray-50 hover:border-primary-500 hover:text-primary-700 block pl-3 pr-4 py-2 border-l-4 text-base font-medium" onClick={() => setIsMenuOpen(false)}>
                  Dashboard
                </Link>
                <Link to="/connect-store" className="border-transparent text-gray-600 hover:bg-gray-50 hover:border-primary-500 hover:text-primary-700 block pl-3 pr-4 py-2 border-l-4 text-base font-medium" onClick={() => setIsMenuOpen(false)}>
                  Connect Store
                </Link>
                <Link to="/settings" className="border-transparent text-gray-600 hover:bg-gray-50 hover:border-primary-500 hover:text-primary-700 block pl-3 pr-4 py-2 border-l-4 text-base font-medium" onClick={() => setIsMenuOpen(false)}>
                  Settings
                </Link>
                <button onClick={() => { setIsMenuOpen(false); handleLogout(); }} className="border-transparent text-gray-600 hover:bg-gray-50 hover:border-red-500 hover:text-red-700 block pl-3 pr-4 py-2 border-l-4 text-base font-medium w-full text-left">
                  Logout
                </button>
              </>
            ) : (
              <>
                <Link to="/login" className="border-transparent text-gray-600 hover:bg-gray-50 hover:border-primary-500 hover:text-primary-700 block pl-3 pr-4 py-2 border-l-4 text-base font-medium" onClick={() => setIsMenuOpen(false)}>
                  Login
                </Link>
                <Link to="/register" className="border-transparent text-gray-600 hover:bg-gray-50 hover:border-primary-500 hover:text-primary-700 block pl-3 pr-4 py-2 border-l-4 text-base font-medium" onClick={() => setIsMenuOpen(false)}>
                  Register
                </Link>
              </>
            )}
          </div>
        </div>
      )}
    </nav>
  );
};

export default Navbar;
