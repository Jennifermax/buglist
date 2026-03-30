'use client';

import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import AnimatedCharacters from '../../components/animated-characters';
import BuglistLogo from '../../components/buglist-logo';
import './login.css';

export default function LoginPage() {
  const router = useRouter();
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [isTyping, setIsTyping] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState('');
  const [theme, setTheme] = useState('light');

  useEffect(() => {
    const savedTheme = localStorage.getItem('theme') || 'light';
    setTheme(savedTheme);
    document.documentElement.setAttribute('data-theme', savedTheme);
  }, []);

  const toggleTheme = () => {
    const newTheme = theme === 'light' ? 'dark' : 'light';
    setTheme(newTheme);
    localStorage.setItem('theme', newTheme);
    document.documentElement.setAttribute('data-theme', newTheme);
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setIsLoading(true);
    setError('');

    setTimeout(() => {
      const validUsers = ['axel', 'corn', 'felix'];
      const validPassword = 'qwer123';

      if (validUsers.includes(username.toLowerCase()) && password === validPassword) {
        localStorage.setItem('isLoggedIn', 'true');
        localStorage.setItem('username', username.toLowerCase());
        router.push('/');
      } else {
        setError('Invalid username or password. Please try again.');
        setIsLoading(false);
      }
    }, 800);
  };

  return (
    <div className="login-page">
      {/* Theme Toggle */}
      <button className="theme-toggle-login" onClick={toggleTheme}>
        {theme === 'light' ? '🌙' : '☀️'}
      </button>

      {/* Left Content Section with Animated Characters */}
      <div className="login-left-section">
        <div className="login-brand">
          <a href="/" className="brand-link">
            <span className="brand-icon">
              <BuglistLogo size={40} />
            </span>
            <span className="brand-text-animated">
              {'Buglist'.split('').map((char, index) => (
                <span key={index}>
                  {char}
                </span>
              ))}
            </span>
          </a>
          <p className="brand-tagline">Track bugs, ship faster</p>
        </div>

        <div className="animated-container">
          <AnimatedCharacters
            isTyping={isTyping}
            showPassword={showPassword}
            passwordLength={password.length}
          />
        </div>

        <div className="footer-links">
          <a href="#">Privacy Policy</a>
          <a href="#">Terms of Service</a>
        </div>

        {/* Decorative elements */}
        <div className="decorative-grid" />
        <div className="decorative-blur decorative-blur-1" />
        <div className="decorative-blur decorative-blur-2" />
      </div>

      {/* Right Login Section */}
      <div className="login-right-section">
        <div className="login-form-wrapper">
          {/* Mobile Logo */}
          <div className="mobile-brand">
            <span className="brand-icon">
              <BuglistLogo size={32} />
            </span>
            <span className="brand-text-animated">
              {'Buglist'.split('').map((char, index) => (
                <span key={index}>
                  {char}
                </span>
              ))}
            </span>
          </div>

          {/* Header */}
          <div className="form-header">
            <h1>Welcome back!</h1>
            <p>Sign in to track and squash bugs</p>
          </div>

          {/* Login Form */}
          <form onSubmit={handleSubmit} className="login-form">
            <div className="form-field">
              <label htmlFor="username">Username</label>
              <input
                id="username"
                type="text"
                placeholder="Enter username"
                autoComplete="off"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                onFocus={() => setIsTyping(true)}
                onBlur={() => setIsTyping(false)}
                required
              />
            </div>

            <div className="form-field">
              <label htmlFor="password">Password</label>
              <div className="password-field">
                <input
                  id="password"
                  type={showPassword ? 'text' : 'password'}
                  placeholder="Enter password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  required
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  className="password-toggle"
                >
                  {showPassword ? '👁️' : '👁️‍🗨️'}
                </button>
              </div>
            </div>

            {error && (
              <div className="error-alert">
                {error}
              </div>
            )}

            <button
              type="submit"
              className="submit-button"
              disabled={isLoading}
            >
              {isLoading ? 'Signing in...' : 'Sign in'}
            </button>
          </form>
        </div>
      </div>
    </div>
  );
}
