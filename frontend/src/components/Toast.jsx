import React, { createContext, useContext, useState, useCallback } from 'react';
import { CheckCircle2, AlertTriangle, Info, AlertCircle, X } from 'lucide-react';

const ToastContext = createContext(null);

export function ToastProvider({ children }) {
  const [toasts, setToasts] = useState([]);

  const removeToast = useCallback((id) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  }, []);

  const addToast = useCallback((message, type = 'info', duration = 3500) => {
    const id = `${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
    setToasts((prev) => [...prev, { id, message, type }]);

    if (duration > 0) {
      setTimeout(() => {
        removeToast(id);
      }, duration);
    }
  }, [removeToast]);

  const toast = {
    success: (msg, dur) => addToast(msg, 'success', dur),
    error: (msg, dur) => addToast(msg, 'error', dur),
    info: (msg, dur) => addToast(msg, 'info', dur),
    warning: (msg, dur) => addToast(msg, 'warning', dur)
  };

  return (
    <ToastContext.Provider value={toast}>
      {children}
      <div className="toast-container" aria-live="polite">
        {toasts.map((t) => {
          let icon = <Info size={16} className="toast-icon info" />;
          if (t.type === 'success') icon = <CheckCircle2 size={16} className="toast-icon success" />;
          if (t.type === 'error') icon = <AlertTriangle size={16} className="toast-icon error" />;
          if (t.type === 'warning') icon = <AlertCircle size={16} className="toast-icon warning" />;

          return (
            <div key={t.id} className={`toast-card toast-${t.type}`} role="status">
              <div className="toast-icon-wrap">{icon}</div>
              <div className="toast-message">{t.message}</div>
              <button
                className="toast-close-btn"
                onClick={() => removeToast(t.id)}
                aria-label="Close notification"
              >
                <X size={13} />
              </button>
            </div>
          );
        })}
      </div>
    </ToastContext.Provider>
  );
}

export function useToast() {
  const context = useContext(ToastContext);
  if (!context) {
    // Fallback if used outside provider
    return {
      success: (m) => console.log('[Toast Success]:', m),
      error: (m) => console.error('[Toast Error]:', m),
      info: (m) => console.log('[Toast Info]:', m),
      warning: (m) => console.warn('[Toast Warning]:', m)
    };
  }
  return context;
}
