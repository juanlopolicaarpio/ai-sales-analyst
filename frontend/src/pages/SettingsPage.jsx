import React, { useState, useEffect } from 'react';
import { useAuth } from '../context/AuthContext';
import { authAPI, preferencesAPI } from '../utils/api';
import Layout from '../components/Layout';
import toast from 'react-hot-toast';
import { FiSettings, FiSave, FiBell, FiUser, FiCheckCircle } from 'react-icons/fi';

const SettingsPage = () => {
  const { user, updateUserData } = useAuth();
  const [activeTab, setActiveTab] = useState('profile');
  const [profileData, setProfileData] = useState({
    full_name: '',
    email: '',
    slack_user_id: '',
    whatsapp_number: ''
  });
  const [preferencesData, setPreferencesData] = useState({
    notification_email: true,
    notification_slack: false,
    notification_whatsapp: false,
    digest_frequency: 'daily',
    alert_threshold: 10
  });
  const [loading, setLoading] = useState(false);
  const [prefLoading, setPrefLoading] = useState(false);
  const [isTestingNotification, setIsTestingNotification] = useState(false);

  useEffect(() => {
    if (user) {
      setProfileData({
        full_name: user.full_name || '',
        email: user.email || '',
        slack_user_id: user.slack_user_id || '',
        whatsapp_number: user.whatsapp_number || ''
      });
    }
    fetchPreferences();
  }, [user]);

  const fetchPreferences = async () => {
    try {
      setPrefLoading(true);
      const preferences = await preferencesAPI.getPreferences();
      setPreferencesData(preferences);
    } catch (error) {
      console.error('Failed to fetch preferences:', error);
      toast.error('Failed to load your notification preferences.');
    } finally {
      setPrefLoading(false);
    }
  };

  const handleProfileChange = (e) => {
    const { name, value } = e.target;
    setProfileData((prev) => ({ ...prev, [name]: value }));
  };

  const handlePreferenceChange = (e) => {
    const { name, value, type, checked } = e.target;
    setPreferencesData((prev) => ({
      ...prev,
      [name]: type === 'checkbox' ? checked : value
    }));
  };

  const updateProfile = async (e) => {
    e.preventDefault();
    try {
      setLoading(true);
      // Update the user profile
      await authAPI.updateProfile(profileData);
      await updateUserData();
      toast.success('Profile updated successfully!');
    } catch (error) {
      console.error('Failed to update profile:', error);
      
      // Handle validation errors
      if (error.response?.data?.detail) {
        const detail = error.response.data.detail;
        if (Array.isArray(detail)) {
          detail.forEach(err => {
            if (err.msg) {
              toast.error(err.msg);
            }
          });
        } else {
          toast.error(detail);
        }
      } else {
        toast.error('Failed to update profile.');
      }
    } finally {
      setLoading(false);
    }
  };

  const updatePreferences = async (e) => {
    e.preventDefault();
    try {
      setPrefLoading(true);
      await preferencesAPI.updatePreferences(preferencesData);
      toast.success('Notification preferences updated!');
    } catch (error) {
      console.error('Failed to update preferences:', error);
      toast.error(error.response?.data?.detail || 'Failed to update preferences.');
    } finally {
      setPrefLoading(false);
    }
  };

  const testNotification = async () => {
    try {
      setIsTestingNotification(true);
      await preferencesAPI.testNotification();
      toast.success('Test notification sent!');
    } catch (error) {
      console.error('Failed to send test notification:', error);
      toast.error(error.response?.data?.detail || 'Failed to send test notification.');
    } finally {
      setIsTestingNotification(false);
    }
  };

  return (
    <Layout>
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-gray-900">Settings</h1>
        <p className="text-gray-600 mt-1">Manage your account and notification preferences</p>
      </div>

      <div className="bg-white shadow rounded-lg">
        <div className="flex border-b border-gray-200">
          <button
            className={`px-6 py-4 font-medium text-sm flex items-center ${
              activeTab === 'profile'
                ? 'border-b-2 border-primary-500 text-primary-600'
                : 'text-gray-500 hover:text-gray-700'
            }`}
            onClick={() => setActiveTab('profile')}
          >
            <FiUser className="mr-2" />
            Profile
          </button>
          <button
            className={`px-6 py-4 font-medium text-sm flex items-center ${
              activeTab === 'notifications'
                ? 'border-b-2 border-primary-500 text-primary-600'
                : 'text-gray-500 hover:text-gray-700'
            }`}
            onClick={() => setActiveTab('notifications')}
          >
            <FiBell className="mr-2" />
            Notifications
          </button>
        </div>

        <div className="p-6">
          {activeTab === 'profile' && (
            <form onSubmit={updateProfile} className="space-y-6">
              <div>
                <label htmlFor="full_name" className="form-label">Full Name</label>
                <input
                  id="full_name"
                  name="full_name"
                  type="text"
                  required
                  className="form-input"
                  value={profileData.full_name}
                  onChange={handleProfileChange}
                />
              </div>
              
              <div>
                <label htmlFor="email" className="form-label">Email address</label>
                <input
                  id="email"
                  name="email"
                  type="email"
                  required
                  className="form-input"
                  value={profileData.email}
                  onChange={handleProfileChange}
                  disabled
                />
                <p className="mt-1 text-xs text-gray-500">Email cannot be changed</p>
              </div>
              
              <div className="border-t border-gray-200 pt-4 mt-4">
                <p className="text-sm text-gray-700 mb-4">Contact Information</p>
                
                <div className="space-y-4">
                  <div>
                    <label htmlFor="slack_user_id" className="form-label">Slack User ID</label>
                    <input
                      id="slack_user_id"
                      name="slack_user_id"
                      type="text"
                      className="form-input"
                      value={profileData.slack_user_id}
                      onChange={handleProfileChange}
                      placeholder="U01ABC123DEF"
                    />
                    <p className="mt-1 text-xs text-gray-500">Format: Starts with U or W followed by alphanumeric characters (e.g., U01ABC123DEF)</p>
                  </div>
                  
                  <div>
                    <label htmlFor="whatsapp_number" className="form-label">WhatsApp Number</label>
                    <input
                      id="whatsapp_number"
                      name="whatsapp_number"
                      type="text"
                      className="form-input"
                      value={profileData.whatsapp_number}
                      onChange={handleProfileChange}
                      placeholder="+1234567890"
                    />
                    <p className="mt-1 text-xs text-gray-500">Include country code (e.g., +1 for US, +44 for UK). 10-15 digits total.</p>
                  </div>
                </div>
              </div>
              
              <div className="flex justify-end">
                <button
                  type="submit"
                  className="btn btn-primary flex items-center"
                  disabled={loading}
                >
                  {loading ? (
                    <>
                      <div className="animate-spin mr-2 h-4 w-4 border-b-2 border-white rounded-full"></div>
                      Saving...
                    </>
                  ) : (
                    <>
                      <FiSave className="mr-2" />
                      Save Changes
                    </>
                  )}
                </button>
              </div>
            </form>
          )}

          {activeTab === 'notifications' && (
            <form onSubmit={updatePreferences} className="space-y-6">
              <div>
                <h3 className="text-lg font-medium text-gray-900 mb-4">Notification Channels</h3>
                <div className="space-y-3">
                  <div className="flex items-center">
                    <input
                      id="notification_email"
                      name="notification_email"
                      type="checkbox"
                      className="h-4 w-4 text-primary-600 focus:ring-primary-500 border-gray-300 rounded"
                      checked={preferencesData.notification_email}
                      onChange={handlePreferenceChange}
                    />
                    <label htmlFor="notification_email" className="ml-3 block text-sm font-medium text-gray-700">
                      Email Notifications
                    </label>
                  </div>
                  
                  <div className="flex items-center">
                    <input
                      id="notification_slack"
                      name="notification_slack"
                      type="checkbox"
                      className="h-4 w-4 text-primary-600 focus:ring-primary-500 border-gray-300 rounded"
                      checked={preferencesData.notification_slack}
                      onChange={handlePreferenceChange}
                      disabled={!profileData.slack_user_id}
                    />
                    <label htmlFor="notification_slack" className="ml-3 block text-sm font-medium text-gray-700">
                      Slack Notifications
                      {!profileData.slack_user_id && (
                        <span className="text-xs text-gray-500 ml-2">
                          (Add your Slack ID in profile settings first)
                        </span>
                      )}
                    </label>
                  </div>
                  
                  <div className="flex items-center">
                    <input
                      id="notification_whatsapp"
                      name="notification_whatsapp"
                      type="checkbox"
                      className="h-4 w-4 text-primary-600 focus:ring-primary-500 border-gray-300 rounded"
                      checked={preferencesData.notification_whatsapp}
                      onChange={handlePreferenceChange}
                      disabled={!profileData.whatsapp_number}
                    />
                    <label htmlFor="notification_whatsapp" className="ml-3 block text-sm font-medium text-gray-700">
                      WhatsApp Notifications
                      {!profileData.whatsapp_number && (
                        <span className="text-xs text-gray-500 ml-2">
                          (Add your WhatsApp number in profile settings first)
                        </span>
                      )}
                    </label>
                  </div>
                </div>
              </div>
              
              <div className="border-t border-gray-200 pt-4">
                <h3 className="text-lg font-medium text-gray-900 mb-4">Notification Preferences</h3>
                <div className="space-y-4">
                  <div>
                    <label htmlFor="digest_frequency" className="form-label">Report Frequency</label>
                    <select
                      id="digest_frequency"
                      name="digest_frequency"
                      className="form-input"
                      value={preferencesData.digest_frequency}
                      onChange={handlePreferenceChange}
                    >
                      <option value="daily">Daily</option>
                      <option value="weekly">Weekly</option>
                      <option value="monthly">Monthly</option>
                    </select>
                    <p className="mt-1 text-xs text-gray-500">How often you want to receive sales reports</p>
                  </div>
                  
                  <div>
                    <label htmlFor="alert_threshold" className="form-label">
                      Alert Threshold (%)
                    </label>
                    <input
                      id="alert_threshold"
                      name="alert_threshold"
                      type="number"
                      min="1"
                      max="100"
                      className="form-input"
                      value={preferencesData.alert_threshold}
                      onChange={handlePreferenceChange}
                    />
                    <p className="mt-1 text-xs text-gray-500">
                      Get alerted when sales drop or increase by this percentage
                    </p>
                  </div>
                </div>
              </div>
              
              <div className="flex justify-between pt-4">
                <button
                  type="button"
                  onClick={testNotification}
                  className="btn btn-secondary flex items-center"
                  disabled={isTestingNotification}
                >
                  {isTestingNotification ? (
                    <>
                      <div className="animate-spin mr-2 h-4 w-4 border-b-2 border-primary-600 rounded-full"></div>
                      Sending...
                    </>
                  ) : (
                    <>
                      <FiBell className="mr-2" />
                      Test Notification
                    </>
                  )}
                </button>
                
                <button
                  type="submit"
                  className="btn btn-primary flex items-center"
                  disabled={prefLoading}
                >
                  {prefLoading ? (
                    <>
                      <div className="animate-spin mr-2 h-4 w-4 border-b-2 border-white rounded-full"></div>
                      Saving...
                    </>
                  ) : (
                    <>
                      <FiSave className="mr-2" />
                      Save Preferences
                    </>
                  )}
                </button>
              </div>
            </form>
          )}
        </div>
      </div>
    </Layout>
  );
};

export default SettingsPage;