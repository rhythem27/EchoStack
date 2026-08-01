import React, { useState } from 'react';
import { X, Lock, Mail, User, ShieldCheck, AlertCircle, ArrowRight, UserCheck } from 'lucide-react';

const API_BASE_URL = 'http://localhost:8000';

export default function AuthModal({ isOpen, onClose, onAuthSuccess }) {
  const [activeTab, setActiveTab] = useState('login'); // 'login' | 'register'
  
  // Login form state
  const [loginIdentifier, setLoginIdentifier] = useState('');
  const [loginPassword, setLoginPassword] = useState('');

  // Register form state
  const [regFullName, setRegFullName] = useState('');
  const [regUsername, setRegUsername] = useState('');
  const [regEmail, setRegEmail] = useState('');
  const [regPassword, setRegPassword] = useState('');

  // UI state
  const [loading, setLoading] = useState(false);
  const [errorMsg, setErrorMsg] = useState('');
  const [successMsg, setSuccessMsg] = useState('');

  if (!isOpen) return null;

  const handleUsernameChange = (e) => {
    // Automatically force lowercase and remove spaces
    const val = e.target.value.toLowerCase().replace(/\s+/g, '');
    setRegUsername(val);
  };

  const handleFullNameChange = (e) => {
    // Allow letters and spaces only
    const val = e.target.value.replace(/[^A-Za-z\s]/g, '');
    setRegFullName(val);
  };

  const handleLoginSubmit = async (e) => {
    e.preventDefault();
    setErrorMsg('');
    setSuccessMsg('');

    if (!loginIdentifier || !loginPassword) {
      setErrorMsg('Please enter your username/email and password.');
      return;
    }

    setLoading(true);
    try {
      const response = await fetch(`${API_BASE_URL}/api/users/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          identifier: loginIdentifier,
          password: loginPassword
        })
      });

      const data = await response.json();
      if (!response.ok) {
        throw new Error(data.detail || 'Login failed. Please check your credentials.');
      }

      // Save token and user details to localStorage
      localStorage.setItem('echostack_token', data.access_token);
      localStorage.setItem('echostack_user', JSON.stringify(data.user));

      setSuccessMsg('Logged in successfully!');
      setTimeout(() => {
        onAuthSuccess(data.user, data.access_token);
        onClose();
      }, 500);
    } catch (err) {
      setErrorMsg(err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleRegisterSubmit = async (e) => {
    e.preventDefault();
    setErrorMsg('');
    setSuccessMsg('');

    // Frontend validations
    if (!regFullName.trim()) {
      setErrorMsg('Full name is required.');
      return;
    }
    if (!/^[A-Za-z\s]+$/.test(regFullName.trim())) {
      setErrorMsg('Full name can only contain letters and spaces.');
      return;
    }
    if (!regUsername.trim()) {
      setErrorMsg('Username is required.');
      return;
    }
    if (regUsername !== regUsername.toLowerCase() || /\s/.test(regUsername)) {
      setErrorMsg('Username must be lowercase with no spaces.');
      return;
    }
    if (!regEmail.trim()) {
      setErrorMsg('Email address is required.');
      return;
    }
    if (!regPassword || regPassword.length < 6) {
      setErrorMsg('Password must be at least 6 characters long.');
      return;
    }

    setLoading(true);
    try {
      const response = await fetch(`${API_BASE_URL}/api/users/register`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          full_name: regFullName.trim(),
          username: regUsername.trim(),
          email: regEmail.trim(),
          password: regPassword
        })
      });

      const data = await response.json();
      if (!response.ok) {
        throw new Error(data.detail || 'Registration failed.');
      }

      // Save token and user details to localStorage
      localStorage.setItem('echostack_token', data.access_token);
      localStorage.setItem('echostack_user', JSON.stringify(data.user));

      setSuccessMsg('Account created successfully!');
      setTimeout(() => {
        onAuthSuccess(data.user, data.access_token);
        onClose();
      }, 500);
    } catch (err) {
      setErrorMsg(err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="auth-modal-overlay" onClick={onClose}>
      <div className="auth-modal-content glass-card" onClick={(e) => e.stopPropagation()}>
        {/* Close Button */}
        <button className="auth-modal-close" onClick={onClose} aria-label="Close">
          <X size={20} />
        </button>

        {/* Modal Header */}
        <div className="auth-modal-header">
          <div className="auth-logo-badge">
            <ShieldCheck size={28} className="auth-logo-icon" />
          </div>
          <h2 className="auth-title">EchoStack Identity Portal</h2>
          <p className="auth-subtitle">Secure Access & User Authentication</p>
        </div>

        {/* Auth Tab Switcher */}
        <div className="auth-tabs">
          <button
            className={`auth-tab-btn ${activeTab === 'login' ? 'active' : ''}`}
            onClick={() => { setActiveTab('login'); setErrorMsg(''); }}
          >
            Log In
          </button>
          <button
            className={`auth-tab-btn ${activeTab === 'register' ? 'active' : ''}`}
            onClick={() => { setActiveTab('register'); setErrorMsg(''); }}
          >
            Create Account
          </button>
        </div>

        {/* Alert Messages */}
        {errorMsg && (
          <div className="auth-alert auth-alert-error">
            <AlertCircle size={18} />
            <span>{errorMsg}</span>
          </div>
        )}
        {successMsg && (
          <div className="auth-alert auth-alert-success">
            <UserCheck size={18} />
            <span>{successMsg}</span>
          </div>
        )}

        {/* LOGIN FORM */}
        {activeTab === 'login' && (
          <form onSubmit={handleLoginSubmit} className="auth-form">
            <div className="auth-field">
              <label htmlFor="login-identifier">Username or Email</label>
              <div className="auth-input-wrapper">
                <Mail size={18} className="auth-input-icon" />
                <input
                  id="login-identifier"
                  type="text"
                  placeholder="Enter email or username"
                  value={loginIdentifier}
                  onChange={(e) => setLoginIdentifier(e.target.value)}
                  required
                />
              </div>
            </div>

            <div className="auth-field">
              <label htmlFor="login-password">Password</label>
              <div className="auth-input-wrapper">
                <Lock size={18} className="auth-input-icon" />
                <input
                  id="login-password"
                  type="password"
                  placeholder="Enter your password"
                  value={loginPassword}
                  onChange={(e) => setLoginPassword(e.target.value)}
                  required
                />
              </div>
            </div>

            <button type="submit" className="auth-submit-btn" disabled={loading}>
              {loading ? 'Authenticating...' : 'Sign In'}
              <ArrowRight size={18} />
            </button>
          </form>
        )}

        {/* REGISTER FORM */}
        {activeTab === 'register' && (
          <form onSubmit={handleRegisterSubmit} className="auth-form">
            <div className="auth-field">
              <label htmlFor="reg-fullname">Full Name</label>
              <div className="auth-input-wrapper">
                <User size={18} className="auth-input-icon" />
                <input
                  id="reg-fullname"
                  type="text"
                  placeholder="John Doe (letters only)"
                  value={regFullName}
                  onChange={handleFullNameChange}
                  required
                />
              </div>
              <small className="auth-hint">Letters and spaces only, no special symbols.</small>
            </div>

            <div className="auth-field">
              <label htmlFor="reg-username">Username</label>
              <div className="auth-input-wrapper">
                <User size={18} className="auth-input-icon" />
                <input
                  id="reg-username"
                  type="text"
                  placeholder="johndoe (lowercase, no spaces)"
                  value={regUsername}
                  onChange={handleUsernameChange}
                  required
                />
              </div>
              <small className="auth-hint">Must be all lowercase with no spaces.</small>
            </div>

            <div className="auth-field">
              <label htmlFor="reg-email">Email Address</label>
              <div className="auth-input-wrapper">
                <Mail size={18} className="auth-input-icon" />
                <input
                  id="reg-email"
                  type="email"
                  placeholder="user@example.com"
                  value={regEmail}
                  onChange={(e) => setRegEmail(e.target.value)}
                  required
                />
              </div>
            </div>

            <div className="auth-field">
              <label htmlFor="reg-password">Create Password</label>
              <div className="auth-input-wrapper">
                <Lock size={18} className="auth-input-icon" />
                <input
                  id="reg-password"
                  type="password"
                  placeholder="Min. 6 characters"
                  value={regPassword}
                  onChange={(e) => setRegPassword(e.target.value)}
                  required
                />
              </div>
            </div>

            <div className="auth-role-notice">
              <ShieldCheck size={16} />
              <span>New accounts are created with standard role by default.</span>
            </div>

            <button type="submit" className="auth-submit-btn" disabled={loading}>
              {loading ? 'Creating Account...' : 'Register Account'}
              <ArrowRight size={18} />
            </button>
          </form>
        )}
      </div>
    </div>
  );
}
